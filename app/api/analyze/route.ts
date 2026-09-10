import { NextResponse } from 'next/server';
import { AnalysisResult } from '@/types/analysis';

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB limit

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

    const apiKey = process.env.OPENAI_API_KEY;

    if (!apiKey) {
      console.error('OPENAI_API_KEY environment variable is not configured.');
      return NextResponse.json(
        { message: 'Speech analysis service is not configured. OPENAI_API_KEY environment variable is missing.' },
        { status: 500 }
      );
    }

    // --- Step 1: Speech-to-Text Transcription via OpenAI Whisper API ---
    const whisperFormData = new FormData();
    const filename = audioFile.name && audioFile.name.includes('.') ? audioFile.name : 'speech.webm';
    whisperFormData.append('file', audioFile, filename);
    whisperFormData.append('model', 'whisper-1');

    const whisperResponse = await fetch('https://api.openai.com/v1/audio/transcriptions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
      },
      body: whisperFormData,
    });

    if (!whisperResponse.ok) {
      const errorText = await whisperResponse.text();
      console.error('Whisper API Error:', errorText);
      return NextResponse.json(
        { message: 'Transcription service encountered an error processing your microphone recording.' },
        { status: 502 }
      );
    }

    const whisperData = await whisperResponse.json();
    const transcriptionText = (whisperData.text || '').trim();

    if (!transcriptionText) {
      return NextResponse.json(
        { message: 'Could not detect clear speech in the recording. Please speak clearly into your microphone and try again.' },
        { status: 422 }
      );
    }

    // --- Step 2: Objective Speech Metrics Calculation ---
    const words = transcriptionText.split(/\s+/).filter(Boolean);
    const wordCount = words.length;
    const estimatedDurationSeconds = Math.max(Math.round(audioFile.size / 16000), 5);
    const wordsPerMinute = Math.round((wordCount / estimatedDurationSeconds) * 60);

    const fillerWordMatches = transcriptionText.match(/\b(um|uh|like|you know|ah|er|hmm)\b/gi) || [];
    const fillerWordCount = fillerWordMatches.length;

    // --- Step 3: Structured Speech & Enunciation Analysis via OpenAI Chat Completions API ---
    const systemPrompt = `You are VoiceLens, an expert speech enunciation, clarity, enunciation, and fluency analyst.
Your task is to analyze transcribed English speech and evaluate enunciation, clarity, fluency, pacing, confidence, and linguistic patterns according to objective speech rubrics.

CRITICAL INSTRUCTION:
Do NOT guess, infer, or mention nationality, ethnicity, or regional identity.
Focus strictly on English phonetics, enunciation clarity, sentence rhythm, syntax, and delivery.

Speech Metadata:
- Transcribed Text: "${transcriptionText}"
- Word Count: ${wordCount} words
- Estimated Duration: ${estimatedDurationSeconds} seconds
- Calculated Words Per Minute: ${wordsPerMinute} WPM
- Detected Filler Words: ${fillerWordCount}`;

    const userPrompt = `Return JSON with this exact schema:
{
  "overallScore": number (1-100),
  "pronunciationScore": { "score": number (1-100), "label": "Pronunciation", "description": string, "status": "good"|"needs_improvement" },
  "clarityScore": { "score": number (1-100), "label": "Clarity", "description": string, "status": "good"|"needs_improvement" },
  "fluencyScore": { "score": number (1-100), "label": "Fluency", "description": string, "status": "good"|"needs_improvement" },
  "speechPace": { "wordsPerMinute": number, "category": "Slow"|"Optimal"|"Fast", "assessment": string },
  "confidenceDelivery": { "score": number (1-100), "pitchVariability": string, "pausesAssessment": string },
  "accentCharacteristics": [
    { "trait": string, "influence": string, "description": string, "confidence": number }
  ],
  "pronunciationIssues": [
    { "id": string, "word": string, "phoneticSpelling": string, "detectedPhonetic": string, "timestamp": string, "severity": "minor"|"moderate"|"major", "explanation": string, "tip": string }
  ],
  "improvementSuggestions": [
    { "id": string, "category": string, "title": string, "description": string, "actionableSteps": [string], "priority": "high"|"medium"|"low" }
  ]
}`;

    const chatResponse = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
        response_format: { type: 'json_object' },
        temperature: 0.3,
      }),
    });

    if (!chatResponse.ok) {
      const errorText = await chatResponse.text();
      console.error('Chat Completion API Error:', errorText);
      return NextResponse.json(
        { message: 'Speech analysis service encountered an error evaluating the transcript.' },
        { status: 502 }
      );
    }

    const chatData = await chatResponse.json();
    const content = chatData.choices?.[0]?.message?.content;
    const parsedAnalysis = JSON.parse(content);

    const fullResult: AnalysisResult = {
      id: `analysis_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
      timestamp: new Date().toISOString(),
      audioDurationSeconds: estimatedDurationSeconds,
      audioFileName: filename,
      transcription: transcriptionText,
      overallScore: parsedAnalysis.overallScore || 80,
      pronunciationScore: parsedAnalysis.pronunciationScore,
      clarityScore: parsedAnalysis.clarityScore,
      fluencyScore: parsedAnalysis.fluencyScore,
      speechPace: {
        wordsPerMinute: wordsPerMinute,
        category: parsedAnalysis.speechPace?.category || (wordsPerMinute > 160 ? 'Fast' : wordsPerMinute < 110 ? 'Slow' : 'Optimal'),
        assessment: parsedAnalysis.speechPace?.assessment || `Speaking rate measured at ${wordsPerMinute} WPM.`,
      },
      confidenceDelivery: parsedAnalysis.confidenceDelivery,
      accentCharacteristics: parsedAnalysis.accentCharacteristics || [],
      pronunciationIssues: parsedAnalysis.pronunciationIssues || [],
      improvementSuggestions: parsedAnalysis.improvementSuggestions || [],
    };

    return NextResponse.json(fullResult, { status: 200 });
  } catch (error) {
    console.error('API Error in /api/analyze:', error);
    return NextResponse.json(
      { message: 'An unexpected error occurred while processing the voice analysis request.' },
      { status: 500 }
    );
  }
}
