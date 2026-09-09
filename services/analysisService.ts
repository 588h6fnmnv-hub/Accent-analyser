import { AnalysisResult } from '@/types/analysis';

export interface AnalysisService {
  analyzeAudio(audioBlobOrFile: Blob | File, filename?: string): Promise<AnalysisResult>;
}

export class ApiAnalysisService implements AnalysisService {
  private apiEndpoint: string;

  constructor(apiEndpoint = '/api/analyze') {
    this.apiEndpoint = apiEndpoint;
  }

  async analyzeAudio(audioBlobOrFile: Blob | File, filename?: string): Promise<AnalysisResult> {
    const formData = new FormData();
    const fileToUpload = audioBlobOrFile instanceof File
      ? audioBlobOrFile
      : new File([audioBlobOrFile], filename || 'recording.webm', { type: audioBlobOrFile.type || 'audio/webm' });

    formData.append('audio', fileToUpload);

    try {
      const response = await fetch(this.apiEndpoint, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `Analysis failed with status ${response.status}`);
      }

      const result: AnalysisResult = await response.json();
      return result;
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('An unexpected error occurred during analysis.');
    }
  }
}

// Default singleton instance
export const analysisService = new ApiAnalysisService();
