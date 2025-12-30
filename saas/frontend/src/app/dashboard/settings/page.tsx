"use client";

import { useUser } from "@clerk/nextjs";
import { useState, useEffect, useRef } from "react";
import { useApi, SubscriptionResponse } from "@/lib/api";

const ALLOWED_REDIRECT_DOMAINS = ["stripe.com", "checkout.stripe.com", "billing.stripe.com"];

function isValidRedirectUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return ALLOWED_REDIRECT_DOMAINS.some(
      (domain) => parsed.hostname === domain || parsed.hostname.endsWith("." + domain)
    );
  } catch {
    return false;
  }
}

interface Subscription {
  tier: string;
  status: string;
  current_period_end?: string;
  cancel_at_period_end: boolean;
}

export default function SettingsPage() {
  const { user } = useUser();
  const { apiRequest } = useApi();
  const apiRequestRef = useRef(apiRequest);
  apiRequestRef.current = apiRequest;

  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);

  useEffect(() => {
    const fetchSubscription = async () => {
      try {
        const response = await apiRequestRef.current<SubscriptionResponse>("/api/billing/subscription");
        setSubscription({
          tier: response.tier || "free",
          status: "active",
          current_period_end: response.current_period_end || undefined,
          cancel_at_period_end: false,
        });
      } catch (err) {
        console.error("Failed to fetch subscription:", err);
        setSubscription({ tier: "free", status: "active", cancel_at_period_end: false });
      } finally {
        setLoading(false);
      }
    };
    fetchSubscription();
  }, []);

  const handleUpgrade = async (plan: string) => {
    setUpgrading(plan);
    try {
      const data = await apiRequest<{ checkout_url: string }>(`/api/billing/checkout/${plan}`, {
        method: "POST",
      });
      if (!isValidRedirectUrl(data.checkout_url)) {
        console.error("Invalid checkout URL received:", data.checkout_url);
        alert("Invalid checkout URL. Please contact support.");
        setUpgrading(null);
        return;
      }
      window.location.href = data.checkout_url;
    } catch (err) {
      const error = err as { detail?: string };
      alert(error.detail || "Failed to start upgrade process");
      setUpgrading(null);
    }
  };

  const handleManageBilling = async () => {
    try {
      const data = await apiRequest<{ portal_url: string }>("/api/billing/portal", {
        method: "POST",
      });
      if (!isValidRedirectUrl(data.portal_url)) {
        console.error("Invalid portal URL received:", data.portal_url);
        alert("Invalid billing portal URL. Please contact support.");
        return;
      }
      window.location.href = data.portal_url;
    } catch (err) {
      const error = err as { detail?: string };
      alert(error.detail || "Failed to open billing portal");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loader-gold w-10 h-10" />
      </div>
    );
  }

  const tierConfig = {
    free: { label: "Starter", color: "bg-cream-500", textColor: "text-obsidian-900" },
    pro: { label: "Professional", color: "bg-gold-gradient", textColor: "text-obsidian-900" },
    team: { label: "Enterprise", color: "bg-gold-gradient", textColor: "text-obsidian-900" },
  };

  const currentTier = tierConfig[subscription?.tier as keyof typeof tierConfig] || tierConfig.free;

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="font-display text-3xl font-bold text-cream-100">Settings</h1>
        <p className="text-cream-500 mt-1">Manage your account and subscription</p>
      </div>

      {/* Account Info */}
      <div className="premium-card p-6 rounded-2xl">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-12 h-12 rounded-xl bg-gold-400/10 border border-gold-400/20 flex items-center justify-center">
            <svg className="w-6 h-6 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <div>
            <h2 className="font-display text-xl font-semibold text-cream-100">Account</h2>
            <p className="text-cream-500 text-sm">Your personal information</p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-cream-500 mb-1">Email</label>
            <p className="text-cream-100">{user?.primaryEmailAddress?.emailAddress || "—"}</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-cream-500 mb-1">Member Since</label>
            <p className="text-cream-100">
              {user?.createdAt ? new Date(user.createdAt).toLocaleDateString() : "—"}
            </p>
          </div>
        </div>
      </div>

      {/* Subscription */}
      <div className="premium-card p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gold-400/10 border border-gold-400/20 flex items-center justify-center">
              <svg className="w-6 h-6 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
              </svg>
            </div>
            <div>
              <h2 className="font-display text-xl font-semibold text-cream-100">Subscription</h2>
              <p className="text-cream-500 text-sm">Manage your plan</p>
            </div>
          </div>
          <div className={`px-4 py-1.5 rounded-full text-sm font-semibold ${currentTier.color} ${currentTier.textColor}`}>
            {currentTier.label}
          </div>
        </div>

        {subscription?.tier === "free" ? (
          <div className="grid md:grid-cols-2 gap-4">
            {/* Pro Plan */}
            <div className="p-5 rounded-xl bg-obsidian-700/50 border border-obsidian-600 hover:border-gold-400/30 transition-colors">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-display font-semibold text-cream-100">Professional</h3>
                  <p className="text-gold-400 font-bold text-2xl mt-1">
                    $9<span className="text-cream-500 text-sm font-normal">/mo</span>
                  </p>
                </div>
                <div className="w-10 h-10 rounded-lg bg-gold-400/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
              </div>
              <ul className="space-y-2 text-sm text-cream-400 mb-5">
                <li className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  5 GB storage
                </li>
                <li className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  365 days history
                </li>
                <li className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Unlimited queries
                </li>
              </ul>
              <button
                onClick={() => handleUpgrade("pro")}
                disabled={upgrading === "pro"}
                className="w-full btn-gold py-2.5 rounded-lg text-sm disabled:opacity-50"
              >
                {upgrading === "pro" ? (
                  <span className="flex items-center justify-center gap-2">
                    <div className="loader-gold w-4 h-4" />
                    Processing...
                  </span>
                ) : (
                  "Upgrade to Pro"
                )}
              </button>
            </div>

            {/* Team Plan */}
            <div className="p-5 rounded-xl bg-obsidian-700/50 border border-obsidian-600 hover:border-gold-400/30 transition-colors">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-display font-semibold text-cream-100">Enterprise</h3>
                  <p className="text-gold-400 font-bold text-2xl mt-1">
                    $29<span className="text-cream-500 text-sm font-normal">/mo</span>
                  </p>
                </div>
                <div className="w-10 h-10 rounded-lg bg-gold-400/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                </div>
              </div>
              <ul className="space-y-2 text-sm text-cream-400 mb-5">
                <li className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  25 GB storage
                </li>
                <li className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Unlimited history
                </li>
                <li className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  REST API access
                </li>
              </ul>
              <button
                onClick={() => handleUpgrade("team")}
                disabled={upgrading === "team"}
                className="w-full btn-outline-gold py-2.5 rounded-lg text-sm disabled:opacity-50"
              >
                {upgrading === "team" ? (
                  <span className="flex items-center justify-center gap-2">
                    <div className="loader-gold w-4 h-4" />
                    Processing...
                  </span>
                ) : (
                  "Upgrade to Enterprise"
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {subscription?.current_period_end && (
              <p className="text-cream-400">
                {subscription.cancel_at_period_end ? "Subscription ends on " : "Next billing date: "}
                <span className="text-cream-100 font-medium">
                  {new Date(subscription.current_period_end).toLocaleDateString()}
                </span>
              </p>
            )}
            <button
              onClick={handleManageBilling}
              className="btn-outline-gold px-5 py-2.5 rounded-lg text-sm"
            >
              Manage Billing
            </button>
          </div>
        )}
      </div>

      {/* Danger Zone */}
      <div className="premium-card p-6 rounded-2xl border-red-500/20">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
            <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div>
            <h2 className="font-display text-xl font-semibold text-red-400">Danger Zone</h2>
            <p className="text-cream-500 text-sm">Irreversible account actions</p>
          </div>
        </div>

        <p className="text-cream-400 text-sm mb-4">
          Deleting your account will permanently remove all your data, including your database,
          extraction history, and all stored Discord data. This action cannot be undone.
        </p>

        <button className="px-5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-colors text-sm font-medium">
          Delete Account
        </button>
      </div>
    </div>
  );
}
