# VoiceLens iOS - Implementation Plan

## Overview

Convert the existing VoiceLens Python CLI/TUI application into a native iOS app using Swift/SwiftUI with **fully on-device processing**. No cloud dependencies, no remote backends.

**Reference Implementation**: Existing Python VoiceLens in `/Users/shalinmuhammed/Desktop/voicelens/voicelens/`

---

## Architecture Overview

### Python → iOS Component Mapping

| Python Component | iOS Implementation Strategy |
|------------------|----------------------------|
| **Transcriber (faster-whisper)** | ✅ **whisper.cpp** (ggml) via C++ bridge - Metal accelerated on iOS |
| **Transcriber (whisper.cpp CLI)** | ✅ **whisper.cpp** embedded - already Metal-accelerated on Apple Silicon |
| **Accent Classifier (SpeechBrain ECAPA-TDNN)** | ⚠️ **Core ML conversion** or **Apple's SFSpeechRecognizer** + custom accent model |
| **Pronunciation (SpeechBrain ECAPA)** | ⚠️ **Core ML conversion** or **Apple's SoundAnalysis** + custom model |
| **Mispronunciation Detection** | ✅ **Swift** (uses Whisper timestamps + phoneme alignment) |
| **Speech Metrics** | ✅ **Swift** (pure Swift port of metrics analyzer) |
| **Audio Recording** | ✅ **AVAudioEngine** / **AVAudioRecorder** |
| **Audio File I/O** | ✅ **AVFoundation** / **AudioToolbox** |
| **Forced Alignment** | ✅ **Whisper timestamps** + custom G2P (Swift port) |
| **Hallucination Detection** | ✅ **Swift port** of existing patterns |
| **TUI Screens** | → **SwiftUI Views** |

---

## iOS Project Structure

```
VoiceLens-iOS/
├── VoiceLens.xcodeproj
├── VoiceLens/
│   ├── App/
│   │   ├── VoiceLensApp.swift
│   │   └── AppDelegate.swift
│   ├── Views/
│   │   ├── HomeView.swift
│   │   ├── RecordingView.swift
│   │   ├── AnalyzingView.swift
│   │   ├── ResultsView.swift
│   │   ├── SettingsView.swift
│   │   ├── DoctorView.swift
│   │   ├── ModelsView.swift
│   │   └── Components/
│   │       ├── WaveformView.swift
│   │       ├── ScoreBarView.swift
│   │       ├── AccentBadgeView.swift
│   │       └── MetricCardView.swift
│   ├── ViewModels/
│   │   ├── RecordingViewModel.swift
│   │   ├── AnalyzingViewModel.swift
│   │   ├── ResultsViewModel.swift
│   │   └── HomeViewModel.swift
│   ├── Audio/
│   │   ├── AudioRecorder.swift
│   │   ├── AudioPlayer.swift
│   │   ├── AudioSessionManager.swift
│   │   └── AudioFileManager.swift
│   ├── Transcription/
│   │   ├── WhisperTranscriber.swift
│   │   ├── WhisperCppBridge.swift (C++ bridge)
│   │   ├── TranscriptionResult.swift
│   │   └── WhisperParams.swift
│   ├── Analysis/
│   │   ├── SpeechMetricsAnalyzer.swift
│   │   ├── AccentAnalyzer.swift
│   │   ├── PronunciationAnalyzer.swift
│   │   ├── MispronunciationDetector.swift
│   │   ├── MispronunciationResult.swift
│   │   ├── SpeechMetrics.swift
│   │   ├── AccentResult.swift
│   │   ├── PronunciationResult.swift
│   │   └── AnalysisPipeline.swift
│   ├── Accent/
│   │   ├── AccentClassifier.swift
│   │   ├── AccentCentroids.swift
│   │   └── AccentVocabulary.swift
│   ├── Pronunciation/
│   │   ├── PronunciationBackend.swift
│   │   ├── CoreMLPronunciationBackend.swift
│   │   ├── DummyPronunciationBackend.swift
│   │   └── MispronunciationDetector.swift
│   ├── Accent/
│   │   ├── AccentClassifier.swift
│   │   ├── AccentEmbeddings.swift
│   │   └── AccentVocabulary.swift
│   ├── Models/
│   │   ├── AnalysisResult.swift
│   │   ├── Transcript.swift
│   │   ├── AccentResult.swift
│   │   ├── PronunciationResult.swift
│   │   ├── SpeechMetrics.swift
│   │   └── AnalysisResult.swift
│   ├── Storage/
│   │   └── TempFileManager.swift
│   ├── UI/
│   │   ├── Theme.swift
│   │   ├── Colors.swift
│   │   ├── Typography.swift
│   │   └── Extensions/
│   ├── WhisperCpp/
│   │   ├── whisper.h (bridging header)
│   │   ├── whisper.cpp (compiled)
│   │   ├── ggml-base.en.bin (model)
│   │   └── WhisperCppBridge.mm (Objective-C++ bridge)
│   └── Resources/
│       ├── Models/
│       │   ├── ggml-base.en.bin
│       │   ├── accent_centroids.mlmodelc
│       │   └── pronunciation_model.mlmodelc
│       └── Fonts/
│           └── SF Mono / SF Pro
├── VoiceLensTests/
│   ├── Audio/
│   ├── Transcription/
│   ├── Analysis/
│   ├── Accent/
│   ├── Pronunciation/
│   ├── Metrics/
│   └── Integration/
├── VoiceLensUITests/
└── README.md
```

---

## Component Implementation Details

### 1. Audio Recording (`AudioRecorder.swift`)

**Python Reference**: `voicelens/recorder/audio.py` (AudioRecorder class)

**iOS Implementation**: `AVAudioEngine` with tap on input node

```swift
class AudioRecorder: ObservableObject {
    @Published var isRecording = false
    @Published var audioLevel: Float = 0.0
    @Published var duration: TimeInterval = 0
    
    private let audioEngine = AVAudioEngine()
    private var audioFile: AVAudioFile?
    private var recordingTimer: Timer?
    private let sampleRate: Double = 16000
    private let format: AVAudioFormat
    
    func startRecording() throws
    func stopRecording() -> URL // returns temp file URL
    func getAudioLevel() -> Float // for waveform visualization
}
```

**Key differences from Python**:
- Use `AVAudioEngine` with `inputNode.installTap` instead of `sounddevice` callback
- `AVAudioRecorder` alternative for simpler file-based recording
- Handle iOS audio session categories (`.record`, `.playAndRecord`)
- Handle iOS microphone permission requests

---

### 2. Transcription (`WhisperTranscriber.swift` + `WhisperCppBridge`)

**Python Reference**: `voicelens/transcriber/whisper.py` (faster-whisper) + `whisper_cpp.py`

**iOS Implementation**: **whisper.cpp** (ggml) via C++ bridge - **PRIMARY CHOICE**

**Why whisper.cpp over faster-whisper on iOS?**
- faster-whisper uses CTranslate2 which has limited iOS support
- whisper.cpp (ggml) has **native Metal support** on iOS
- whisper.cpp is a single C file + headers, easy to embed
- Already built and working in the project (`whisper_cpp/bin/whisper-cli`)
- Models are `.bin` files (ggml format) - already have `ggml-base.en.bin` and `ggml-small.en.bin`

**Architecture**:
```
Swift: WhisperTranscriber.swift
    ↓
Swift/Obj-C++ Bridge: WhisperCppBridge.mm
    ↓
C++: whisper.cpp (ggml) + ggml library
    ↓
Model: ggml-base.en.bin (bundled in app bundle)
```

**WhisperCppBridge.mm** (Objective-C++ bridge):
```objc
#import <Foundation/Foundation.h>
#import "whisper.h"

@interface WhisperCppBridge : NSObject
- (instancetype)initWithModel:(NSString *)modelPath;
- (NSString *)transcribeAudioAtPath:(NSString *)audioPath
                    withParams:(NSDictionary *)params
                          error:(NSError **)error;
- (NSArray<NSDictionary *> *)transcribeWithTimestampsAtPath:(NSString *)audioPath
                                                    error:(NSError **)error;
@end
```

**Swift Wrapper**:
```swift
struct WhisperParams {
    let language: String = "en"
    let beamSize: Int = 8
    let bestOf: Int = 8
    let temperature: Float = 0.0
    let conditionOnPreviousText: Bool = false
    let vadFilter: Bool = true
    let vadThreshold: Float = 0.5
    let minSilenceDurationMs: Int = 2000
    let speechPadMs: Int = 400
    let compressionRatioThreshold: Float = 2.4
    let logProbThreshold: Float = -1.0
    let noSpeechThreshold: Float = 0.6
    let initialPrompt: String = "This is a recording of natural English speech. Transcribe exactly what is spoken including fillers like um, uh, hmm. Do not add or remove words."
    let wordTimestamps: Bool
}

struct TranscriptionResult {
    let text: String
    let segments: [Segment]
    let language: String
    let duration: TimeInterval
}

struct Segment {
    let text: String
    let start: TimeInterval
    let end: TimeInterval
    let confidence: Float
    let words: [WordTimestamp]?
}

struct WordTimestamp {
    let word: String
    let start: TimeInterval
    let end: TimeInterval
    let confidence: Float
}
```

**Model Bundling**:
- Bundle `ggml-base.en.bin` (148MB) in app bundle
- Optionally include `ggml-small.en.bin` (136MB) for better accuracy
- Models go in `Resources/Models/` and copied to app bundle at build time

---

### 3. Speech Metrics Analysis (`SpeechMetricsAnalyzer.swift`)

**Python Reference**: `voicelens/metrics/analyzer.py` (SpeechMetricsAnalyzer)

**iOS Implementation**: **Pure Swift port** - no external dependencies

```swift
struct SpeechMetrics {
    let durationSeconds: Double
    let wordCount: Int
    let wordsPerMinute: Double
    let averageWordsPerSentence: Double
    let pauseCount: Int
    let averagePauseDuration: Double
    let longestPause: Double
    let fillerWordCount: Int
    let fillerWords: [String]
    let repeatedWordCount: Int
    let repeatedWords: [String]
    let fluencyScore: Double
    let confidenceScore: Double
    let syllableCount: Int
    let averageSyllablesPerWord: Double
    let sentenceCount: Int
    let averageWordsPerSentence: Double
}

class SpeechMetricsAnalyzer {
    private let silenceThresholdRatio: Float = 0.02
    private let minDurationForMetrics: TimeInterval = 3.0
    private let minWordsForMetrics: Int = 3
    
    func analyze(audioURL: URL, transcript: String) async throws -> SpeechMetrics
    
    // Port all methods:
    // - estimatePauses (using AVAudioPCMBuffer)
    // - countSyllables
    // - detectRepeatedWords
    // - calculateFluencyScore
    // - calculateConfidenceScore
    // - filler word detection (regex patterns)
    // - short recording protection
}
```

**Key iOS adaptations**:
- Use `AVAudioPCMBuffer` instead of PyTorch tensors
- Use `vDSP` (Accelerate framework) for RMS, FFT operations
- Port regex patterns for filler detection directly
- Use `vDSP_vabs`, `vDSP_rmsqv` for efficient signal processing

---

### 4. Accent Analysis (`AccentAnalyzer.swift`)

**Python Reference**: `voicelens/accent/classifier.py` (AccentClassifier)

**Challenge**: SpeechBrain ECAPA-TDNN doesn't run natively on iOS

**Options ranked by feasibility**:

| Option | Feasibility | Effort | Quality |
|--------|-------------|--------|---------|
| **Apple SFSpeechRecognizer + custom** | ⭐⭐⭐ High | Medium | Good |
| **Core ML converted ECAPA-TDNN** | ⭐⭐ Medium | High | Good |
| **ONNX Runtime + ECAPA-TDNN** | ⭐⭐ Medium | Medium | Good |
| **Custom lightweight CNN on MFCC** | ⭐⭐⭐ High | Low | Medium |
| **Vocabulary fallback only** | ⭐⭐⭐ High | Low | Limited |

**Recommended Approach**: **Hybrid - Core ML + Vocabulary Fallback**

**Phase 1 (MVP)**: Use vocabulary-based classification with confidence thresholds (already implemented in Python, port to Swift)

**Phase 2 (Enhanced)**: Convert ECAPA-TDNN to Core ML
- Export SpeechBrain ECAPA-TDNN to ONNX → Core ML
- Use `coremltools` for conversion
- Bundle `.mlmodelc` in app bundle
- Compute embedding → cosine similarity to pre-computed centroids

**Swift Implementation**:
```swift
struct AccentResult {
    let predictedAccent: String
    let confidence: Double
    let top3Accents: [(accent: String, confidence: Double)]
    let notes: [String]
}

enum AccentType: String, CaseIterable {
    case indianEnglish = "Indian English"
    case americanEnglish = "American English"
    case britishEnglish = "British English"
    case australianEnglish = "Australian English"
    case canadianEnglish = "Canadian English"
    case unknown = "Unknown"
}

class AccentClassifier {
    // Phase 1: Vocabulary-based (port from Python)
    func classifyFromTranscript(_ transcript: String) -> AccentResult
    
    // Phase 2: Audio embedding-based (Core ML)
    func classifyFromAudio(_ audioURL: URL) async throws -> AccentResult
    
    // Hybrid: try audio first, fallback to transcript
    func classify(audioURL: URL, transcript: String?) async throws -> AccentResult
}
```

**Vocabulary Port**: Direct port of `ACCENT_VOCABULARY` dictionary to Swift

---

### 5. Pronunciation Analysis (`PronunciationAnalyzer.swift`)

**Python Reference**: `voicelens/pronunciation/speechbrain_backend.py` + `mispronunciation.py`

**Challenge**: SpeechBrain ECAPA-TDNN for pronunciation assessment

**Options**:
1. **Core ML conversion** of SpeechBrain ECAPA-TDNN + custom scoring
2. **Apple's SoundAnalysis framework** (SoundClassification) - limited to sound events
3. **Custom lightweight approach** using Whisper alignment + audio quality metrics

**Recommended**: **Hybrid - Core ML for embeddings + Swift scoring**

```swift
struct PronunciationResult {
    let overallScore: Double          // 0-100
    let pronunciationSimilarity: Double  // 0-1
    let confidence: Double            // 0-1
    let backend: String
    let notes: [String]
}

struct MispronunciationResult {
    let word: String
    let confidence: Double
    let score: Double
    let startTime: TimeInterval
    let endTime: TimeInterval
    let duration: TimeInterval
    let phonemeCount: Int
}

protocol PronunciationBackend {
    func analyze(audioURL: URL, transcript: String) async throws -> PronunciationResult
}

// Core ML Backend (Phase 2)
class CoreMLPronunciationBackend: PronunciationBackend {
    // Core ML converted ECAPA-TDNN
    // Compute embeddings → similarity + audio quality metrics
}

// Dummy Backend (MVP fallback)
class DummyPronunciationBackend: PronunciationBackend {
    func analyze(audioURL: URL, transcript: String) async throws -> PronunciationResult {
        // Return basic audio quality metrics
        return PronunciationResult(
            overallScore: 0,
            pronunciationSimilarity: 0,
            confidence: 0,
            backend: "unavailable",
            notes: ["Pronunciation assessment unavailable on this device"]
        )
    }
}
```

**Mispronunciation Detection** (port from Python):
- Uses Whisper alignment timestamps + phoneme alignment
- Compute word-level scores combining: confidence, similarity, duration, difficulty
- Only report words actually in transcript (no hallucination)

---

### 6. Forced Alignment (`WhisperAligner.swift`)

**Python Reference**: `voicelens/alignment/aligner.py`

**iOS Implementation**: **Swift port** using Whisper word timestamps

```swift
struct WordAlignment {
    let word: String
    let startTime: TimeInterval
    let endTime: TimeInterval
    let confidence: Float
    let phonemes: [PhonemeAlignment]
}

struct PhonemeAlignment {
    let phoneme: String
    let startTime: TimeInterval
    let endTime: TimeInterval
}

struct AlignmentResult {
    let words: [WordAlignment]
    let notes: [String]
}

class WhisperAligner {
    let transcriber: WhisperTranscriber
    
    func align(audioURL: URL, transcript: String) async throws -> AlignmentResult {
        // 1. Get word timestamps from Whisper (already transcribed)
        let (_, wordTimestamps) = try await transcriber.transcribeWithTimestamps(audioURL: audioURL)
        
        // 2. Filter to only words in transcript
        let transcriptWords = Set(transcript.lowercased().words.map { clean($0) })
        
        // 3. Filter word timestamps to only transcript words
        // 4. Generate phoneme alignments using G2P
        // 5. Distribute word duration across phonemes
    }
}
```

**G2P Port**: Port `convert_word_to_phonemes` to Swift

---

### 7. Recording & File Management

**Python Reference**: `voicelens/recorder/audio.py`, `voicelens/tui/screens.py` (cleanup logic)

```swift
class AudioRecorder: ObservableObject {
    @Published var isRecording = false
    @Published var audioLevel: Float = 0.0
    @Published var duration: TimeInterval = 0
    
    private let audioEngine = AVAudioEngine()
    private var audioFile: AVAudioFile?
    private var recordingTimer: Timer?
    
    func startRecording() throws
    func stopRecording() -> URL  // returns temp file URL
    func cancel()
}

class TempFileManager {
    static let shared = TempFileManager()
    private var currentTempFile: URL?
    
    func registerTempFile(_ url: URL) { currentTempFile = url }
    func cleanupCurrent() { currentTempFile?.delete(); currentTempFile = nil }
    func cleanupAll() { /* clean all voicelens temp files */ }
    
    init() {
        // Register atexit equivalent
        // Use UIApplication.willTerminateNotification
    }
}
```

---

### 8. Data Models (Shared)

```swift
struct AnalysisResult: Codable {
    let id: String
    let createdAt: Date
    let audioDurationSeconds: Double
    let transcript: Transcript
    let accent: AccentResult
    let pronunciation: PronunciationResult
    let metrics: SpeechMetrics
    let fillerWordsList: [FillerWordCount]
    let repeatedWordsList: [RepeatedWordCount]
    let difficultWordsList: [DifficultWord]
    let overallFeedback: [String]
}

struct Transcript {
    let text: String
    let language: String
    let wordCount: Int
}

struct AccentResult: Codable {
    let predictedAccent: String
    let confidence: Double
    let top3Accents: [AccentScore]
    let notes: [String]
}

struct AccentScore: Codable {
    let accent: String
    let confidence: Double
}

struct PronunciationResult: Codable {
    let overallScore: Double
    let pronunciationSimilarity: Double
    let confidence: Double
    let backend: String
    let notes: [String]
}

struct SpeechMetrics: Codable {
    let durationSeconds: Double
    let wordCount: Int
    let wordsPerMinute: Double
    let averageWordsPerSentence: Double
    let pauseCount: Int
    let averagePauseDuration: Double
    let longestPause: Double
    let fillerWordCount: Int
    let fillerWords: [String]
    let repeatedWordCount: Int
    let repeatedWords: [String]
    let fluencyScore: Double
    let confidenceScore: Double
    let syllableCount: Int
    let averageSyllablesPerWord: Double
    let sentenceCount: Int
    let averageWordsPerSentence: Double
}
```

---

## UI Implementation (SwiftUI)

### Design System (Achromatic Precision)

```swift
struct Theme {
    // Colors
    static let background = Color(hex: "0A0A0A")        // Near black
    static let surface = Color(hex: "121212")            // Dark surface
    static let surfaceElevated = Color(hex: "1A1A1A")    // Elevated surface
    static let primary = Color.white                     // White text
    static let secondary = Color(hex: "A0A0A0")          // Gray text
    static let muted = Color(hex: "666666")              // Muted text
    static let accent = Color(hex: "00D4AA")             // Teal accent
    static let accentGreen = Color(hex: "00D4AA")
    static let accentYellow = Color(hex: "FFD600")
    static let accentRed = Color(hex: "FF4444")
    static let border = Color(hex: "2A2A2A")             // Subtle borders
    
    // Typography
    static let fontMono = Font.system(.body, design: .monospaced)
    static let fontMonoSmall = Font.system(.caption, design: .monospaced)
    static let fontMonoLarge = Font.system(.title, design: .monospaced).bold()
    static let fontBody = Font.system(.body, design: .default)
    static let fontCaption = Font.system(.caption, design: .default)
    
    // Spacing
    static let spacingXS: CGFloat = 4
    static let spacingSM: CGFloat = 8
    static let spacingMD: CGFloat = 16
    static let spacingLG: CGFloat = 24
    static let spacingXL: CGFloat = 32
}
```

### View Components

```swift
// Waveform visualization during recording
struct WaveformView: View {
    let level: Float
    let barCount = 60
    
// Score bar
struct ScoreBarView: View {
    let score: Double
    let maxWidth: CGFloat = 200

// Accent badge
struct AccentBadgeView: View {
    let accent: String
    let confidence: Double
    let isUncertain: Bool
    
// Metric card
struct MetricCardView: View {
    let label: String
    let value: String
    let color: Color
```

---

## App Flow

```
HomeView
    │
    ├─► RecordingView (tap to start, tap to stop)
    │       │
    │       ├─ Waveform animation
    │       ├─ Timer (mm:ss.ss)
    │       ├─ Audio level meter
    │       └─ Tap to stop → saves to temp file → AnalyzingView
    │
    ├─► AnalyzingView
    │       ├─ Steps: Transcribing → Analyzing → Preparing
    │       ├─ Progress animation
    │       └─ Cancel button
    │
    └──► ResultsView
            ├─ Transcript (full text)
            ├─ Accent + confidence
            ├─ Overall Score
            ├─ Pronunciation score + similarity
            ├─ WPM, Duration, Word Count
            ├─ Fillers & Pauses
            ├─ Difficult words
            ├─ Insights
            └─ Actions: [Record Again] [Back]
```

---

## Build Configuration

### Xcode Project Settings

```xml
<!-- Build Settings -->
OTHER_LDFLAGS = $(inherited) -lc++ -lstdc++
HEADER_SEARCH_PATHS = $(inherited) $(PROJECT_DIR)/VoiceLens/WhisperCpp
CLANG_CXX_LANGUAGE_STANDARD = c++17
CLANG_CXX_LIBRARY = libc++

// Embed frameworks
// - CoreML.framework
// - AVFoundation.framework
// - AVFAudio.framework
// - Speech.framework
// - SoundAnalysis.framework
// - Accelerate.framework
// - Speech.framework

// Signing & Capabilities
// - Microphone: YES
// - Speech Recognition: YES (if using SFSpeechRecognizer)

// Info.plist
NSMicrophoneUsageDescription = "VoiceLens needs microphone access to record your voice for analysis."
NSSpeechRecognitionUsageDescription = "VoiceLens uses speech recognition for accent analysis."
```

### Build Phases
1. **Compile Sources**: Add `WhisperCppBridge.mm` (Objective-C++)
2. **Embed Frameworks**: None (static linking)
3. **Copy Bundle Resources**: 
   - `ggml-base.en.bin` → `Models/`
   - `accent_centroids.mlmodelc` (when available)
   - `pronunciation_model.mlmodelc` (when available)

---

## Dependencies

### System Frameworks
- AVFoundation
- AVFAudio
- Speech
- SoundAnalysis
- CoreML
- Accelerate
- AVFoundation
- CoreAudio
- CoreML

### Embedded Libraries
- **whisper.cpp** (ggml) - compiled as static library
- **ggml-base.en.bin** - bundled model
- **accent_centroids.mlmodelc** - Core ML accent centroids (when available)
- **pronunciation_model.mlmodelc** - Core ML pronunciation model (when available)

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Xcode project setup with SwiftUI
- [ ] Audio recording with AVAudioEngine
- [ ] Whisper.cpp integration (C++ bridge + ggml-base.en.bin)
- [ ] Basic transcription flow
- [ ] Temp file management with cleanup

### Phase 2: Core Analysis (Week 3-4)
- [ ] SpeechMetricsAnalyzer port to Swift
- [ ] WhisperAligner for forced alignment
- [ ] Transcription + alignment pipeline
- [ ] Basic ResultsView with transcript display

### Phase 3: Analysis Modules (Week 5-6)
- [ ] Accent classification (vocabulary fallback first)
- [ ] Speech metrics analyzer
- [ ] Pronunciation analysis (dummy backend first)
- [ ] Mispronunciation detection
- [ ] Full analysis pipeline

### Phase 4: Accent & Pronunciation Enhancement (Week 7-8)
- [ ] Core ML accent classifier (centroids)
- [ ] Core ML pronunciation backend
- [ ] Accent centroids computation tool
- [ ] Pronunciation Core ML model

### Phase 5: Polish & Testing (Week 9-10)
- [ ] UI polish (Achromatic Precision theme)
- [ ] Unit tests for all analyzers
- [ ] Integration tests
- [ ] Real iPhone testing
- [ ] Performance optimization
- [ ] App Store preparation

---

## Testing Strategy

```swift
// Unit Tests
class SpeechMetricsAnalyzerTests: XCTestCase {
    func testWPMCalculation()
    func testPauseDetection()
    func testFillerDetection()
    func testShortRecordingProtection()
    func testFluencyScore()
    func testConfidenceScore()
}

class TranscriptionTests: XCTestCase {
    func testTranscriptionResultParsing()
    func testHallucinationDetection()
    func testWordTimestamps()
}

class AccentClassifierTests: XCTestCase {
    func testVocabularyClassification()
    func testMixedAccentDetection()
    func testUnknownFallback()
}

// Integration Tests
class AnalysisPipelineTests: XCTestCase {
    func testFullPipelineWithSampleAudio()
    func testShortRecordingHandling()
    func testHallucinationFiltering()
    func testTempFileCleanup()
}

// UI Tests
class VoiceLensUITests: XCTestCase {
    func testRecordStopAnalyzeFlow()
    func testCancelRecording()
    func testRecordAgainFlow()
}
```

---

## Real Device Testing Checklist

- [ ] Microphone permission handling
- [ ] Audio session interruption handling (phone calls, etc.)
- [ ] Background/foreground transitions
- [ ] Memory usage with large models
- [ ] Battery impact
- [ ] Thermal throttling
- [ ] Different iOS versions (15, 16, 17, 18)
- [ ] Different devices (iPhone SE, 14, 15, 16 Pro)
- [ ] Offline operation (Airplane mode)

---

## Known Limitations & Mitigations

| Limitation | Mitigation |
|------------|------------|
| whisper.cpp model size (~148MB base) | Offer model size selection; support tiny/small |
| Accent classification without centroids | Vocab fallback + "Unknown" when uncertain |
| Pronunciation without Core ML | Dummy backend with quality metrics |
| No persistent history | By design (privacy-first) |
| whisper.cpp model size (148MB) | Offer model size selector; warn on cellular |
| Metal shader compilation at first launch | Pre-warm on first launch |

---

## Next Steps

1. **Create Xcode project** with SwiftUI app target
2. **Add whisper.cpp** as static library target
3. **Build whisper.cpp bridge** (Objective-C++)
4. **Implement AudioRecorder** with AVAudioEngine
4. **Build WhisperTranscriber** with C++ bridge
5. **Port SpeechMetricsAnalyzer** to Swift
6. **Build RecordingView + AnalyzingView + ResultsView**
7. **Port SpeechMetricsAnalyzer, WhisperAligner**
8. **Build AccentClassifier (vocab fallback first)**
9. **Build full analysis pipeline**
10. **Build ResultsView with Achromatic Precision theme**
11. **Integration testing on device**

---

## Appendix: whisper.cpp on iOS Build Notes

```bash
# Build whisper.cpp for iOS
cd whisper.cpp
cmake -B build-ios -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_SYSROOT=iphoneos \
      -DCMAKE_OSX_DEPLOYMENT_TARGET=15.0 \
      -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON \
      -DBUILD_SHARED_LIBS=OFF -DWHISPER_BUILD_TESTS=OFF
cmake --build build-ios --config Release -j$(sysctl -n hw.ncpus)

# Output: build-ios/src/libwhisper.a (static library)
# Copy to Xcode project
```

**Model bundling**:
```bash
# Copy models to Xcode project
cp whisper.cpp/models/ggml-base.en.bin VoiceLens/Resources/Models/
cp whisper.cpp/models/ggml-small.en.bin VoiceLens/Resources/Models/  # optional
```

---

## Key Files to Create First

1. `VoiceLens.xcodeproj` - Xcode project
2. `VoiceLens/WhisperCpp/whisper.h` - whisper.cpp header (copy from whisper.cpp)
2. `VoiceLens/WhisperCpp/whisper.cpp` - copy from whisper.cpp (or use as static lib)
3. `VoiceLens/WhisperCpp/WhisperCppBridge.h/.mm` - Obj-C++ bridge
4. `VoiceLens/Audio/AudioRecorder.swift`
5. `VoiceLens/Transcription/WhisperTranscriber.swift`
6. `VoiceLens/Transcription/WhisperParams.swift`
7. `VoiceLens/Transcription/TranscriptionResult.swift`
7. `VoiceLens/Audio/AudioRecorder.swift`
8. `VoiceLens/Analysis/SpeechMetricsAnalyzer.swift`
8. `VoiceLens/Analysis/WhisperAligner.swift`
9. `VoiceLens/Views/RecordingView.swift`
9. `VoiceLens/Views/AnalyzingView.swift`
10. `VoiceLens/Views/ResultsView.swift`
11. `VoiceLens/Views/HomeView.swift`
12. `VoiceLens/App/VoiceLensApp.swift`
13. `VoiceLens/UI/Theme.swift`
14. `VoiceLens/Analysis/SpeechMetricsAnalyzer.swift`
15. `VoiceLens/Analysis/WhisperAligner.swift`
16. `VoiceLens/Models/AnalysisResult.swift`
17. `VoiceLens/Audio/TempFileManager.swift`
18. `VoiceLens/ViewModels/RecordingViewModel.swift`

---

This plan provides a complete roadmap to build VoiceLens as a native iOS app with fully on-device processing.