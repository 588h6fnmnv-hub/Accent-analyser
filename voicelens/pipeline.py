"""VoiceLens Core Pipeline Execution Module.

Provides shared execution logic for both the CLI and Python HTTP API.
"""

import concurrent.futures
import logging
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from voicelens.alignment.aligner import AlignmentResult, WhisperAligner
from voicelens.metrics.analyzer import SpeechMetrics, SpeechMetricsAnalyzer
from voicelens.pronunciation import (
    MispronunciationAnalyzer,
    MispronunciationResult,
    PronunciationAnalyzer,
    PronunciationResult,
    DummyBackend,
)
from voicelens.transcriber import Transcriber, TranscriberError
from voicelens.core.config import Config

console = Console()
logger = logging.getLogger(__name__)

# Global transcriber cache for reuse
_transcriber_cache: dict[str, Transcriber] = {}


def clamp_0_100(value: float) -> float:
    """Clamp a value to the 0-100 range."""
    return max(0.0, min(100.0, value))


def clamp_0_1(value: float) -> float:
    """Clamp a value to the 0-1 range."""
    return max(0.0, min(1.0, value))


def generate_clean_feedback(
    pron_score: float | None,
    wpm: float | None,
    filler_count: int | None,
    detected_accent: str | None,
    fluency_score: float | None = None,
    confidence_score: float | None = None,
) -> list[str]:
    """Generates plain text overall feedback bullet points for analysis results."""
    feedback = []

    if detected_accent:
        feedback.append(f"• Accent Profile: Detected accent is {detected_accent}.")
    else:
        feedback.append(
            "• Accent Profile: Accent classification failed or was skipped."
        )

    # Pronunciation feedback
    if pron_score is None:
        feedback.append(
            "• Pronunciation: Pronunciation assessment failed or was skipped."
        )
    elif pron_score >= 80.0:
        feedback.append(
            "• Pronunciation: Excellent clarity! Your spoken acoustic features "
            "align closely with target speech standards."
        )
    elif pron_score >= 60.0:
        feedback.append(
            "• Pronunciation: Good clarity. Some words can be enunciated more "
            "clearly to improve similarity scores."
        )
    else:
        feedback.append(
            "• Pronunciation: Needs practice. Focus on vowel projection and "
            "distinct consonant closures."
        )

    # Pace feedback
    if wpm is None:
        feedback.append(
            "• Pace (Speed): Speech delivery pace metrics failed or were skipped."
        )
    elif wpm > 160.0:
        feedback.append(
            "• Pace (Speed): Fast speaking rate. Try slowing down slightly to "
            "make your speech easier to follow."
        )
    elif wpm < 110.0 and wpm > 0.0:
        feedback.append(
            "• Pace (Speed): Slow speaking rate. Increasing pace slightly can "
            "boost conversational naturalness."
        )
    elif wpm == 0.0:
        feedback.append("• Pace (Speed): No coherent conversational speech detected.")
    else:
        feedback.append(
            "• Pace (Speed): Natural pace. Your words-per-minute rate is in the "
            "ideal zone."
        )

    # Filler words feedback
    if filler_count is None:
        feedback.append("• Filler Words: Filler word tracking failed or was skipped.")
    elif filler_count > 4:
        feedback.append(
            "• Filler Words: High filler density. Try to reduce unconscious "
            "fillers to sound more authoritative."
        )
    else:
        feedback.append(
            "• Filler Words: Excellent discipline. Minimal or no filler words "
            "were detected."
        )

    # Fluency feedback
    if fluency_score is not None:
        if fluency_score >= 80:
            feedback.append(
                f"• Fluency: Excellent flow (score: {fluency_score}/100). "
                "Smooth delivery with minimal disruptions."
            )
        elif fluency_score >= 60:
            feedback.append(
                f"• Fluency: Good flow (score: {fluency_score}/100). "
                "Some pauses or fillers slightly affect smoothness."
            )
        else:
            feedback.append(
                f"• Fluency: Needs improvement (score: {fluency_score}/100). "
                "Frequent pauses, fillers, or repetitions disrupt flow."
            )

    # Confidence feedback
    if confidence_score is not None:
        if confidence_score >= 70:
            feedback.append(
                f"• Confidence: High (score: {confidence_score}/100). "
                "Steady, assured delivery."
            )
        elif confidence_score >= 40:
            feedback.append(
                f"• Confidence: Moderate (score: {confidence_score}/100). "
                "Some hesitation detected."
            )
        else:
            feedback.append(
                f"• Confidence: Low (score: {confidence_score}/100). "
                "Noticeable hesitation or uncertainty."
            )

    return feedback


def run_voicelens_pipeline(
    audio_path: str | Path,
    transcriber: Transcriber | None = None,
    model_size: str | None = None,
) -> dict[str, Any]:
    """Runs the full VoiceLens speech transcription and analysis pipeline.

    Args:
        audio_path: Path to the WAV or audio recording.
        transcriber: Optional pre-initialized Transcriber instance.
        model_size: Optional model size to use (overrides config).

    Returns:
        dict[str, Any]: Structured analysis output dictionary matching the schema.

    Raises:
        FileNotFoundError: If audio_path does not exist.
        TranscriberError: If transcription fails completely.
    """
    pipeline_start = time.perf_counter()
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file does not exist: {path}")

    # Determine model size from config if not provided
    if model_size is None:
        config = Config()
        model_size = config.get("model", "base")

    # Create or reuse transcriber (with caching)
    cache_key = model_size
    if transcriber is None:
        if cache_key in _transcriber_cache:
            transcriber = _transcriber_cache[cache_key]
            logger.info(f"Reusing cached Transcriber instance (model={model_size})")
        else:
            transcriber = Transcriber(model_size=model_size)
            _transcriber_cache[cache_key] = transcriber
            logger.info(f"Created new Transcriber instance (model={model_size})")
    else:
        logger.info("Reusing provided Transcriber instance")

    # 1. Transcribe audio with Whisper
    transcribe_start = time.perf_counter()
    transcript = transcriber.transcribe(path)
    transcribe_time = time.perf_counter() - transcribe_start
    logger.info(f"Transcription completed in {transcribe_time:.2f}s")

    # Handle empty or likely-hallucinated transcript
    # whisper.cpp can hallucinate short words from silence
    transcript_stripped = transcript.strip()
    
    # Common whisper.cpp hallucination patterns (from whisper.cpp hallucination filtering)
    hallucination_patterns = [
        "thank you",
        "thanks for watching",
        "thanks for listening",
        "subscribe",
        "like and subscribe",
        "follow for more",
        "see you next time",
        "bye",
        "goodbye",
        "the end",
    ]
    
    is_hallucination = False
    if not transcript_stripped:
        is_hallucination = True
        logger.warning("Empty transcript - no speech detected")
    elif len(transcript_stripped) <= 3:
        is_hallucination = True
        logger.warning(f"Very short transcript ({len(transcript_stripped)} chars) - likely hallucination")
    else:
        # Check for known hallucination patterns
        transcript_lower = transcript_stripped.lower()
        for pattern in hallucination_patterns:
            if transcript_lower == pattern or transcript_lower == pattern + ".":
                is_hallucination = True
                logger.warning(f"Detected likely hallucination pattern: '{pattern}'")
                break
        
        # Check for very short transcript from short audio (likely hallucination)
        # This will be validated later when we have audio duration
        if len(transcript_stripped.split()) <= 2:
            logger.warning("Very few words in transcript - may be hallucination from short audio")

    if is_hallucination:
        # Return early with empty results
        analysis_id = f"vl-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(UTC).isoformat()
        
        total_time = time.perf_counter() - pipeline_start
        logger.info(f"Total processing time: {total_time:.2f}s (empty/hallucinated transcript)")
        
        return {
            "id": analysis_id,
            "createdAt": created_at,
            "audioDurationSeconds": 0.0,
            "transcript": {
                "text": "",
                "language": "English (Detected)",
                "wordCount": 0,
            },
            "accent": {
                "predictedAccent": "Unknown",
                "confidence": 0.0,
                "top3Accents": [],
                "notes": ["No speech detected in audio"],
            },
            "pronunciation": {
                "overallScore": 0.0,
                "pronunciationSimilarity": 0.0,
                "confidence": 0.0,
                "backend": "unknown",
                "notes": ["No speech detected for pronunciation assessment"],
            },
            "metrics": {
                "durationSeconds": 0.0,
                "wordCount": 0,
                "wordsPerMinute": 0.0,
                "pauseCount": 0,
                "averagePauseDuration": 0.0,
                "longestPause": 0.0,
                "fillerWordCount": 0,
                "fillerWords": [],
                "repeatedWordCount": 0,
                "repeatedWords": [],
                "fluencyScore": 0.0,
                "confidenceScore": 0.0,
                "syllableCount": 0,
                "averageSyllablesPerWord": 0.0,
                "sentenceCount": 0,
                "averageWordsPerSentence": 0.0,
            },
            "fillerWordsList": [],
            "repeatedWordsList": [],
            "difficultWordsList": [],
            "overallFeedback": [
                "• Accent Profile: No speech detected.",
                "• Pronunciation: No speech detected for assessment.",
                "• Pace (Speed): No coherent conversational speech detected.",
                "• Filler Words: No speech detected.",
                "• Fluency: No speech detected.",
                "• Confidence: No speech detected.",
            ],
        }

    # 2. Concurrently execute analysis modules
    # Pass the SAME transcriber to aligner so it can reuse transcript/timestamps
    aligner = WhisperAligner(transcriber=transcriber)
    metrics_analyzer = SpeechMetricsAnalyzer()

    # Initialize pronunciation backend with fallback
    try:
        from voicelens.pronunciation.speechbrain_backend import SpeechBrainBackend

        pron_backend = SpeechBrainBackend()
        logger.info("Using SpeechBrain backend for pronunciation assessment")
    except Exception as e:
        logger.warning(f"SpeechBrain backend unavailable, using DummyBackend: {e}")
        pron_backend = DummyBackend()

    pron_analyzer = PronunciationAnalyzer(backend=pron_backend)

    # Initialize accent classifier with fallback
    try:
        from voicelens.accent.classifier import AccentClassifier

        accent_classifier = AccentClassifier()
        logger.info("Using SpeechBrain backend for accent classification")
    except Exception as e:
        logger.warning(f"Accent classifier unavailable: {e}")
        accent_classifier = None

    mis_analyzer = MispronunciationAnalyzer()

    align_result: AlignmentResult | None = None
    metrics: SpeechMetrics | None = None
    pron_result: PronunciationResult | None = None
    accent_result: Any = None

    analysis_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_align = executor.submit(aligner.align, path, transcript)
        future_metrics = executor.submit(metrics_analyzer.analyze, path, transcript)
        future_pron = executor.submit(pron_analyzer.analyze, path, transcript)
        future_accent = (
            executor.submit(accent_classifier.classify, path, transcript)
            if accent_classifier
            else None
        )

        try:
            align_result = future_align.result()
        except Exception as e:
            logger.warning(f"Forced Alignment failed: {e}")
            align_result = None

        try:
            metrics = future_metrics.result()
        except Exception as e:
            logger.warning(f"Speech Metrics failed: {e}")
            metrics = None

        try:
            pron_result = future_pron.result()
        except Exception as e:
            logger.warning(f"Pronunciation Assessment failed: {e}")
            pron_result = None

        if future_accent:
            try:
                accent_result = future_accent.result()
            except Exception as e:
                logger.warning(f"Accent Classification failed: {e}")
                accent_result = None

    analysis_time = time.perf_counter() - analysis_start

    # Identify mispronounced/difficult words
    mispronounced_list: list[MispronunciationResult] = []
    if align_result and pron_result:
        try:
            mispronounced_list = mis_analyzer.detect(
                align_result, pron_result.pronunciation_similarity
            )
            # Additional filter: only keep difficult words that are actually in the transcript
            # (protects against alignment/transcription artifacts)
            transcript_words = set()
            for word_candidate in re.findall(r"[a-zA-Z']+", transcript):
                cleaned = re.sub(r"[^a-zA-Z]", "", word_candidate).lower()
                if cleaned:
                    transcript_words.add(cleaned)
            mispronounced_list = [
                item for item in mispronounced_list
                if re.sub(r"[^a-zA-Z]", "", item.word).lower() in transcript_words
            ]
            # Filter out low-confidence difficult words (likely hallucinations)
            # Only keep words with alignment confidence >= 0.3
            mispronounced_list = [
                item for item in mispronounced_list
                if item.confidence >= 0.3
            ]
        except Exception as e:
            logger.warning(f"Mispronunciation Detection failed: {e}")
            mispronounced_list = []

    # 3. Compute realistic composite overall score reflecting component uncertainties
    scores_with_weights = []

    if pron_result is not None:
        p_sim = max(0.0, min(1.0, pron_result.pronunciation_similarity))
        p_conf = pron_result.confidence
        if p_conf > 1.0:
            p_conf = p_conf / 100.0
        p_conf = max(0.0, min(1.0, p_conf))

        scores_with_weights.append((0.40, p_sim * 100.0))
        scores_with_weights.append((0.30, p_conf * 100.0))

    if accent_result is not None:
        a_conf = accent_result.confidence
        if a_conf > 1.0:
            a_conf = a_conf / 100.0
        a_conf = max(0.0, min(1.0, a_conf))

        scores_with_weights.append((0.20, a_conf * 100.0))

    if align_result is not None and align_result.words:
        w_confs = [
            w.confidence / 100.0 if w.confidence > 1.0 else w.confidence
            for w in align_result.words
        ]
        avg_w_conf = max(0.0, min(1.0, sum(w_confs) / len(w_confs)))
        scores_with_weights.append((0.10, avg_w_conf * 100.0))

    if scores_with_weights:
        total_weight = sum(w for w, _ in scores_with_weights)
        weighted_sum = sum(w * s for w, s in scores_with_weights)
        overall_score = round(weighted_sum / total_weight, 2)
        overall_score = max(0.0, min(100.0, overall_score))
    else:
        overall_score = 0.0

    # 4. Format structured output dictionary
    analysis_id = f"vl-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(UTC).isoformat()

    word_count = metrics.word_count if metrics else len(transcript.split())
    duration_sec = metrics.duration_seconds if metrics else 0.0
    wpm = metrics.words_per_minute if metrics else 0.0
    pause_count = metrics.pause_count if metrics else 0
    avg_pause = metrics.average_pause_duration if metrics else 0.0
    longest_pause = metrics.longest_pause if metrics else 0.0
    filler_count = metrics.filler_word_count if metrics else 0
    filler_words = metrics.filler_words if metrics else []
    # New metrics
    repeated_count = metrics.repeated_word_count if metrics else 0
    repeated_words = metrics.repeated_words if metrics else []
    fluency_score = metrics.fluency_score if metrics else None
    confidence_score = metrics.confidence_score if metrics else None
    syllable_count = metrics.syllable_count if metrics else 0
    avg_syllables = metrics.average_syllables_per_word if metrics else 0.0

    sentences = [s for s in re.split(r"[.!?]+", transcript) if s.strip()]
    sentence_count = max(1, len(sentences))
    avg_words_per_sentence = (
        metrics.average_words_per_sentence if metrics else float(word_count) / sentence_count
    )

    # Build filler words count breakdown list
    filler_counts: dict[str, int] = {}
    for fw in filler_words:
        filler_counts[fw] = filler_counts.get(fw, 0) + 1

    filler_list = [{"word": w, "count": c} for w, c in sorted(filler_counts.items())]

    # Build repeated words count breakdown list
    repeated_counts: dict[str, int] = {}
    for rw in repeated_words:
        repeated_counts[rw] = repeated_counts.get(rw, 0) + 1

    repeated_list = [{"word": w, "count": c} for w, c in sorted(repeated_counts.items())]

    difficult_list = [
        {
            "word": item.word,
            "confidence": (
                item.confidence / 100.0 if item.confidence > 1.0 else item.confidence
            ),
            "score": item.score,
            "startTime": item.start_time,
            "endTime": item.end_time,
        }
        for item in mispronounced_list[:10]
    ]

    accent_conf = accent_result.confidence if accent_result else 0.0
    # Normalize confidence to 0-1 range (handle both 0-1 and 0-100 scales)
    if accent_conf > 1.0:
        accent_conf = accent_conf / 100.0
    accent_conf = max(0.0, min(1.0, round(accent_conf, 4)))

    pron_conf = pron_result.confidence if pron_result else 0.0
    # Normalize confidence to 0-1 range (handle both 0-1 and 0-100 scales)
    if pron_conf > 1.0:
        pron_conf = pron_conf / 100.0
    pron_conf = max(0.0, min(1.0, round(pron_conf, 4)))

    pron_sim = pron_result.pronunciation_similarity if pron_result else 0.0
    if pron_sim > 1.0:
        pron_sim = pron_sim / 100.0
    pron_sim = max(0.0, min(1.0, round(pron_sim, 4)))

    top3_accents = []
    if accent_result and accent_result.top_3_accents:
        for acc, conf in accent_result.top_3_accents:
            c_norm = conf / 100.0 if conf > 1.0 else conf
            top3_accents.append(
                {"accent": acc, "confidence": max(0.0, min(1.0, round(c_norm, 4)))}
            )

    # Fix: only pass pron_score if pronunciation actually succeeded
    overall_feedback = generate_clean_feedback(
        pron_score=overall_score if pron_result else None,
        wpm=wpm if metrics else None,
        filler_count=filler_count if metrics else None,
        detected_accent=accent_result.predicted_accent if accent_result else None,
        fluency_score=fluency_score,
        confidence_score=confidence_score,
    )

    total_time = time.perf_counter() - pipeline_start

    # Log timing summary
    logger.info(f"Transcription completed in {transcribe_time:.2f}s")
    logger.info(f"VoiceLens analysis completed in {analysis_time:.2f}s")
    logger.info(f"Total processing time: {total_time:.2f}s")

    return {
        "id": analysis_id,
        "createdAt": created_at,
        "audioDurationSeconds": duration_sec,
        "transcript": {
            "text": transcript,
            "language": "English (Detected)",
            "wordCount": word_count,
        },
        "accent": {
            "predictedAccent": (
                accent_result.predicted_accent if accent_result else "Unknown"
            ),
            "confidence": accent_conf,
            "top3Accents": top3_accents,
            "notes": accent_result.notes if accent_result else [],
        },
        "pronunciation": {
            "overallScore": overall_score,
            "pronunciationSimilarity": pron_sim,
            "confidence": pron_conf,
            "backend": pron_result.backend if pron_result else "unknown",
            "notes": pron_result.notes if pron_result else [],
        },
        "metrics": {
            "durationSeconds": duration_sec,
            "wordCount": word_count,
            "wordsPerMinute": wpm,
            "pauseCount": pause_count,
            "averagePauseDuration": avg_pause,
            "longestPause": longest_pause,
            "fillerWordCount": filler_count,
            "fillerWords": filler_words,
            "repeatedWordCount": repeated_count,
            "repeatedWords": repeated_words,
            "fluencyScore": fluency_score,
            "confidenceScore": confidence_score,
            "syllableCount": syllable_count,
            "averageSyllablesPerWord": avg_syllables,
            "sentenceCount": sentence_count,
            "averageWordsPerSentence": avg_words_per_sentence,
        },
        "fillerWordsList": filler_list,
        "repeatedWordsList": repeated_list,
        "difficultWordsList": difficult_list,
        "overallFeedback": overall_feedback,
    }