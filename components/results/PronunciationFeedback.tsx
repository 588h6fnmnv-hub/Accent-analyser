import { PronunciationIssue } from '@/types/analysis';
import { Volume2, AlertCircle, HelpCircle } from 'lucide-react';

interface PronunciationFeedbackProps {
  issues: PronunciationIssue[];
}

export function PronunciationFeedback({ issues }: PronunciationFeedbackProps) {
  const getSeverityBadge = (severity: PronunciationIssue['severity']) => {
    switch (severity) {
      case 'major':
        return 'bg-red-950/80 text-red-300 border-red-800/60';
      case 'moderate':
        return 'bg-amber-950/80 text-amber-300 border-amber-800/60';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6 shadow-md">
      <div className="flex items-center space-x-2 border-b border-slate-800 pb-4">
        <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg">
          <Volume2 className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-xl font-bold text-white">Pronunciation & Phonetic Feedback</h3>
          <p className="text-xs text-slate-400">Word-level phonetic breakdown and enunciation recommendations</p>
        </div>
      </div>

      {issues.length === 0 ? (
        <div className="p-6 text-center text-slate-400 bg-slate-950 rounded-xl border border-slate-800">
          No notable pronunciation issues detected in this speech sample!
        </div>
      ) : (
        <div className="space-y-4">
          {issues.map((issue) => (
            <div key={issue.id} className="bg-slate-950/80 p-5 rounded-xl border border-slate-800 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center space-x-3">
                  <span className="text-base font-bold text-white">{issue.word}</span>
                  <div className="flex items-center space-x-2 text-xs font-mono">
                    <span className="text-slate-400">Target:</span>
                    <span className="text-emerald-400 font-semibold">{issue.phoneticSpelling}</span>
                    <span className="text-slate-600">|</span>
                    <span className="text-slate-400">Detected:</span>
                    <span className="text-amber-400 font-semibold">{issue.detectedPhonetic}</span>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  {issue.timestamp && (
                    <span className="text-xs font-mono text-slate-500 bg-slate-900 px-2 py-0.5 rounded">
                      {issue.timestamp}
                    </span>
                  )}
                  <span
                    className={`text-xs px-2.5 py-0.5 rounded-full border capitalize font-medium ${getSeverityBadge(
                      issue.severity
                    )}`}
                  >
                    {issue.severity}
                  </span>
                </div>
              </div>

              <div className="text-xs text-slate-300 leading-relaxed flex items-start space-x-2 bg-slate-900/50 p-3 rounded-lg border border-slate-800/50">
                <AlertCircle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                <span>{issue.explanation}</span>
              </div>

              <div className="text-xs text-indigo-200 leading-relaxed flex items-start space-x-2 bg-indigo-950/20 p-3 rounded-lg border border-indigo-900/30">
                <HelpCircle className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-indigo-300">Practice Tip: </span>
                  <span>{issue.tip}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
