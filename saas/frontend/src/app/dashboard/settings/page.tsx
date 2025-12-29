"use client";

import { useUser } from "@clerk/nextjs";
import { useState, useEffect, useRef } from "react";
import { useApi, SubscriptionResponse } from "@/lib/api";

// SECURITY: Allowed domains for redirect URLs (prevent open redirect attacks)
const ALLOWED_REDIRECT_DOMAINS = ["stripe.com", "checkout.stripe.com", "billing.stripe.com"];

function isValidRedirectUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return ALLOWED_REDIRECT_DOMAINS.some(
      (domain) =>
        parsed.hostname === domain || parsed.hostname.endsWith("." + domain)
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
        setSubscription({
          tier: "free",
          status: "active",
          cancel_at_period_end: false,
        });
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
      // SECURITY: Validate redirect URL before navigating
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
      // SECURITY: Validate redirect URL before navigating
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
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">Settings</h1>

      {/* Account Info */}
      <div className="bg-gray-800 p-6 rounded-xl mb-8">
        <h2 className="text-xl font-semibold mb-4">Account</h2>
        <div className="space-y-4">
          <div>
            <label className="text-gray-400 text-sm">Email</label>
            <p className="text-white">{user?.primaryEmailAddress?.emailAddress}</p>
          </div>
          <div>
            <label className="text-gray-400 text-sm">Member Since</label>
            <p className="text-white">
              {user?.createdAt
                ? new Date(user.createdAt).toLocaleDateString()
                : "N/A"}
            </p>
          </div>
        </div>
      </div>

      {/* Subscription */}
      <div className="bg-gray-800 p-6 rounded-xl mb-8">
        <h2 className="text-xl font-semibold mb-4">Subscription</h2>
        <div className="flex items-center gap-4 mb-6">
          <div className="bg-indigo-600 px-4 py-2 rounded-lg text-sm font-medium uppercase">
            {subscription?.tier}
          </div>
          <span className="text-gray-400">
            {subscription?.status === "active" ? "Active" : subscription?.status}
          </span>
        </div>

        {subscription?.tier === "free" ? (
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-gray-700 p-4 rounded-lg">
              <h3 className="font-semibold mb-2">Pro - $9/mo</h3>
              <ul className="text-gray-400 text-sm space-y-1 mb-4">
                <li>5 GB storage</li>
                <li>365 days history</li>
                <li>Unlimited queries</li>
              </ul>
              <button
                onClick={() => handleUpgrade("pro")}
                disabled={upgrading === "pro"}
                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-600 px-4 py-2 rounded-lg transition"
              >
                {upgrading === "pro" ? "Processing..." : "Upgrade to Pro"}
              </button>
            </div>

            <div className="bg-gray-700 p-4 rounded-lg">
              <h3 className="font-semibold mb-2">Team - $29/mo</h3>
              <ul className="text-gray-400 text-sm space-y-1 mb-4">
                <li>25 GB storage</li>
                <li>Unlimited history</li>
                <li>API access</li>
              </ul>
              <button
                onClick={() => handleUpgrade("team")}
                disabled={upgrading === "team"}
                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-600 px-4 py-2 rounded-lg transition"
              >
                {upgrading === "team" ? "Processing..." : "Upgrade to Team"}
              </button>
            </div>
          </div>
        ) : (
          <div>
            {subscription?.current_period_end && (
              <p className="text-gray-400 mb-4">
                {subscription.cancel_at_period_end
                  ? "Subscription ends on "
                  : "Next billing date: "}
                {new Date(subscription.current_period_end).toLocaleDateString()}
              </p>
            )}
            <button
              onClick={handleManageBilling}
              className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg transition"
            >
              Manage Billing
            </button>
          </div>
        )}
      </div>

      {/* Danger Zone */}
      <div className="bg-gray-800 p-6 rounded-xl border border-red-900">
        <h2 className="text-xl font-semibold mb-4 text-red-400">Danger Zone</h2>
        <p className="text-gray-400 mb-4">
          Deleting your account will permanently remove all your data, including
          your database and extraction history. This action cannot be undone.
        </p>
        <button className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg transition">
          Delete Account
        </button>
      </div>
    </div>
  );
}
