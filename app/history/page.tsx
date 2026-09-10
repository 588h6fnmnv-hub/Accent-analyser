'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

export interface HistoryItem {
  id: string;
  timestamp: string;
  referenceId: string;
  overallScore: number;
  accentProfile: string;
  duration: string;
}

const STORAGE_KEY = 'voicelens_history_logs';

export default function HistoryPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const mappedItems: HistoryItem[] = parsed.map((item, idx) => {
            const date = item.timestamp ? new Date(item.timestamp) : new Date();
            const dateStr = date.toISOString().replace('T', '-').substring(0, 19).replace(/-/g, '.');
            const mins = Math.floor((item.audioDurationSeconds || 15) / 60);
            const secs = ((item.audioDurationSeconds || 15) % 60).toFixed(1).padStart(4, '0');
            const profile = item.accentCharacteristics?.[0]?.trait || 'Standard_Enunciation';

            return {
              id: item.id || `h_local_${idx}`,
              timestamp: dateStr,
              referenceId: `V-${(item.id || 'LOCAL').substring(0, 6).toUpperCase()}`,
              overallScore: item.overallScore || 80,
              accentProfile: profile.replace(/\s+/g, '_'),
              duration: `${mins.toString().padStart(2, '0')}:${secs}`,
            };
          });

          const timer = setTimeout(() => {
            setHistoryItems(mappedItems);
            setLoading(false);
          }, 0);
          return () => clearTimeout(timer);
        }
      }
      const timer = setTimeout(() => setLoading(false), 0);
      return () => clearTimeout(timer);
    } catch (err) {
      console.error('Error loading history from localStorage:', err);
      const timer = setTimeout(() => setLoading(false), 0);
      return () => clearTimeout(timer);
    }
  }, []);

  const filteredHistory = historyItems.filter(
    (item) =>
      item.referenceId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.accentProfile.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.timestamp.includes(searchTerm)
  );

  const avgClarity = historyItems.length > 0
    ? (historyItems.reduce((acc, curr) => acc + curr.overallScore, 0) / historyItems.length).toFixed(1)
    : '0.0';

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center font-mono text-mono-data text-on-surface-variant py-24">
        Loading history logs...
      </div>
    );
  }

  return (
    <div className="flex-1 w-full max-w-7xl mx-auto px-gutter py-margin-page">
      <header className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h1 className="font-display-metrics text-display-metrics text-primary mb-2">History</h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant">
            Analysis logs and waveform records.
          </p>
        </div>
        <div className="flex gap-4">
          <Link
            href="/analyse"
            className="bg-primary text-background px-4 py-2 font-label-sm text-label-sm uppercase tracking-widest hover:bg-surface-tint transition-colors font-semibold"
          >
            New Analysis
          </Link>
        </div>
      </header>

      {/* Analytics Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-surface-container-low border border-outline-variant/40 p-4 rounded-DEFAULT">
          <div className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest mb-2">
            Total Analyses
          </div>
          <div className="font-display-metrics text-display-metrics text-primary">{historyItems.length}</div>
        </div>
        <div className="bg-surface-container-low border border-outline-variant/40 p-4 rounded-DEFAULT">
          <div className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest mb-2">
            Avg. Clarity Score
          </div>
          <div className="font-display-metrics text-display-metrics text-primary">
            {avgClarity}<span className="font-headline-md text-headline-md text-on-surface-variant ml-1">%</span>
          </div>
        </div>
        <div className="bg-surface-container-low border border-outline-variant/40 p-4 rounded-DEFAULT">
          <div className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest mb-2">
            System Status
          </div>
          <div className="flex items-center gap-2 mt-4">
            <span className="w-2 h-2 bg-primary rounded-full animate-pulse" />
            <span className="font-mono text-mono-data text-primary">OPTIMAL</span>
          </div>
        </div>
      </div>

      {/* History Table Workspace */}
      <div className="bg-surface-container-low border border-outline-variant/40 rounded-DEFAULT overflow-hidden">
        <div className="p-4 border-b border-outline-variant/40 flex justify-between items-center">
          <div className="relative w-64">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm">
              search
            </span>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search logs..."
              className="w-full bg-background border border-outline-variant text-primary font-body-md text-body-md py-1.5 pl-9 pr-3 focus:outline-none focus:border-primary transition-colors placeholder:text-on-surface-variant"
            />
          </div>
          <div className="flex items-center gap-2 text-on-surface-variant font-label-sm text-label-sm">
            <span className="material-symbols-outlined text-sm">filter_list</span>
            <span>FILTER</span>
          </div>
        </div>

        {historyItems.length === 0 ? (
          <div className="p-12 text-center space-y-4">
            <span className="material-symbols-outlined text-[48px] text-on-surface-variant">
              history
            </span>
            <h3 className="font-headline-lg text-headline-lg text-primary">No Analysis History Yet</h3>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-sm mx-auto">
              Your voice analysis history is completely empty. Record your speech to create your first analysis log.
            </p>
            <div className="pt-2">
              <Link
                href="/analyse"
                className="inline-block bg-primary text-background font-label-sm text-label-sm uppercase tracking-widest px-6 py-3 rounded-DEFAULT hover:bg-surface-tint transition-colors font-semibold"
              >
                Start Recording
              </Link>
            </div>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto w-full">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-outline-variant/40">
                    <th className="py-3 px-4 font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-normal whitespace-nowrap w-48">
                      Date / Time
                    </th>
                    <th className="py-3 px-4 font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-normal">
                      Reference ID
                    </th>
                    <th className="py-3 px-4 font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-normal text-right w-32">
                      Overall Score
                    </th>
                    <th className="py-3 px-4 font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-normal w-48">
                      Accent Profile
                    </th>
                    <th className="py-3 px-4 font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-normal text-right w-24">
                      Duration
                    </th>
                    <th className="py-3 px-4 w-12" />
                  </tr>
                </thead>
                <tbody className="font-mono text-mono-data text-primary">
                  {filteredHistory.map((item) => (
                    <tr
                      key={item.id}
                      className="border-b border-outline-variant/20 hover:bg-surface-container-high transition-colors group cursor-pointer"
                    >
                      <td className="py-3 px-4">{item.timestamp}</td>
                      <td className="py-3 px-4 text-on-surface-variant">{item.referenceId}</td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <span>{item.overallScore}</span>
                          <div className="w-16 h-1 bg-surface-container rounded-full overflow-hidden flex">
                            <div
                              className="bg-primary h-full"
                              style={{ width: `${item.overallScore}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">{item.accentProfile}</td>
                      <td className="py-3 px-4 text-right">{item.duration}</td>
                      <td className="py-3 px-4 text-center">
                        <Link href="/results" className="text-on-surface-variant group-hover:text-primary transition-colors">
                          <span className="material-symbols-outlined text-sm">arrow_forward</span>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="p-4 border-t border-outline-variant/40 flex justify-between items-center text-on-surface-variant font-label-sm text-label-sm">
              <div>Showing 1-{filteredHistory.length} of {historyItems.length} entries</div>
              <div className="flex gap-4">
                <button className="hover:text-primary transition-colors disabled:opacity-50" disabled>
                  PREV
                </button>
                <button className="hover:text-primary transition-colors">NEXT</button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
