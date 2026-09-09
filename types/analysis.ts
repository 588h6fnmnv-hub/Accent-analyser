export interface CategoryScore {
  score: number; // 0 - 100
  label: string;
  description: string;
  status: 'excellent' | 'good' | 'needs_improvement' | 'attention';
}

export interface AccentCharacteristic {
  trait: string;
  influence: string; // e.g., "General American", "British / Received Pronunciation", "Non-native Vowel Shift"
  description: string;
  confidence: number; // percentage
}

export interface PronunciationIssue {
  id: string;
  word: string;
  phoneticSpelling: string;
  detectedPhonetic: string;
  timestamp?: string;
  severity: 'minor' | 'moderate' | 'major';
  explanation: string;
  tip: string;
}

export interface ImprovementSuggestion {
  id: string;
  category: 'Pronunciation' | 'Clarity' | 'Fluency' | 'Pace' | 'Intonation';
  title: string;
  description: string;
  actionableSteps: string[];
  priority: 'high' | 'medium' | 'low';
}

export interface SpeechPaceDetails {
  wordsPerMinute: number;
  category: 'Slow' | 'Optimal' | 'Fast' | 'Variable';
  assessment: string;
}

export interface ConfidenceDeliveryDetails {
  score: number; // 0 - 100
  pitchVariability: string; // e.g. "Monotone", "Dynamic", "Natural"
  pausesAssessment: string;
}

export interface AnalysisResult {
  id: string;
  timestamp: string;
  audioDurationSeconds: number;
  audioFileName?: string;
  isMock: boolean; // Explicit indicator distinguishing demo/mock data from real ML backend

  // High-level Scores
  overallScore: number;
  pronunciationScore: CategoryScore;
  clarityScore: CategoryScore;
  fluencyScore: CategoryScore;

  // Speaking Characteristics
  speechPace: SpeechPaceDetails;
  confidenceDelivery: ConfidenceDeliveryDetails;

  // Detailed Analysis
  accentCharacteristics: AccentCharacteristic[];
  pronunciationIssues: PronunciationIssue[];
  improvementSuggestions: ImprovementSuggestion[];

  transcription?: string;
}
