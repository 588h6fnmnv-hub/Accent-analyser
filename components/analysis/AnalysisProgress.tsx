'use client';

import { useState, useEffect } from 'react';
import { Loader2, Mic, Cpu, Sparkles, CheckCircle2 } from 'lucide-react';

interface AnalysisProgressProps {
  statusText?: string;
}

const STEPS = [
  { label: 'Processing audio input...', icon: Mic },
  { label: 'Transcribing speech & acoustic features...', icon: Cpu },
  { label: 'Evaluating pronunciation & clarity metrics...', icon: Sparkles },
  { label: 'Generating tailored accent report...', icon: CheckCircle2 },
];

export function AnalysisProgress({ statusText }: AnalysisProgressProps) {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev < STEPS.length - 1 ? prev + 1 : prev));
    }, 400);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center p-8 bg-slate-900/90 border border-slate-800 rounded-2xl w-full max-w-xl mx-auto shadow-2xl space-y-6">
      <div className="p-4 bg-indigo-600/20 text-indigo-400 rounded-full animate-spin">
        <Loader2 className="w-10 h-10" />
      </div>

      <div className="text-center space-y-2">
        <h3 className="text-xl font-bold text-white">Analysing Your Voice</h3>
        <p className="text-sm text-slate-400">
          {statusText || 'Our speech engine is evaluating your audio sample.'}
        </p>
      </div>

      <div className="w-full space-y-3 pt-2">
        {STEPS.map((step, idx) => {
          const Icon = step.icon;
          const isDone = idx < activeStep;
          const isCurrent = idx === activeStep;

          return (
            <div
              key={idx}
              className={`flex items-center space-x-3 p-3 rounded-xl border text-sm transition-all duration-300 ${
                isDone
                  ? 'border-indigo-900/50 bg-indigo-950/30 text-indigo-200'
                  : isCurrent
                  ? 'border-indigo-500 bg-slate-800 text-white shadow-md'
                  : 'border-slate-800/60 bg-slate-950/20 text-slate-500'
              }`}
            >
              <div
                className={`p-1.5 rounded-lg ${
                  isDone
                    ? 'bg-indigo-600/30 text-indigo-300'
                    : isCurrent
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-800 text-slate-600'
                }`}
              >
                <Icon className="w-4 h-4" />
              </div>
              <span className="font-medium flex-1">{step.label}</span>
              {isDone && <CheckCircle2 className="w-4 h-4 text-indigo-400" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
