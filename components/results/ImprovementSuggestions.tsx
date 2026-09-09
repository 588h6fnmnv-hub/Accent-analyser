import { ImprovementSuggestion } from '@/types/analysis';
import { Lightbulb, CheckCircle2 } from 'lucide-react';

interface ImprovementSuggestionsProps {
  suggestions: ImprovementSuggestion[];
}

export function ImprovementSuggestions({ suggestions }: ImprovementSuggestionsProps) {
  const getPriorityBadge = (priority: ImprovementSuggestion['priority']) => {
    switch (priority) {
      case 'high':
        return 'bg-red-950/80 text-red-300 border-red-800/60';
      case 'medium':
        return 'bg-indigo-950/80 text-indigo-300 border-indigo-800/60';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6 shadow-md">
      <div className="flex items-center space-x-2 border-b border-slate-800 pb-4">
        <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg">
          <Lightbulb className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-xl font-bold text-white">Actionable Improvement Plan</h3>
          <p className="text-xs text-slate-400">Targeted drills and habits to refine your accent and speech clarity</p>
        </div>
      </div>

      <div className="space-y-4">
        {suggestions.map((suggestion) => (
          <div key={suggestion.id} className="bg-slate-950/80 p-5 rounded-xl border border-slate-800 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <span className="px-2.5 py-1 rounded-md bg-indigo-950 text-indigo-300 border border-indigo-800/50 text-xs font-semibold uppercase">
                  {suggestion.category}
                </span>
                <h4 className="text-base font-bold text-white">{suggestion.title}</h4>
              </div>

              <span className={`text-xs px-2.5 py-0.5 rounded-full border capitalize font-medium ${getPriorityBadge(suggestion.priority)}`}>
                {suggestion.priority} priority
              </span>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">{suggestion.description}</p>

            {suggestion.actionableSteps && suggestion.actionableSteps.length > 0 && (
              <div className="bg-slate-900/60 p-3.5 rounded-lg border border-slate-800 space-y-2 mt-2">
                <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">
                  Recommended Action Steps:
                </span>
                <ul className="space-y-1.5">
                  {suggestion.actionableSteps.map((step, idx) => (
                    <li key={idx} className="text-xs text-slate-300 flex items-start space-x-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                      <span>{step}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
