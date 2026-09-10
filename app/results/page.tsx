'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { AnalysisResult } from '@/types/analysis';
import { ScoreCard } from '@/components/results/ScoreCard';
import { AccentSummary } from '@/components/results/AccentSummary';
import { PronunciationFeedback } from '@/components/results/PronunciationFeedback';
import { ImprovementSuggestions } from '@/components/results/ImprovementSuggestions';

// Default Fallback Demo Analysis Result if accessed directly
const DEMO_FALLBACK_ANALYSIS: AnalysisResult = {
  id: 'demo_sample_01',
  timestamp: new Date().toISOString(),
  audioDurationSeconds: 18,
  audioFileName: 'speech_sample_demo.wav',
  isMock: true,
  overallScore: 82,
  pronunciationScore: {
    score: 86,
    label: 'Pronunciation',
    description: 'Vowel clarity and consonant articulation are strong, with slight non-native phoneme shifts.',
    status: 'good',
  },
  clarityScore: {
    score: 84,
    label: 'Clarity',
    description: 'Enunciation is distinct and easy to understand for international listeners.',
    status: 'good',
  },
  fluencyScore: {
    score: 78,
    label: 'Fluency',
    description: 'Speech is generally smooth, though occasional pauses occur before complex vocabulary.',
    status: 'needs_improvement',
  },
  speechPace: {
    wordsPerMinute: 135,
    category: 'Optimal',
    assessment: 'Your speaking pace is natural and comfortable (130-150 WPM target range).',
  },
  confidenceDelivery: {
    score: 80,
    pitchVariability: 'Natural pitch variation with good sentence emphasis.',
    pausesAssessment: 'Pauses occur mostly at natural punctuation and sentence boundaries.',
  },
  accentCharacteristics: [
    {
      trait: 'Neutral / Soft Euro-American Vowels',
      influence: 'North American influence with mild vowel reduction',
      description: 'Open vowels like /æ/ in "cat" are well-articulated. Short vowels tend to be slightly raised.',
      confidence: 88,
    },
    {
      trait: 'Dental Consonants Articulation',
      influence: 'Mild non-native dentalization',
      description: 'The "th" sound (/θ/ and /ð/) is occasionally substituted with /t/ or /d/.',
      confidence: 76,
    },
    {
      trait: 'Rhotic R Pronunciation',
      influence: 'General American / Rhotic',
      description: 'Post-vocalic /r/ sounds are pronounced clearly and consistently.',
      confidence: 82,
    },
  ],
  pronunciationIssues: [
    {
      id: 'p1',
      word: 'Thinking',
      phoneticSpelling: '/ˈθɪŋ.kɪŋ/',
      detectedPhonetic: '/ˈtɪŋ.kɪŋ/',
      timestamp: '00:03',
      severity: 'moderate',
      explanation: 'The voiceless dental fricative "th" (/θ/) was pronounced closer to a hard "t" (/t/).',
      tip: 'Place the tip of your tongue gently between your front teeth and blow air lightly through.',
    },
    {
      id: 'p2',
      word: 'Schedule',
      phoneticSpelling: '/ˈskedʒ.uːl/',
      detectedPhonetic: '/ˈʃed.uːl/',
      timestamp: '00:12',
      severity: 'minor',
      explanation: 'Mixed British ("sked-") and American ("shed-") phonetic patterns observed.',
      tip: 'Consistency in American or British conventions helps enhance clarity in formal speech.',
    },
    {
      id: 'p3',
      word: 'World',
      phoneticSpelling: '/wɜːld/',
      detectedPhonetic: '/wɔːld/',
      timestamp: '00:19',
      severity: 'minor',
      explanation: 'Vowel sound was slightly shortened before the dark /l/ consonant.',
      tip: 'Sustain the central vowel /ɜː/ slightly longer before transitioning to the /ld/ cluster.',
    },
  ],
  improvementSuggestions: [
    {
      id: 's1',
      category: 'Pronunciation',
      title: 'Master the "TH" Fricative Sounds (/θ/ and /ð/)',
      description: 'Practice contrasting words like "think vs tink" and "there vs dare" in front of a mirror.',
      actionableSteps: [
        'Lightly rest your tongue tip between top and bottom front teeth.',
        'Practice continuous airflow without stopping the sound into a /t/.',
        'Record 5 sentences starting with "I think..." and check tongue placement.',
      ],
      priority: 'high',
    },
    {
      id: 's2',
      category: 'Fluency',
      title: 'Reduce Hesitation Before Complex Technical Terms',
      description: 'Use continuous breathing to connect words together without micro-pauses.',
      actionableSteps: [
        'Practice reading technical passages out loud using speech shadowing technique.',
        'Maintain steady exhale through multi-syllable words.',
      ],
      priority: 'medium',
    },
    {
      id: 's3',
      category: 'Intonation',
      title: 'Vary Sentence Pitch at Key Stress Points',
      description: 'Elevate pitch slightly on keywords to sound even more engaging and confident.',
      actionableSteps: [
        'Identify the most important noun or verb in each sentence.',
        'Apply slight pitch peak on that key stressed syllable.',
      ],
      priority: 'low',
    },
  ],
  transcription:
    'Thank you for using VoiceLens. I am testing my speech clarity, pronunciation, and speaking pace in this voice recording session.',
};

export default function ResultsPage() {
  const [result, setResult] = useState<AnalysisResult>(DEMO_FALLBACK_ANALYSIS);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = sessionStorage.getItem('latest_analysis_result');
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          const timer = setTimeout(() => {
            setResult(parsed);
          }, 0);
          return () => clearTimeout(timer);
        } catch {
          // Keep fallback
        }
      }
    }
  }, []);

  const categoryScores = [
    result.pronunciationScore,
    result.clarityScore,
    result.fluencyScore,
  ];

  return (
    <div className="max-w-6xl mx-auto px-gutter py-10 sm:py-16 space-y-8 w-full">
      {/* Top Banner Notice for Mock Data */}
      {result.isMock && (
        <div className="p-4 bg-surface-container-low border border-outline-variant/40 rounded-DEFAULT flex items-center justify-between gap-3 text-on-surface-variant text-body-md">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-[20px]">
              info
            </span>
            <span>
              <strong>Demonstration Mode:</strong> Displaying realistic mock analysis results until live AI model backend is connected.
            </span>
          </div>
          <span className="font-mono text-mono-data uppercase border border-outline-variant px-2 py-0.5 rounded-DEFAULT">
            Demo Data
          </span>
        </div>
      )}

      {/* Header Actions & Meta */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-outline-variant/40 pb-6">
        <div>
          <span className="font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant">
            Speech Analysis Report
          </span>
          <h1 className="font-display-metrics text-display-metrics text-primary mt-1">Analysis Results</h1>
          <div className="flex flex-wrap items-center gap-4 font-mono text-mono-data text-on-surface-variant mt-3">
            <span>
              {new Date(result.timestamp).toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
            <span>•</span>
            <span>Duration: {result.audioDurationSeconds}s</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/analyse"
            className="bg-primary text-background font-label-sm text-label-sm uppercase tracking-widest px-6 py-3 rounded-DEFAULT hover:bg-surface-tint transition-colors font-semibold"
          >
            Analyze New Sample
          </Link>
        </div>
      </div>

      {/* Main Scorecard Component */}
      <ScoreCard
        score={result.overallScore}
        label="Overall Speech Rating"
        categoryScores={categoryScores}
      />

      {/* Speech Transcription */}
      {result.transcription && (
        <div className="bg-surface-container-low border border-outline-variant/40 rounded-DEFAULT p-6 space-y-3">
          <span className="font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant block">
            Speech Transcription
          </span>
          <p className="font-body-lg text-body-lg text-primary italic bg-surface p-4 rounded-DEFAULT border border-outline-variant/30 leading-relaxed">
            &ldquo;{result.transcription}&rdquo;
          </p>
        </div>
      )}

      {/* Accent Profile */}
      <AccentSummary
        characteristics={result.accentCharacteristics}
        speechPace={result.speechPace}
        confidenceDelivery={result.confidenceDelivery}
      />

      {/* Pronunciation Feedback */}
      <PronunciationFeedback issues={result.pronunciationIssues} />

      {/* Improvement Suggestions */}
      <ImprovementSuggestions suggestions={result.improvementSuggestions} />

      {/* Bottom CTA */}
      <div className="pt-6 border-t border-outline-variant/40 flex flex-col sm:flex-row items-center justify-between gap-4 font-label-sm text-label-sm text-on-surface-variant">
        <Link href="/analyse" className="hover:text-primary transition-colors uppercase tracking-widest">
          ← Back to Voice Analyzer
        </Link>
        <span>VoiceLens Achromatic Precision</span>
      </div>
    </div>
  );
}
