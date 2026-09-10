'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { AnalysisResult } from '@/types/analysis';
import { ScoreCard } from '@/components/results/ScoreCard';
import { AccentSummary } from '@/components/results/AccentSummary';
import { PronunciationFeedback } from '@/components/results/PronunciationFeedback';
import { ImprovementSuggestions } from '@/components/results/ImprovementSuggestions';

export default function ResultsPage() {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = sessionStorage.getItem('latest_analysis_result');
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          const timer = setTimeout(() => {
            setResult(parsed);
            setLoading(false);
          }, 0);
          return () => clearTimeout(timer);
        } catch (err) {
          console.error('Error parsing stored analysis result:', err);
          const timer = setTimeout(() => setLoading(false), 0);
          return () => clearTimeout(timer);
        }
      } else {
        const timer = setTimeout(() => setLoading(false), 0);
        return () => clearTimeout(timer);
      }
    }
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center font-mono text-mono-data text-on-surface-variant py-24">
        Loading analysis results...
      </div>
    );
  }

  if (!result) {
    return (
      <div className="max-w-3xl mx-auto px-gutter py-24 text-center space-y-6">
        <h1 className="font-display-metrics text-display-metrics text-primary">No Analysis Session Found</h1>
        <p className="font-body-lg text-body-lg text-on-surface-variant max-w-md mx-auto">
          You haven&apos;t recorded or analyzed any voice sessions yet. Record your speech to view your enunciation, clarity, and accent breakdown.
        </p>
        <div>
          <Link
            href="/analyse"
            className="inline-block bg-primary text-background font-label-sm text-label-sm uppercase tracking-widest px-8 py-4 rounded-DEFAULT hover:bg-surface-tint transition-colors font-semibold"
          >
            Record Speech Now
          </Link>
        </div>
      </div>
    );
  }

  const categoryScores = [
    result.pronunciationScore,
    result.clarityScore,
    result.fluencyScore,
  ].filter(Boolean);

  return (
    <div className="max-w-6xl mx-auto px-gutter py-10 sm:py-16 space-y-8 w-full">
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
      {result.speechPace && result.confidenceDelivery && (
        <AccentSummary
          characteristics={result.accentCharacteristics || []}
          speechPace={result.speechPace}
          confidenceDelivery={result.confidenceDelivery}
        />
      )}

      {/* Pronunciation Feedback */}
      <PronunciationFeedback issues={result.pronunciationIssues || []} />

      {/* Improvement Suggestions */}
      <ImprovementSuggestions suggestions={result.improvementSuggestions || []} />

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
