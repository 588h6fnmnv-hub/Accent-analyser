"""VoiceLens Core Pipeline Execution Module.

Provides shared execution logic for both the CLI and Python HTTP API.
"""

import concurrent.futures
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from voicelens.accent.classifier import AccentClassifier, AccentResult
from voicelens.alignment.aligner import AlignmentResult, WhisperAligner
from voicelens.metrics.analyzer import SpeechMetrics, SpeechMetricsAnalyzer
from voicelens.pronunciation import (
    MispronunciationAnalyzer,
    MispronunciationResult,
    PronunciationAnalyzer,
    PronunciationResult,
    SpeechBrainBackend,
)
from voicelens.transcriber.whisper import WhisperTranscriber

console = Console()


def generate_clean_feedback(
    pron_score: float | None,
    wpm: float | None,
    filler_count: int | None,
    detected_accent: str | None,
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

    return feedback


def run_voicelens_pipeline(
    audio_path: str | Path,
    transcriber: WhisperTranscriber | None = None,
) -> dict[str, Any]:
    """Runs the full VoiceLens speech transcription and analysis pipeline.

    Args:
        audio_path: Path to the WAV or audio recording.
        transcriber: Optional pre-initialized WhisperTranscriber instance.

    Returns:
        dict[str, Any]: Structured analysis output dictionary matching the schema.

    Raises:
        FileNotFoundError: If audio_path does not exist.
        WhisperTranscriberError: If transcription fails completely.
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file does not exist: {path}")

    tx = transcriber or WhisperTranscriber()

    # 1. Transcribe audio with Whisper
    transcript = tx.transcribe(path)

    # 2. Concurrently execute analysis modules
    aligner = WhisperAligner(transcriber=tx)
    metrics_analyzer = SpeechMetricsAnalyzer()
    pron_backend = SpeechBrainBackend()
    pron_analyzer = PronunciationAnalyzer(backend=pron_backend)
    accent_classifier = AccentClassifier()
    mis_analyzer = MispronunciationAnalyzer()

    align_result: AlignmentResult | None = None
    metrics: SpeechMetrics | None = None
    pron_result: PronunciationResult | None = None
    accent_result: AccentResult | None = None

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_align = executor.submit(aligner.align, path, transcript)
        future_metrics = executor.submit(metrics_analyzer.analyze, path, transcript)
        future_pron = executor.submit(pron_analyzer.analyze, path, transcript)
        future_accent = executor.submit(accent_classifier.classify, path)

        try:
            align_result = future_align.result()
        except Exception as e:
            console.print(
                f"\n[bold yellow]⚠️  Warning (Forced Alignment):[/bold yellow] "
                f"Failed to align audio timing. Details: {e}"
            )
            align_result = None

        try:
            metrics = future_metrics.result()
        except Exception as e:
            console.print(
                f"\n[bold yellow]⚠️  Warning (Speech Metrics):[/bold yellow] "
                f"Failed to compute delivery metrics. Details: {e}"
            )
            metrics = None

        try:
            pron_result = future_pron.result()
        except Exception as e:
            console.print(
                f"\n[bold yellow]⚠️  Warning (Pronunciation Assessment):"
                f"[/bold yellow] Failed to analyze score. Details: {e}"
            )
            pron_result = None

        try:
            accent_result = future_accent.result()
        except Exception as e:
            console.print(
                f"\n[bold yellow]⚠️  Warning (Accent Classification):[/bold yellow] "
                f"Failed to classify accent. Details: {e}"
            )
            accent_result = None

    # Identify mispronounced/difficult words
    mispronounced_list: list[MispronunciationResult] = []
    if align_result and pron_result:
        try:
            mispronounced_list = mis_analyzer.detect(
                align_result, pron_result.pronunciation_similarity
            )
        except Exception as e:
            console.print(
                f"\n[bold yellow]⚠️  Warning (Mispronunciation Detection):"
                f"[/bold yellow] Failed to identify words. Details: {e}"
            )
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
    analysis_id = f"vl-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:4]}"
    created_at = datetime.now(UTC).isoformat()

    word_count = metrics.word_count if metrics else len(transcript.split())
    duration_sec = metrics.duration_seconds if metrics else 0.0
    wpm = metrics.words_per_minute if metrics else 0.0
    pause_count = metrics.pause_count if metrics else 0
    avg_pause = metrics.average_pause_duration if metrics else 0.0
    longest_pause = metrics.longest_pause if metrics else 0.0
    filler_count = metrics.filler_word_count if metrics else 0
    filler_words = metrics.filler_words if metrics else []
    sentences = [s for s in re.split(r"[.!?]+", transcript) if s.strip()]
    sentence_count = max(1, len(sentences))
    avg_words_per_sentence = (
        metrics.average_words_per_sentence if metrics else float(word_count)
    )

    # Build filler words count breakdown list
    filler_counts: dict[str, int] = {}
    for fw in filler_words:
        filler_counts[fw] = filler_counts.get(fw, 0) + 1

    filler_list = [{"word": w, "count": c} for w, c in sorted(filler_counts.items())]

    difficult_list = [
        {
            "word": item.word,
            "confidence": (
                item.confidence / 100.0 if item.confidence > 1.0 else item.confidence
            ),
            "score": item.score,
            "startTime": item.start_time,
            "endTime": item.end_time,
            "start_time": item.start_time,
            "end_time": item.end_time,
        }
        for item in mispronounced_list[:10]
    ]

    accent_conf = accent_result.confidence if accent_result else 0.0
    if accent_conf > 1.0:
        accent_conf = accent_conf / 100.0
    accent_conf = max(0.0, min(1.0, round(accent_conf, 4)))

    pron_conf = pron_result.confidence if pron_result else 0.0
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

    overall_feedback = generate_clean_feedback(
        pron_score=overall_score if pron_result or accent_result else None,
        wpm=wpm if metrics else None,
        filler_count=filler_count if metrics else None,
        detected_accent=accent_result.predicted_accent if accent_result else None,
    )

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
            "duration_seconds": duration_sec,
            "wordCount": word_count,
            "word_count": word_count,
            "wordsPerMinute": wpm,
            "words_per_minute": wpm,
            "pauseCount": pause_count,
            "pause_count": pause_count,
            "averagePauseDuration": avg_pause,
            "average_pause_duration": avg_pause,
            "longestPause": longest_pause,
            "longest_pause": longest_pause,
            "fillerWordCount": filler_count,
            "filler_word_count": filler_count,
            "fillerWords": filler_words,
            "filler_words": filler_words,
            "sentenceCount": sentence_count,
            "sentence_count": sentence_count,
            "averageWordsPerSentence": avg_words_per_sentence,
            "average_words_per_sentence": avg_words_per_sentence,
        },
        "fillerWordsList": filler_list,
        "difficultWordsList": difficult_list,
        "overallFeedback": overall_feedback,
    }
