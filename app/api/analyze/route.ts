import { NextResponse } from 'next/server';

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB limit
const DEFAULT_LOCAL_BACKEND = 'http://127.0.0.1:8000';

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

    const backendBaseUrl = process.env.NEXT_PUBLIC_VOICELENS_API_URL || DEFAULT_LOCAL_BACKEND;
    const backendEndpoint = `${backendBaseUrl.replace(/\/$/, '')}/api/analyze`;

    // Forward the recorded audio file to local FastAPI VoiceLens backend
    const backendFormData = new FormData();
    const filename = audioFile.name && audioFile.name.includes('.') ? audioFile.name : 'speech.webm';
    backendFormData.append('audio', audioFile, filename);

    let backendResponse: Response;
    try {
      backendResponse = await fetch(backendEndpoint, {
        method: 'POST',
        body: backendFormData,
      });
    } catch (connectionError) {
      console.error('Local VoiceLens backend connection error:', connectionError);
      return NextResponse.json(
        { message: 'VoiceLens analysis engine is offline. Start the local VoiceLens backend and try again.' },
        { status: 503 }
      );
    }

    if (!backendResponse.ok) {
      const errorText = await backendResponse.text().catch(() => '');
      console.error(`Local backend error (${backendResponse.status}):`, errorText);
      return NextResponse.json(
        { message: 'VoiceLens local analysis backend encountered an error processing your recording.' },
        { status: backendResponse.status >= 500 ? 502 : backendResponse.status }
      );
    }

    const analysisData = await backendResponse.json();
    return NextResponse.json(analysisData, { status: 200 });
  } catch (error) {
    console.error('API Error in /api/analyze:', error);
    return NextResponse.json(
      { message: 'An unexpected error occurred while processing the voice analysis request.' },
      { status: 500 }
    );
  }
}
