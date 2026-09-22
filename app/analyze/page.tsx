'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useAudioRecorder, RecordingState, AudioRecorderError, AudioRecorderErrorCode, getBrowserSupportInfo } from '@/lib/audio';
import { apiClient, AnalysisResult, VoiceLensApiError, AnalysisErrorCode } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { useRouter } from 'next/navigation';

type AppStep = 'home' | 'recording' | 'analyzing' | 'results' | 'error';

interface AnalyzePageState {
  step: AppStep;
  recordingState: RecordingState;
  recordingTime: number;
  error: string | null;
  errorCode?: AnalysisErrorCode | AudioRecorderErrorCode;
  result: AnalysisResult | null;
  isSupported: boolean;
  supportReason?: string;
}

export default function AnalyzePage() {
  const router = useRouter();
  const [state, setState] = useState<AnalyzePageState>({
    step: 'home',
    recordingState: 'idle',
    recordingTime: 0,
    error: null,
    result: null,
    isSupported: true,
  });

  const [recordingInterval, setRecordingInterval] = useState<ReturnType<typeof setInterval> | null>(null);
  const recordingStartTimeRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const audioRecorder = useAudioRecorder({
    onStop: async (blob: Blob) => {
      setState((prev) => ({ ...prev, step: 'analyzing', recordingState: 'stopped' }));
      if (recordingInterval) clearInterval(recordingInterval);

      abortControllerRef.current = new AbortController();

      try {
        const result = await apiClient.analyzeAudio(blob, 'recording.webm', {
          signal: abortControllerRef.current.signal,
        });
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('voicelens_current_result', JSON.stringify(result));
        }
        setState((prev) => ({ ...prev, step: 'results', result, error: null }));
        router.push('/results');
      } catch (error) {
        if (error instanceof VoiceLensApiError && error.code === 'TIMEOUT') {
          setState((prev) => ({
            ...prev,
            step: 'error',
            error: 'Analysis timed out. The server took too long to respond. Please try again.',
            errorCode: error.code,
          }));
        } else if (error instanceof VoiceLensApiError && error.code === 'NETWORK_ERROR') {
          setState((prev) => ({
            ...prev,
            step: 'error',
            error: 'Network error. Please check your connection and try again.',
            errorCode: error.code,
          }));
        } else if (error instanceof VoiceLensApiError && error.code === 'EMPTY_RECORDING') {
          setState((prev) => ({
            ...prev,
            step: 'error',
            error: 'Recording is empty. Please record some audio first.',
            errorCode: error.code,
          }));
        } else if (error instanceof VoiceLensApiError && error.code === 'BACKEND_UNAVAILABLE') {
          setState((prev) => ({
            ...prev,
            step: 'error',
            error: 'Backend unavailable. Please ensure the VoiceLens API is running and try again.',
            errorCode: error.code,
          }));
        } else if (error instanceof VoiceLensApiError && error.code === 'TRANSCRIPTION_FAILED') {
          setState((prev) => ({
            ...prev,
            step: 'error',
            error: 'Transcription failed. Please try recording again with clearer speech.',
            errorCode: error.code,
          }));
        } else {
          setState((prev) => ({
            ...prev,
            step: 'error',
            error: error instanceof VoiceLensApiError ? error.message : 'Analysis failed. Please try again.',
            errorCode: error instanceof VoiceLensApiError ? error.code : 'UNKNOWN_ERROR',
          }));
        }
      }
    },
    onError: (error: AudioRecorderError) => {
      if (recordingInterval) clearInterval(recordingInterval);

      if (error.code === 'PERMISSION_DENIED') {
        setState((prev) => ({
          ...prev,
          step: 'error',
          recordingState: 'idle',
          error: 'Microphone access denied. Please allow microphone access in your browser settings and reload the page.',
          errorCode: error.code,
        }));
      } else if (error.code === 'DEVICE_NOT_FOUND') {
        setState((prev) => ({
          ...prev,
          step: 'error',
          recordingState: 'idle',
          error: 'No microphone found. Please connect a microphone and try again.',
          errorCode: error.code,
        }));
      } else if (error.code === 'NOT_SUPPORTED') {
        setState((prev) => ({
          ...prev,
          step: 'error',
          recordingState: 'idle',
          error: 'Audio recording is not supported in this browser. Please use a modern browser like Chrome, Firefox, or Safari.',
          errorCode: error.code,
        }));
      } else if (error.code === 'SECURITY_ERROR') {
        setState((prev) => ({
          ...prev,
          step: 'error',
          recordingState: 'idle',
          error: 'Recording requires HTTPS. Please use HTTPS or localhost.',
          errorCode: error.code,
        }));
      } else {
        setState((prev) => ({
          ...prev,
          step: 'error',
          recordingState: 'idle',
          error: error.message,
          errorCode: error.code,
        }));
      }
    },
  });

  useEffect(() => {
    const supportInfo = getBrowserSupportInfo();
    setState((prev) => ({
      ...prev,
      isSupported: supportInfo.supported,
      supportReason: supportInfo.reason,
    }));

    const checkHealth = async () => {
      const healthy = await apiClient.healthCheck().then(() => true).catch(() => false);
      if (!healthy) {
        setState((prev) => ({
          ...prev,
          error: 'Backend unavailable. Make sure the VoiceLens API is running.',
        }));
      }
    };
    checkHealth();
  }, []);

  const handleStartRecording = useCallback(async () => {
    if (!state.isSupported) return;

    setState((prev) => ({
      ...prev,
      step: 'recording',
      recordingState: 'recording',
      recordingTime: 0,
      error: null,
    }));

    recordingStartTimeRef.current = Date.now();

    const interval = setInterval(() => {
      setState((prev) => ({ ...prev, recordingTime: Math.floor((Date.now() - recordingStartTimeRef.current) / 1000) }));
    }, 1000);
    setRecordingInterval(interval);

    try {
      await audioRecorder.start();
    } catch {
      if (interval) clearInterval(interval);
    }
  }, [audioRecorder, state.isSupported]);

  const handleStopRecording = useCallback(async () => {
    if (recordingInterval) clearInterval(recordingInterval);

    try {
      await audioRecorder.stop();
    } catch {
      // Error handled in onError callback
    }
  }, [audioRecorder, recordingInterval]);

  const handleRetry = useCallback(() => {
    setState((prev) => ({
      ...prev,
      step: 'home',
      error: null,
      errorCode: undefined,
    }));
  }, []);

  const handleNewAnalysis = useCallback(() => {
    router.push('/analyze');
  }, [router]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <main className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">VoiceLens</h1>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-3xl">

          {/* Browser Support Error */}
          {!state.isSupported && state.step === 'home' && (
            <Card variant="bordered" className="border-red-500 dark:border-red-500">
              <CardContent className="flex flex-col items-center gap-4 text-center py-8 text-red-600 dark:text-red-400">
                <svg className="w-12 h-12 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold">Unsupported Browser</h2>
                  <p className="text-sm max-w-md">
                    {state.supportReason || 'Audio recording is not supported in this browser.'}
                  </p>
                  <p className="text-sm">
                    Please use a modern browser like Chrome, Firefox, or Safari on HTTPS or localhost.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Error State */}
          {state.error && state.step === 'error' && (
            <Card variant="bordered" className="mb-6 border-red-500 dark:border-red-500">
              <CardContent className="flex flex-col items-center gap-3 text-center text-red-600 dark:text-red-400">
                <svg className="w-10 h-10 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <p className="text-sm max-w-md">{state.error}</p>
                <Button variant="primary" size="md" onClick={handleRetry}>
                  Try Again
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Home / Ready to Record */}
          {state.step === 'home' && state.isSupported && (
            <Card variant="bordered">
              <CardContent className="text-center py-12">
                <div className="w-24 h-24 mx-auto mb-6 rounded-full border-2 border-gray-200 dark:border-gray-700 flex items-center justify-center">
                  <svg className="w-10 h-10 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h10m-7 0a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <h2 className="text-2xl font-semibold mb-2">Ready to Analyze</h2>
                <p className="text-gray-500 dark:text-gray-400 mb-8 max-w-md mx-auto">
                  Press the button below to start recording. VoiceLens will transcribe your speech
                  and provide detailed analysis including pronunciation, accent, fluency, and more.
                </p>
                <Button size="lg" onClick={handleStartRecording} className="w-full sm:w-auto min-w-[200px]">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10" />
                  </svg>
                  Start Recording
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Recording State */}
          {state.step === 'recording' && (
            <Card variant="elevated">
              <CardContent className="text-center py-12">
                <div className="relative mb-8">
                  <div className="w-32 h-32 mx-auto rounded-full border-4 border-red-500 flex items-center justify-center animate-pulse">
                    <div className="w-16 h-16 rounded-full bg-red-500" />
                  </div>
                  <div className="absolute -bottom-4 left-1/2 -translate-x-1/2">
                    <span className="px-3 py-1 bg-red-500 text-white text-xs font-mono rounded-full">
                      REC
                    </span>
                  </div>
                </div>

                <div className="mb-6">
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Recording...</p>
                  <p className="text-4xl font-mono font-bold tabular-nums">{formatTime(state.recordingTime)}</p>
                </div>

                <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
                  Speak clearly into your microphone. Press Stop when finished.
                </p>

                <Button
                  variant="danger"
                  size="lg"
                  onClick={handleStopRecording}
                  className="w-full sm:w-auto min-w-[200px]"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                  </svg>
                  Stop Recording
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Analyzing State */}
          {state.step === 'analyzing' && (
            <Card variant="elevated">
              <CardContent className="text-center py-12">
                <div className="w-16 h-16 mx-auto mb-6 border-4 border-gray-200 dark:border-gray-700 border-t-black dark:border-t-white rounded-full animate-spin" />
                <h2 className="text-xl font-semibold mb-2">Analyzing Your Speech</h2>
                <p className="text-gray-500 dark:text-gray-400 mb-6">
                  Running transcription, pronunciation analysis, accent detection, and fluency metrics...
                </p>
                <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div className="h-full bg-black dark:bg-white animate-pulse w-1/3" />
                </div>
              </CardContent>
            </Card>
          )}

        </div>
      </div>
    </main>
  );
}