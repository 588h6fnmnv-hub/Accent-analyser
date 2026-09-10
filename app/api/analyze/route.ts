import { NextResponse } from 'next/server';
import { AnalysisResult } from '@/types/analysis';

// Maximum audio file size (25MB)
const MAX_FILE_SIZE = 25 * 1024 * 1024;

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

    if (audioFile.size > MAX_FILE_SIZE) {
      return NextResponse.json(
        { message: 'Audio recording exceeds maximum allowed duration.' },
        { status: 400 }
      );
    }

    if (audioFile.size === 0) {
      return NextResponse.json(
        { message: 'Audio recording appears to be empty. Please speak again.' },
        { status: 400 }
      );
    }

    // Simulate analysis processing time
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // Generate realistic demonstration mock analysis results
    const mockResult: AnalysisResult = {
      id: `analysis_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
      timestamp: new Date().toISOString(),
      audioDurationSeconds: Math.min(Math.max(Math.round(audioFile.size / 16000), 5), 120),
      audioFileName: audioFile.name || 'recorded_speech.webm',
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

    return NextResponse.json(mockResult, { status: 200 });
  } catch (error) {
    console.error('API Error in /api/analyze:', error);
    return NextResponse.json(
      { message: 'An error occurred while processing the voice analysis request.' },
      { status: 500 }
    );
  }
}
