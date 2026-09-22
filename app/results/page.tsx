'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { AnalysisResult } from '@/lib/api';
import { formatDuration } from '@/lib/audio';

const RESULTS_KEY = 'voicelens_current_result';

export default function ResultsPage() {
  const router = useRouter();
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadResult = () => {
      try {
        if (typeof window === 'undefined') {
          setError('Results not available');
          setLoading(false);
          return;
        }

        const stored = sessionStorage.getItem(RESULTS_KEY);
        if (!stored) {
          setError('No analysis results found. Please run a new analysis.');
          setLoading(false);
          return;
        }

        const parsed = JSON.parse(stored);
        setResult(parsed);
      } catch {
        setError('Failed to load results');
      } finally {
        setLoading(false);
      }
    };

    loadResult();
  }, []);

  const handleNewAnalysis = () => {
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem(RESULTS_KEY);
    }
    router.push('/analyze');
  };

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center">
          <div className="w-12 h-12 mx-auto mb-4 border-4 border-gray-200 dark:border-gray-700 border-t-black dark:border-t-white rounded-full animate-spin" />
          <p className="text-gray-500 dark:text-gray-400">Loading results...</p>
        </div>
      </main>
    );
  }

  if (error || !result) {
    return (
      <main className="min-h-screen flex items-center justify-center px-4">
        <Card variant="bordered" className="max-w-md w-full border-red-500 dark:border-red-500">
          <CardContent className="text-center py-8">
            <svg className="w-12 h-12 mx-auto mb-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h2 className="text-xl font-semibold mb-2">Results Not Found</h2>
            <p className="text-gray-500 dark:text-gray-400 mb-6">
              {error || 'This analysis could not be found.'}
            </p>
            <Button onClick={handleNewAnalysis} className="w-full sm:w-auto min-w-[200px]">
              New Analysis
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 dark:text-green-400';
    if (score >= 60) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const formatDate = (isoString: string) => {
    return new Date(isoString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <main className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <a href="/analyze" className="text-2xl font-semibold tracking-tight hover:opacity-75">VoiceLens</a>
            <span className="text-sm text-gray-500 dark:text-gray-400">/ Results</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500 dark:text-gray-400 font-mono">
              {formatDate(result.createdAt)}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex items-start justify-center px-4 py-8">
        <div className="w-full max-w-4xl space-y-6">
          {/* Transcript Card */}
          <Card variant="bordered">
            <CardHeader>
              <CardTitle>Transcript</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-base whitespace-pre-wrap font-mono text-sm leading-relaxed">
                {result.transcript.text || 'No speech detected'}
              </p>
              <div className="mt-4 flex flex-wrap gap-4 text-sm text-gray-500 dark:text-gray-400">
                <span>Duration: {formatDuration(result.audioDurationSeconds)}</span>
                <span>Words: {result.transcript.wordCount}</span>
                <span>Language: {result.transcript.language}</span>
              </div>
            </CardContent>
            </Card>

          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card variant="bordered">
              <CardContent className="text-center">
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">WPM</p>
                <p className={`text-3xl font-bold font-mono ${getScoreColor(result.metrics.wordsPerMinute)}`}>
                  {result.metrics.wordsPerMinute.toFixed(1)}
                </p>
              </CardContent>
            </Card>
            <Card variant="bordered">
              <CardContent className="text-center">
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Fluency</p>
                <p className={`text-3xl font-bold font-mono ${getScoreColor(result.metrics.fluencyScore)}`}>
                  {result.metrics.fluencyScore.toFixed(1)}
                </p>
              </CardContent>
            </Card>
            <Card variant="bordered">
              <CardContent className="text-center">
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Pronunciation</p>
                <p className={`text-3xl font-bold font-mono ${getScoreColor(result.pronunciation.overallScore)}`}>
                  {result.pronunciation.overallScore.toFixed(1)}
                </p>
              </CardContent>
            </Card>
            <Card variant="bordered">
              <CardContent className="text-center">
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Confidence</p>
                <p className={`text-3xl font-bold font-mono ${getScoreColor(result.metrics.confidenceScore)}`}>
                  {result.metrics.confidenceScore.toFixed(1)}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Detailed Metrics */}
          <div className="grid md:grid-cols-2 gap-4">
            <Card variant="bordered">
              <CardHeader>
                <CardTitle>Speech Delivery</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Word Count</p>
                    <p className="font-mono text-lg">{result.metrics.wordCount}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Syllables</p>
                    <p className="font-mono text-lg">{result.metrics.syllableCount}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Sentences</p>
                    <p className="font-mono text-lg">{result.metrics.sentenceCount}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Avg Words/Sentence</p>
                    <p className="font-mono text-lg">{result.metrics.averageWordsPerSentence.toFixed(1)}</p>
                  </div>
                </div>
                <div className="pt-4 border-t border-gray-200 dark:border-gray-700 grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Pause Count</p>
                    <p className="font-mono text-lg">{result.metrics.pauseCount}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Avg Pause</p>
                    <p className="font-mono text-lg">{result.metrics.averagePauseDuration.toFixed(2)}s</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Longest Pause</p>
                    <p className="font-mono text-lg">{result.metrics.longestPause.toFixed(2)}s</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Avg Syllables/Word</p>
                    <p className="font-mono text-lg">{result.metrics.averageSyllablesPerWord.toFixed(2)}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card variant="bordered">
              <CardHeader>
                <CardTitle>Filler & Repeated Words</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                    Filler Words ({result.metrics.fillerWordCount})
                  </p>
                  {result.metrics.fillerWords.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {result.metrics.fillerWords.map((word, i) => (
                        <span key={i} className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-sm font-mono">
                          {word}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 dark:text-gray-500">No filler words detected</p>
                  )}
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                    Repeated Words ({result.metrics.repeatedWordCount})
                  </p>
                  {result.metrics.repeatedWords.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {result.metrics.repeatedWords.map((word, i) => (
                        <span key={i} className="px-2 py-1 bg-amber-100 dark:bg-amber-900 rounded text-sm font-mono text-amber-800 dark:text-amber-200">
                          {word}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 dark:text-gray-500">No repeated words detected</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Accent & Pronunciation */}
          <div className="grid md:grid-cols-2 gap-4">
            <Card variant="bordered">
              <CardHeader>
                <CardTitle>Accent Analysis</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="text-center">
                  <p className={`text-4xl font-bold font-mono ${getScoreColor(result.accent.confidence * 100)}`}>
                    {(result.accent.confidence * 100).toFixed(1)}%
                  </p>
                  <p className="text-xl font-semibold mt-1">{result.accent.predictedAccent}</p>
                </div>
                {result.accent.top3Accents.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Top Predictions</p>
                    {result.accent.top3Accents.map((acc, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <span>{acc.accent}</span>
                        <span className="font-mono text-gray-500 dark:text-gray-400">
                          {(acc.confidence * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card variant="bordered">
              <CardHeader>
                <CardTitle>Pronunciation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="text-center">
                  <p className={`text-4xl font-bold font-mono ${getScoreColor(result.pronunciation.overallScore)}`}>
                    {result.pronunciation.overallScore.toFixed(1)}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Overall Score</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Similarity</p>
                    <p className="font-mono text-xl">{(result.pronunciation.pronunciationSimilarity * 100).toFixed(1)}%</p>
                  </div>
                  <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Confidence</p>
                    <p className="font-mono text-xl">{(result.pronunciation.confidence * 100).toFixed(1)}%</p>
                  </div>
                </div>
                {result.pronunciation.notes.length > 0 && (
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Notes</p>
                    <ul className="space-y-1 text-sm text-gray-600 dark:text-gray-300">
                      {result.pronunciation.notes.map((note, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="font-mono text-xs">•</span>
                          <span>{note}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Difficult Words */}
          {result.difficultWordsList.length > 0 && (
            <Card variant="bordered">
              <CardHeader>
                <CardTitle>Difficult / Mispronounced Words</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                        <th className="pb-2 font-medium">Word</th>
                        <th className="pb-2 font-medium">Score</th>
                        <th className="pb-2 font-medium">Confidence</th>
                        <th className="pb-2 font-medium">Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.difficultWordsList.map((word, i) => (
                        <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                          <td className="py-2 font-mono font-medium">{word.word}</td>
                          <td className="py-2">{word.score.toFixed(1)}</td>
                          <td className="py-2 font-mono">{(word.confidence * 100).toFixed(1)}%</td>
                          <td className="py-2 font-mono">{word.startTime.toFixed(1)}s - {word.endTime.toFixed(1)}s</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Feedback */}
          <Card variant="bordered">
            <CardHeader>
              <CardTitle>Feedback</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {result.overallFeedback.map((item, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm">
                    <span className="font-mono text-xs text-gray-400 mt-1">•</span>
                    <span className="text-gray-700 dark:text-gray-300">{item}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
            </Card>

          {/* Actions */}
          <div className="flex flex-wrap gap-3 justify-center pt-4">
            <Button onClick={handleNewAnalysis} className="min-w-[180px]">
              New Analysis
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}