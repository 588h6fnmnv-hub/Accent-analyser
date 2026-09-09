export type AudioStatus =
  | 'idle'
  | 'recording'
  | 'recorded'
  | 'uploading'
  | 'analysing'
  | 'completed'
  | 'error';

export interface AudioRecordingState {
  status: AudioStatus;
  durationSeconds: number;
  audioBlob: Blob | null;
  audioUrl: string | null;
  file: File | null;
  error: string | null;
}

export interface AudioValidationOptions {
  maxSizeMB?: number;
  allowedFormats?: string[];
}

export const DEFAULT_AUDIO_VALIDATION: AudioValidationOptions = {
  maxSizeMB: 25,
  allowedFormats: [
    'audio/wav',
    'audio/wave',
    'audio/mp3',
    'audio/mpeg',
    'audio/m4a',
    'audio/mp4',
    'audio/webm',
    'audio/ogg',
    'audio/aac',
    'audio/x-m4a',
  ],
};
