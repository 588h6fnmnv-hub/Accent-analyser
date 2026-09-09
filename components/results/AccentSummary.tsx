import { AccentCharacteristic, SpeechPaceDetails, ConfidenceDeliveryDetails } from '@/types/analysis';
import { Globe, Gauge, Activity } from 'lucide-react';

interface AccentSummaryProps {
  characteristics: AccentCharacteristic[];
  speechPace: SpeechPaceDetails;
  confidenceDelivery: ConfidenceDeliveryDetails;
}

export function AccentSummary({ characteristics, speechPace, confidenceDelivery }: AccentSummaryProps) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6 shadow-md">
      <div className="flex items-center space-x-2 border-b border-slate-800 pb-4">
        <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg">
          <Globe className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-xl font-bold text-white">Accent & Delivery Profile</h3>
          <p className="text-xs text-slate-400">Speech pace, rhythm characteristics, and phonetic influences</p>
        </div>
      </div>

      {/* Pace & Confidence Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5 font-semibold text-slate-300">
              <Gauge className="w-4 h-4 text-indigo-400" /> Speech Pace
            </span>
            <span className="px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 font-mono border border-indigo-800/50">
              {speechPace.category}
            </span>
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-white">{speechPace.wordsPerMinute}</span>
            <span className="text-xs text-slate-400">Words per minute (WPM)</span>
          </div>
          <p className="text-xs text-slate-400">{speechPace.assessment}</p>
        </div>

        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5 font-semibold text-slate-300">
              <Activity className="w-4 h-4 text-emerald-400" /> Confidence & Delivery
            </span>
            <span className="px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 font-mono border border-emerald-800/50">
              {confidenceDelivery.score}/100
            </span>
          </div>
          <p className="text-xs text-slate-300 font-medium">{confidenceDelivery.pitchVariability}</p>
          <p className="text-xs text-slate-400">{confidenceDelivery.pausesAssessment}</p>
        </div>
      </div>

      {/* Phonetic Accent Characteristics List */}
      <div className="space-y-3 pt-2">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Detected Accent Traits
        </h4>

        <div className="space-y-3">
          {characteristics.map((item, idx) => (
            <div key={idx} className="bg-slate-950/70 p-4 rounded-xl border border-slate-800/70 space-y-1">
              <div className="flex items-center justify-between">
                <h5 className="text-sm font-semibold text-white">{item.trait}</h5>
                <span className="text-xs font-mono text-indigo-400 bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-800/40">
                  {item.confidence}% match
                </span>
              </div>
              <p className="text-xs font-medium text-slate-400">{item.influence}</p>
              <p className="text-xs text-slate-400 pt-1 leading-relaxed">{item.description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
