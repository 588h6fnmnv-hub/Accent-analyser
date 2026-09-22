/**
 * VoiceLens API Client
 * Connects the frontend to the FastAPI backend
 */

export interface Transcript {
  text: string;
  language: string;
  wordCount: number;
}

export interface Accent {
  predictedAccent: string;
  confidence: number;
  top3Accents: Array<{ accent: string; confidence: number }>;
  notes: string[];
}

export interface Pronunciation {
  overallScore: number;
  pronunciationSimilarity: number;
  confidence: number;
  backend: string;
  notes: string[];
}

export interface Metrics {
  durationSeconds: number;
  wordCount: number;
  wordsPerMinute: number;
  pauseCount: number;
  averagePauseDuration: number;
  longestPause: number;
  fillerWordCount: number;
  fillerWords: string[];
  repeatedWordCount: number;
  repeatedWords: string[];
  fluencyScore: number;
  confidenceScore: number;
  syllableCount: number;
  averageSyllablesPerWord: number;
  sentenceCount: number;
  averageWordsPerSentence: number;
}

export interface FillerWordItem {
  word: string;
  count: number;
}

export interface RepeatedWordItem {
  word: string;
  count: number;
}

export interface DifficultWord {
  word: string;
  confidence: number;
  score: number;
  startTime: number;
  endTime: number;
}

export interface AnalysisResult {
  id: string;
  createdAt: string;
  audioDurationSeconds: number;
  transcript: Transcript;
  accent: Accent;
  pronunciation: Pronunciation;
  metrics: Metrics;
  fillerWordsList: FillerWordItem[];
  repeatedWordsList: RepeatedWordItem[];
  difficultWordsList: DifficultWord[];
  overallFeedback: string[];
}

export interface HealthCheck {
  status: string;
  service: string;
  version: string;
}

export interface ApiError {
  detail: string;
}

export type AnalysisErrorCode =
  | 'NETWORK_ERROR'
  | 'TIMEOUT'
  | 'EMPTY_RECORDING'
  | 'UNSUPPORTED_FORMAT'
  | 'TRANSCRIPTION_FAILED'
  | 'ANALYSIS_FAILED'
  | 'BACKEND_UNAVAILABLE'
  | 'UNKNOWN_ERROR';

export class VoiceLensApiError extends Error {
  public readonly code: AnalysisErrorCode;
  public readonly status?: number;
  public readonly originalError?: Error;

  constructor(code: AnalysisErrorCode, message: string, status?: number, originalError?: Error) {
    super(message);
    this.name = 'VoiceLensApiError';
    this.code = code;
    this.status = status;
    this.originalError = originalError;
  }
}

const DEFAULT_API_URL = 'http://127.0.0.1:8000';

function getApiUrl(): string {
  if (typeof window !== 'undefined') {
    return process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL;
  }
  return process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL;
}

class VoiceLensApiClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || getApiUrl();
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let detail: string;
      try {
        const error: ApiError = await response.json();
        detail = error.detail || `Request failed: ${response.status}`;
      } catch {
        detail = `Request failed: ${response.status}`;
      }

      let code: AnalysisErrorCode = 'UNKNOWN_ERROR';
      if (response.status === 400) {
        if (detail.toLowerCase().includes('empty')) code = 'EMPTY_RECORDING';
        else if (detail.toLowerCase().includes('unsupported') || detail.toLowerCase().includes('format')) code = 'UNSUPPORTED_FORMAT';
        else code = 'ANALYSIS_FAILED';
      } else if (response.status === 422) {
        if (detail.toLowerCase().includes('transcription')) code = 'TRANSCRIPTION_FAILED';
        else code = 'ANALYSIS_FAILED';
      } else if (response.status >= 500) {
        code = 'BACKEND_UNAVAILABLE';
      }

      throw new VoiceLensApiError(code, detail, response.status);
    }

    return response.json();
  }

  async healthCheck(): Promise<HealthCheck> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(`${this.baseUrl}/api/health`, {
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      return this.handleResponse<HealthCheck>(response);
    } catch (error) {
      if (error instanceof VoiceLensApiError) throw error;
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new VoiceLensApiError('TIMEOUT', 'Health check timed out');
      }
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new VoiceLensApiError('NETWORK_ERROR', 'Cannot connect to backend. Check your internet connection.');
      }
      throw new VoiceLensApiError('UNKNOWN_ERROR', error instanceof Error ? error.message : 'Health check failed');
    }
  }

  async analyzeAudio(
    audioBlob: Blob,
    filename: string = 'recording.webm',
    options?: { signal?: AbortSignal }
  ): Promise<AnalysisResult> {
    if (audioBlob.size === 0) {
      throw new VoiceLensApiError('EMPTY_RECORDING', 'Recording is empty. Please record some audio first.');
    }

    const formData = new FormData();
    formData.append('file', audioBlob, filename);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000);

      const response = await fetch(`${this.baseUrl}/api/analyze`, {
        method: 'POST',
        body: formData,
        signal: options?.signal || controller.signal,
      });

      clearTimeout(timeoutId);
      return this.handleResponse<AnalysisResult>(response);
    } catch (error) {
      if (error instanceof VoiceLensApiError) throw error;
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new VoiceLensApiError('TIMEOUT', 'Analysis timed out. The server took too long to respond.');
      }
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new VoiceLensApiError('NETWORK_ERROR', 'Network error. Please check your connection and try again.');
      }
      throw new VoiceLensApiError('UNKNOWN_ERROR', error instanceof Error ? error.message : 'Analysis failed');
    }
  }

  setBaseUrl(url: string): void {
    this.baseUrl = url;
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }
}

export const apiClient = new VoiceLensApiClient();

export async function checkBackendHealth(): Promise<boolean> {
  try {
    await apiClient.healthCheck();
    return true;
  } catch {
    return false;
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof VoiceLensApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
}

export function getErrorCode(error: unknown): AnalysisErrorCode {
  if (error instanceof VoiceLensApiError) {
    return error.code;
  }
  return 'UNKNOWN_ERROR';
}