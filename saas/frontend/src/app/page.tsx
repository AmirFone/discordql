"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";

export default function Home() {
  const { isSignedIn } = useAuth();

  return (
    <div className="min-h-screen bg-base-50 text-ink-800 noise-overlay">
      {/* Ambient Gold Glow Background */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-gold-400/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-gold-500/8 rounded-full blur-3xl" />
      </div>

      {/* Navigation */}
      <nav className="relative z-10 container mx-auto px-6 py-6 flex justify-between items-center">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-lg bg-gold-gradient flex items-center justify-center shadow-gold-sm">
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <span className="font-display text-2xl font-semibold text-gold-gradient">
            Discord Analytics
          </span>
        </Link>

        <div className="flex items-center gap-6">
          {isSignedIn ? (
            <Link
              href="/dashboard"
              className="btn-gold px-6 py-2.5 rounded-lg"
            >
              Dashboard
            </Link>
          ) : (
            <>
              <Link
                href="/sign-in"
                className="text-ink-600 hover:text-gold-600 transition-colors font-medium"
              >
                Sign In
              </Link>
              <Link
                href="/sign-up"
                className="btn-gold px-6 py-2.5 rounded-lg"
              >
                Get Started
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* Hero Section */}
      <main className="relative z-10 container mx-auto px-6 pt-20 pb-32">
        <div className="text-center max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-gold-400/40 bg-gold-400/10 mb-8 opacity-0 animate-fade-in-up">
            <span className="w-2 h-2 rounded-full bg-gold-400 animate-pulse" />
            <span className="text-gold-600 text-sm font-medium tracking-wide">
              Open Source Discord Analytics
            </span>
          </div>

          <h1 className="font-display text-5xl md:text-7xl font-bold mb-8 leading-tight opacity-0 animate-fade-in-up stagger-1 text-ink-900">
            Transform Your Discord
            <br />
            <span className="text-gold-gradient">Into Insights</span>
          </h1>

          <p className="text-xl md:text-2xl text-ink-600 mb-12 max-w-2xl mx-auto leading-relaxed opacity-0 animate-fade-in-up stagger-2">
            Extract your complete message history, analyze conversations with powerful SQL queries,
            and discover patterns in your community.
          </p>

          <div className="flex justify-center gap-4 opacity-0 animate-fade-in-up stagger-3">
            <Link
              href="/sign-up"
              className="btn-gold px-8 py-4 rounded-xl text-lg font-semibold"
            >
              Get Started Free
            </Link>
            <Link
              href="#features"
              className="btn-outline-gold px-8 py-4 rounded-xl text-lg"
            >
              Explore Features
            </Link>
          </div>
        </div>

        {/* Features Section */}
        <div id="features" className="mt-32">
          <div className="text-center mb-16">
            <h2 className="font-display text-3xl md:text-4xl font-bold mb-4 text-ink-900">
              Powerful <span className="text-gold-gradient">Features</span>
            </h2>
            <p className="text-ink-600 max-w-xl mx-auto">
              Everything you need to understand your Discord community
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
                  </svg>
                ),
                title: "Full Data Extraction",
                description: "Extract your complete message history, reactions, mentions, and user data. Choose how far back to sync.",
              },
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                ),
                title: "Secure & Isolated",
                description: "Your data lives in a dedicated PostgreSQL database with Row-Level Security and enterprise-grade encryption.",
              },
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                ),
                title: "SQL Query Editor",
                description: "Write and execute SQL queries with syntax highlighting, schema browser, and instant results. Export to CSV.",
              },
            ].map((feature, i) => (
              <div
                key={i}
                className="premium-card p-8 rounded-2xl hover:border-gold-400/50 transition-all duration-300 group"
              >
                <div className="w-14 h-14 rounded-xl bg-gold-400/15 border border-gold-400/30 flex items-center justify-center text-gold-600 mb-6 group-hover:bg-gold-400/25 transition-colors">
                  {feature.icon}
                </div>
                <h3 className="font-display text-xl font-semibold mb-3 text-ink-800">
                  {feature.title}
                </h3>
                <p className="text-ink-600 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Simple CTA Section */}
        <div className="mt-32 text-center">
          <div className="premium-card p-12 rounded-3xl max-w-3xl mx-auto gold-glow">
            <h2 className="font-display text-3xl font-bold mb-6 text-ink-900">
              Ready to get started?
            </h2>
            <p className="text-ink-600 text-lg mb-8 max-w-xl mx-auto">
              Extract your Discord data and gain insights in minutes.
            </p>
            <Link
              href="/sign-up"
              className="btn-gold px-10 py-4 rounded-xl text-lg font-semibold inline-block"
            >
              Get Started Free
            </Link>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-surface-400">
        <div className="container mx-auto px-6 py-12">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gold-gradient flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <span className="text-ink-500 text-sm">
                &copy; 2025 Discord Analytics. All rights reserved.
              </span>
            </div>
            <div className="flex items-center gap-8">
              <Link href="/privacy" className="text-ink-500 hover:text-gold-600 transition-colors text-sm">
                Privacy Policy
              </Link>
              <Link href="/terms" className="text-ink-500 hover:text-gold-600 transition-colors text-sm">
                Terms of Service
              </Link>
              <Link href="/docs" className="text-ink-500 hover:text-gold-600 transition-colors text-sm">
                Documentation
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
