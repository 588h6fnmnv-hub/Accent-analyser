import Link from 'next/link';

export function Footer() {
  return (
    <footer className="bg-background border-t border-outline-variant/40 w-full mt-auto z-10">
      <div className="flex flex-col md:flex-row justify-between items-center w-full px-gutter py-stack-md max-w-7xl mx-auto">
        <div className="font-label-sm text-label-sm text-primary mb-4 md:mb-0">
          © {new Date().getFullYear()} VoiceLens. Achromatic Precision.
        </div>
        <nav className="flex items-center gap-6 font-label-sm text-label-sm text-on-surface-variant">
          <Link href="/analyse" className="hover:text-primary transition-colors duration-200">
            Analyze
          </Link>
          <Link href="/history" className="hover:text-primary transition-colors duration-200">
            History
          </Link>
          <Link href="/" className="hover:text-primary transition-colors duration-200">
            About
          </Link>
        </nav>
      </div>
    </footer>
  );
}
