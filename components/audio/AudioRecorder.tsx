'use client';

import { useState, useRef, useEffect } from 'react';
import { Mic, Square, Trash2, AlertCircle } from 'lucide-react';
import { AudioPlayer } from './AudioPlayer';

interface AudioRecorderProps {
  onAudioRecorded: (blob: Blob, durationSeconds: number) => void;
  onClear: () => void;
  recordedAudioUrl: string | null;
}

export function AudioRecorder({
  onAudioRecorded,
  onClear,
  recordedAudioUrl,
}: AudioRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [permissionError, setPermissionError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    };
  }, []);

  const startRecording = async () => {
    setPermissionError(null);
    audioChunksRef.current = [];

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setPermissionError('Microphone access is not supported by your browser.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mimeType = MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : MediaRecorder.isTypeSupported('audio/mp4')
        ? 'audio/mp4'
        : '';

      const mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: mimeType || 'audio/webm',
        });

        if (audioBlob.size === 0) {
          setPermissionError('Recorded audio was empty. Please try speaking into your microphone.');
          return;
        }

        onAudioRecorded(audioBlob, recordingTime);

        // Stop microphone tracks
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(200);
      setIsRecording(true);
      setRecordingTime(0);

      timerIntervalRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err: unknown) {
      console.error('Error accessing microphone:', err);
      if (err instanceof DOMException && (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError')) {
        setPermissionError('Microphone permission denied. Please allow microphone access in your browser settings.');
      } else {
        setPermissionError('Could not access microphone. Please check your audio input device.');
      }
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    }
  };

  const handleDiscard = () => {
    setRecordingTime(0);
    onClear();
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex flex-col items-center justify-center p-6 bg-slate-900/60 border border-slate-800 rounded-2xl w-full max-w-xl mx-auto shadow-inner">
      {permissionError && (
        <div className="w-full mb-4 p-3 bg-red-900/30 border border-red-700/50 rounded-xl flex items-center gap-3 text-red-200 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
          <span>{permissionError}</span>
        </div>
      )}

      {!recordedAudioUrl ? (
        <div className="flex flex-col items-center gap-6 py-4">
          {/* Recording pulse visualizer status */}
          <div className="relative flex items-center justify-center">
            {isRecording && (
              <>
                <div className="absolute w-28 h-28 bg-red-500/20 rounded-full animate-ping" />
                <div className="absolute w-24 h-24 bg-red-500/30 rounded-full animate-pulse" />
              </>
            )}
            <button
              onClick={isRecording ? stopRecording : startRecording}
              className={`relative z-10 p-6 rounded-full text-white shadow-lg transition-all duration-300 transform active:scale-95 ${
                isRecording
                  ? 'bg-red-600 hover:bg-red-500 ring-4 ring-red-500/40'
                  : 'bg-indigo-600 hover:bg-indigo-500 ring-4 ring-indigo-500/20'
              }`}
              aria-label={isRecording ? 'Stop Recording' : 'Start Recording'}
            >
              {isRecording ? <Square className="w-8 h-8 fill-current" /> : <Mic className="w-8 h-8" />}
            </button>
          </div>

          <div className="text-center">
            <p className="text-lg font-semibold text-white">
              {isRecording ? 'Recording Speech...' : 'Click Microphone to Start Recording'}
            </p>
            <p className="text-sm font-mono text-slate-400 mt-1">
              {isRecording ? formatTimer(recordingTime) : 'Speak clearly for 10–30 seconds for best results'}
            </p>
          </div>
        </div>
      ) : (
        <div className="w-full space-y-4">
          <div className="flex items-center justify-between text-sm text-slate-300 px-1">
            <span className="font-medium">Recorded Voice Preview</span>
            <button
              onClick={handleDiscard}
              className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-red-400 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              <span>Discard & Re-record</span>
            </button>
          </div>

          <AudioPlayer src={recordedAudioUrl} />
        </div>
      )}
    </div>
  );
}
