"use client";

import { useUser } from "@clerk/nextjs";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useApi, BotStatusResponse, SubscriptionResponse } from "@/lib/api";

interface UsageStats {
  storage_used_mb: number;
  storage_limit_mb: number;
  queries_this_month: number;
  queries_limit: number;
  extractions_this_month: number;
}

export default function DashboardPage() {
  const { user } = useUser();
  const { apiRequest } = useApi();
  const apiRequestRef = useRef(apiRequest);
  apiRequestRef.current = apiRequest;

  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [botStatus, setBotStatus] = useState<BotStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [botResponse, subscriptionResponse] = await Promise.allSettled([
          apiRequestRef.current<BotStatusResponse>("/api/bot/status"),
          apiRequestRef.current<SubscriptionResponse>("/api/billing/subscription"),
        ]);

        if (botResponse.status === "fulfilled") {
          setBotStatus(botResponse.value);
        }

        if (subscriptionResponse.status === "fulfilled") {
          const sub = subscriptionResponse.value;
          setUsage({
            storage_used_mb: (sub.storage_used_bytes || 0) / (1024 * 1024),
            storage_limit_mb: (sub.storage_limit_bytes || 500 * 1024 * 1024) / (1024 * 1024),
            queries_this_month: sub.queries_this_month || 0,
            queries_limit: sub.queries_limit || 1000,
            extractions_this_month: 0,
          });
        } else {
          setUsage({
            storage_used_mb: 0,
            storage_limit_mb: 500,
            queries_this_month: 0,
            queries_limit: 1000,
            extractions_this_month: 0,
          });
        }
      } catch (err) {
        console.error("Failed to fetch dashboard data:", err);
        setBotStatus({ connected: false, guild_id: null, guild_name: null, last_sync_at: null });
        setUsage({
          storage_used_mb: 0,
          storage_limit_mb: 500,
          queries_this_month: 0,
          queries_limit: 1000,
          extractions_this_month: 0,
        });
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loader-gold w-10 h-10" />
      </div>
    );
  }

  const storagePercentage = Math.min(
    ((usage?.storage_used_mb || 0) / (usage?.storage_limit_mb || 1)) * 100,
    100
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold text-cream-100">
            Welcome back, <span className="text-gold-gradient">{user?.firstName || "there"}</span>
          </h1>
          <p className="text-cream-500 mt-1">
            Here&apos;s an overview of your Discord Analytics
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/query"
            className="btn-outline-gold px-4 py-2 rounded-lg text-sm"
          >
            Run Query
          </Link>
          <Link
            href="/dashboard/bot"
            className="btn-gold px-4 py-2 rounded-lg text-sm"
          >
            Start Extraction
          </Link>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid md:grid-cols-3 gap-6">
        {/* Storage Card */}
        <div className="premium-card p-6 rounded-2xl">
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-xl bg-gold-400/10 border border-gold-400/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
              </svg>
            </div>
            <span className="text-xs text-cream-500 uppercase tracking-wider">Storage</span>
          </div>
          <div className="mb-2">
            <span className="font-display text-3xl font-bold text-cream-100">
              {usage?.storage_used_mb.toFixed(1)}
            </span>
            <span className="text-cream-500 text-sm ml-1">MB</span>
          </div>
          <div className="relative h-2 bg-obsidian-700 rounded-full overflow-hidden mb-2">
            <div
              className="absolute inset-y-0 left-0 bg-gradient-to-r from-gold-500 to-gold-400 rounded-full transition-all duration-500"
              style={{ width: `${storagePercentage}%` }}
            />
          </div>
          <p className="text-cream-500 text-xs">
            {storagePercentage.toFixed(0)}% of {usage?.storage_limit_mb} MB used
          </p>
        </div>

        {/* Queries Card */}
        <div className="premium-card p-6 rounded-2xl">
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-xl bg-gold-400/10 border border-gold-400/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <span className="text-xs text-cream-500 uppercase tracking-wider">Queries</span>
          </div>
          <div className="mb-2">
            <span className="font-display text-3xl font-bold text-cream-100">
              {usage?.queries_this_month.toLocaleString()}
            </span>
          </div>
          <p className="text-cream-500 text-xs">
            of {usage?.queries_limit.toLocaleString()} queries this month
          </p>
        </div>

        {/* Extractions Card */}
        <div className="premium-card p-6 rounded-2xl">
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-xl bg-gold-400/10 border border-gold-400/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
            </div>
            <span className="text-xs text-cream-500 uppercase tracking-wider">Extractions</span>
          </div>
          <div className="mb-2">
            <span className="font-display text-3xl font-bold text-cream-100">
              {usage?.extractions_this_month}
            </span>
          </div>
          <p className="text-cream-500 text-xs">
            extractions this month
          </p>
        </div>
      </div>

      {/* Bot Status */}
      <div className="premium-card p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h2 className="font-display text-xl font-semibold text-cream-100">Bot Connection</h2>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
            botStatus?.connected
              ? "bg-green-500/10 text-green-400 border border-green-500/20"
              : "bg-obsidian-700 text-cream-500 border border-obsidian-600"
          }`}>
            <span className={`w-2 h-2 rounded-full ${
              botStatus?.connected ? "bg-green-400 animate-pulse" : "bg-cream-600"
            }`} />
            {botStatus?.connected ? "Connected" : "Disconnected"}
          </div>
        </div>

        {botStatus?.connected ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gold-400/10 border border-gold-400/20 flex items-center justify-center">
                <svg className="w-6 h-6 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <div>
                <p className="font-medium text-cream-100">{botStatus.guild_name}</p>
                <p className="text-sm text-cream-500">
                  ID: {botStatus.guild_id}
                  {botStatus.last_sync_at && (
                    <span className="ml-3">
                      Last sync: {new Date(botStatus.last_sync_at).toLocaleString()}
                    </span>
                  )}
                </p>
              </div>
            </div>
            <Link
              href="/dashboard/bot"
              className="btn-outline-gold px-4 py-2 rounded-lg text-sm"
            >
              Manage Bot
            </Link>
          </div>
        ) : (
          <div className="text-center py-8">
            <div className="w-16 h-16 rounded-2xl bg-obsidian-700 border border-obsidian-600 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-cream-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <p className="text-cream-400 mb-4">No Discord bot connected yet</p>
            <Link
              href="/dashboard/bot"
              className="btn-gold px-6 py-2.5 rounded-lg inline-block"
            >
              Connect Your Bot
            </Link>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="font-display text-xl font-semibold text-cream-100 mb-4">Quick Actions</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {[
            {
              href: "/dashboard/query",
              icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              ),
              label: "SQL Editor",
              description: "Write and execute queries",
            },
            {
              href: "/dashboard/bot",
              icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              ),
              label: "Sync Data",
              description: "Start a new extraction",
            },
            {
              href: "/dashboard/settings",
              icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
              ),
              label: "Upgrade Plan",
              description: "Unlock more features",
            },
          ].map((action, i) => (
            <Link
              key={i}
              href={action.href}
              className="premium-card p-5 rounded-xl flex items-center gap-4 hover:border-gold-400/30 transition-all duration-200 group"
            >
              <div className="w-12 h-12 rounded-xl bg-obsidian-700 border border-obsidian-600 flex items-center justify-center text-cream-400 group-hover:bg-gold-400/10 group-hover:border-gold-400/20 group-hover:text-gold-400 transition-colors">
                {action.icon}
              </div>
              <div>
                <p className="font-medium text-cream-100 group-hover:text-gold-400 transition-colors">
                  {action.label}
                </p>
                <p className="text-sm text-cream-500">{action.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
