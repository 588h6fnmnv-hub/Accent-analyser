import { CategoryScore } from '@/types/analysis';

interface ScoreCardProps {
  score: number;
  maxScore?: number;
  label: string;
  categoryScores?: CategoryScore[];
}

export function ScoreCard({ score, maxScore = 100, label, categoryScores }: ScoreCardProps) {
  const getScoreColor = (val: number) => {
    if (val >= 85) return 'text-emerald-400 border-emerald-500/30 bg-emerald-950/20';
    if (val >= 70) return 'text-indigo-400 border-indigo-500/30 bg-indigo-950/20';
    if (val >= 50) return 'text-amber-400 border-amber-500/30 bg-amber-950/20';
    return 'text-red-400 border-red-500/30 bg-red-950/20';
  };

  const getBarColor = (val: number) => {
    if (val >= 85) return 'bg-emerald-500';
    if (val >= 70) return 'bg-indigo-500';
    if (val >= 50) return 'bg-amber-500';
    return 'bg-red-500';
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6 shadow-md">
      {/* Primary Score Overview */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Analysis Overview
          </span>
          <h2 className="text-2xl font-bold text-white mt-0.5">{label}</h2>
        </div>

        <div
          className={`flex items-baseline space-x-1 px-5 py-3 rounded-2xl border ${getScoreColor(
            score
          )}`}
        >
          <span className="text-4xl font-extrabold tracking-tight">{score}</span>
          <span className="text-slate-400 text-sm font-medium">/{maxScore}</span>
        </div>
      </div>

      {/* Breakdown Scores Grid */}
      {categoryScores && categoryScores.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {categoryScores.map((cat, idx) => (
            <div key={idx} className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-white">{cat.label}</span>
                <span className="font-bold font-mono text-indigo-300">{cat.score}/100</span>
              </div>

              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${getBarColor(cat.score)}`}
                  style={{ width: `${cat.score}%` }}
                />
              </div>

              <p className="text-xs text-slate-400 leading-relaxed pt-1">{cat.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
