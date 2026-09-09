'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Sparkles, ArrowLeft, RefreshCw, AlertCircle, Calendar, FileText } from 'lucide-react';
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
    'Thank you for using Accent Analyser. I am testing my speech clarity, pronunciation, and speaking pace in this audio recording session.',
};

export default function ResultsPage() {
  const [result, setResult] = useState<AnalysisResult>(DEMO_FALLBACK_ANALYSIS);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = sessionStorage.getItem('latest_analysis_result');
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          // Set state inside effect asynchronously / on mount from storage
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
    <div className="max-w-5xl mx-auto px-4 py-10 sm:py-16 space-y-8">
      {/* Top Banner Notice for Mock Data */}
      {result.isMock && (
        <div className="p-3.5 bg-amber-950/40 border border-amber-800/60 rounded-xl flex items-center justify-between gap-3 text-amber-200 text-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <span>
              <strong>Demonstration Mode:</strong> Displaying realistic mock analysis results until live AI model backend is connected.
            </span>
          </div>
          <span className="hidden sm:inline-block px-2 py-0.5 bg-amber-900/60 rounded text-[10px] font-mono uppercase">
            Demo Data
          </span>
        </div>
      )}

      {/* Header Actions & Meta */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center space-x-2 text-xs text-indigo-400 font-semibold uppercase tracking-wider mb-1">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Speech Analysis Report</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Your Accent & Voice Analysis</h1>
          <div className="flex items-center space-x-4 text-xs text-slate-400 mt-2">
            <span className="flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-slate-500" />
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
            {result.audioFileName && (
              <>
                <span>•</span>
                <span className="truncate max-w-[150px]">{result.audioFileName}</span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <Link
            href="/analyse"
            className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 text-sm font-semibold transition-colors shadow-sm"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Analyse Another Sample</span>
          </Link>
        </div>
      </div>

      {/* Main Scorecard Component */}
      <ScoreCard
        score={result.overallScore}
        label="Overall Speech Rating"
        categoryScores={categoryScores}
      />

      {/* Speech Transcription (if available) */}
      {result.transcription && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-2">
          <div className="flex items-center space-x-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            <FileText className="w-4 h-4 text-indigo-400" />
            <span>Audio Sample Transcription</span>
          </div>
          <p className="text-sm text-slate-200 italic bg-slate-950 p-4 rounded-xl border border-slate-800/80 leading-relaxed">
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
      <div className="pt-6 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4 text-slate-400 text-sm">
        <Link href="/analyse" className="inline-flex items-center space-x-2 text-indigo-400 hover:text-indigo-300">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Microphone / Upload</span>
        </Link>
        <span className="text-xs text-slate-500">Accent Analyser • Ready for Vercel Deployment</span>
      </div>
    </div>
  );
}
