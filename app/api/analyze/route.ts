import { NextResponse } from 'next/server';
import { AnalysisResult } from '@/types/analysis';

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB limit
const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000';

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const audioFile = formData.get('audio') as File | null;

    if (!audioFile) {
      return NextResponse.json(
        { message: 'No audio recording received. Please record your speech.' },
        { status: 400 }
      );
    }

    if (audioFile.size === 0) {
      return NextResponse.json(
        { message: 'Audio recording appears to be empty. Please speak into your microphone and try again.' },
        { status: 400 }
      );
    }

    if (audioFile.size > MAX_FILE_SIZE) {
      return NextResponse.json(
        { message: 'Audio recording exceeds maximum allowed duration.' },
        { status: 400 }
      );
    }

    // Support configurable online/local VoiceLens FastAPI backend URL
    const backendBaseUrl =
      process.env.VOICELENS_API_URL ||
      process.env.NEXT_PUBLIC_VOICELENS_API_URL ||
      DEFAULT_BACKEND_URL;

    const backendEndpoint = `${backendBaseUrl.replace(/\/$/, '')}/api/analyze`;

    // Forward recorded audio file to VoiceLens FastAPI engine (run_voicelens_pipeline)
    const backendFormData = new FormData();
    const filename = audioFile.name && audioFile.name.includes('.') ? audioFile.name : 'speech.webm';
    backendFormData.append('file', audioFile, filename);

    let backendResponse: Response;
    try {
      backendResponse = await fetch(backendEndpoint, {
        method: 'POST',
        body: backendFormData,
      });
    } catch (connectionError) {
      console.error(`VoiceLens backend connection error (${backendEndpoint}):`, connectionError);
      return NextResponse.json(
        { message: 'VoiceLens analysis engine is offline. Start the local VoiceLens backend and try again.' },
        { status: 503 }
      );
    }

    if (!backendResponse.ok) {
      const errorText = await backendResponse.text().catch(() => '');
      console.error(`VoiceLens backend error (${backendResponse.status}):`, errorText);
      return NextResponse.json(
        { message: 'VoiceLens analysis engine encountered an error processing your recording.' },
        { status: backendResponse.status >= 500 ? 502 : backendResponse.status }
      );
    }

    const rawData = await backendResponse.json();

    // Map Python run_voicelens_pipeline JSON schema to frontend AnalysisResult contract
    const mappedResult: AnalysisResult = {
      id: rawData.id || `analysis_${Date.now()}`,
      timestamp: rawData.createdAt || new Date().toISOString(),
      audioDurationSeconds: Math.round(rawData.audioDurationSeconds || rawData.metrics?.duration_seconds || 15),
      audioFileName: filename,
      transcription: rawData.transcript?.text || '',

      overallScore: Math.round(rawData.pronunciation?.overallScore || 0),

      pronunciationScore: {
        score: Math.round((rawData.pronunciation?.pronunciationSimilarity || 0) * 100),
        label: 'Pronunciation',
        description: rawData.pronunciation?.notes?.[0] || 'Phonetic acoustic similarity evaluation.',
        status: (rawData.pronunciation?.overallScore || 0) >= 75 ? 'good' : 'needs_improvement',
      },

      clarityScore: {
        score: Math.round((rawData.pronunciation?.confidence || 0) * 100),
        label: 'Clarity',
        description: 'Acoustic enunciation clarity and phoneme alignment confidence.',
        status: (rawData.pronunciation?.confidence || 0) >= 0.75 ? 'good' : 'needs_improvement',
      },

      fluencyScore: {
        score: Math.round(
          Math.max(
            0,
            100 -
              (rawData.metrics?.pause_count || 0) * 5 -
              (rawData.metrics?.filler_word_count || 0) * 8
          )
        ),
        label: 'Fluency',
        description: `Fluency calculated from ${rawData.metrics?.pause_count || 0} pauses and ${rawData.metrics?.filler_word_count || 0} filler words.`,
        status: (rawData.metrics?.filler_word_count || 0) <= 2 ? 'good' : 'needs_improvement',
      },

      speechPace: {
        wordsPerMinute: Math.round(rawData.metrics?.words_per_minute || 0),
        category:
          (rawData.metrics?.words_per_minute || 0) > 160
            ? 'Fast'
            : (rawData.metrics?.words_per_minute || 0) < 110
            ? 'Slow'
            : 'Optimal',
        assessment: `Speaking rate measured at ${Math.round(rawData.metrics?.words_per_minute || 0)} WPM over ${rawData.metrics?.word_count || 0} words.`,
      },

      confidenceDelivery: {
        score: Math.round((rawData.accent?.confidence || 0) * 100),
        pitchVariability: `Accent Classification Match: ${rawData.accent?.predictedAccent || 'Neutral'}`,
        pausesAssessment: `Average pause duration: ${Number(rawData.metrics?.average_pause_duration || 0).toFixed(1)}s (Longest: ${Number(rawData.metrics?.longest_pause || 0).toFixed(1)}s)`,
      },

      accentCharacteristics: (rawData.accent?.top3Accents || []).map((acc: { accent: string; confidence: number }) => ({
        trait: acc.accent,
        influence: 'VoiceLens Accent Classifier',
        description: `Similarity confidence score: ${Math.round(acc.confidence * 100)}%`,
        confidence: Math.round(acc.confidence * 100),
      })),

      pronunciationIssues: (rawData.difficultWordsList || []).map((word: { word: string; score: number; confidence: number; start_time?: number }, idx: number) => ({
        id: `issue_${idx}`,
        word: word.word,
        phoneticSpelling: '/target/',
        detectedPhonetic: '/detected/',
        timestamp: word.start_time ? `00:${Math.floor(word.start_time).toString().padStart(2, '0')}` : undefined,
        severity: word.score < 0.5 ? 'major' : 'moderate',
        explanation: `Sub-optimal enunciation alignment score: ${Math.round(word.score * 100)}%`,
        tip: `Enunciate ${word.word} clearly with distinct vowel closure and sustained airflow.`,
      })),

      improvementSuggestions: (rawData.overallFeedback || []).map((fb: string, idx: number) => ({
        id: `sug_${idx}`,
        category: 'Speech Delivery',
        title: fb.split(':')[0]?.replace(/^[•\s]+/, '') || 'Feedback',
        description: fb.replace(/^[•\s]+/, ''),
        actionableSteps: [fb.replace(/^[•\s]+/, '')],
        priority: idx === 0 ? 'high' : idx === 1 ? 'medium' : 'low',
      })),
    };

    return NextResponse.json(mappedResult, { status: 200 });
  } catch (error) {
    console.error('API Error in /api/analyze:', error);
    return NextResponse.json(
      { message: 'An unexpected error occurred while processing the voice analysis request.' },
      { status: 500 }
    );
  }
}
