import Link from 'next/link';
import { Mic, Upload, Sparkles, Volume2, Target, TrendingUp, ShieldCheck, ArrowRight } from 'lucide-react';

export default function Home() {
  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)]">
      {/* Hero Section */}
      <section className="relative py-20 md:py-28 px-4 overflow-hidden bg-gradient-to-b from-slate-900 via-slate-950 to-slate-950 border-b border-slate-800">
        <div className="max-w-5xl mx-auto text-center space-y-8">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-950/80 border border-indigo-800/60 text-indigo-300 text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>AI-Powered Speech Evaluation</span>
          </div>

          <h1 className="text-4xl sm:text-6xl font-extrabold text-white tracking-tight leading-tight">
            Analyse Your English Accent & <br className="hidden sm:inline" />
            <span className="bg-gradient-to-r from-indigo-400 via-indigo-200 to-indigo-500 bg-clip-text text-transparent">
              Elevate Your Speech Clarity
            </span>
          </h1>

          <p className="max-w-2xl mx-auto text-lg text-slate-300 leading-relaxed">
            Record your voice or upload audio to receive instant feedback on your pronunciation, speaking pace, clarity, and accent characteristics.
          </p>

          {/* Primary & Secondary Call To Actions */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <Link
              href="/analyse?mode=record"
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-8 py-4 text-base font-semibold rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 transition-all shadow-lg hover:shadow-indigo-500/25"
            >
              <Mic className="w-5 h-5" />
              <span>Analyse My Voice</span>
            </Link>

            <Link
              href="/analyse?mode=upload"
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-8 py-4 text-base font-semibold rounded-xl bg-slate-800/90 text-slate-200 hover:bg-slate-700 hover:text-white border border-slate-700 transition-all"
            >
              <Upload className="w-5 h-5 text-slate-400" />
              <span>Upload Audio File</span>
            </Link>
          </div>

          {/* Sample Dashboard link preview */}
          <div className="pt-2">
            <Link
              href="/results"
              className="inline-flex items-center space-x-1.5 text-xs text-slate-400 hover:text-indigo-400 transition-colors"
            >
              <span>Explore Sample Analysis Dashboard</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Process Breakdown Section */}
      <section className="py-16 px-4 bg-slate-950 border-b border-slate-800">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12 space-y-2">
            <h2 className="text-2xl sm:text-3xl font-bold text-white">How Accent Analyser Works</h2>
            <p className="text-slate-400 text-sm max-w-lg mx-auto">
              Get comprehensive feedback on your speech in three simple steps.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="bg-slate-900/80 border border-slate-800 p-6 rounded-2xl relative space-y-4">
              <div className="w-10 h-10 bg-indigo-600/20 text-indigo-400 rounded-xl flex items-center justify-center font-bold text-lg">
                1
              </div>
              <h3 className="text-lg font-semibold text-white">Record or Upload Audio</h3>
              <p className="text-sm text-slate-400 leading-relaxed">
                Speak into your browser microphone for 10-30 seconds or drag and drop an existing speech recording.
              </p>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 p-6 rounded-2xl relative space-y-4">
              <div className="w-10 h-10 bg-indigo-600/20 text-indigo-400 rounded-xl flex items-center justify-center font-bold text-lg">
                2
              </div>
              <h3 className="text-lg font-semibold text-white">Automated Speech Analysis</h3>
              <p className="text-sm text-slate-400 leading-relaxed">
                Our speech processing engine evaluates phonetic alignment, speaking pace, enunciation, and fluency.
              </p>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 p-6 rounded-2xl relative space-y-4">
              <div className="w-10 h-10 bg-indigo-600/20 text-indigo-400 rounded-xl flex items-center justify-center font-bold text-lg">
                3
              </div>
              <h3 className="text-lg font-semibold text-white">Receive Actionable Feedback</h3>
              <p className="text-sm text-slate-400 leading-relaxed">
                View detailed scores, identified phoneme issues, detected accent characteristics, and personalized drills.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Highlights Section */}
      <section className="py-16 px-4 bg-slate-900/50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12 space-y-2">
            <h2 className="text-2xl sm:text-3xl font-bold text-white">Core Speech Insights</h2>
            <p className="text-slate-400 text-sm max-w-lg mx-auto">
              Targeted metrics designed for global professionals and English learners.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
              <div className="p-2.5 bg-indigo-600/20 text-indigo-400 rounded-lg w-fit">
                <Target className="w-5 h-5" />
              </div>
              <h4 className="text-base font-semibold text-white">Pronunciation Precision</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Pinpoint exact phoneme substitutions and vowel shifts in multi-syllable words.
              </p>
            </div>

            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
              <div className="p-2.5 bg-indigo-600/20 text-indigo-400 rounded-lg w-fit">
                <Volume2 className="w-5 h-5" />
              </div>
              <h4 className="text-base font-semibold text-white">Speech Pace & Rhythm</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Track your words per minute (WPM) and pause distribution for natural delivery.
              </p>
            </div>

            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
              <div className="p-2.5 bg-indigo-600/20 text-indigo-400 rounded-lg w-fit">
                <TrendingUp className="w-5 h-5" />
              </div>
              <h4 className="text-base font-semibold text-white">Clarity & Fluency</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Evaluate enunciation clarity and hesitation patterns to speak with confidence.
              </p>
            </div>

            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
              <div className="p-2.5 bg-indigo-600/20 text-indigo-400 rounded-lg w-fit">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h4 className="text-base font-semibold text-white">Actionable Drills</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Get specific tongue positioning tips and exercises to refine your accent over time.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
