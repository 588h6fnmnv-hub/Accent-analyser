import { PronunciationIssue } from '@/types/analysis';

interface PronunciationFeedbackProps {
  issues: PronunciationIssue[];
}

export function PronunciationFeedback({ issues }: PronunciationFeedbackProps) {
  return (
    <div className="bg-surface-container-low border border-outline-variant/40 rounded-DEFAULT p-6 space-y-6">
      <div className="border-b border-outline-variant/40 pb-4">
        <span className="font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant">
          Phonetics
        </span>
        <h3 className="font-headline-lg text-headline-lg text-primary mt-1">Pronunciation & Phonetic Breakdown</h3>
      </div>

      {!issues || issues.length === 0 ? (
        <div className="p-6 text-center font-body-md text-on-surface-variant bg-surface rounded-DEFAULT border border-outline-variant">
          No notable pronunciation issues detected in this speech sample.
        </div>
      ) : (
        <div className="overflow-x-auto w-full bg-surface border border-outline-variant rounded-DEFAULT">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-outline-variant/40 bg-surface-container-low">
                <th className="py-3 px-4 font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-normal">
                  Word
                </th>
                <th className="py-3 px-4 font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-normal font-mono">
                  Target Phonetic
                </th>
                <th className="py-3 px-4 font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-normal font-mono">
                  Detected Phonetic
                </th>
                <th className="py-3 px-4 font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-normal">
                  Explanation & Tip
                </th>
              </tr>
            </thead>
            <tbody className="font-mono text-mono-data text-primary">
              {issues.map((issue) => (
                <tr key={issue.id} className="border-b border-outline-variant/20 hover:bg-surface-container-high transition-colors">
                  <td className="py-3 px-4 font-headline-md font-sans text-primary">{issue.word}</td>
                  <td className="py-3 px-4 text-primary font-mono">{issue.phoneticSpelling}</td>
                  <td className="py-3 px-4 text-on-surface-variant font-mono">{issue.detectedPhonetic}</td>
                  <td className="py-3 px-4 font-sans text-body-md text-on-surface-variant">
                    <p className="text-primary font-medium">{issue.explanation}</p>
                    <p className="text-on-surface-variant text-xs mt-0.5">{issue.tip}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
