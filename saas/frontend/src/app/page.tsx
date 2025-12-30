"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";

export default function Home() {
  const { isSignedIn } = useAuth();

  return (
    <div className="min-h-screen bg-obsidian-900 text-cream-100 noise-overlay">
      {/* Ambient Gold Glow Background */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-gold-400/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-gold-500/5 rounded-full blur-3xl" />
      </div>

      {/* Navigation */}
      <nav className="relative z-10 container mx-auto px-6 py-6 flex justify-between items-center">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-lg bg-gold-gradient flex items-center justify-center shadow-gold-sm">
            <svg className="w-6 h-6 text-obsidian-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
                className="text-cream-300 hover:text-gold-400 transition-colors font-medium"
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
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-gold-400/30 bg-gold-400/5 mb-8 opacity-0 animate-fade-in-up">
            <span className="w-2 h-2 rounded-full bg-gold-400 animate-pulse" />
            <span className="text-gold-300 text-sm font-medium tracking-wide">
              Premium Data Intelligence Platform
            </span>
          </div>

          <h1 className="font-display text-5xl md:text-7xl font-bold mb-8 leading-tight opacity-0 animate-fade-in-up stagger-1">
            Transform Your Discord
            <br />
            <span className="text-gold-gradient">Into Insights</span>
          </h1>

          <p className="text-xl md:text-2xl text-cream-400 mb-12 max-w-2xl mx-auto leading-relaxed opacity-0 animate-fade-in-up stagger-2">
            Extract your complete message history, analyze conversations with powerful SQL queries,
            and discover patterns in your community.
          </p>

          <div className="flex justify-center gap-4 opacity-0 animate-fade-in-up stagger-3">
            <Link
              href="/sign-up"
              className="btn-gold px-8 py-4 rounded-xl text-lg font-semibold"
            >
              Start Free Trial
            </Link>
            <Link
              href="#features"
              className="btn-outline-gold px-8 py-4 rounded-xl text-lg"
            >
              Explore Features
            </Link>
          </div>
        </div>

        {/* Stats Bar */}
        <div className="mt-24 grid grid-cols-3 gap-8 max-w-3xl mx-auto opacity-0 animate-fade-in-up stagger-4">
          {[
            { value: "10M+", label: "Messages Analyzed" },
            { value: "500+", label: "Active Servers" },
            { value: "99.9%", label: "Uptime SLA" },
          ].map((stat, i) => (
            <div key={i} className="text-center">
              <div className="font-display text-4xl font-bold text-gold-400 mb-2">{stat.value}</div>
              <div className="text-cream-500 text-sm uppercase tracking-wider">{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Features Section */}
        <div id="features" className="mt-40">
          <div className="text-center mb-16">
            <h2 className="font-display text-3xl md:text-4xl font-bold mb-4">
              Enterprise-Grade <span className="text-gold-gradient">Analytics</span>
            </h2>
            <p className="text-cream-400 max-w-xl mx-auto">
              Everything you need to understand your Discord community at scale
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
                description: "Extract your complete message history, reactions, mentions, and user data. Choose how far back to sync - from 30 days to unlimited history.",
              },
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                ),
                title: "Isolated Database",
                description: "Your data lives in a dedicated PostgreSQL database with Row-Level Security. Complete tenant isolation with enterprise-grade encryption.",
              },
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                ),
                title: "SQL Query Editor",
                description: "Write and execute SQL queries with syntax highlighting, schema browser, and instant results. Export to CSV or integrate via API.",
              },
            ].map((feature, i) => (
              <div
                key={i}
                className="premium-card p-8 rounded-2xl hover:border-gold-400/30 transition-all duration-300 group"
              >
                <div className="w-14 h-14 rounded-xl bg-gold-400/10 border border-gold-400/20 flex items-center justify-center text-gold-400 mb-6 group-hover:bg-gold-400/20 transition-colors">
                  {feature.icon}
                </div>
                <h3 className="font-display text-xl font-semibold mb-3 text-cream-100">
                  {feature.title}
                </h3>
                <p className="text-cream-400 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Pricing Section */}
        <div className="mt-40">
          <div className="text-center mb-16">
            <h2 className="font-display text-3xl md:text-4xl font-bold mb-4">
              Transparent <span className="text-gold-gradient">Pricing</span>
            </h2>
            <p className="text-cream-400 max-w-xl mx-auto">
              Start free, scale as you grow. No hidden fees.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {/* Free Tier */}
            <div className="premium-card p-8 rounded-2xl">
              <div className="mb-6">
                <h3 className="font-display text-xl font-semibold mb-1">Starter</h3>
                <p className="text-cream-500 text-sm">Perfect for exploration</p>
              </div>
              <div className="mb-8">
                <span className="font-display text-5xl font-bold">$0</span>
                <span className="text-cream-500">/month</span>
              </div>
              <ul className="space-y-4 mb-8">
                {["500 MB storage", "30 days of history", "1,000 queries/month", "Schema browser"].map((item, i) => (
                  <li key={i} className="flex items-center gap-3 text-cream-300">
                    <svg className="w-5 h-5 text-gold-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {item}
                  </li>
                ))}
              </ul>
              <Link
                href="/sign-up"
                className="block text-center btn-outline-gold px-6 py-3 rounded-xl w-full"
              >
                Get Started
              </Link>
            </div>

            {/* Pro Tier */}
            <div className="gold-accent-card p-8 rounded-2xl relative scale-105">
              <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                <span className="bg-gold-gradient px-4 py-1.5 rounded-full text-obsidian-900 text-sm font-semibold">
                  Most Popular
                </span>
              </div>
              <div className="mb-6">
                <h3 className="font-display text-xl font-semibold mb-1">Professional</h3>
                <p className="text-cream-500 text-sm">For growing communities</p>
              </div>
              <div className="mb-8">
                <span className="font-display text-5xl font-bold text-gold-gradient">$9</span>
                <span className="text-cream-500">/month</span>
              </div>
              <ul className="space-y-4 mb-8">
                {["5 GB storage", "365 days of history", "Unlimited queries", "Priority support", "Advanced analytics"].map((item, i) => (
                  <li key={i} className="flex items-center gap-3 text-cream-300">
                    <svg className="w-5 h-5 text-gold-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {item}
                  </li>
                ))}
              </ul>
              <Link
                href="/sign-up"
                className="block text-center btn-gold px-6 py-3 rounded-xl w-full"
              >
                Start Pro Trial
              </Link>
            </div>

            {/* Team Tier */}
            <div className="premium-card p-8 rounded-2xl">
              <div className="mb-6">
                <h3 className="font-display text-xl font-semibold mb-1">Enterprise</h3>
                <p className="text-cream-500 text-sm">For large organizations</p>
              </div>
              <div className="mb-8">
                <span className="font-display text-5xl font-bold">$29</span>
                <span className="text-cream-500">/month</span>
              </div>
              <ul className="space-y-4 mb-8">
                {["25 GB storage", "Unlimited history", "Unlimited queries", "REST API access", "Dedicated support"].map((item, i) => (
                  <li key={i} className="flex items-center gap-3 text-cream-300">
                    <svg className="w-5 h-5 text-gold-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {item}
                  </li>
                ))}
              </ul>
              <Link
                href="/sign-up"
                className="block text-center btn-outline-gold px-6 py-3 rounded-xl w-full"
              >
                Contact Sales
              </Link>
            </div>
          </div>
        </div>

        {/* CTA Section */}
        <div className="mt-40 text-center">
          <div className="premium-card p-16 rounded-3xl max-w-4xl mx-auto gold-glow">
            <h2 className="font-display text-3xl md:text-4xl font-bold mb-6">
              Ready to unlock your <span className="text-gold-gradient">community insights</span>?
            </h2>
            <p className="text-cream-400 text-lg mb-10 max-w-xl mx-auto">
              Join hundreds of community managers using Discord Analytics to understand their servers better.
            </p>
            <Link
              href="/sign-up"
              className="btn-gold px-10 py-4 rounded-xl text-lg font-semibold inline-block"
            >
              Start Your Free Trial
            </Link>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-obsidian-700">
        <div className="container mx-auto px-6 py-12">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gold-gradient flex items-center justify-center">
                <svg className="w-5 h-5 text-obsidian-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <span className="text-cream-400 text-sm">
                &copy; 2025 Discord Analytics. All rights reserved.
              </span>
            </div>
            <div className="flex items-center gap-8">
              <Link href="/privacy" className="text-cream-500 hover:text-gold-400 transition-colors text-sm">
                Privacy Policy
              </Link>
              <Link href="/terms" className="text-cream-500 hover:text-gold-400 transition-colors text-sm">
                Terms of Service
              </Link>
              <Link href="/docs" className="text-cream-500 hover:text-gold-400 transition-colors text-sm">
                Documentation
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
