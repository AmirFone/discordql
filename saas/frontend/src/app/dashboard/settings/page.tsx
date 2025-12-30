"use client";

import { useUser } from "@clerk/nextjs";

export default function SettingsPage() {
  const { user } = useUser();

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="font-display text-3xl font-bold text-ink-800">Settings</h1>
        <p className="text-ink-500 mt-1">Manage your account</p>
      </div>

      {/* Account Info */}
      <div className="premium-card p-6 rounded-2xl">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-12 h-12 rounded-xl bg-gold-400/15 border border-gold-400/30 flex items-center justify-center">
            <svg className="w-6 h-6 text-gold-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <div>
            <h2 className="font-display text-xl font-semibold text-ink-800">Account</h2>
            <p className="text-ink-500 text-sm">Your personal information</p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-ink-500 mb-1">Email</label>
            <p className="text-ink-800">{user?.primaryEmailAddress?.emailAddress || "—"}</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink-500 mb-1">Member Since</label>
            <p className="text-ink-800">
              {user?.createdAt ? new Date(user.createdAt).toLocaleDateString() : "—"}
            </p>
          </div>
        </div>
      </div>

      {/* Plan */}
      <div className="premium-card p-6 rounded-2xl">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gold-400/15 border border-gold-400/30 flex items-center justify-center">
            <svg className="w-6 h-6 text-gold-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
            </svg>
          </div>
          <div>
            <h2 className="font-display text-xl font-semibold text-ink-800">Plan</h2>
            <p className="text-ink-500 text-sm">Free forever - all features included</p>
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="premium-card p-6 rounded-2xl border-red-500/20">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
            <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div>
            <h2 className="font-display text-xl font-semibold text-red-600">Danger Zone</h2>
            <p className="text-ink-500 text-sm">Irreversible account actions</p>
          </div>
        </div>

        <p className="text-ink-600 text-sm mb-4">
          Deleting your account will permanently remove all your data, including your database,
          extraction history, and all stored Discord data. This action cannot be undone.
        </p>

        <button className="px-5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 hover:bg-red-500/20 transition-colors text-sm font-medium">
          Delete Account
        </button>
      </div>
    </div>
  );
}
