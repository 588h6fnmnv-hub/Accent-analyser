import { ScoreMetric } from '@/types/analysis';

interface ScoreCardProps {
  score: number;
  maxScore?: number;
  label: string;
  categoryScores?: ScoreMetric[];
}

export function ScoreCard({ score, maxScore = 100, label, categoryScores }: ScoreCardProps) {
  return (
    <div className="bg-surface-container-low border border-outline-variant/40 rounded-DEFAULT p-6 space-y-6">
      {/* Primary Score Overview */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-b border-outline-variant/40 pb-6">
        <div>
          <span className="font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant">
            Analysis Overview
          </span>
          <h2 className="font-headline-lg text-headline-lg text-primary mt-1">{label}</h2>
        </div>

        <div className="flex items-baseline gap-1 px-6 py-3 bg-surface border border-outline-variant rounded-DEFAULT">
          <span className="font-display-metrics text-display-metrics text-primary">{score}</span>
          <span className="font-mono text-mono-data text-on-surface-variant">/{maxScore}</span>
        </div>
      </div>

      {/* Breakdown Scores Grid */}
      {categoryScores && categoryScores.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {categoryScores.map((cat, idx) => (
            <div key={idx} className="bg-surface p-4 rounded-DEFAULT border border-outline-variant/30 space-y-3">
              <div className="flex items-center justify-between text-body-md">
                <span className="font-headline-md text-headline-md text-primary">{cat.label}</span>
                <span className="font-mono text-mono-data text-primary font-bold">{cat.score}/100</span>
              </div>

              <div className="w-full bg-surface-container-high h-1.5 rounded-full overflow-hidden flex">
                <div
                  className="bg-primary h-full rounded-full transition-all duration-500"
                  style={{ width: `${cat.score}%` }}
                />
              </div>

              <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">{cat.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
