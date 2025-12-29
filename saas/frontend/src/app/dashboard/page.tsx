"use client";

import { useUser } from "@clerk/nextjs";
import { useEffect, useState, useRef } from "react";
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
        // Fetch bot status and subscription in parallel
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
            extractions_this_month: 0, // TODO: Add to API
          });
        } else {
          // Set defaults for free tier if subscription fetch fails
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
        // Set defaults
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
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">
        Welcome back, {user?.firstName || "there"}!
      </h1>

      {/* Stats Grid */}
      <div className="grid md:grid-cols-3 gap-6 mb-8">
        {/* Storage */}
        <div className="bg-gray-800 p-6 rounded-xl">
          <h3 className="text-gray-400 text-sm mb-2">Storage Used</h3>
          <p className="text-2xl font-bold">
            {usage?.storage_used_mb.toFixed(1)} MB
          </p>
          <div className="mt-2 bg-gray-700 rounded-full h-2">
            <div
              className="bg-indigo-600 rounded-full h-2"
              style={{
                width: `${Math.min(((usage?.storage_used_mb || 0) / (usage?.storage_limit_mb || 1)) * 100, 100)}%`,
              }}
            />
          </div>
          <p className="text-gray-500 text-sm mt-1">
            of {usage?.storage_limit_mb} MB
          </p>
        </div>

        {/* Queries */}
        <div className="bg-gray-800 p-6 rounded-xl">
          <h3 className="text-gray-400 text-sm mb-2">Queries This Month</h3>
          <p className="text-2xl font-bold">{usage?.queries_this_month}</p>
          <p className="text-gray-500 text-sm mt-1">
            of {usage?.queries_limit} queries
          </p>
        </div>

        {/* Extractions */}
        <div className="bg-gray-800 p-6 rounded-xl">
          <h3 className="text-gray-400 text-sm mb-2">Extractions</h3>
          <p className="text-2xl font-bold">{usage?.extractions_this_month}</p>
          <p className="text-gray-500 text-sm mt-1">this month</p>
        </div>
      </div>

      {/* Bot Status */}
      <div className="bg-gray-800 p-6 rounded-xl mb-8">
        <h2 className="text-xl font-semibold mb-4">Bot Connection</h2>
        {botStatus?.connected ? (
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 bg-green-500 rounded-full" />
            <span>Connected to {botStatus.guild_name}</span>
            {botStatus.last_sync_at && (
              <span className="text-gray-500 text-sm">
                Last sync: {new Date(botStatus.last_sync_at).toLocaleString()}
              </span>
            )}
          </div>
        ) : (
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-3 h-3 bg-gray-500 rounded-full" />
              <span className="text-gray-400">No bot connected</span>
            </div>
            <a
              href="/dashboard/bot"
              className="inline-block bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg transition"
            >
              Connect Your Bot
            </a>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="bg-gray-800 p-6 rounded-xl">
        <h2 className="text-xl font-semibold mb-4">Quick Actions</h2>
        <div className="grid md:grid-cols-3 gap-4">
          <a
            href="/dashboard/query"
            className="bg-gray-700 hover:bg-gray-600 p-4 rounded-lg transition text-center"
          >
            <div className="text-2xl mb-2">SQL</div>
            <div>Run SQL Query</div>
          </a>
          <a
            href="/dashboard/bot"
            className="bg-gray-700 hover:bg-gray-600 p-4 rounded-lg transition text-center"
          >
            <div className="text-2xl mb-2">SYNC</div>
            <div>Start Extraction</div>
          </a>
          <a
            href="/dashboard/settings"
            className="bg-gray-700 hover:bg-gray-600 p-4 rounded-lg transition text-center"
          >
            <div className="text-2xl mb-2">PRO</div>
            <div>Upgrade Plan</div>
          </a>
        </div>
      </div>
    </div>
  );
}
