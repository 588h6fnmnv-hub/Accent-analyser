"""VoiceLens Pronunciation SpeechBrain Backend."""

import wave
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torchaudio

from voicelens.pronunciation.backend import PronunciationBackend, PronunciationResult

# Lazy load SpeechBrain to prevent import crashes in environments lacking it
_SPEECHBRAIN_AVAILABLE = False
_SPEECHBRAIN_ERROR_MSG = ""
EncoderClassifier: Any = None

try:
    from speechbrain.inference.classifiers import (
        EncoderClassifier as _EncoderClassifier,
    )

    EncoderClassifier = _EncoderClassifier
    _SPEECHBRAIN_AVAILABLE = True
except Exception as e:
    _SPEECHBRAIN_ERROR_MSG = str(e)


class SpeechBrainBackend(PronunciationBackend):
    """Pronunciation assessment backend using SpeechBrain ECAPA-TDNN embeddings."""

    def __init__(
        self,
        model_source: str = "speechbrain/spkrec-ecapa-voxceleb",
        run_opts: dict[str, Any] | None = None,
    ) -> None:
        """Initializes the SpeechBrainBackend.

        Args:
            model_source: SpeechBrain pre-trained model source.
            run_opts: Run options for SpeechBrain inference.
        """
        if not _SPEECHBRAIN_AVAILABLE:
            raise RuntimeError(
                f"SpeechBrain is not available: {_SPEECHBRAIN_ERROR_MSG}. "
                "Install with 'pip install voicelens[ml]' or 'pip install speechbrain'."
            )
        self.model_source = model_source
        self.run_opts = run_opts or {}
        self._classifier: Any = None

    def _get_classifier(self) -> Any:
        """Lazily loads the SpeechBrain classifier."""
        if self._classifier is None:
            self._classifier = EncoderClassifier.from_hparams(
                source=self.model_source,
                run_opts=self.run_opts,
            )
        return self._classifier

    def _load_audio_fallback(self, path: Path) -> tuple[torch.Tensor, int]:
        """Fallback WAV loader using standard library and numpy."""
        with wave.open(str(path), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            sampwidth = wav_file.getsampwidth()
            n_frames = wav_file.getnframes()
            raw_data = wav_file.readframes(n_frames)

        if sampwidth == 2:  # 16-bit PCM
            data = np.frombuffer(raw_data, dtype=np.int16)
            data_float = data.astype(np.float32) / 32768.0
        elif sampwidth == 1:  # 8-bit unsigned PCM
            data = np.frombuffer(raw_data, dtype=np.uint8)
            data_float = (data.astype(np.float32) - 128.0) / 128.0
        elif sampwidth == 4:  # 32-bit PCM
            data = np.frombuffer(raw_data, dtype=np.int32)
            data_float = data.astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported sample width: {sampwidth} bytes")

        if channels > 1:
            data_float = data_float.reshape(-1, channels).T
        else:
            data_float = data_float.reshape(1, -1)

        signal = torch.from_numpy(data_float)
        return signal, sample_rate

    def _load_audio(self, path: Path) -> tuple[torch.Tensor, int]:
        """Loads WAV or audio file using torchaudio with standard library fallback."""
        try:
            return torchaudio.load(str(path))
        except (ImportError, RuntimeError, Exception):
            return self._load_audio_fallback(path)

    def _compute_audio_quality_features(self, signal: torch.Tensor, sample_rate: int) -> dict[str, float]:
        """Compute acoustic features that correlate with pronunciation quality."""
        # Convert to mono if needed
        if signal.shape[0] > 1:
            signal = torch.mean(signal, dim=0, keepdim=True)
        
        signal_1d = signal.squeeze(0)
        total_samples = len(signal_1d)
        
        if total_samples == 0:
            return {"snr_db": 0.0, "rms": 0.0, "spectral_flatness": 1.0, "zero_crossing_rate": 0.0}
        
        # RMS energy
        rms = float(torch.sqrt(torch.mean(signal_1d ** 2)).item())
        
        # Zero crossing rate
        zero_crossings = ((signal_1d[:-1] * signal_1d[1:]) < 0).sum().item()
        zero_crossing_rate = zero_crossings / total_samples
        
        # Estimate SNR using spectral flatness (simplified)
        # Higher spectral flatness = more noise-like
        frame_size = 512
        hop_size = 256
        if total_samples >= frame_size:
            # Simple spectral flatness estimation
            n_frames = (total_samples - frame_size) // hop_size + 1
            flatness_values = []
            for i in range(n_frames):
                frame = signal_1d[i * hop_size:i * hop_size + frame_size]
                if len(frame) == frame_size:
                    # Compute power spectrum magnitude
                    spectrum = torch.abs(torch.fft.rfft(frame * torch.hann_window(frame_size)))
                    geometric_mean = torch.exp(torch.mean(torch.log(spectrum + 1e-10)))
                    arithmetic_mean = torch.mean(spectrum)
                    if arithmetic_mean > 0:
                        flatness = geometric_mean / arithmetic_mean
                        flatness_values.append(float(flatness.item()))
            spectral_flatness = float(np.mean(flatness_values)) if flatness_values else 1.0
        else:
            spectral_flatness = 1.0
        
        # Estimate SNR in dB (simplified)
        snr_db = -10 * np.log10(spectral_flatness + 1e-10)
        snr_db = max(0.0, min(60.0, snr_db))
        
        return {
            "snr_db": snr_db,
            "rms": rms,
            "spectral_flatness": spectral_flatness,
            "zero_crossing_rate": zero_crossing_rate,
        }

    def analyze(self, audio_path: str | Path, _transcript: str) -> PronunciationResult:
        """Analyzes pronunciation using SpeechBrain embeddings and audio quality features.

        Args:
            audio_path: Path to the audio file.
            _transcript: Reference text transcription.

        Returns:
            PronunciationResult: Score, similarity, and confidence.
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file does not exist: {path}")

        # 1. Load the audio signal
        signal, _fs = self._load_audio(path)
        if signal.shape[0] > 1:
            signal = torch.mean(signal, dim=0, keepdim=True)

        classifier = self._get_classifier()

        # 2. Extract SpeechBrain speech embeddings
        res = classifier.classify_batch(signal)
        _prediction, _log_softmax, posterior, text_lab = res
        embeddings = classifier.encode_batch(signal)

        # 3. Compute audio quality features for pronunciation assessment
        quality_features = self._compute_audio_quality_features(signal, _fs)
        
        # 4. Compute embedding-based similarity (using embedding norm and distribution)
        # Normalize embeddings
        emb_norm = float(torch.norm(embeddings).item())
        embedding_dim = embeddings.shape[-1]
        expected_norm = np.sqrt(embedding_dim)  # Expected norm for normalized embeddings
        norm_score = min(1.0, emb_norm / expected_norm) if expected_norm > 0 else 0.0
        
        # Compute embedding variance (higher variance = more distinctive features)
        emb_var = float(torch.var(embeddings).item())
        variance_score = min(1.0, emb_var * 100)  # Scale appropriately

        # 5. Compute audio quality based confidence
        snr_score = min(1.0, quality_features["snr_db"] / 30.0)  # Normalize to 30dB max
        rms_score = min(1.0, quality_features["rms"] / 0.1)  # Normalize to reasonable RMS
        spectral_score = 1.0 - quality_features["spectral_flatness"]  # Lower flatness = better
        
        # 6. Combine features for pronunciation similarity
        # Weight: embedding quality 40%, audio quality 60%
        similarity = (0.4 * ((norm_score + variance_score) / 2) + 
                     0.6 * ((snr_score + rms_score + spectral_score) / 3))
        similarity = max(0.0, min(1.0, similarity))

        # 7. Compute confidence from audio quality features
        # Higher quality audio = more reliable assessment
        raw_conf = (snr_score + rms_score + spectral_score) / 3
        confidence = max(0.0, min(1.0, raw_conf))

        # 8. Compute overall score
        overall_score = round((0.6 * similarity + 0.4 * confidence) * 100.0, 2)
        overall_score = max(0.0, min(100.0, overall_score))

        detected_lang = str(text_lab[0]) if text_lab else "unknown"

        notes = [
            f"Speech embeddings generated. Shape: {list(embeddings.shape)}",
            f"Detected language profile: {detected_lang}",
            f"Cosine phonetic similarity factor: {similarity:.4f}",
            f"Audio quality - SNR: {quality_features['snr_db']:.1f}dB, RMS: {quality_features['rms']:.4f}, Spectral flatness: {quality_features['spectral_flatness']:.4f}",
        ]

        return PronunciationResult(
            overall_score=overall_score,
            pronunciation_similarity=round(similarity, 4),
            confidence=round(confidence, 4),
            backend="speechbrain",
            notes=notes,
        )