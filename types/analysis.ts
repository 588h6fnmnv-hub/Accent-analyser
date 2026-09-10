export interface ScoreMetric {
  score: number;
  label: string;
  description: string;
  status: 'good' | 'needs_improvement' | 'warning';
}

export interface SpeechPaceDetails {
  wordsPerMinute: number;
  category: 'Slow' | 'Optimal' | 'Fast';
  assessment: string;
}

export interface ConfidenceDeliveryDetails {
  score: number;
  pitchVariability: string;
  pausesAssessment: string;
}

export interface AccentCharacteristic {
  trait: string;
  influence: string;
  description: string;
  confidence: number; // 0 - 100 percentage
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
  category: string;
  title: string;
  description: string;
  actionableSteps: string[];
  priority: 'high' | 'medium' | 'low';
}

export interface AnalysisResult {
  id: string;
  timestamp: string;
  audioDurationSeconds: number;
  audioFileName?: string;

  // Primary scores
  overallScore: number; // 0 - 100
  pronunciationScore: ScoreMetric;
  clarityScore: ScoreMetric;
  fluencyScore: ScoreMetric;

  // Detailed speech delivery metrics
  speechPace: SpeechPaceDetails;
  confidenceDelivery: ConfidenceDeliveryDetails;

  // Breakdown insights
  accentCharacteristics: AccentCharacteristic[];
  pronunciationIssues: PronunciationIssue[];
  improvementSuggestions: ImprovementSuggestion[];

  // Transcription
  transcription: string;
}
