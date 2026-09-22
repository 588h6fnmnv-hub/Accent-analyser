"""Tests for VoiceLens Speech Metrics Analyzer."""

import tempfile
import wave
from pathlib import Path

import pytest

from voicelens.metrics.analyzer import SpeechMetricsAnalyzer


def create_test_wav(path: Path, duration: float = 1.0, sample_rate: int = 16000, 
                    frequency: float = 440.0, amplitude: float = 0.5) -> None:
    """Create a test WAV file with a sine wave."""
    import numpy as np
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave_data = amplitude * np.sin(2 * np.pi * frequency * t)
    
    # Add some silence at the beginning and end
    silence = np.zeros(int(sample_rate * 0.1))
    wave_data = np.concatenate([silence, wave_data, silence])
    
    # Convert to int16
    wave_int16 = (wave_data * 32767).astype(np.int16)
    
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(wave_int16.tobytes())


def create_silent_wav(path: Path, duration: float = 1.0, sample_rate: int = 16000) -> None:
    """Create a silent WAV file."""
    import numpy as np
    
    silence = np.zeros(int(sample_rate * duration), dtype=np.int16)
    
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(silence.tobytes())


class TestSpeechMetricsAnalyzer:
    """Tests for SpeechMetricsAnalyzer."""

    def setup_method(self):
        """Set up analyzer for tests."""
        self.analyzer = SpeechMetricsAnalyzer()

    def test_analyzer_initialization(self):
        """Test analyzer initializes correctly."""
        assert self.analyzer is not None
        assert self.analyzer.silence_threshold_ratio == 0.02

    def test_empty_transcript(self):
        """Test analysis with empty transcript."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_silent_wav(wav_path, duration=2.0)
            
            metrics = self.analyzer.analyze(wav_path, "")
            
            assert metrics.word_count == 0
            assert metrics.words_per_minute == 0.0
            assert metrics.filler_word_count == 0
            assert metrics.repeated_word_count == 0

    def test_simple_transcript(self):
        """Test analysis with simple transcript."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_test_wav(wav_path, duration=5.0)
            
            transcript = "This is a test sentence."
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            assert metrics.word_count == 5
            assert metrics.words_per_minute > 0
            assert metrics.sentence_count == 1

    def test_filler_word_detection(self):
        """Test filler word detection accuracy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_test_wav(wav_path, duration=10.0)
            
            # Test various filler words
            transcript = "Um, I think this is basically a test, you know."
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            # Should detect: um, think, basically, you know
            assert metrics.filler_word_count >= 3
            filler_words_lower = [f.lower() for f in metrics.filler_words]
            assert "um" in filler_words_lower
            assert "basically" in filler_words_lower

    def test_filler_word_no_false_positives(self):
        """Test that filler detection doesn't have false positives."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_test_wav(wav_path, duration=5.0)
            
            # Words that contain filler-like substrings but aren't fillers
            transcript = "The umbrella is basically useful."
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            # "umbrella" contains "um" but shouldn't count
            # "basically" should count
            filler_words_lower = [f.lower() for f in metrics.filler_words]
            assert "basically" in filler_words_lower
            # "um" should not be detected from "umbrella"

    def test_wpm_calculation(self):
        """Test WPM calculation accuracy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            # 60 seconds of audio
            create_test_wav(wav_path, duration=60.0)
            
            # 150 words in 60 seconds = 150 WPM
            transcript = " ".join([f"word{i}" for i in range(150)])
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            # Should be close to 150 WPM
            assert abs(metrics.words_per_minute - 150.0) < 5.0

    def test_repeated_word_detection(self):
        """Test repeated word detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_test_wav(wav_path, duration=5.0)
            
            transcript = "This is is a test test test sentence."
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            # "is" repeated once, "test" repeated twice = 3 total
            assert metrics.repeated_word_count == 3
            assert "is" in metrics.repeated_words
            assert "test" in metrics.repeated_words

    def test_pause_detection_with_silence(self):
        """Test pause detection with actual silence in audio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            
            # Create audio with silence gaps
            import numpy as np
            sample_rate = 16000
            
            # 1s tone, 1s silence, 1s tone, 1s silence, 1s tone
            tone_duration = 1.0
            silence_duration = 1.0
            
            t = np.linspace(0, tone_duration, int(sample_rate * tone_duration), False)
            tone = 0.5 * np.sin(2 * np.pi * 440 * t)
            silence = np.zeros(int(sample_rate * silence_duration))
            
            wave_data = np.concatenate([tone, silence, tone, silence, tone])
            wave_int16 = (wave_data * 32767).astype(np.int16)
            
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(wave_int16.tobytes())
            
            transcript = "First part. Second part. Third part."
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            # Should detect 2 pauses (the 1s silences)
            assert metrics.pause_count >= 2
            assert metrics.longest_pause >= 0.8  # Close to 1s

    def test_syllable_counting(self):
        """Test syllable counting heuristic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_test_wav(wav_path, duration=5.0)
            
            transcript = "Hello world beautiful"
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            # Hello=2, world=1, beautiful=3 -> total 6
            assert metrics.syllable_count == 6
            assert abs(metrics.average_syllables_per_word - 2.0) < 0.1

    def test_fluency_score_calculation(self):
        """Test fluency score calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_test_wav(wav_path, duration=30.0)
            
            # Good fluency: normal pace, few pauses, no fillers
            transcript = "This is a well spoken sentence with good fluency."
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            # Should have decent fluency score
            assert metrics.fluency_score > 50
            
            # Poor fluency: many fillers
            transcript_poor = "Um uh like basically you know this is poor fluency."
            metrics_poor = self.analyzer.analyze(wav_path, transcript_poor)
            
            # Should have lower fluency score
            assert metrics_poor.fluency_score < metrics.fluency_score

    def test_confidence_score_calculation(self):
        """Test confidence score calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_test_wav(wav_path, duration=10.0)
            
            # Confident: longer utterance, steady pace
            transcript = "This is a confident and clear statement with good structure."
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            assert metrics.confidence_score > 0

    def test_short_recording(self):
        """Test with very short recording."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_test_wav(wav_path, duration=0.5)
            
            transcript = "Hi"
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            assert metrics.word_count == 1
            assert metrics.duration_seconds > 0

    def test_multi_sentence(self):
        """Test with multiple sentences."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_test_wav(wav_path, duration=10.0)
            
            transcript = "First sentence. Second sentence! Third sentence?"
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            assert metrics.sentence_count == 3
            assert metrics.average_words_per_sentence > 0

    def test_silence_audio_no_hallucination(self):
        """Test that silence doesn't produce metrics from hallucinated transcript."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_silent_wav(wav_path, duration=2.0)
            
            # Even if transcript has text (hallucination), pause detection should work
            transcript = "Thank you."  # Common hallucination
            metrics = self.analyzer.analyze(wav_path, transcript)
            
            # Duration should be based on audio, not transcript
            assert abs(metrics.duration_seconds - 2.0) < 0.5


class TestSpeechMetricsAnalyzerEdgeCases:
    """Edge case tests for SpeechMetricsAnalyzer."""

    def setup_method(self):
        self.analyzer = SpeechMetricsAnalyzer()

    def test_no_audio_file(self):
        """Test error handling for missing audio file."""
        with pytest.raises(Exception):
            self.analyzer.analyze(Path("/nonexistent.wav"), "test")

    def test_zero_duration(self):
        """Test handling of zero duration audio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            create_silent_wav(wav_path, duration=0.01)  # Very short
            
            metrics = self.analyzer.analyze(wav_path, "test")
            assert metrics.duration_seconds >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])