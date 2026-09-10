'use client';

import { useState, useRef, useEffect } from 'react';

interface AudioRecorderProps {
  onAudioRecorded: (blob: Blob, durationSeconds: number) => void;
  onRecordingStart?: () => void;
  isRecordingMode?: boolean;
}

export function AudioRecorder({
  onAudioRecorded,
  onRecordingStart,
}: AudioRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [permissionError, setPermissionError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const durationRef = useRef<number>(0);

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
    durationRef.current = 0;

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

        const finalDuration = durationRef.current || 1;
        onAudioRecorded(audioBlob, finalDuration);

        // Stop microphone tracks immediately
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(200);
      setIsRecording(true);
      setRecordingTime(0);
      if (onRecordingStart) {
        onRecordingStart();
      }

      timerIntervalRef.current = setInterval(() => {
        setRecordingTime((prev) => {
          const next = prev + 1;
          durationRef.current = next;
          return next;
        });
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

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Generate 64 bars for the bell-curve waveform
  const bars = Array.from({ length: 64 }, (_, i) => {
    const distanceToCenter = Math.abs((i - 32) / 32);
    const baseHeight = Math.max(10, Math.round(100 - distanceToCenter * 80));
    const animDuration = (0.5 + (i % 5) * 0.25).toFixed(2);
    const animDelay = (-((i * 0.1) % 2)).toFixed(2);

    let colorClass = 'bg-surface-variant';
    if (distanceToCenter < 0.2) {
      colorClass = 'bg-primary';
    } else if (distanceToCenter < 0.6) {
      colorClass = 'bg-secondary';
    }

    return { id: i, baseHeight, animDuration, animDelay, colorClass };
  });

  return (
    <div className="z-10 flex flex-col items-center w-full max-w-3xl px-gutter mx-auto">
      {permissionError && (
        <div className="w-full mb-6 p-4 bg-error-container/20 border border-error/40 rounded-DEFAULT text-error text-body-md flex items-center justify-between">
          <span>{permissionError}</span>
          <button
            onClick={() => setPermissionError(null)}
            className="text-xs uppercase tracking-widest hover:underline ml-4 cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {!isRecording ? (
        <div className="flex flex-col items-center">
          {/* Interactive Microphone Zone */}
          <div
            onClick={startRecording}
            className="mb-12 relative flex items-center justify-center mic-container cursor-pointer group"
          >
            <div className="absolute w-40 h-40 rounded-full border border-surface-variant opacity-30 mic-ring transition-all duration-500" />
            <div className="absolute w-48 h-48 rounded-full border border-surface-container-high opacity-10 transition-all duration-500 group-hover:scale-105" />
            <button
              aria-label="Start recording"
              className="w-24 h-24 rounded-full bg-surface-container-low border border-outline-variant flex items-center justify-center relative z-10 transition-all duration-300 group-hover:border-primary group-hover:bg-surface-container focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
            >
              <span className="material-symbols-outlined text-[40px] text-primary transition-transform duration-300 group-hover:scale-110">
                mic
              </span>
            </button>
          </div>

          <button
            onClick={startRecording}
            className="w-full max-w-xs bg-primary text-background font-headline-md text-headline-md py-3 px-6 rounded-DEFAULT hover:bg-surface-tint transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-background focus:ring-primary font-semibold cursor-pointer"
          >
            Start recording
          </button>
        </div>
      ) : (
        <div className="flex flex-col items-center w-full">
          {/* Metadata Top */}
          <div className="flex flex-col items-center gap-2 mb-12">
            <div className="flex items-center gap-3 border border-outline-variant/50 rounded-full px-4 py-1.5 bg-surface-container-low/50 backdrop-blur-sm">
              <div className="w-2 h-2 rounded-full bg-primary animate-pulse shadow-[0_0_8px_rgba(255,255,255,0.5)]" />
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">
                Recording in progress
              </span>
            </div>
          </div>

          {/* Precision Timer */}
          <div className="font-display-metrics text-display-metrics text-primary tabular-nums tracking-tighter mb-8">
            {formatTimer(recordingTime)}
            <span className="text-on-surface-variant text-[24px] ml-1">:45</span>
          </div>

          {/* Achromatic Waveform Visualizer */}
          <div className="relative w-full max-w-lg h-32 flex items-end justify-center gap-[2px] mb-16 overflow-hidden border-b border-outline-variant/50 pb-2">
            <div className="absolute bottom-2 left-0 w-full border-b border-outline-variant border-dashed opacity-30 z-0" />
            {bars.map((bar) => (
              <div
                key={bar.id}
                className={`w-[3px] rounded-t-[1px] wave-bar z-10 mix-blend-screen ${bar.colorClass}`}
                style={{
                  height: `${bar.baseHeight}%`,
                  animationDuration: `${bar.animDuration}s`,
                  animationDelay: `${bar.animDelay}s`,
                }}
              />
            ))}
          </div>

          {/* Stop Recording Action */}
          <button
            onClick={stopRecording}
            className="group flex items-center justify-center gap-3 bg-primary text-background font-label-sm text-label-sm uppercase tracking-widest font-semibold px-8 py-4 rounded-DEFAULT hover:bg-secondary transition-all duration-300 active:scale-95 shadow-[0_0_0_1px_rgba(255,255,255,0.1)] cursor-pointer"
          >
            <span
              className="material-symbols-outlined text-[18px] group-hover:scale-90 transition-transform"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              stop_circle
            </span>
            Stop recording
          </button>

          <div className="mt-6 font-mono text-mono-data text-outline-variant opacity-50">
            Input: Internal Microphone (Linear PCM)
          </div>
        </div>
      )}
    </div>
  );
}
