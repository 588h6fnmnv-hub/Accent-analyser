"""VoiceLens Accent Analysis - Acoustic Feature-Based Accent Classification.

This module implements a proper acoustic feature-based accent classification system
that analyzes HOW words are spoken rather than WHAT is said.

Architecture:
    Audio
      ↓
Audio quality validation
  ↓
Voice activity detection
  ↓
Whisper transcription (for word timestamps)
  ↓
Phoneme / pronunciation alignment
  ↓
Acoustic feature extraction
  ↓
Phonetic/prosodic features
  ↓
Accent model
  ↓
Calibrated probabilities
  ↓
Accent analysis report

The system primarily uses acoustic/phonetic features rather than transcript content.
"""

import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from enum import Enum

import numpy as np
import torch
import torchaudio

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


class AccentClass(Enum):
    """Supported accent classes."""
    INDIAN_ENGLISH = "Indian English"
    AMERICAN_ENGLISH = "American English"
    BRITISH_ENGLISH = "British English"
    CANADIAN_ENGLISH = "Canadian English"
    AUSTRALIAN_ENGLISH = "Australian English"
    UNKNOWN = "Unknown"
    
    @classmethod
    def all(cls) -> list[str]:
        return [c.value for c in cls if c != cls.UNKNOWN]


class AudioQuality(Enum):
    """Audio quality assessment levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNUSABLE = "unusable"


@dataclass
class AudioQualityReport:
    """Detailed audio quality assessment."""
    duration_seconds: float
    snr_db: float
    rms_level: float
    spectral_flatness: float
    zero_crossing_rate: float
    clipping_ratio: float
    silence_ratio: float
    quality: AudioQuality
    issues: list[str]
    recommended: bool
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SegmentAccentResult:
    """Accent analysis result for a single speech segment."""
    segment_index: int
    start_time: float
    end_time: float
    duration: float
    predicted_accent: str
    model_probabilities: dict[str, float]
    confidence: float
    reliability: str  # "High", "Moderate", "Low", "Very Low"
    audio_quality: AudioQualityReport
    acoustic_features: dict[str, float]


@dataclass
class AccentResult:
    """Comprehensive accent classification result."""
    
    # Primary result
    predicted_accent: str
    model_probability: float  # 0.0-1.0 raw model probability
    calibrated_confidence: float  # 0.0-1.0 calibrated confidence
    reliability: str  # "High", "Moderate", "Low", "Very Low"
    
    # Alternative predictions
    alternative_accents: list[dict[str, Any]]  # [{"accent": "...", "probability": 0.xx, "calibrated": 0.xx}, ...]
    
    # Segmentation info
    segment_count: int
    segment_results: list[SegmentAccentResult] = field(default_factory=list)
    
    # Audio info
    audio_duration: float
    audio_quality: AudioQualityReport
    
    # Supporting info
    model_probabilities: dict[str, float]  # Raw model output
    calibrated_probabilities: dict[str, float]  # Temperature-calibrated
    top_3_accents: list[dict[str, Any]] = field(default_factory=list)  # [{"accent": "...", "probability": 0.xx, "calibrated": 0.xx}, ...]
    model_name: str = ""
    acoustic_features: dict[str, float] = field(default_factory=dict)
    
    # Quality and reliability
    audio_quality: AudioQualityReport = field(default_factory=lambda: AudioQualityReport(
        duration_seconds=0, snr_db=0, rms_level=0, spectral_flatness=0,
        zero_crossing_rate=0, clipping_ratio=0, silence_ratio=0,
        quality=AudioQuality.UNUSABLE, issues=[], recommended=False
    ))
    segment_count: int = 0
    audio_duration: float = 0.0
    warnings: list[str] = field(default_factory=list)
    
    # Disclaimer
    disclaimer: str = (
        "Accent estimation is probabilistic and can be affected by "
        "microphone quality, speaking style, vocabulary, age, "
        "recording length, and the speaker's linguistic background."
    )


class AudioQualityAnalyzer:
    """Analyzes audio quality for accent classification reliability."""
    
    MIN_DURATION_SECONDS = 8.0  # Minimum for reliable accent analysis
    RECOMMENDED_DURATION_SECONDS = 15.0
    MAX_CLIPPING_RATIO = 0.01
    MAX_SILENCE_RATIO = 0.5
    MIN_SNR_DB = 10.0
    
    def __init__(self) -> None:
        self._target_sample_rate = 16000
    
    def analyze(self, audio_path: Path) -> AudioQualityReport:
        """Perform comprehensive audio quality analysis."""
        issues = []
        details = {}
        
        try:
            waveform, sample_rate = self._load_audio(audio_path)
        except Exception as e:
            logger.warning(f"Failed to load audio for quality analysis: {e}")
            return AudioQualityReport(
                duration_seconds=0,
                snr_db=0,
                rms_level=0,
                spectral_flatness=1.0,
                zero_crossing_rate=0,
                clipping_ratio=1.0,
                silence_ratio=1.0,
                quality=AudioQuality.UNUSABLE,
                issues=[f"Failed to load audio: {e}"],
                recommended=False,
            )
        
        # Resample if needed
        if sample_rate != 16000:
            import torchaudio.transforms as T
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
            waveform = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)(waveform)
            sample_rate = 16000
        else:
            waveform = waveform
        
        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        signal = waveform.squeeze(0)
        total_samples = len(signal)
        duration_seconds = total_samples / sample_rate
        details["duration_seconds"] = duration_seconds
        
        # 1. Duration check
        if duration_seconds < self.MIN_DURATION_SECONDS:
            issues.append(f"Recording too short ({duration_seconds:.1f}s). Minimum {self.MIN_DURATION_SECONDS}s recommended.")
        
        if duration_seconds < self.RECOMMENDED_DURATION_SECONDS:
            issues.append(f"Recording shorter than recommended ({self.RECOMMENDED_DURATION_SECONDS}s). Results may be less reliable.")
        
        # 2. RMS level
        rms = float(torch.sqrt(torch.mean(signal ** 2)).item())
        details["rms_level"] = rms
        if rms < 0.01:
            issues.append("Very low volume - recording may be too quiet")
        elif rms > 0.9:
            issues.append("Very high volume - possible clipping")
        
        # 3. Clipping detection
        clipping_threshold = 0.99
        clipping_ratio = float((torch.abs(signal) > clipping_threshold).float().mean().item())
        details["clipping_ratio"] = clipping_ratio
        if clipping_ratio > self.MAX_CLIPPING_RATIO:
            issues.append(f"Clipping detected ({clipping_ratio*100:.1f}% of samples)")
        
        # 4. Silence detection
        frame_duration = 0.01  # 10ms frames
        frame_length = int(sample_rate * frame_duration)
        if frame_length > 0:
            num_frames = total_samples // frame_length
            if num_frames > 0:
                reshaped = signal[:num_frames * frame_length].view(num_frames, frame_length)
                frame_rms = torch.sqrt(torch.mean(reshaped ** 2, dim=1))
                silence_threshold = 0.001
                silent_frames = (frame_rms < silence_threshold).float().sum().item()
                silence_ratio = silent_frames / num_frames
                details["silence_ratio"] = silence_ratio
                if silence_ratio > self.MAX_SILENCE_RATIO:
                    issues.append(f"High silence ratio ({silence_ratio*100:.1f}%)")
        
        # 4. SNR estimation
        snr_db = self._estimate_snr(signal, sample_rate)
        details["snr_db"] = snr_db
        if snr_db < self.MIN_SNR_DB:
            issues.append(f"Low signal-to-noise ratio ({snr_db:.1f} dB)")
        
        # 5. Spectral flatness
        spectral_flatness = self._compute_spectral_flatness(signal)
        details["spectral_flatness"] = spectral_flatness
        if spectral_flatness > 0.8:
            issues.append("High spectral flatness - possibly noisy or tonal")
        
        # 6. Zero crossing rate
        zcr = self._compute_zcr(signal)
        details["zero_crossing_rate"] = zcr
        
        # Determine overall quality
        quality = self._assess_quality(duration_seconds, snr_db, rms, spectral_flatness, clipping_ratio, silence_ratio)
        recommended = quality in (AudioQuality.EXCELLENT, AudioQuality.GOOD, AudioQuality.FAIR)
        
        if not recommended:
            issues.append(f"Audio quality assessed as {quality.value} - results may be unreliable")
        
        return AudioQualityReport(
            duration_seconds=duration_seconds,
            snr_db=snr_db,
            rms_level=rms,
            spectral_flatness=spectral_flatness,
            zero_crossing_rate=zcr,
            clipping_ratio=clipping_ratio,
            silence_ratio=silence_ratio,
            quality=quality,
            issues=issues,
            recommended=recommended,
            details=details,
        )
    
    def _load_audio(self, audio_path: Path) -> tuple[torch.Tensor, int]:
        """Load audio file with torchaudio fallback."""
        # Suppress torchaudio verbose warnings
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
    
    def _estimate_snr(self, signal: torch.Tensor, sample_rate: int) -> float:
        """Estimate SNR in dB using spectral flatness method."""
        try:
            frame_size = 512
            hop_size = 256
            total_samples = len(signal)
            if total_samples < frame_size:
                return 30.0  # Default assumption
            
            n_frames = (len(signal) - frame_size) // 256 + 1
            if n_frames <= 0:
                return 30.0
            
            flatness_values = []
            for i in range(n_frames):
                frame = signal[i * 256:i * 256 + frame_size]
                if len(frame) == frame_size:
                    spectrum = torch.abs(torch.fft.rfft(frame * torch.hann_window(frame_size)))
                    geometric_mean = torch.exp(torch.mean(torch.log(spectrum + 1e-10)))
                    arithmetic_mean = torch.mean(spectrum)
                    if arithmetic_mean > 0:
                        flatness = geometric_mean / arithmetic_mean
                        flatness_values.append(float(flatness.item()))
            
            if flatness_values:
                spectral_flatness = float(np.mean(flatness_values))
                # Estimate SNR from spectral flatness (empirical)
                snr_db = -10 * np.log10(spectral_flatness + 1e-10)
                return max(0.0, min(60.0, snr_db))
        except Exception:
            pass
        return 30.0  # Default assumption
    
    def _compute_spectral_flatness(self, signal: torch.Tensor) -> float:
        """Compute spectral flatness of signal."""
        try:
            frame_size = 512
            hop_size = 256
            total_samples = len(signal)
            if total_samples < frame_size:
                return 1.0
            
            n_frames = (len(signal) - 512) // 256 + 1
            if n_frames <= 0:
                return 1.0
            
            flatness_values = []
            for i in range(n_frames):
                frame = signal[i * 256:i * 256 + 512]
                if len(frame) == 512:
                    spectrum = torch.abs(torch.fft.rfft(frame * torch.hann_window(512)))
                    geometric_mean = torch.exp(torch.mean(torch.log(spectrum + 1e-10)))
                    arithmetic_mean = torch.mean(spectrum)
                    if arithmetic_mean > 0:
                        flatness = geometric_mean / arithmetic_mean
                        flatness_values.append(float(flatness.item()))
            
            return float(np.mean(flatness_values)) if flatness_values else 1.0
        except Exception:
            return 1.0
    
    def _compute_zcr(self, signal: torch.Tensor) -> float:
        """Compute zero crossing rate."""
        zero_crossings = ((signal[:-1] * signal[1:]) < 0).sum().item()
        return zero_crossings / len(signal) if len(signal) > 0 else 0.0
    
    def _assess_quality(
        self,
        duration: float,
        snr_db: float,
        rms: float,
        spectral_flatness: float,
        clipping_ratio: float,
        silence_ratio: float,
    ) -> AudioQuality:
        """Assess overall audio quality."""
        score = 100
        
        # Duration penalty
        if duration < 3.0:
            score -= 40
        elif duration < 8.0:
            score -= 20
        elif duration < 15.0:
            score -= 10
        
        # SNR penalty
        if snr_db < 10:
            score -= 30
        elif snr_db < 20:
            score -= 15
        elif snr_db < 30:
            score -= 5
        
        # RMS level
        if rms < 0.01:
            score -= 25
        elif rms < 0.05:
            score -= 10
        
        # Clipping penalty
        if clipping_ratio > 0.01:
            score -= 20
        elif clipping_ratio > 0.001:
            score -= 10
        
        # Silence penalty
        if silence_ratio > 0.5:
            score -= 20
        elif silence_ratio > 0.3:
            score -= 10
        
        # Spectral flatness
        if spectral_flatness > 0.8:
            score -= 15
        elif spectral_flatness > 0.6:
            score -= 5
        
        if score >= 85:
            return AudioQuality.EXCELLENT
        elif score >= 70:
            return AudioQuality.GOOD
        elif score >= 50:
            return AudioQuality.FAIR
        elif score >= 30:
            return AudioQuality.POOR
        else:
            return AudioQuality.UNUSABLE


class AcousticFeatureExtractor:
    """Extracts acoustic features for accent classification."""
    
    def __init__(self) -> None:
        self._target_sample_rate = 16000
        self._embedding_model: Any = None
        self._embedding_model_name = "speechbrain/spkrec-ecapa-voxceleb"
    
    def _get_embedding_model(self) -> Any:
        """Lazily loads the SpeechBrain ECAPA-TDNN embedding model."""
        if self._embedding_model is None:
            try:
                from speechbrain.inference.classifiers import EncoderClassifier
                logger.info("Loading ECAPA-TDNN embedding model...")
                self._embedding_model = EncoderClassifier.from_hparams(
                    source="speechbrain/spkrec-ecapa-voxceleb",
                    run_opts={"device": "cpu" if not torch.backends.mps.is_available() else "mps"},
                )
                logger.info("ECAPA-TDNN model loaded successfully")
            except Exception as e:
                logger.warning(f"Could not load ECAPA-TDNN model: {e}")
                self._embedding_model = None
        return self._embedding_model
    
    def extract_features(self, audio_path: Path) -> dict[str, float]:
        """Extract comprehensive acoustic features from audio file."""
        features = {}
        
        try:
            # Load audio
            import torchaudio
            waveform, sample_rate = torchaudio.load(str(audio_path))
            
            # Convert to mono if stereo
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            
            # Resample if needed
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
                waveform = resampler(waveform)
                sample_rate = 16000
            
            signal = waveform.squeeze(0)
            
            # 1. Basic signal properties
            features["duration_seconds"] = len(signal) / 16000
            features["rms"] = float(torch.sqrt(torch.mean(torch.tensor(signal) ** 2)).item())
            features["peak_amplitude"] = float(torch.max(torch.abs(torch.tensor(signal))).item())
            
            # 2. Spectral features
            features.update(self._compute_spectral_features(torch.tensor(signal), 16000))
            
            # 3. Pitch/F0 features (using simple autocorrelation)
            features.update(self._compute_pitch_features(torch.tensor(signal), 16000))
            
            # 3. Energy dynamics
            features.update(self._compute_energy_features(torch.tensor(signal)))
            
            # 4. Rhythm/prosody features
            features.update(self._compute_rhythm_features(torch.tensor(signal), 16000))
            
            # 5. Speaker embedding (ECAPA-TDNN)
            try:
                model = self._get_embedding_model()
                if model is not None:
                    # Resample to 16kHz if needed for embedding model
                    if sample_rate != 16000:
                        resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
                        waveform_16k = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)(torch.tensor(audio_data).unsqueeze(0))
                    else:
                        waveform_16k = torch.tensor(audio_data).unsqueeze(0).float() / 32768.0
                    
                    with torch.no_grad():
                        embedding = model.encode_batch(waveform_16k)
                        embedding = embedding.squeeze().cpu().numpy()
                    
                    # Embedding statistics
                    features["embedding_norm"] = float(np.linalg.norm(embedding))
                    features["embedding_mean"] = float(np.mean(embedding))
                    features["embedding_std"] = float(np.std(embedding))
                    features["embedding_dim"] = embedding.shape[0]
                except Exception as e:
                    logger.debug(f"Could not extract speaker embedding: {e}")
                    features["embedding_norm"] = 0.0
                    features["embedding_mean"] = 0.0
                    features["embedding_std"] = 0.0
                    features["embedding_dim"] = 0
            
        except Exception as e:
            logger.warning(f"Feature extraction failed: {e}")
            features["extraction_error"] = str(e)
        
        return features
    
    def _compute_spectral_features(self, signal: torch.Tensor, sample_rate: int) -> dict[str, float]:
        """Compute spectral features."""
        features = {}
        try:
            signal_np = signal.numpy()
            
            # Compute mel spectrogram
            import torchaudio.transforms as T
            mel_transform = T.MelSpectrogram(
                sample_rate=16000,
                n_fft=400,
                hop_length=160,
                n_mels=80,
            )
            signal_tensor = torch.tensor(signal).unsqueeze(0)
            mel_spec = mel_transform(signal_tensor)
            
            # Log mel spectrogram statistics
            log_mel = torch.log(mel_spec + 1e-10)
            features["mel_mean"] = float(torch.mean(log_mel).item())
            features["mel_std"] = float(torch.std(log_mel).item())
            
            # Spectral centroid
            n_fft = 400
            hop_length = 160
            stft = torch.stft(
                torch.tensor(signal).float(),
                n_fft=n_fft,
                hop_length=hop_length,
                window=torch.hann_window(n_fft),
                return_complex=True,
            )
            magnitude = torch.abs(stft)
            freqs = torch.linspace(0, 8000, magnitude.shape[1])
            
            # Spectral centroid
            centroid = torch.sum(magnitude * freqs.unsqueeze(0).unsqueeze(0), dim=1) / (torch.sum(magnitude, dim=1) + 1e-10)
            features["spectral_centroid_mean"] = float(torch.mean(centroid).item())
            features["spectral_centroid_std"] = float(torch.std(centroid).item())
            
            # Spectral rolloff (95% energy)
            cumsum = torch.cumsum(magnitude, dim=1)
            total_energy = cumsum[:, -1:]
            rolloff_idx = (cumsum > 0.95 * total_energy.unsqueeze(1)).float().argmax(dim=1)
            rolloff_freq = freqs[rolloff_idx].float().mean()
            features["spectral_rolloff_mean"] = float(rolloff_freq.item())
            
            # Spectral bandwidth
            centroid_expanded = centroid.unsqueeze(1).expand_as(magnitude)
            bandwidth = torch.sqrt(torch.sum(((torch.arange(magnitude.shape[1]).float().unsqueeze(0).expand_as(magnitude) - centroid_expanded) ** 2) * magnitude, dim=1) / (torch.sum(magnitude, dim=1) + 1e-10))
            features["spectral_bandwidth_mean"] = float(torch.mean(bandwidth).item())
            
            # Spectral flatness
            geometric_mean = torch.exp(torch.mean(torch.log(magnitude + 1e-10), dim=1))
            arithmetic_mean = torch.mean(magnitude, dim=1)
            flatness = geometric_mean / (arithmetic_mean + 1e-10)
            features["spectral_flatness_mean"] = float(torch.mean(flatness).item())
            features["spectral_flatness_std"] = float(torch.std(flatness).item())
            
            # Zero crossing rate
            features["zcr"] = float(torch.mean(((signal[:-1] * signal[1:]) < 0).float()).item())
            
            # Energy
            features["energy"] = float(torch.mean(signal ** 2).item())
            
        except Exception as e:
            logger.debug(f"Spectral feature extraction failed: {e}")
        
        return features
    
    def _compute_pitch_features(self, signal: torch.Tensor, sample_rate: int) -> dict[str, float]:
        """Extract pitch/F0 features using autocorrelation."""
        features = {}
        try:
            signal_np = signal.numpy()
            
            # Simple autocorrelation-based pitch detection
            # Compute autocorrelation
            corr = np.correlate(signal_np, signal_np, mode='full')
            corr = corr[len(corr)//2:]
            
            # Find peaks in autocorrelation (excluding zero lag)
            min_period = int(0.002 * 16000)  # 2ms min period (500 Hz)
            max_period = int(0.02 * 16000)   # 20ms max period (50 Hz)
            
            if len(corr) > max_period:
                # Find peaks in the relevant range
                search_range = corr[min_period:max_period]
                if len(search_range) > 0:
                    peak_idx = np.argmax(search_range) + min_period
                    f0 = 16000 / peak_idx if peak_idx > 0 else 0
                    features["f0_mean"] = float(f0)
                    features["f0_period"] = float(peak_idx)
            
            # Also compute using pyin-like approach (simplified)
            # Frame-based F0
            frame_size = 512
            hop_size = 256
            if len(signal_np) > frame_size:
                n_frames = (len(signal_np) - frame_size) // hop_size + 1
                f0_values = []
                for i in range(n_frames):
                    frame = signal_np[i*hop_size:i*hop_size+frame_size]
                    if len(frame) == frame_size:
                        # Autocorrelation
                        corr = np.correlate(frame, frame, mode='full')
                        corr = corr[len(corr)//2:]
                        min_p = int(0.002 * 16000)
                        max_p = int(0.02 * 16000)
                        if len(corr) > max_p:
                            search = corr[min_p:max_p]
                            if len(search) > 0:
                                peak = np.argmax(search) + min_p
                                if peak > 0:
                                    f0_values.append(16000 / peak)
                
                if f0_values:
                    features["f0_mean"] = float(np.mean(f0_values))
                    features["f0_std"] = float(np.std(f0_values))
                    features["f0_min"] = float(np.min(f0_values))
                    features["f0_max"] = float(np.max(f0_values))
                    features["f0_range"] = float(np.max(f0_values) - np.min(f0_values))
                    # F0 variability (coefficient of variation)
                    if np.mean(f0_values) > 0:
                        features["f0_cv"] = float(np.std(f0_values) / np.mean(f0_values))
        
        except Exception as e:
            logger.debug(f"Pitch feature extraction failed: {e}")
        
        return features
    
    def _compute_energy_features(self, signal: torch.Tensor) -> dict[str, float]:
        """Compute energy-related features."""
        features = {}
        try:
            signal_np = signal.numpy()
            
            # RMS energy
            rms = np.sqrt(np.mean(signal_np ** 2))
            features["rms_energy"] = float(rms)
            
            # Peak amplitude
            peak = np.max(np.abs(signal_np))
            features["peak_amplitude"] = float(peak)
            
            # Dynamic range
            if rms > 0:
                features["dynamic_range_db"] = float(20 * np.log10(peak / (rms + 1e-10)))
            
            # Frame-level energy
            frame_size = 512
            hop_size = 256
            if len(signal_np) > frame_size:
                n_frames = (len(signal_np) - frame_size) // 256 + 1
                frame_energies = []
                for i in range(n_frames):
                    frame = signal_np[i*256:i*256+512]
                    if len(frame) == 512:
                        energy = np.sum(frame ** 2)
                        frame_energies.append(energy)
                
                if frame_energies:
                    features["frame_energy_mean"] = float(np.mean(frame_energies))
                    features["frame_energy_std"] = float(np.std(frame_energies))
                    features["energy_cv"] = float(np.std(frame_energies) / (np.mean(frame_energies) + 1e-10))
                    
                    # Energy peaks (stress indicators)
                    if len(frame_energies) > 2:
                        peaks = np.where(
                            (frame_energies[1:-1] > frame_energies[:-2]) & 
                            (frame_energies[1:-1] > frame_energies[2:])
                        )[0]
                        features["energy_peak_count"] = len(peaks)
                        features["energy_peak_rate"] = len(peaks) / (len(frame_energies) / 100)
        
        except Exception as e:
            logger.debug(f"Energy feature extraction failed: {e}")
        
        return features
    
    def _compute_rhythm_features(self, signal: torch.Tensor, sample_rate: int) -> dict[str, float]:
        """Compute rhythm and timing features."""
        features = {}
        try:
            signal_np = signal.numpy()
            
            # Use onset detection via energy changes
            frame_size = 512
            hop_size = 256
            if len(signal_np) > 1024:
                n_frames = (len(signal_np) - 512) // 256 + 1
                frame_energies = []
                for i in range(n_frames):
                    frame = signal_np[i*256:i*256+512]
                    if len(frame) == 512:
                        frame_energies.append(np.sum(frame ** 2))
                
                if len(frame_energies) > 1:
                    # Onset detection via energy changes
                    energy_diff = np.diff(frame_energies)
                    onset_threshold = np.mean(np.abs(energy_diff)) + 2 * np.std(np.abs(energy_diff))
                    onsets = np.where(np.abs(energy_diff) > onset_threshold)[0]
                    
                    if len(onsets) > 1:
                        # Inter-onset intervals (IOI)
                        ioi = np.diff(onsets) * (hop_size / 16000)  # in seconds
                        features["ioi_mean"] = float(np.mean(ioi))
                        features["ioi_std"] = float(np.std(ioi))
                        features["ioi_cv"] = float(np.std(ioi) / (np.mean(ioi) + 1e-10))
                        features["onset_rate"] = len(onsets) / (len(signal_np) / 16000)
                        
                        # Rhythm regularity
                        if len(ioi) > 2:
                            # Pairwise variability index
                            npvi = np.mean(np.abs(np.diff(ioi)) / (ioi[:-1] + ioi[1:]) * 2) * 100
                            features["npvi"] = float(npvi)  # Normalized Pairwise Variability Index
        
        except Exception as e:
            logger.debug(f"Rhythm feature extraction failed: {e}")
        
        return features


class AccentFeatureModel:
    """Accent classification model using acoustic features.
    
    This is a lightweight classifier that can be trained on accent data.
    For now, it uses a simple logistic regression on acoustic features.
    In production, this would be replaced by a trained neural network.
    """
    
    ACCENT_CLASSES = ["Indian English", "American English", "British English", "Canadian English", "Australian English"]
    
    def __init__(self) -> None:
        self._model: Any = None
        self._scaler: Any = None
        self._feature_names: list[str] = []
        self._is_trained = False
        self._feature_importance: dict[str, float] = {}
    
    def _get_feature_vector(self, features: dict[str, float]) -> np.ndarray:
        """Convert feature dictionary to fixed-size vector."""
        # Define expected features in consistent order
        expected_features = [
            "duration_seconds",
            "rms_energy", "peak_amplitude", "dynamic_range_db",
            "mel_mean", "mel_std",
            "spectral_centroid_mean", "spectral_centroid_std",
            "spectral_rolloff_mean",
            "spectral_bandwidth_mean",
            "spectral_flatness_mean", "spectral_flatness_std",
            "zcr", "energy",
            "f0_mean", "f0_std", "f0_min", "f0_max", "f0_range", "f0_cv",
            "rms_energy", "peak_amplitude", "dynamic_range_db",
            "frame_energy_mean", "frame_energy_std", "energy_cv",
            "energy_peak_count", "energy_peak_rate",
            "f0_mean", "f0_std", "f0_min", "f0_max", "f0_range", "f0_cv",
            "frame_energy_mean", "frame_energy_std", "energy_cv",
            "energy_peak_count", "energy_peak_rate",
            "ioi_mean", "ioi_std", "ioi_cv", "onset_rate", "npvi",
            "embedding_norm", "embedding_mean", "embedding_std", "embedding_dim",
        ]
        
        self._feature_names = expected_features
        vector = np.zeros(len(expected_features))
        for i, feat in enumerate(expected_features):
            vector[i] = features.get(feat, 0.0)
        return vector
    
    def _create_default_model(self) -> Any:
        """Create a default untrained model (logistic regression)."""
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        
        model = LogisticRegression(
            multi_class='multinomial',
            solver='lbfgs',
            max_iter=1000,
            C=1.0,
            random_state=42,
        )
        scaler = StandardScaler()
        return {"model": model, "scaler": scaler}
    
    def predict_proba(self, features: dict[str, float]) -> dict[str, float]:
        """Predict accent probabilities from features."""
        if not self._is_trained:
            # Return uniform distribution if not trained
            prob = 1.0 / len(self.ACCENT_CLASSES)
            return {accent: prob for accent in self.ACCENT_CLASSES}
        
        try:
            vector = self._get_feature_vector(features).reshape(1, -1)
            vector_scaled = self._scaler.transform(vector)
            probas = self._model.predict_proba(vector_scaled)[0]
            return {accent: float(prob) for accent, prob in zip(self.ACCENT_CLASSES, probas)}
        except Exception as e:
            logger.warning(f"Prediction failed: {e}")
            prob = 1.0 / len(self.ACCENT_CLASSES)
            return {accent: prob for accent in self.ACCENT_CLASSES}
    
    def predict(self, features: dict[str, float]) -> tuple[str, float, dict[str, float]]:
        """Predict accent from features."""
        probas = self.predict_proba(features)
        if not probas:
            return "Unknown", 0.0, {}
        
        predicted = max(probas, key=probas.get)
        confidence = probas[predicted]
        return predicted, confidence, probas
    
    def train(self, X: list[dict[str, float]], y: list[str]) -> None:
        """Train the model on labeled data."""
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        
        # Prepare feature matrix
        X = np.array([self._get_feature_vector(f) for f in X])
        y = np.array([self.ACCENT_CLASSES.index(accent) if accent in self.ACCENT_CLASSES else 0 for accent in y])
        
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Train logistic regression
        model = LogisticRegression(
            multi_class='multinomial',
            solver='lbfgs',
            max_iter=1000,
            C=1.0,
            random_state=42,
        )
        model.fit(X_scaled, y)
        
        self._model = model
        self._scaler = scaler
        self._is_trained = True
        logger.info(f"Accent classifier trained on {len(X)} samples")
    
    def save(self, path: Path) -> None:
        """Save model to disk."""
        import pickle
        with open(path, 'wb') as f:
            pickle.dump({
                "model": self._model,
                "scaler": self._scaler,
                "feature_names": self._feature_names,
                "is_trained": self._is_trained,
            }, f)
    
    @classmethod
    def load(cls, path: Path) -> "AccentFeatureModel":
        """Load model from disk."""
        import pickle
        with open(path, 'rb') as f:
            data = pickle.load(f)
        model = cls()
        model._model = data["model"]
        model._scaler = data["scaler"]
        model._feature_names = data["feature_names"]
        model._is_trained = data["is_trained"]
        return model


class AccentAnalyzer:
    """Main accent analysis engine.
    
    Orchestrates the full accent analysis pipeline:
    1. Audio quality validation
    2. Transcription (Whisper)
    3. Forced alignment (word/phoneme timestamps)
    3. Acoustic feature extraction
    4. Accent classification
    5. Multi-segment aggregation
    5. Confidence calibration and reporting
    """
    
    SUPPORTED_ACCENTS = [
        "Indian English",
        "American English", 
        "British English",
        "Canadian English",
        "Australian English",
    ]
    
    MIN_AUDIO_DURATION = 8.0  # seconds
    RECOMMENDED_DURATION = 15.0  # seconds
    
    def __init__(
        self,
        model_path: Path | None = None,
        whisper_model: str = "base.en",
        device: str = "auto",
    ) -> None:
        self.whisper_model = whisper_model
        self.device = device if device != "auto" else ("mps" if torch.backends.mps.is_available() else "cpu")
        
        # Initialize components
        self.quality_analyzer = AudioQualityAnalyzer()
        self.feature_extractor = AcousticFeatureExtractor()
        self.accent_model = AccentFeatureModel()
        
        # Load custom model if provided
        if model_path and model_path.exists():
            try:
                self.accent_model = AccentFeatureModel.load(model_path)
                logger.info(f"Loaded custom accent model from {model_path}")
            except Exception as e:
                logger.warning(f"Could not load custom model: {e}")
        
        # Initialize transcriber (lazy)
        self._transcriber: Any = None
        self._aligner: Any = None
    
    @property
    def transcriber(self) -> Any:
        """Lazy-load transcriber."""
        if self._transcriber is None:
            from voicelens.transcriber import Transcriber
            self._transcriber = Transcriber(model_size="base.en")
        return self._transcriber
    
    @property
    def aligner(self) -> Any:
        """Lazy-load aligner."""
        if self._aligner is None:
            from voicelens.alignment.aligner import WhisperAligner
            self._aligner = WhisperAligner(transcriber=self.transcriber)
        return self._aligner
    
    def analyze(
        self,
        audio_path: str | Path,
        transcript: str = "",
        min_duration: float = 8.0,
    ) -> AccentResult:
        """Run complete accent analysis on audio file.
        
        Args:
            audio_path: Path to WAV audio file
            transcript: Optional transcript text (if already available)
            min_duration: Minimum audio duration for reliable analysis
            
        Returns:
            AccentResult with full analysis
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")
        
        # 1. Audio quality validation
        quality_report = self.quality_analyzer.analyze(audio_path)
        
        # Check minimum duration
        if quality_report.duration_seconds < self.MIN_AUDIO_DURATION:
            return AccentResult(
                predicted_accent="Unknown",
                model_probability=0.0,
                calibrated_confidence=0.0,
                reliability="Very Low",
                alternative_accents=[],
                segment_count=0,
                audio_duration=quality_report.duration_seconds,
                audio_quality=quality_report,
                model_probabilities={},
                calibrated_probabilities={},
                warnings=[
                    f"Recording too short ({quality_report.duration_seconds:.1f}s). "
                    f"Minimum {self.MIN_AUDIO_DURATION}s required for reliable analysis."
                ],
            )
        
        # 2. Transcription (if not provided)
        if not transcript:
            transcript = self.transcriber.transcribe(path)
            if not transcript.strip():
                return AccentResult(
                    predicted_accent="Unknown",
                    model_probability=0.0,
                    calibrated_confidence=0.0,
                    reliability="Very Low",
                    alternative_accents=[],
                    segment_count=0,
                    audio_duration=quality_report.duration_seconds,
                    audio_quality=quality_report,
                    model_probabilities={},
                    calibrated_probabilities={},
                    warnings=["No speech detected in recording"],
                )
        else:
            transcript = transcript.strip()
        
        # 3. Forced alignment for word/phoneme timestamps
        alignment_result = None
        try:
            alignment_result = self.aligner.align(audio_path, transcript)
        except Exception as e:
            logger.warning(f"Alignment failed: {e}")
        
        # 4. Multi-segment analysis
        segment_results = self._analyze_segments(audio_path, transcript)
        
        # 5. Aggregate segment results
        final_result = self._aggregate_results(segment_results, quality_report)
        
        return final_result
    
    def _analyze_segments(
        self,
        audio_path: Path,
        transcript: str,
    ) -> list[SegmentAccentResult]:
        """Split audio into segments and analyze each."""
        # For now, analyze the whole file as one segment
        # TODO: Implement VAD-based segmentation
        result = self._analyze_single_segment(audio_path, transcript)
        return [result]
    
    def _analyze_single_segment(
        self,
        audio_path: Path,
        transcript: str,
    ) -> SegmentAccentResult:
        """Analyze a single audio segment."""
        # Audio quality for this segment
        quality = self.quality_analyzer.analyze(audio_path)
        
        # Extract acoustic features
        features = self.feature_extractor.extract_features(audio_path)
        
        # Predict accent
        predicted, confidence, probas = self.accent_model.predict(features)
        
        # Calibrate confidence (simple Platt scaling placeholder)
        calibrated = min(confidence, 0.95)  # Cap at 95%
        
        # Determine reliability
        reliability = self._assess_reliability(confidence, quality)
        
        # Get alternative accents
        alternatives = [
            {"accent": acc, "probability": prob, "calibrated": min(prob, 0.95)}
            for acc, prob in sorted(
                self.accent_model.predict_proba({}).items(),
                key=lambda x: x[1],
                reverse=True
            )[1:4]
        ]
        
        return SegmentAccentResult(
            segment_index=0,
            start_time=0.0,
            end_time=0.0,  # Will be updated with actual duration
            duration=0.0,
            predicted_accent=accent,
            model_probabilities=probas,
            confidence=calibrated,
            reliability=reliability,
            audio_quality=quality,
            acoustic_features={},
        )
    
    def _assess_reliability(self, confidence: float, quality: AudioQualityReport) -> str:
        """Assess overall reliability of the prediction."""
        if quality.quality == AudioQuality.UNUSABLE:
            return "Very Low"
        elif quality.quality == AudioQuality.POOR:
            return "Low"
        elif quality.quality == AudioQuality.FAIR:
            return "Moderate" if confidence > 0.7 else "Low"
        elif quality.quality == AudioQuality.GOOD:
            return "High" if confidence > 0.8 else "Moderate"
        else:  # EXCELLENT
            return "High" if confidence > 0.7 else "Moderate"
    
    def _aggregate_results(
        self,
        segment_results: list[SegmentAccentResult],
        quality_report: AudioQualityReport,
    ) -> AccentResult:
        """Aggregate multi-segment results into final prediction."""
        if not segment_results:
            return AccentResult(
                predicted_accent="Unknown",
                model_probability=0.0,
                calibrated_confidence=0.0,
                reliability="Very Low",
                alternative_accents=[],
                segment_count=0,
                audio_duration=quality_report.duration_seconds,
                audio_quality=quality_report,
                model_probabilities={},
                calibrated_probabilities={},
                warnings=["No valid speech segments found"],
            )
        
        # Average probabilities across segments (weighted by duration)
        total_duration = sum(s.duration for s in segment_results)
        combined_probas = {}
        
        for segment in segment_results:
            weight = segment.duration / total_duration if total_duration > 0 else 1.0 / len(segment_results)
            for accent, prob in segment.model_probabilities.items():
                combined_probas[accent] = combined_probas.get(accent, 0.0) + prob * weight
        
        # Normalize
        total = sum(combined_probas.values())
        if total > 0:
            combined_probas = {k: v/total for k, v in combined_probas.items()}
        
        # Get top prediction
        if combined_probas:
            predicted = max(combined_probas, key=combined_probas.get)
            model_prob = combined_probas[predicted]
        else:
            predicted = "Unknown"
            model_prob = 0.0
        
        # Calibrate confidence
        calibrated = min(model_prob, 0.95)
        
        # Overall reliability
        reliability = self._assess_reliability(calibrated, quality_report)
        
        # Alternatives
        sorted_accents = sorted(combined_probas.items(), key=lambda x: x[1], reverse=True)
        alternatives = [
            {"accent": acc, "probability": prob, "calibrated": min(prob, 0.95)}
            for acc, prob in sorted_accents[1:4]
        ]
        
        # Top 3
        top3 = [
            {"accent": acc, "probability": prob, "calibrated": min(prob, 0.95)}
            for acc, prob in sorted_accents[:3]
        ]
        
        # Calibrated probabilities
        calibrated_probas = {k: min(v, 0.95) for k, v in combined_probas.items()}
        
        # Build feature summary
        feature_summary = {}
        if segment_results:
            # Average key features across segments
            for key in ["f0_mean", "f0_cv", "spectral_centroid_mean", "spectral_flatness_mean", "ioi_cv", "npvi"]:
                values = [s.acoustic_features.get(key, 0) for s in segment_results if key in s.acoustic_features]
                if values:
                    feature_summary[key] = float(np.mean(values))
        
        return AccentResult(
            predicted_accent=predicted,
            model_probability=model_prob,
            calibrated_confidence=calibrated,
            reliability=reliability,
            alternative_accents=alternatives,
            segment_count=len(segment_results),
            segment_results=segment_results,
            audio_duration=quality_report.duration_seconds,
            audio_quality=quality_report,
            model_probabilities=combined_probas,
            calibrated_probabilities=calibrated_probas,
            top_3_accents=top3,
            model_name="acoustic-feature-classifier",
            acoustic_features=feature_summary,
            audio_quality=quality_report,
            segment_count=len(segment_results),
            audio_duration=quality_report.duration_seconds,
            warnings=quality_report.issues,
        )


# Convenience function for direct use
def analyze_accent(
    audio_path: str | Path,
    transcript: str = "",
    whisper_model: str = "base.en",
) -> AccentResult:
    """Convenience function for one-off accent analysis."""
    analyzer = AccentAnalyzer()
    return analyzer.analyze(audio_path, transcript)


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        transcript = sys.argv[2] if len(sys.argv) > 2 else ""
        
        result = analyze_accent(audio_file, transcript)
        
        print(f"\n{'='*60}")
        print(f"VOICELENS ACCENT ANALYSIS")
        print(f"{'='*60}")
        print(f"\nAccent: {result.predicted_accent}")
        print(f"Confidence: {result.calibrated_confidence*100:.1f}%")
        print(f"Reliability: {result.reliability}")
        print(f"\nAlternative accents:")
        for alt in result.alternative_accents:
            print(f"  {alt['accent']}: {alt['probability']*100:.1f}% (calibrated: {alt['calibrated']*100:.1f}%)")
        print(f"\nOverall Score: {result.result.get('pronunciation', {}).get('overallScore', 'N/A')}")
        print(f"WPM: {result.result.get('metrics', {}).get('wordsPerMinute', 0):.1f}")
        print(f"Duration: {result.audio_duration:.1f}s")
        print(f"Audio Quality: {result.audio_quality.quality.value}")
        if result.audio_quality.issues:
            print("Issues:")
            for issue in result.audio_quality.issues:
                print(f"  - {issue}")
        print(f"\nDisclaimer: {result.disclaimer}")
" 2>&1 | head -100