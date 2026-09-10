'use client';

export function AnalysisProgress({ statusText }: { statusText?: string }) {
  const steps = [
    { label: 'Recording', icon: 'check', isCompleted: true },
    { label: 'Transcribing', icon: 'progress_activity', isActive: true },
    { label: 'Analyzing pronunciation', icon: 'circle' },
    { label: 'Analyzing speech', icon: 'circle' },
    { label: 'Generating feedback', icon: 'circle' },
  ];

  return (
    <div className="w-full max-w-2xl px-gutter py-margin-page animate-fade-in flex flex-col mx-auto my-auto">
      <header className="mb-8 animate-slide-up" style={{ animationDelay: '100ms' }}>
        <h1 className="font-display-metrics text-display-metrics text-primary mb-2 tracking-tighter">
          Analyzing your voice
        </h1>
        <p className="font-body-lg text-body-lg text-on-surface-variant max-w-md">
          {statusText || 'Running isolated acoustic models and transcribing phonemes. Please wait.'}
        </p>
      </header>

      <div className="flex flex-col gap-4 w-full max-w-md animate-slide-up" style={{ animationDelay: '200ms' }}>
        {steps.map((item, index) => (
          <div
            key={index}
            className={`flex items-center gap-3 transition-opacity duration-300 ${
              item.isCompleted || item.isActive ? 'opacity-100' : 'opacity-50'
            }`}
          >
            <div className="w-6 h-6 flex items-center justify-center shrink-0">
              {item.isCompleted ? (
                <span className="material-symbols-outlined text-primary font-bold text-[20px]">
                  check
                </span>
              ) : item.isActive ? (
                <span className="material-symbols-outlined text-primary animate-spin text-[20px]">
                  progress_activity
                </span>
              ) : (
                <span
                  className="material-symbols-outlined text-[8px] text-on-surface-variant"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  circle
                </span>
              )}
            </div>
            <span
              className={`font-headline-md text-headline-md text-primary ${
                item.isActive ? 'animate-pulse' : ''
              }`}
            >
              {item.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
