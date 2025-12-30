"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useApi, SubscriptionResponse } from "@/lib/api";
import PricingCard, { PricingToggle, pricingPlans } from "./PricingCard";

interface UsageData {
  storage_used_mb: number;
  storage_limit_mb: number;
  queries_this_month: number;
  queries_limit: number;
  extractions_this_month: number;
}

export default function BillingSection() {
  const { apiRequest } = useApi();
  const apiRequestRef = useRef(apiRequest);
  apiRequestRef.current = apiRequest;

  const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgradeLoading, setUpgradeLoading] = useState<string | null>(null);
  const [interval, setInterval] = useState<"month" | "year">("month");

  const fetchBillingData = useCallback(async () => {
    try {
      const [subResponse, usageResponse] = await Promise.allSettled([
        apiRequestRef.current<SubscriptionResponse>("/api/billing/subscription"),
        apiRequestRef.current<UsageData>("/api/billing/usage"),
      ]);

      if (subResponse.status === "fulfilled") {
        setSubscription(subResponse.value);
      }

      if (usageResponse.status === "fulfilled") {
        setUsage(usageResponse.value);
      }
    } catch (error) {
      console.error("Failed to fetch billing data:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBillingData();
  }, [fetchBillingData]);

  const handleUpgrade = async (plan: "pro" | "team") => {
    setUpgradeLoading(plan);
    try {
      const response = await apiRequest<{ checkout_url: string }>(`/api/billing/checkout/${plan}`, {
        method: "POST",
      });

      if (response.checkout_url) {
        window.location.href = response.checkout_url;
      }
    } catch (error) {
      console.error("Failed to create checkout session:", error);
      alert("Failed to start upgrade process. Please try again.");
    } finally {
      setUpgradeLoading(null);
    }
  };

  const handleManageBilling = async () => {
    try {
      const response = await apiRequest<{ portal_url: string }>("/api/billing/portal", {
        method: "POST",
      });

      if (response.portal_url) {
        window.location.href = response.portal_url;
      }
    } catch (error) {
      console.error("Failed to create portal session:", error);
      alert("Failed to open billing portal. Please try again.");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="loader-gold w-8 h-8" />
      </div>
    );
  }

  const currentTier = subscription?.tier || "free";

  return (
    <div className="space-y-8">
      {/* Current Subscription */}
      <div className="premium-card rounded-xl p-6">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-display text-lg font-semibold text-cream-100 mb-1">
              Current Subscription
            </h3>
            <div className="flex items-center gap-3">
              <span
                className={`px-3 py-1 rounded-full text-sm font-medium ${
                  currentTier === "free"
                    ? "bg-cream-500/10 text-cream-400 border border-cream-500/20"
                    : currentTier === "pro"
                    ? "bg-gold-400/10 text-gold-400 border border-gold-400/20"
                    : "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                }`}
              >
                {pricingPlans[currentTier as keyof typeof pricingPlans]?.name || "Starter"}
              </span>
              <span className="px-2 py-0.5 rounded-md text-xs bg-green-500/10 text-green-400">
                Active
              </span>
            </div>
            {subscription?.current_period_end && (
              <p className="text-cream-500 text-sm mt-2">
                Renews on{" "}
                {new Date(subscription.current_period_end).toLocaleDateString()}
              </p>
            )}
          </div>
          {currentTier !== "free" && (
            <button
              onClick={handleManageBilling}
              className="btn-outline-gold px-4 py-2 rounded-lg text-sm"
            >
              Manage Billing
            </button>
          )}
        </div>
      </div>

      {/* Usage Stats */}
      {usage && (
        <div className="premium-card rounded-xl p-6">
          <h3 className="font-display text-lg font-semibold text-cream-100 mb-6">
            Usage This Month
          </h3>
          <div className="grid md:grid-cols-3 gap-6">
            {/* Storage */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-cream-400 text-sm">Storage</span>
                <span className="text-cream-300 text-sm font-medium">
                  {usage.storage_used_mb.toFixed(1)} / {usage.storage_limit_mb} MB
                </span>
              </div>
              <div className="h-2 bg-obsidian-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-gold-500 to-gold-400 rounded-full transition-all"
                  style={{
                    width: `${Math.min((usage.storage_used_mb / usage.storage_limit_mb) * 100, 100)}%`,
                  }}
                />
              </div>
            </div>

            {/* Queries */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-cream-400 text-sm">Queries</span>
                <span className="text-cream-300 text-sm font-medium">
                  {usage.queries_this_month.toLocaleString()}
                  {usage.queries_limit < 999999 && ` / ${usage.queries_limit.toLocaleString()}`}
                </span>
              </div>
              <div className="h-2 bg-obsidian-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-gold-500 to-gold-400 rounded-full transition-all"
                  style={{
                    width: `${
                      usage.queries_limit < 999999
                        ? Math.min((usage.queries_this_month / usage.queries_limit) * 100, 100)
                        : 10
                    }%`,
                  }}
                />
              </div>
            </div>

            {/* Extractions */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-cream-400 text-sm">Extractions</span>
                <span className="text-cream-300 text-sm font-medium">
                  {usage.extractions_this_month}
                </span>
              </div>
              <div className="h-2 bg-obsidian-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-gold-500 to-gold-400 rounded-full transition-all"
                  style={{ width: `${Math.min(usage.extractions_this_month * 10, 100)}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Pricing Cards */}
      <div>
        <div className="text-center mb-8">
          <h3 className="font-display text-2xl font-bold text-cream-100 mb-2">
            {currentTier === "free" ? "Upgrade Your Plan" : "Available Plans"}
          </h3>
          <p className="text-cream-500">
            {currentTier === "free"
              ? "Unlock more features and higher limits"
              : "Switch plans or manage your subscription"}
          </p>
        </div>

        <div className="flex justify-center mb-8">
          <PricingToggle interval={interval} onChange={setInterval} />
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <PricingCard
            name={pricingPlans.free.name}
            price={0}
            interval="month"
            description={pricingPlans.free.description}
            features={pricingPlans.free.features}
            isCurrentPlan={currentTier === "free"}
            onSelect={() => {}}
            buttonText="Current Plan"
          />
          <PricingCard
            name={pricingPlans.pro.name}
            price={interval === "month" ? pricingPlans.pro.price : Math.round(pricingPlans.pro.yearlyPrice / 12)}
            interval={interval}
            description={pricingPlans.pro.description}
            features={pricingPlans.pro.features}
            isPopular={true}
            isCurrentPlan={currentTier === "pro"}
            onSelect={() => handleUpgrade("pro")}
            buttonText={currentTier === "pro" ? "Current Plan" : "Upgrade to Pro"}
            loading={upgradeLoading === "pro"}
          />
          <PricingCard
            name={pricingPlans.team.name}
            price={interval === "month" ? pricingPlans.team.price : Math.round(pricingPlans.team.yearlyPrice / 12)}
            interval={interval}
            description={pricingPlans.team.description}
            features={pricingPlans.team.features}
            isCurrentPlan={currentTier === "team"}
            onSelect={() => handleUpgrade("team")}
            buttonText={currentTier === "team" ? "Current Plan" : "Upgrade to Enterprise"}
            loading={upgradeLoading === "team"}
          />
        </div>
      </div>

      {/* FAQ */}
      <div className="premium-card rounded-xl p-6">
        <h3 className="font-display text-lg font-semibold text-cream-100 mb-4">
          Frequently Asked Questions
        </h3>
        <div className="space-y-4">
          <details className="group">
            <summary className="flex items-center justify-between cursor-pointer list-none">
              <span className="text-cream-200 font-medium">Can I cancel anytime?</span>
              <svg className="w-5 h-5 text-cream-500 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </summary>
            <p className="text-cream-500 text-sm mt-2">
              Yes! You can cancel your subscription at any time. You&apos;ll continue to have access until the end of your billing period.
            </p>
          </details>
          <details className="group">
            <summary className="flex items-center justify-between cursor-pointer list-none">
              <span className="text-cream-200 font-medium">What happens to my data if I downgrade?</span>
              <svg className="w-5 h-5 text-cream-500 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </summary>
            <p className="text-cream-500 text-sm mt-2">
              Your data is preserved when you downgrade. However, if you exceed the free tier limits, you won&apos;t be able to run new extractions until you upgrade or delete some data.
            </p>
          </details>
          <details className="group">
            <summary className="flex items-center justify-between cursor-pointer list-none">
              <span className="text-cream-200 font-medium">Do you offer refunds?</span>
              <svg className="w-5 h-5 text-cream-500 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </summary>
            <p className="text-cream-500 text-sm mt-2">
              We offer a 14-day money-back guarantee. If you&apos;re not satisfied, contact support within 14 days for a full refund.
            </p>
          </details>
        </div>
      </div>
    </div>
  );
}
