"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";

export default function Home() {
  const { isSignedIn } = useAuth();

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-gray-800 text-white">
      {/* Navigation */}
      <nav className="container mx-auto px-6 py-4 flex justify-between items-center">
        <div className="text-2xl font-bold text-indigo-400">
          Discord Analytics
        </div>
        <div className="space-x-4">
          {isSignedIn ? (
            <Link
              href="/dashboard"
              className="bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg transition"
            >
              Dashboard
            </Link>
          ) : (
            <>
              <Link
                href="/sign-in"
                className="hover:text-indigo-400 transition"
              >
                Sign In
              </Link>
              <Link
                href="/sign-up"
                className="bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg transition"
              >
                Get Started
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* Hero Section */}
      <main className="container mx-auto px-6 py-20">
        <div className="text-center max-w-4xl mx-auto">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            Unlock Insights from Your{" "}
            <span className="text-indigo-400">Discord Server</span>
          </h1>
          <p className="text-xl text-gray-300 mb-10">
            Extract your Discord message history, analyze conversations with SQL,
            and discover patterns in your community. Your data, your database, your queries.
          </p>
          <div className="flex justify-center gap-4">
            <Link
              href="/sign-up"
              className="bg-indigo-600 hover:bg-indigo-700 px-8 py-4 rounded-lg text-lg font-semibold transition"
            >
              Start Free
            </Link>
            <Link
              href="#features"
              className="border border-gray-600 hover:border-indigo-400 px-8 py-4 rounded-lg text-lg transition"
            >
              Learn More
            </Link>
          </div>
        </div>

        {/* Features Section */}
        <div id="features" className="mt-32 grid md:grid-cols-3 gap-8">
          <div className="bg-gray-800 p-8 rounded-xl">
            <div className="text-4xl mb-4">📊</div>
            <h3 className="text-xl font-semibold mb-3">Full Data Extraction</h3>
            <p className="text-gray-400">
              Extract your complete message history, reactions, mentions, and more.
              Choose how far back to sync - from 30 days to unlimited.
            </p>
          </div>

          <div className="bg-gray-800 p-8 rounded-xl">
            <div className="text-4xl mb-4">🔒</div>
            <h3 className="text-xl font-semibold mb-3">Your Own Database</h3>
            <p className="text-gray-400">
              Each user gets a dedicated PostgreSQL database. Your data is completely
              isolated and never shared with other users.
            </p>
          </div>

          <div className="bg-gray-800 p-8 rounded-xl">
            <div className="text-4xl mb-4">⚡</div>
            <h3 className="text-xl font-semibold mb-3">SQL Query Editor</h3>
            <p className="text-gray-400">
              Write and execute SQL queries against your data. Full schema visibility,
              query history, and instant results.
            </p>
          </div>
        </div>

        {/* Pricing Section */}
        <div className="mt-32">
          <h2 className="text-3xl font-bold text-center mb-12">Simple Pricing</h2>
          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {/* Free Tier */}
            <div className="bg-gray-800 p-8 rounded-xl border border-gray-700">
              <h3 className="text-xl font-semibold mb-2">Free</h3>
              <p className="text-4xl font-bold mb-4">$0<span className="text-lg text-gray-400">/mo</span></p>
              <ul className="space-y-3 text-gray-300 mb-8">
                <li>✓ 500 MB storage</li>
                <li>✓ 30 days of history</li>
                <li>✓ 1,000 queries/month</li>
                <li>✓ Schema viewer</li>
              </ul>
              <Link
                href="/sign-up"
                className="block text-center border border-indigo-600 text-indigo-400 px-6 py-3 rounded-lg hover:bg-indigo-600 hover:text-white transition"
              >
                Get Started
              </Link>
            </div>

            {/* Pro Tier */}
            <div className="bg-indigo-900 p-8 rounded-xl border-2 border-indigo-500 relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-indigo-500 px-3 py-1 rounded-full text-sm">
                Popular
              </div>
              <h3 className="text-xl font-semibold mb-2">Pro</h3>
              <p className="text-4xl font-bold mb-4">$9<span className="text-lg text-gray-400">/mo</span></p>
              <ul className="space-y-3 text-gray-300 mb-8">
                <li>✓ 5 GB storage</li>
                <li>✓ 365 days of history</li>
                <li>✓ Unlimited queries</li>
                <li>✓ Priority support</li>
              </ul>
              <Link
                href="/sign-up"
                className="block text-center bg-indigo-600 px-6 py-3 rounded-lg hover:bg-indigo-700 transition"
              >
                Start Pro
              </Link>
            </div>

            {/* Team Tier */}
            <div className="bg-gray-800 p-8 rounded-xl border border-gray-700">
              <h3 className="text-xl font-semibold mb-2">Team</h3>
              <p className="text-4xl font-bold mb-4">$29<span className="text-lg text-gray-400">/mo</span></p>
              <ul className="space-y-3 text-gray-300 mb-8">
                <li>✓ 25 GB storage</li>
                <li>✓ Unlimited history</li>
                <li>✓ Unlimited queries</li>
                <li>✓ API access</li>
              </ul>
              <Link
                href="/sign-up"
                className="block text-center border border-indigo-600 text-indigo-400 px-6 py-3 rounded-lg hover:bg-indigo-600 hover:text-white transition"
              >
                Start Team
              </Link>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="container mx-auto px-6 py-12 mt-20 border-t border-gray-700">
        <div className="flex justify-between items-center">
          <p className="text-gray-400">© 2025 Discord Analytics. All rights reserved.</p>
          <div className="space-x-6">
            <Link href="/privacy" className="text-gray-400 hover:text-white transition">
              Privacy
            </Link>
            <Link href="/terms" className="text-gray-400 hover:text-white transition">
              Terms
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
