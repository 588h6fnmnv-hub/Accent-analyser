/**
 * Audio recording utilities for VoiceLens
 * Uses MediaRecorder API for browser microphone recording
 */

'use client';

import { useRef, useCallback } from 'react';

export type RecordingState = 'idle' | 'recording' | 'paused' | 'stopped';

export interface AudioRecorderOptions {
  mimeType?: string;
  audioBitsPerSecond?: number;
  onDataAvailable?: (blob: Blob) => void;
  onStop?: (blob: Blob) => void;
  onError?: (error: AudioRecorderError) => void;
}

export type AudioRecorderErrorCode =
  | 'PERMISSION_DENIED'
  | 'DEVICE_NOT_FOUND'
  | 'CONSTRAINT_NOT_SATISFIED'
  | 'NOT_SUPPORTED'
  | 'SECURITY_ERROR'
  | 'ABORT_ERROR'
  | 'UNKNOWN_ERROR';

export class AudioRecorderError extends Error {
  public readonly code: AudioRecorderErrorCode;
  public readonly originalError?: Error;

  constructor(code: AudioRecorderErrorCode, message: string, originalError?: Error) {
    super(message);
    this.name = 'AudioRecorderError';
    this.code = code;
    this.originalError = originalError;
  }
}

function getSupportedMimeType(): string {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/ogg',
    'audio/mp4',
    'audio/wav',
  ];

  if (typeof MediaRecorder === 'undefined') {
    return types[0];
  }

  for (const type of types) {
    if (MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return types[0];
}

function mapDOMExceptionToError(error: DOMException): AudioRecorderError {
  switch (error.name) {
    case 'NotAllowedError':
    case 'PermissionDeniedError':
      return new AudioRecorderError(
        'PERMISSION_DENIED',
        'Microphone access was denied. Please allow microphone access in your browser settings and try again.',
        error
      );
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return new AudioRecorderError(
        'DEVICE_NOT_FOUND',
        'No microphone found. Please connect a microphone and try again.',
        error
      );
    case 'ConstraintNotSatisfiedError':
    case 'OverconstrainedError':
      return new AudioRecorderError(
        'CONSTRAINT_NOT_SATISFIED',
        'Microphone constraints could not be satisfied. Try using a different browser or device.',
        error
      );
    case 'NotSupportedError':
      return new AudioRecorderError(
        'NOT_SUPPORTED',
        'Audio recording is not supported in this browser. Please use a modern browser like Chrome, Firefox, or Safari.',
        error
      );
    case 'SecurityError':
      return new AudioRecorderError(
        'SECURITY_ERROR',
        'Recording was blocked due to security restrictions. Ensure you are on HTTPS or localhost.',
        error
      );
    case 'AbortError':
      return new AudioRecorderError(
        'ABORT_ERROR',
        'Recording was aborted.',
        error
      );
    default:
      return new AudioRecorderError(
        'UNKNOWN_ERROR',
        `Recording error: ${error.message}`,
        error
      );
  }
}

export function useAudioRecorder(options: AudioRecorderOptions = {}) {
  const mimeType = options.mimeType || getSupportedMimeType();
  const audioBitsPerSecond = options.audioBitsPerSecond || 128000;

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const stateRef = useRef<RecordingState>('idle');

  const isMediaRecorderSupported = useCallback((): boolean => {
    return typeof MediaRecorder !== 'undefined' && typeof navigator !== 'undefined' && typeof navigator.mediaDevices !== 'undefined';
  }, []);

  const start = useCallback(async (): Promise<void> => {
    if (stateRef.current === 'recording') return;

    if (!isMediaRecorderSupported()) {
      const error = new AudioRecorderError(
        'NOT_SUPPORTED',
        'MediaRecorder is not supported in this browser. Please use a modern browser like Chrome, Firefox, or Safari.'
      );
      options.onError?.(error);
      throw error;
    }

    if (typeof window === 'undefined') {
      const error = new AudioRecorderError(
        'UNKNOWN_ERROR',
        'Window object not available'
      );
      options.onError?.(error);
      throw error;
    }

    if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      const error = new AudioRecorderError(
        'SECURITY_ERROR',
        'Microphone access requires HTTPS. Please deploy to HTTPS or use localhost.'
      );
      options.onError?.(error);
      throw error;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
      });

      streamRef.current = stream;

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType,
        audioBitsPerSecond,
      });

      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
          options.onDataAvailable?.(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        options.onStop?.(blob);
        stateRef.current = 'stopped';
      };

      mediaRecorder.onerror = (event: Event & { error?: DOMException }) => {
        const error = event.error
          ? mapDOMExceptionToError(event.error)
          : new AudioRecorderError('UNKNOWN_ERROR', 'MediaRecorder error: unknown');
        options.onError?.(error);
        stateRef.current = 'idle';
      };

      mediaRecorder.start(100);
      stateRef.current = 'recording';
    } catch (error) {
      stateRef.current = 'idle';
      if (error instanceof DOMException) {
        const mappedError = mapDOMExceptionToError(error);
        options.onError?.(mappedError);
        throw mappedError;
      }
      if (error instanceof AudioRecorderError) {
        options.onError?.(error);
        throw error;
      }
      const unknownError = new AudioRecorderError(
        'UNKNOWN_ERROR',
        error instanceof Error ? error.message : 'Failed to start recording',
        error instanceof Error ? error : undefined
      );
      options.onError?.(unknownError);
      throw unknownError;
    }
  }, [isMediaRecorderSupported, mimeType, audioBitsPerSecond, options]);

  const stop = useCallback((): Promise<Blob> => {
    return new Promise((resolve, reject) => {
      const mediaRecorder = mediaRecorderRef.current;
      if (!mediaRecorder || stateRef.current !== 'recording') {
        const error = new AudioRecorderError('UNKNOWN_ERROR', 'Not recording');
        reject(error);
        return;
      }

      const originalOnStop = mediaRecorder.onstop;
      mediaRecorder.onstop = (event: Event) => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        if (originalOnStop) {
          originalOnStop.call(mediaRecorder, event);
        }
        resolve(blob);
      };

      mediaRecorder.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      stateRef.current = 'idle';
    });
  }, [mimeType]);

  const pause = useCallback((): void => {
    const mediaRecorder = mediaRecorderRef.current;
    if (mediaRecorder && stateRef.current === 'recording') {
      mediaRecorder.pause();
      stateRef.current = 'paused';
    }
  }, []);

  const resume = useCallback((): void => {
    const mediaRecorder = mediaRecorderRef.current;
    if (mediaRecorder && stateRef.current === 'paused') {
      mediaRecorder.resume();
      stateRef.current = 'recording';
    }
  }, []);

  const getState = useCallback((): RecordingState => stateRef.current, []);

  const isRecording = useCallback((): boolean => stateRef.current === 'recording', []);

  const isSupported = useCallback((): boolean => isMediaRecorderSupported(), [isMediaRecorderSupported]);

  const cleanup = useCallback((): void => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    mediaRecorderRef.current = null;
    chunksRef.current = [];
    stateRef.current = 'idle';
  }, []);

  return {
    start,
    stop,
    pause,
    resume,
    getState,
    isRecording,
    isSupported,
    cleanup,
    mimeType,
  };
}

export function createAudioBlob(chunks: Blob[], mimeType: string = getSupportedMimeType()): Blob {
  return new Blob(chunks, { type: mimeType });
}

export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function isAudioRecorderSupported(): boolean {
  return typeof MediaRecorder !== 'undefined' && typeof navigator !== 'undefined' && typeof navigator.mediaDevices !== 'undefined';
}

export function getBrowserSupportInfo(): { supported: boolean; reason?: string } {
  if (typeof MediaRecorder === 'undefined') {
    return { supported: false, reason: 'MediaRecorder API not available' };
  }
  if (typeof navigator === 'undefined' || typeof navigator.mediaDevices === 'undefined') {
    return { supported: false, reason: 'MediaDevices API not available' };
  }
  if (typeof window !== 'undefined' && window.location.protocol !== 'https:' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    return { supported: false, reason: 'Requires HTTPS or localhost' };
  }
  return { supported: true };
}