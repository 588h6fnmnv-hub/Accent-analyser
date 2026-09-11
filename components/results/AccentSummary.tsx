import { AccentCharacteristic, SpeechPaceDetails, ConfidenceDeliveryDetails } from '@/types/analysis';

interface AccentSummaryProps {
  characteristics: AccentCharacteristic[];
  speechPace: SpeechPaceDetails;
  confidenceDelivery: ConfidenceDeliveryDetails;
}

export function AccentSummary({ characteristics, speechPace, confidenceDelivery }: AccentSummaryProps) {
  return (
    <div className="bg-surface-container-low border border-outline-variant/40 rounded-DEFAULT p-6 space-y-6">
      <div className="border-b border-outline-variant/40 pb-4">
        <span className="font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant">
          Profile & Delivery
        </span>
        <h3 className="font-headline-lg text-headline-lg text-primary mt-1">Accent & Delivery Analysis</h3>
      </div>

      {/* Pace & Confidence Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-surface p-4 rounded-DEFAULT border border-outline-variant/30 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
              Speech Pace
            </span>
            <span className="font-mono text-mono-data text-primary px-2 py-0.5 bg-surface-container border border-outline-variant rounded-DEFAULT">
              {speechPace.category}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display-metrics text-[32px] text-primary">{speechPace.wordsPerMinute}</span>
            <span className="font-mono text-mono-data text-on-surface-variant">WPM</span>
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant">{speechPace.assessment}</p>
        </div>

        <div className="bg-surface p-4 rounded-DEFAULT border border-outline-variant/30 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
              Confidence & Delivery
            </span>
            <span className="font-mono text-mono-data text-primary px-2 py-0.5 bg-surface-container border border-outline-variant rounded-DEFAULT">
              {confidenceDelivery.score}/100
            </span>
          </div>
          <p className="font-headline-md text-headline-md text-primary">{confidenceDelivery.pitchVariability}</p>
          <p className="font-body-md text-body-md text-on-surface-variant">{confidenceDelivery.pausesAssessment}</p>
        </div>
      </div>

      {/* Phonetic Accent Characteristics List */}
      {characteristics && characteristics.length > 0 && (
        <div className="space-y-3 pt-2">
          <span className="font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant block">
            Detected Accent Traits
          </span>

          <div className="space-y-3">
            {characteristics.map((item, idx) => (
              <div key={idx} className="bg-surface p-4 rounded-DEFAULT border border-outline-variant/30 space-y-1">
                <div className="flex items-center justify-between">
                  <h5 className="font-headline-md text-headline-md text-primary">{item.trait}</h5>
                  <span className="font-mono text-mono-data text-primary border border-outline-variant px-2 py-0.5 rounded-DEFAULT">
                    {item.confidence}% match
                  </span>
                </div>
                <p className="font-body-md text-body-md text-on-surface-variant font-medium">{item.influence}</p>
                <p className="font-body-md text-body-md text-on-surface-variant pt-1 leading-relaxed">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
