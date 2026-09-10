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

    const groqApiKey = process.env.GROQ_API_KEY;
    const geminiApiKey = process.env.GEMINI_API_KEY;

    if (!groqApiKey || !geminiApiKey) {
      console.error('Missing required API keys: GROQ_API_KEY or GEMINI_API_KEY is not configured.');
      return NextResponse.json(
        { message: 'Speech analysis service is not configured. GROQ_API_KEY and GEMINI_API_KEY environment variables are required.' },
        { status: 500 }
      );
    }

    // --- Step 1: Free-Tier Speech-to-Text Transcription via Groq Whisper API (whisper-large-v3) ---
    const groqFormData = new FormData();
    const filename = audioFile.name && audioFile.name.includes('.') ? audioFile.name : 'speech.webm';
    groqFormData.append('file', audioFile, filename);
    groqFormData.append('model', 'whisper-large-v3');

    const groqResponse = await fetch('https://api.groq.com/openai/v1/audio/transcriptions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${groqApiKey}`,
      },
      body: groqFormData,
    });

    if (!groqResponse.ok) {
      const errorText = await groqResponse.text();
      console.error('Groq Whisper API Error:', errorText);
      return NextResponse.json(
        { message: 'Transcription service (Groq Whisper) encountered an error processing your recording.' },
        { status: 502 }
      );
    }

    const groqData = await groqResponse.json();
    const transcriptionText = (groqData.text || '').trim();

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

    // --- Step 3: Free-Tier Structured Speech Analysis via Google Gemini API (gemini-1.5-flash) ---
    const systemInstruction = `You are VoiceLens, an expert speech enunciation, clarity, enunciation, and fluency analyst.
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

    const promptText = `${systemInstruction}

Return JSON with this exact schema:
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

    const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${geminiApiKey}`;

    const geminiResponse = await fetch(geminiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        contents: [
          {
            parts: [{ text: promptText }],
          },
        ],
        generationConfig: {
          responseMimeType: 'application/json',
          temperature: 0.3,
        },
      }),
    });

    if (!geminiResponse.ok) {
      const errorText = await geminiResponse.text();
      console.error('Gemini API Error:', errorText);
      return NextResponse.json(
        { message: 'Speech analysis service (Gemini) encountered an error evaluating the transcript.' },
        { status: 502 }
      );
    }

    const geminiData = await geminiResponse.json();
    const responseText = geminiData.candidates?.[0]?.content?.parts?.[0]?.text;

    if (!responseText) {
      return NextResponse.json(
        { message: 'Received empty response from speech analysis service.' },
        { status: 502 }
      );
    }

    const parsedAnalysis = JSON.parse(responseText);

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
