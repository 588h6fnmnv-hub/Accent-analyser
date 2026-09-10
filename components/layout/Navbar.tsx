'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const pathname = usePathname();

  const navLinks = [
    { name: 'Analyze', href: '/analyse' },
    { name: 'History', href: '/history' },
    { name: 'About', href: '/' },
  ];

  return (
    <header className="bg-background border-b border-outline-variant/40 w-full sticky top-0 z-50 backdrop-blur-md bg-background/90">
      <div className="flex justify-between items-center w-full px-gutter max-w-7xl mx-auto h-16">
        {/* Logo */}
        <Link
          href="/"
          className="font-headline-lg text-headline-lg font-bold text-primary tracking-tight hover:opacity-90 transition-opacity"
        >
          VoiceLens
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-8 font-headline-md text-headline-md">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`transition-colors duration-200 ${
                  isActive
                    ? 'text-primary border-b-2 border-primary pb-1 font-medium'
                    : 'text-on-surface-variant hover:text-primary'
                }`}
              >
                {link.name}
              </Link>
            );
          })}
        </nav>

        {/* Dark Mode Toggle Placeholder */}
        <div className="flex items-center gap-4">
          <button
            aria-label="Toggle Dark Mode"
            className="text-primary hover:text-primary transition-colors p-2"
          >
            <span className="material-symbols-outlined text-[20px]">dark_mode</span>
          </button>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden text-primary p-2"
            aria-label="Toggle Navigation Menu"
          >
            <span className="material-symbols-outlined text-[24px]">
              {mobileMenuOpen ? 'close' : 'menu'}
            </span>
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-background border-b border-outline-variant px-gutter py-4 space-y-3">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`block font-headline-md text-headline-md py-1 ${
                  isActive ? 'text-primary font-semibold' : 'text-on-surface-variant hover:text-primary'
                }`}
              >
                {link.name}
              </Link>
            );
          })}
        </div>
      )}
    </header>
  );
}
