import Link from 'next/link';

export function Footer() {
  return (
    <footer className="bg-slate-950 text-slate-400 text-sm border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div>
          <h3 className="text-white font-semibold text-base mb-2">Accent Analyser</h3>
          <p className="text-slate-400 text-xs leading-relaxed">
            A modern voice and speech analysis tool designed to help non-native speakers, professionals, and language learners improve clarity, pronunciation, and confidence in spoken English.
          </p>
        </div>

        <div>
          <h4 className="text-white font-medium mb-3">Quick Links</h4>
          <ul className="space-y-2 text-xs">
            <li>
              <Link href="/" className="hover:text-indigo-400 transition-colors">
                Home
              </Link>
            </li>
            <li>
              <Link href="/analyse" className="hover:text-indigo-400 transition-colors">
                Analyse My Voice
              </Link>
            </li>
            <li>
              <Link href="/results" className="hover:text-indigo-400 transition-colors">
                Sample Results Dashboard
              </Link>
            </li>
          </ul>
        </div>

        <div>
          <h4 className="text-white font-medium mb-3">Disclaimer</h4>
          <p className="text-xs text-slate-400 leading-relaxed">
            Accent Analyser provides speech feedback for educational and practice purposes. Scores and recommendations are generated using speech evaluation metrics and mock feedback models in early preview.
          </p>
        </div>
      </div>

      <div className="border-t border-slate-800/80 py-4 text-center text-xs text-slate-400">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row justify-between items-center gap-2">
          <span>&copy; {new Date().getFullYear()} Accent Analyser. All rights reserved.</span>
          <span>Optimized for Vercel Deployment</span>
        </div>
      </div>
    </footer>
  );
}
