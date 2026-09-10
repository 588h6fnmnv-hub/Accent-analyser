'use client';

import { useState, Suspense } from 'react';
import { useRouter } from 'next/navigation';
import { AudioRecorder } from '@/components/audio/AudioRecorder';
import { AnalysisProgress } from '@/components/analysis/AnalysisProgress';
import { AudioStatus } from '@/types/audio';
import { analysisService } from '@/services/analysisService';

function AnalysePageContent() {
  const router = useRouter();
  const [status, setStatus] = useState<AudioStatus>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleAudioRecorded = async (blob: Blob, durationSeconds: number) => {
    setStatus('analysing');
    setErrorMessage(null);

    try {
      const filename = `recorded_speech_${durationSeconds}s.webm`;
      const result = await analysisService.analyzeAudio(blob, filename);

      if (typeof window !== 'undefined') {
        sessionStorage.setItem('latest_analysis_result', JSON.stringify(result));
      }

      setStatus('completed');
      router.push('/results');
    } catch (err: unknown) {
      console.error('Analysis error:', err);
      setStatus('error');
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('An unexpected error occurred while analyzing your speech.');
      }
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-gutter py-24 relative overflow-hidden">
      {/* Background Grid */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage:
            'linear-gradient(to right, #ffffff 1px, transparent 1px), linear-gradient(to bottom, #ffffff 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />

      {status === 'analysing' ? (
        <AnalysisProgress />
      ) : (
        <div className="max-w-3xl w-full flex flex-col items-center text-center z-10 relative">
          <h1 className="font-display-metrics text-display-metrics text-primary mb-stack-md tracking-tight">
            Analyze your voice
          </h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl mx-auto mb-16">
            Record your voice and get a detailed analysis of your pronunciation, accent and speaking style.
          </p>

          {errorMessage && (
            <div className="w-full max-w-xl mb-8 p-4 bg-error-container/20 border border-error/40 rounded-DEFAULT text-error text-body-md text-left flex items-center justify-between">
              <span>{errorMessage}</span>
              <button
                onClick={() => setErrorMessage(null)}
                className="text-xs uppercase tracking-widest hover:underline ml-4"
              >
                Dismiss
              </button>
            </div>
          )}

          <AudioRecorder onAudioRecorded={handleAudioRecorded} />
        </div>
      )}
    </div>
  );
}

export default function AnalysePage() {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex items-center justify-center font-mono text-mono-data text-on-surface-variant">
          Initializing VoiceLens...
        </div>
      }
    >
      <AnalysePageContent />
    </Suspense>
  );
}
