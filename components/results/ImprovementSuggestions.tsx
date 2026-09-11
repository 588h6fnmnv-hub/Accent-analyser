import { ImprovementSuggestion } from '@/types/analysis';

interface ImprovementSuggestionsProps {
  suggestions: ImprovementSuggestion[];
}

export function ImprovementSuggestions({ suggestions }: ImprovementSuggestionsProps) {
  return (
    <div className="bg-surface-container-low border border-outline-variant/40 rounded-DEFAULT p-6 space-y-6">
      <div className="border-b border-outline-variant/40 pb-4">
        <span className="font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant">
          Recommendations
        </span>
        <h3 className="font-headline-lg text-headline-lg text-primary mt-1">Actionable Improvement Plan</h3>
      </div>

      {!suggestions || suggestions.length === 0 ? (
        <div className="p-6 text-center font-body-md text-on-surface-variant bg-surface rounded-DEFAULT border border-outline-variant">
          No specific improvement suggestions required for this speech sample.
        </div>
      ) : (
        <div className="space-y-4">
          {suggestions.map((suggestion) => (
            <div key={suggestion.id} className="bg-surface p-5 rounded-DEFAULT border border-outline-variant/30 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-mono-data text-primary px-2.5 py-0.5 bg-surface-container border border-outline-variant rounded-DEFAULT uppercase">
                    {suggestion.category}
                  </span>
                  <h4 className="font-headline-md text-headline-md text-primary">{suggestion.title}</h4>
                </div>

                <span className="font-mono text-mono-data text-on-surface-variant border border-outline-variant px-2.5 py-0.5 rounded-DEFAULT capitalize">
                  {suggestion.priority} priority
                </span>
              </div>

              <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">{suggestion.description}</p>

              {suggestion.actionableSteps && suggestion.actionableSteps.length > 0 && (
                <div className="bg-surface-container-low p-4 rounded-DEFAULT border border-outline-variant/30 space-y-2">
                  <span className="font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant block">
                    Action Steps
                  </span>
                  <ul className="space-y-2">
                    {suggestion.actionableSteps.map((step, idx) => (
                      <li key={idx} className="font-body-md text-body-md text-primary flex items-start gap-2">
                        <span className="material-symbols-outlined text-primary text-[18px] shrink-0 mt-0.5">
                          check
                        </span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
