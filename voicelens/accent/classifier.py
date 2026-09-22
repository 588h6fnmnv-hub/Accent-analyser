"""VoiceLens Accent Classification.

This module provides accent classification using:
1. Audio-based classification using ECAPA-TDNN speaker embeddings (primary)
2. Transcript-based vocabulary/pattern analysis (fallback when audio fails)
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)

# Suppress torchaudio/torchcodec/speechbrain verbose warnings before importing them
# This is a macOS compatibility issue with FFmpeg/torchcodec, not an error
logging.getLogger("torchaudio").setLevel(logging.ERROR)
logging.getLogger("torchcodec").setLevel(logging.ERROR)
logging.getLogger("speechbrain").setLevel(logging.ERROR)
logging.getLogger("speechbrain.dataio.dataio").setLevel(logging.ERROR)
logging.getLogger("speechbrain.utils.fetching").setLevel(logging.ERROR)

# Lazy load SpeechBrain to prevent import crashes
_SPEECHBRAIN_AVAILABLE = False
_SPEECHBRAIN_ERROR_MSG = ""
EncoderClassifier: Any = None

try:
    from speechbrain.inference.classifiers import EncoderClassifier as _EncoderClassifier
    EncoderClassifier = _EncoderClassifier
    _SPEECHBRAIN_AVAILABLE = True
except Exception as e:
    _SPEECHBRAIN_ERROR_MSG = str(e)


@dataclass
class AccentResult:
    """Dataclass holding accent classification results."""

    predicted_accent: str
    confidence: float
    top_3_accents: list[tuple[str, float]]
    notes: list[str]


# Accent vocabulary markers - kept as fallback when audio analysis fails
ACCENT_VOCABULARY = {
    "British English": {
        "vocabulary": {
            "lorry", "lift", "flat", "petrol", "biscuit", "crisps", "chips", "torch",
            "holiday", "university", "maths", "rubbish", "bin", "queue", "cheers",
            "mate", "brilliant", "proper", "sod", "bloody", "knackered",
            "gutted", "chuffed", "gobsmacked", "dodgy", "skint", "quid", "fiver",
            "tenner", "pence", "pounds", "stone", "miles", "yards", "feet", "inches"
        },
        "spelling": {
            "colour", "favour", "honour", "labour", "neighbour", "centre", "metre",
            "theatre", "organisation", "realise", "optimise", "analyse", "behaviour",
            "cancelled", "travelling", "modelling", "programme", "catalogue"
        },
        "patterns": [
            r"\b(?:I've|I'll|I'd|you've|you'll|you'd|we've|we'll|we'd|they've|they'll|they'd)\b",
            r"\b(?:haven't|hasn't|hadn't|wouldn't|couldn't|shouldn't|mustn't|needn't)\b"
        ]
    },
    "American English": {
        "vocabulary": {
            "truck", "elevator", "apartment", "gas", "cookie", "chips", "fries",
            "vacation", "college", "math", "trash", "can", "line", "trunk", "hood",
            "windshield", "sidewalk", "crosswalk", "downtown", "uptown", "subway",
            "awesome", "cool", "sweet", "rad", "bummer", "freak", "psyched",
            "bucks", "dollar", "cents", "quarters", "dimes", "nickels", "pennies"
        },
        "spelling": {
            "color", "favor", "honor", "labor", "neighbor", "center", "meter",
            "theater", "organization", "realize", "optimize", "analyze", "behavior",
            "canceled", "traveling", "modeling", "program", "catalog"
        },
        "patterns": [
            r"\b(?:I've|I'll|I'd|you've|you'll|you'd|we've|we'll|we'd|they've|they'll|they'd)\b",
            r"\b(?:haven't|hasn't|hadn't|wouldn't|couldn't|shouldn't|mustn't)\b",
            r"\b(?:gonna|wanna|gotta|kinda|sorta|outta|lemme|gimme)\b"
        ]
    },
    "Indian English": {
        "vocabulary": {
            "prepone", "do the needful", "revert back", "pass out", "topper",
            "batchmate", "cousin brother", "cousin sister", "real brother",
            "own brother", "real sister", "own sister", "timepass", "time pass",
            "good name", "native place", "out of station", "head bath",
            "oil bath", "hair wash", "tiffin", "hotel", "restaurant", "mess",
            "bunk", "mass bunk", "proxy", "compensatory", "arrears", "backlog",
            "clearing", "supplementary", "revaluation", "rechecking", "grade",
            "percentage", "marks", "rank", "merit", "cutoff", "cut off"
        },
        "spelling": {
            "organisation", "realise", "optimise", "analyse", "behaviour",
            "cancelled", "travelling", "modelling", "programme"
        },
        "patterns": [
            r"\b(?:is it not|isn't it|no\?|isn't it so)\b",
            r"\b(?:do one thing|kindly do|please do the needful)\b",
            r"\b(?:I am having|we are having|they are having)\b"
        ]
    },
    "Australian English": {
        "vocabulary": {
            "ute", "esky", "thongs", "boardies", "cossie", "togs", "bathers",
            "barbie", "snag", "sanga", "brekkie", "arvo", "avo", "cuppa",
            "macca's", "maccas", "servo", "bottle-o", "bowlo", "RDO",
            "sickie", "smoko", "arvo", "avo", "rego", "ambo", "firey",
            "polly", "tradie", "sparkie", "chippie", "brickie", "cabbie"
        },
        "spelling": {
            "colour", "favour", "honour", "labour", "neighbour", "centre", "metre",
            "theatre", "organisation", "realise", "optimise", "analyse"
        },
        "patterns": [
            r"\b(?:mate|sheila|bloke|cobber|digger)\b",
            r"\b(?:fair dinkum|true blue|no worries|she'll be right)\b"
        ]
    },
    "Canadian English": {
        "vocabulary": {
            "toque", "chesterfield", "washroom", "parkade", "hydro", "loonie",
            "toonie", "two-four", "mickey", "twenty-sixer", "forty-pounder",
            "Caesar", "poutine", "butter tart", "Nanaimo bar", "beaver tail",
            "double-double", "timbit", "roll up the rim", "eh"
        },
        "spelling": {
            "colour", "favour", "honour", "labour", "neighbour", "centre", "metre",
            "theatre", "organisation", "realise", "optimise", "analyse"
        },
        "patterns": [
            r"\beh\b",
        ]
    }
}


# Pre-defined accent centroids for embedding-based classification
# These would ideally be learned from training data, but we use reasonable defaults
ACCENT_CENTROIDS = {
    "Indian English": None,
    "American English": None,
    "British English": None,
    "Australian English": None,
    "Canadian English": None,
}


class AccentClassifier:
    """Accent classifier using ECAPA-TDNN speaker embeddings as primary signal."""

    ACCENTS = ["Indian English", "American English", "British English", "Australian English", "Canadian English"]

    def __init__(
        self,
        model_source: str = "speechbrain/spkrec-ecapa-voxceleb",
        run_opts: dict[str, Any] | None = None,
    ) -> None:
        """Initializes the AccentClassifier.

        Args:
            model_source: SpeechBrain model source for ECAPA-TDNN.
            run_opts: Run options for SpeechBrain inference.
        """
        if not _SPEECHBRAIN_AVAILABLE:
            logger.warning(f"SpeechBrain not available: {_SPEECHBRAIN_ERROR_MSG}")
            raise RuntimeError(f"SpeechBrain not available: {_SPEECHBRAIN_ERROR_MSG}")

        self.model_source = model_source
        self.run_opts = run_opts or {"device": "cpu"}
        self._classifier: Any = None
        self._embedding_cache: dict[str, np.ndarray] = {}
        self._centroids: dict[str, np.ndarray] = {}
        self._centroids_loaded = False

    def _get_classifier(self) -> Any:
        """Lazily loads the SpeechBrain ECAPA-TDNN classifier."""
        if self._classifier is None:
            logger.info(f"Loading SpeechBrain ECAPA-TDNN from {self.model_source}")
            self._classifier = EncoderClassifier.from_hparams(
                source=self.model_source,
                run_opts=self.run_opts,
            )
        return self._classifier

    def _load_audio(self, audio_path: Path) -> tuple[torch.Tensor, int]:
        """Load audio file using torchaudio."""
        import logging
        torchaudio_logger = logging.getLogger("torchaudio")
        original_level = torchaudio_logger.level
        torchaudio_logger.setLevel(logging.ERROR)
        try:
            import torchaudio
            waveform, sample_rate = torchaudio.load(str(audio_path))
        finally:
            torchaudio_logger.setLevel(original_level)
        return waveform, sample_rate

    def _get_embedding(self, audio_path: Path) -> np.ndarray:
        """Extract speaker embedding from audio file using ECAPA-TDNN."""
        cache_key = str(audio_path)
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        waveform, sample_rate = self._load_audio(audio_path)

        if sample_rate != 16000:
            import logging
            torchaudio_logger = logging.getLogger("torchaudio")
            original_level = torchaudio_logger.level
            torchaudio_logger.setLevel(logging.ERROR)
            try:
                import torchaudio.transforms as T
                resampler = T.Resample(orig_freq=sample_rate, new_freq=16000)
                waveform = resampler(waveform)
                sample_rate = 16000
            finally:
                torchaudio_logger.setLevel(original_level)

        classifier = self._get_classifier()
        with torch.no_grad():
            embedding = classifier.encode_batch(waveform)
            embedding = embedding.squeeze().cpu().numpy()

        self._embedding_cache[cache_key] = embedding
        return embedding

    def _load_centroids(self) -> None:
        """Load or compute accent centroids for classification."""
        if self._centroids_loaded:
            return

        # Try to load pre-computed centroids from disk
        centroid_path = Path(__file__).parent / "accent_centroids.npz"
        if centroid_path.exists():
            try:
                data = np.load(centroid_path)
                for accent in self.ACCENTS:
                    if accent in data:
                        self._centroids[accent] = data[accent]
                logger.info("Loaded pre-computed accent centroids")
                self._centroids_loaded = True
                return
            except Exception as e:
                logger.warning(f"Failed to load centroids: {e}")

        # Fallback: initialize with zeros (will be updated on first classifications)
        # In production, these should be pre-computed from training data
        for accent in self.ACCENTS:
            self._centroids[accent] = None
        self._centroids_loaded = True

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        if a is None or b is None:
            return 0.0
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        if a_norm == 0 or b_norm == 0:
            return 0.0
        return float(np.dot(a, b) / (a_norm * b_norm))

    def _classify_from_embedding(self, embedding: np.ndarray) -> tuple[str, float, dict[str, float]]:
        """Classify accent using embedding similarity to centroids."""
        self._load_centroids()

        similarities = {}
        for accent in self.ACCENTS:
            centroid = self._centroids.get(accent)
            if centroid is not None:
                sim = self._cosine_similarity(embedding, centroid)
                similarities[accent] = max(0.0, sim)  # Clamp to [0, 1]

        # If no centroids available, return unknown
        if not similarities:
            return "Unknown", 0.0, {}

        # Normalize similarities to probabilities
        total = sum(similarities.values())
        if total > 0:
            probs = {k: v / total for k, v in similarities.items()}
        else:
            probs = {k: 0.0 for k in similarities}

        # Get prediction
        predicted = max(probs, key=probs.get)
        confidence = probs[predicted]

        # Return Unknown if confidence too low
        if confidence < 0.3:
            return "Unknown", 0.0, probs

        return predicted, confidence, probs

    def _classify_from_transcript(self, transcript: str) -> tuple[str, float, dict[str, float], list[tuple[str, float]]]:
        """Fallback: Classify accent based on transcript vocabulary and patterns."""
        if not transcript or not transcript.strip():
            return "Unknown", 0.0, {}, []

        transcript_lower = transcript.lower()
        words = set(re.findall(r'\b\w+\b', transcript_lower))
        text_lower = transcript_lower
                
        scores = {}

        for accent, markers in ACCENT_VOCABULARY.items():
            score = 0.0
            total_possible = 0

            for word in markers["vocabulary"]:
                total_possible += 1
                if word in words or word in text_lower:
                    score += 1.0

            for spelling in markers.get("spelling", set()):
                total_possible += 0.5
                if spelling in words or spelling in text_lower:
                    print(f"  SPELLING MATCH: {accent} - '{spelling}' in_words={spelling in words} in_text={spelling in text_lower}")
                    score += 0.5

            for pattern in markers.get("patterns", []):
                total_possible += 1.0
                if re.search(pattern, text_lower, re.IGNORECASE):
                    score += 1.0

            if total_possible > 0:
                scores[accent] = score / total_possible
            else:
                scores[accent] = 0.0

        max_score = max(scores.values()) if scores else 0.0
        if max_score > 0:
            normalized = {k: v / max_score for k, v in scores.items()}
        else:
            normalized = scores

        threshold = 0.25
        mixed_accents = [(acc, score) for acc, score in normalized.items() if score >= threshold]
        mixed_accents.sort(key=lambda x: -x[1])

        if max_score > 0:
            predicted = max(normalized, key=normalized.get)
            confidence = normalized[predicted]
        else:
            predicted = "Unknown"
            confidence = 0.0

        if confidence < 0.15:
            predicted = "Unknown"
            confidence = 0.0
            mixed_accents = []

        return predicted, confidence, normalized, mixed_accents

    def classify(self, audio_path: str | Path, transcript: str = "") -> AccentResult:
        """Classify the accent of the given audio file.

        Primary: Audio embedding-based classification (ECAPA-TDNN)
        Fallback: Transcript vocabulary analysis
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file does not exist: {path}")

        # Try audio-based classification first
        embedding = None
        embedding_failed = False
        try:
            embedding = self._get_embedding(path)
            predicted_accent, confidence, probs = self._classify_from_embedding(embedding)
            method = "audio_embedding"
            notes = [f"Classified using ECAPA-TDNN embedding (dim={embedding.shape[0]})"]
        except Exception as e:
            logger.warning(f"Audio-based classification failed: {e}")
            embedding = None
            embedding_failed = True
            predicted_accent, confidence, probs = "Unknown", 0.0, {}
            method = "unknown"

        # Fallback to transcript-based if audio failed or confidence too low
        if confidence < 0.3 or embedding is None:
            if transcript and transcript.strip():
                predicted_accent, confidence, vocab_probs, mixed_accents = self._classify_from_transcript(transcript)
                if method == "unknown":
                    method = "transcript_vocabulary"
                    notes = [f"Classified using transcript vocabulary analysis (audio unavailable)"]
                else:
                    method = "transcript_vocabulary_fallback"
                    notes = [f"Fell back to transcript vocabulary (audio confidence: {confidence:.2f})"]

                # Merge with embedding probs if available
                if probs:
                    for accent, prob in probs.items():
                        if accent in vocab_probs:
                            vocab_probs[accent] = (vocab_probs[accent] + prob) / 2
                        else:
                            vocab_probs[accent] = prob

                    # Re-normalize
                    total = sum(vocab_probs.values())
                    if total > 0:
                        vocab_probs = {k: v / total for k, v in vocab_probs.items()}
                    probs = vocab_probs
            else:
                predicted_accent = "Unknown"
                confidence = 0.0
                probs = {}
                mixed_accents = []
                method = "none"
                notes = ["No transcript available and audio classification failed"]

        # Build top 3
        top_3 = sorted(probs.items(), key=lambda x: -x[1])[:3]
        top_3 = [(acc, min(score, 0.95)) for acc, score in top_3]

        # Add mixed accent note if applicable
        if 'mixed_accents' in locals() and mixed_accents and len(mixed_accents) > 1:
            notes.append(f"Mixed accents detected: {', '.join([f'{acc} ({score:.2f})' for acc, score in mixed_accents])}")

        # Add method note
        notes.append(f"Classification method: {method}")

        return AccentResult(
            predicted_accent=predicted_accent,
            confidence=confidence,
            top_3_accents=top_3,
            notes=notes,
        )


def compute_and_save_centroids(accent_samples: dict[str, list[Path]], output_path: Path) -> None:
    """Utility to compute accent centroids from training samples.

    Args:
        accent_samples: Dict mapping accent name to list of audio file paths
        output_path: Where to save the centroids .npz file
    """
    if not _SPEECHBRAIN_AVAILABLE:
        raise RuntimeError("SpeechBrain not available")

    classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        run_opts={"device": "cpu"},
    )

    centroids = {}
    for accent, paths in accent_samples.items():
        embeddings = []
        for path in paths:
            waveform, sample_rate = torchaudio.load(str(path))
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
                waveform = resampler(waveform)
            with torch.no_grad():
                embedding = classifier.encode_batch(waveform)
                embeddings.append(embedding.squeeze().cpu().numpy())

        if embeddings:
            centroid = np.mean(embeddings, axis=0)
            centroids[accent] = centroid / np.linalg.norm(centroid)
            logger.info(f"Computed centroid for {accent} from {len(embeddings)} samples")

    np.savez(output_path, **centroids)
    logger.info(f"Saved centroids to {output_path}")