'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Mic, Upload, ArrowRight, AlertTriangle, RefreshCw } from 'lucide-react';
import { AudioRecorder } from '@/components/audio/AudioRecorder';
import { AudioUploader } from '@/components/audio/AudioUploader';
import { AnalysisProgress } from '@/components/analysis/AnalysisProgress';
import { AudioStatus } from '@/types/audio';
import { analysisService } from '@/services/analysisService';

function AnalysePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const modeParam = searchParams.get('mode') === 'upload' ? 'upload' : 'record';
  const [activeTab, setActiveTab] = useState<'record' | 'upload'>(modeParam);

  const [status, setStatus] = useState<AudioStatus>('idle');
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [audioPreviewUrl, setAudioPreviewUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Clean up object URL when component unmounts or audio changes
  useEffect(() => {
    return () => {
      if (audioPreviewUrl) {
        URL.revokeObjectURL(audioPreviewUrl);
      }
    };
  }, [audioPreviewUrl]);

  const handleAudioRecorded = (blob: Blob) => {
    if (audioPreviewUrl) {
      URL.revokeObjectURL(audioPreviewUrl);
    }
    const url = URL.createObjectURL(blob);
    setAudioBlob(blob);
    setSelectedFile(null);
    setAudioPreviewUrl(url);
    setStatus('recorded');
    setErrorMessage(null);
  };

  const handleFileSelected = (file: File) => {
    if (audioPreviewUrl) {
      URL.revokeObjectURL(audioPreviewUrl);
    }
    const url = URL.createObjectURL(file);
    setSelectedFile(file);
    setAudioBlob(null);
    setAudioPreviewUrl(url);
    setStatus('recorded');
    setErrorMessage(null);
  };

  const handleClear = () => {
    if (audioPreviewUrl) {
      URL.revokeObjectURL(audioPreviewUrl);
    }
    setAudioBlob(null);
    setSelectedFile(null);
    setAudioPreviewUrl(null);
    setStatus('idle');
    setErrorMessage(null);
  };

  const handleStartAnalysis = async () => {
    const audioInput = selectedFile || audioBlob;

    if (!audioInput) {
      setErrorMessage('Please record speech or upload an audio file first.');
      return;
    }

    try {
      setStatus('analysing');
      setErrorMessage(null);

      const filename = selectedFile ? selectedFile.name : 'recorded_speech.webm';
      const result = await analysisService.analyzeAudio(audioInput, filename);

      // Store analysis result in sessionStorage for the Results page
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
        setErrorMessage('An unexpected error occurred while analyzing your audio sample.');
      }
    }
  };

  const switchTab = (tab: 'record' | 'upload') => {
    setActiveTab(tab);
    handleClear();
    router.replace(`/analyse?mode=${tab}`);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-10 sm:py-16 space-y-8">
      {/* Header */}
      <div className="text-center space-y-3">
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          Analyse Your Voice
        </h1>
        <p className="text-slate-400 text-sm max-w-lg mx-auto">
          Record speech directly or upload an audio file to evaluate your English accent, clarity, and pronunciation.
        </p>
      </div>

      {status === 'analysing' ? (
        <AnalysisProgress />
      ) : (
        <div className="space-y-6">
          {/* Mode Switcher Tabs */}
          <div className="flex items-center justify-center p-1 bg-slate-900 border border-slate-800 rounded-xl w-fit mx-auto">
            <button
              onClick={() => switchTab('record')}
              className={`flex items-center space-x-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'record'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Mic className="w-4 h-4" />
              <span>Record Voice</span>
            </button>

            <button
              onClick={() => switchTab('upload')}
              className={`flex items-center space-x-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'upload'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Upload className="w-4 h-4" />
              <span>Upload File</span>
            </button>
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="p-4 bg-red-950/40 border border-red-800/60 rounded-xl flex items-start gap-3 text-red-200 text-sm max-w-xl mx-auto">
              <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold text-red-300">Analysis Error</p>
                <p className="text-xs text-red-200/80 mt-1">{errorMessage}</p>
              </div>
            </div>
          )}

          {/* Tab Content */}
          {activeTab === 'record' ? (
            <AudioRecorder
              onAudioRecorded={handleAudioRecorded}
              onClear={handleClear}
              recordedAudioUrl={audioPreviewUrl}
            />
          ) : (
            <AudioUploader
              onFileSelected={handleFileSelected}
              onClear={handleClear}
              selectedFile={selectedFile}
              audioPreviewUrl={audioPreviewUrl}
            />
          )}

          {/* Submit Action Button */}
          {(audioBlob || selectedFile) && (
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-4">
              <button
                onClick={handleClear}
                className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-5 py-3 rounded-xl bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition-colors text-sm font-medium"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Reset</span>
              </button>

              <button
                onClick={handleStartAnalysis}
                className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-8 py-3.5 rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 font-semibold text-base transition-all shadow-lg hover:shadow-indigo-500/20"
              >
                <span>Analyse Audio Now</span>
                <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function AnalysePage() {
  return (
    <Suspense fallback={
      <div className="max-w-4xl mx-auto px-4 py-16 text-center text-slate-400">
        Loading voice analyzer...
      </div>
    }>
      <AnalysePageContent />
    </Suspense>
  );
}
