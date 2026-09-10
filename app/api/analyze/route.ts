import { NextResponse } from 'next/server';
import { AnalysisResult } from '@/types/analysis';

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const audioFile = formData.get('audio') as File | null;

    if (!audioFile) {
      return NextResponse.json(
        { message: 'No audio recording provided. Please record your speech.' },
        { status: 400 }
      );
    }

    if (audioFile.size === 0) {
      return NextResponse.json(
        { message: 'Audio recording appears to be empty. Please speak again.' },
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
    const forceMock = process.env.USE_MOCK_ANALYSIS === 'true';

    // If no OpenAI API key is present or USE_MOCK_ANALYSIS is true, return structured mock result
    if (!apiKey || forceMock) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      return NextResponse.json(getMockAnalysisResult(audioFile.size, audioFile.name), { status: 200 });
    }

    // --- Step 1: Real Transcription via OpenAI Whisper API ---
    const whisperFormData = new FormData();
    // Rename blob to an allowed extension if needed
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
        { message: 'Transcription service encountered an error processing your audio.' },
        { status: 502 }
      );
    }

    const whisperData = await whisperResponse.json();
    const transcriptionText = (whisperData.text || '').trim();

    if (!transcriptionText) {
      return NextResponse.json(
        { message: 'Could not detect clear speech in the recording. Please speak clearly and try again.' },
        { status: 422 }
      );
    }

    // --- Step 2: Objective Speech Metrics Calculation ---
    const words = transcriptionText.split(/\s+/).filter(Boolean);
    const wordCount = words.length;
    // Estimated audio duration based on file size or default 15s
    const estimatedDurationSeconds = Math.max(Math.round(audioFile.size / 16000), 5);
    const wordsPerMinute = Math.round((wordCount / estimatedDurationSeconds) * 60);

    const fillerWordMatches = transcriptionText.match(/\b(um|uh|like|you know|ah|er|hmm)\b/gi) || [];
    const fillerWordCount = fillerWordMatches.length;

    // --- Step 3: Structured Speech Analysis via OpenAI Chat Completions API ---
    const systemPrompt = `You are VoiceLens, an expert speech enunciation, clarity, and accent analyst.
Your task is to analyze transcribed English speech and evaluate enunciation, clarity, fluency, pacing, confidence, and linguistic patterns according to objective rubrics.

CRITICAL INSTRUCTIONS:
1. Do NOT identify or guess nationality, ethnicity, or regional origin.
2. Focus strictly on English phonetics, enunciation, syntax, rhythm, and clarity.
3. Return ONLY a valid JSON object matching the requested schema. No markdown formatting.

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
      isMock: false,
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

function getMockAnalysisResult(fileSize: number, fileName?: string): AnalysisResult {
  return {
    id: `analysis_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
    timestamp: new Date().toISOString(),
    audioDurationSeconds: Math.min(Math.max(Math.round(fileSize / 16000), 5), 120),
    audioFileName: fileName || 'recorded_speech.webm',
    isMock: true,
    overallScore: 82,
    pronunciationScore: {
      score: 86,
      label: 'Pronunciation',
      description: 'Vowel clarity and consonant articulation are strong, with slight non-native phoneme shifts.',
      status: 'good',
    },
    clarityScore: {
      score: 84,
      label: 'Clarity',
      description: 'Enunciation is distinct and easy to understand for international listeners.',
      status: 'good',
    },
    fluencyScore: {
      score: 78,
      label: 'Fluency',
      description: 'Speech is generally smooth, though occasional pauses occur before complex vocabulary.',
      status: 'needs_improvement',
    },
    speechPace: {
      wordsPerMinute: 135,
      category: 'Optimal',
      assessment: 'Your speaking pace is natural and comfortable (130-150 WPM target range).',
    },
    confidenceDelivery: {
      score: 80,
      pitchVariability: 'Natural pitch variation with good sentence emphasis.',
      pausesAssessment: 'Pauses occur mostly at natural punctuation and sentence boundaries.',
    },
    accentCharacteristics: [
      {
        trait: 'Neutral / Soft Euro-American Vowels',
        influence: 'North American influence with mild vowel reduction',
        description: 'Open vowels like /æ/ in "cat" are well-articulated. Short vowels tend to be slightly raised.',
        confidence: 88,
      },
      {
        trait: 'Dental Consonants Articulation',
        influence: 'Mild non-native dentalization',
        description: 'The "th" sound (/θ/ and /ð/) is occasionally substituted with /t/ or /d/.',
        confidence: 76,
      },
      {
        trait: 'Rhotic R Pronunciation',
        influence: 'General American / Rhotic',
        description: 'Post-vocalic /r/ sounds are pronounced clearly and consistently.',
        confidence: 82,
      },
    ],
    pronunciationIssues: [
      {
        id: 'p1',
        word: 'Thinking',
        phoneticSpelling: '/ˈθɪŋ.kɪŋ/',
        detectedPhonetic: '/ˈtɪŋ.kɪŋ/',
        timestamp: '00:03',
        severity: 'moderate',
        explanation: 'The voiceless dental fricative "th" (/θ/) was pronounced closer to a hard "t" (/t/).',
        tip: 'Place the tip of your tongue gently between your front teeth and blow air lightly through.',
      },
      {
        id: 'p2',
        word: 'Schedule',
        phoneticSpelling: '/ˈskedʒ.uːl/',
        detectedPhonetic: '/ˈʃed.uːl/',
        timestamp: '00:12',
        severity: 'minor',
        explanation: 'Mixed British ("sked-") and American ("shed-") phonetic patterns observed.',
        tip: 'Consistency in American or British conventions helps enhance clarity in formal speech.',
      },
      {
        id: 'p3',
        word: 'World',
        phoneticSpelling: '/wɜːld/',
        detectedPhonetic: '/wɔːld/',
        timestamp: '00:19',
        severity: 'minor',
        explanation: 'Vowel sound was slightly shortened before the dark /l/ consonant.',
        tip: 'Sustain the central vowel /ɜː/ slightly longer before transitioning to the /ld/ cluster.',
      },
    ],
    improvementSuggestions: [
      {
        id: 's1',
        category: 'Pronunciation',
        title: 'Master the "TH" Fricative Sounds (/θ/ and /ð/)',
        description: 'Practice contrasting words like "think vs tink" and "there vs dare" in front of a mirror.',
        actionableSteps: [
          'Lightly rest your tongue tip between top and bottom front teeth.',
          'Practice continuous airflow without stopping the sound into a /t/.',
          'Record 5 sentences starting with "I think..." and check tongue placement.',
        ],
        priority: 'high',
      },
      {
        id: 's2',
        category: 'Fluency',
        title: 'Reduce Hesitation Before Complex Technical Terms',
        description: 'Use continuous breathing to connect words together without micro-pauses.',
        actionableSteps: [
          'Practice reading technical passages out loud using speech shadowing technique.',
          'Maintain steady exhale through multi-syllable words.',
        ],
        priority: 'medium',
      },
      {
        id: 's3',
        category: 'Intonation',
        title: 'Vary Sentence Pitch at Key Stress Points',
        description: 'Elevate pitch slightly on keywords to sound even more engaging and confident.',
        actionableSteps: [
          'Identify the most important noun or verb in each sentence.',
          'Apply slight pitch peak on that key stressed syllable.',
        ],
        priority: 'low',
      },
    ],
    transcription:
      'Thank you for using VoiceLens. I am testing my speech clarity, pronunciation, and speaking pace in this voice recording session.',
  };
}
