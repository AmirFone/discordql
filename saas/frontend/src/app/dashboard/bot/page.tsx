"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useApi, BotStatusResponse, BotConnectResponse, ExtractionJobResponse } from "@/lib/api";

// Helper to format time ago (handles UTC timestamps from database)
function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  // Database returns UTC timestamps without 'Z' suffix - add it for proper parsing
  const utcDateStr = dateStr.endsWith('Z') ? dateStr : dateStr.replace(' ', 'T') + 'Z';
  const date = new Date(utcDateStr);
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 0) return "just now"; // Handle edge case
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// Status indicator component
function StatusIndicator({ status }: { status: ExtractionJobResponse["status"] }) {
  const statusConfig = {
    pending: { color: "bg-yellow-500", pulse: true, label: "Starting..." },
    running: { color: "bg-blue-500", pulse: true, label: "Running" },
    completed: { color: "bg-green-500", pulse: false, label: "Completed" },
    failed: { color: "bg-red-500", pulse: false, label: "Failed" },
    cancelled: { color: "bg-gray-500", pulse: false, label: "Cancelled" },
  };
  const config = statusConfig[status];
  return (
    <div className="flex items-center gap-2">
      <span className={`w-3 h-3 rounded-full ${config.color} ${config.pulse ? "animate-pulse" : ""}`} />
      <span className="text-sm font-medium">{config.label}</span>
    </div>
  );
}

export default function BotConfigPage() {
  const { apiRequest } = useApi();
  const apiRequestRef = useRef(apiRequest);
  apiRequestRef.current = apiRequest;

  const [token, setToken] = useState("");
  const [guildId, setGuildId] = useState("");
  const [guildName, setGuildName] = useState("");
  const [syncDays, setSyncDays] = useState(30);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [botStatus, setBotStatus] = useState<BotStatusResponse | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(true);

  // Extraction job tracking
  const [extractionJobs, setExtractionJobs] = useState<ExtractionJobResponse[]>([]);
  const [isCancelling, setIsCancelling] = useState<string | null>(null);

  // Fetch extraction history
  const fetchExtractionHistory = useCallback(async () => {
    try {
      const jobs = await apiRequestRef.current<ExtractionJobResponse[]>("/api/extraction/history?limit=10");
      setExtractionJobs(jobs);
      return jobs;
    } catch (err) {
      console.log("Failed to fetch extraction history:", err);
      return [];
    }
  }, []);

  // Cancel extraction job
  const handleCancelExtraction = async (jobId: string) => {
    setIsCancelling(jobId);
    try {
      await apiRequest(`/api/extraction/cancel/${jobId}`, { method: "POST" });
      // Refresh the jobs list
      await fetchExtractionHistory();
      setSuccess("Extraction cancelled successfully");
    } catch (err) {
      const error = err as { detail?: string };
      setError(error.detail || "Failed to cancel extraction");
    } finally {
      setIsCancelling(null);
    }
  };

  // Fetch current bot status on load
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const status = await apiRequestRef.current<BotStatusResponse>("/api/bot/status");
        setBotStatus(status);
        if (status.connected && status.guild_id) {
          setGuildId(status.guild_id.toString());
          setGuildName(status.guild_name || "");
        }
      } catch (err) {
        // No bot connected yet is fine
        console.log("No bot connected:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchStatus();
    fetchExtractionHistory();
  }, [fetchExtractionHistory]);

  // Poll for updates when there's a running/pending job
  useEffect(() => {
    const hasActiveJob = extractionJobs.some(
      (job) => job.status === "pending" || job.status === "running"
    );

    if (!hasActiveJob) return;

    const pollInterval = setInterval(async () => {
      const updatedJobs = await fetchExtractionHistory();

      // Check if any job just completed/failed
      const previousActiveJobs = extractionJobs.filter(
        (job) => job.status === "pending" || job.status === "running"
      );

      for (const prevJob of previousActiveJobs) {
        const updatedJob = updatedJobs.find((j) => j.id === prevJob.id);
        if (updatedJob && updatedJob.status === "completed") {
          setSuccess(`Extraction completed! ${updatedJob.messages_extracted.toLocaleString()} messages extracted.`);
        } else if (updatedJob && updatedJob.status === "failed") {
          setError(`Extraction failed: ${updatedJob.error_message || "Unknown error"}`);
        }
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(pollInterval);
  }, [extractionJobs, fetchExtractionHistory]);

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setIsConnecting(true);

    try {
      const response = await apiRequest<BotConnectResponse>("/api/bot/connect", {
        method: "POST",
        body: {
          token,
          guild_id: guildId,  // Send as string to preserve precision for large Discord IDs
          guild_name: guildName,
        },
      });

      setBotStatus({
        connected: true,
        guild_id: response.guild_id,
        guild_name: response.guild_name,
        last_sync_at: response.last_sync_at,
      });
      setSuccess("Bot connected successfully!");
      setToken(""); // Clear token from memory for security
    } catch (err) {
      const error = err as { detail?: string };
      setError(error.detail || "Failed to connect bot");
    } finally {
      setIsConnecting(false);
    }
  };

  const handleExtract = async () => {
    setError("");
    setSuccess("");
    setIsExtracting(true);

    try {
      const response = await apiRequest<ExtractionJobResponse>("/api/extraction/start", {
        method: "POST",
        body: {
          guild_id: guildId,  // Send as string to preserve precision for large Discord IDs
          sync_days: syncDays,
        },
      });

      // Add the new job to the list immediately
      setExtractionJobs((prev) => [response, ...prev]);
      setSuccess(`Extraction started! Tracking progress below.`);
    } catch (err) {
      const error = err as { detail?: string };
      setError(error.detail || "Failed to start extraction");
    } finally {
      setIsExtracting(false);
    }
  };

  // Check if there's an active extraction
  const hasActiveExtraction = extractionJobs.some(
    (job) => job.status === "pending" || job.status === "running"
  );

  const handleDisconnect = async () => {
    if (!botStatus?.guild_id) return;

    try {
      await apiRequest(`/api/bot/disconnect?guild_id=${botStatus.guild_id}`, {
        method: "DELETE",
      });
      setBotStatus(null);
      setGuildId("");
      setGuildName("");
      setSuccess("Bot disconnected successfully");
    } catch (err) {
      const error = err as { detail?: string };
      setError(error.detail || "Failed to disconnect bot");
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
      <h1 className="text-3xl font-bold mb-8">Bot Configuration</h1>

      {/* Success/Error Messages */}
      {error && (
        <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded-lg mb-4">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-900/50 border border-green-500 text-green-200 px-4 py-3 rounded-lg mb-4">
          {success}
        </div>
      )}

      {/* Current Connection Status */}
      {botStatus?.connected && (
        <div className="bg-green-900/20 border border-green-700 p-6 rounded-xl mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-green-400">Bot Connected</h2>
              <p className="text-gray-300 mt-1">
                Server: <span className="font-medium">{botStatus.guild_name}</span> (ID: {botStatus.guild_id})
              </p>
              {botStatus.last_sync_at && (
                <p className="text-gray-400 text-sm">
                  Last synced: {new Date(botStatus.last_sync_at).toLocaleString()}
                </p>
              )}
            </div>
            <button
              onClick={handleDisconnect}
              className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg text-sm transition"
            >
              Disconnect
            </button>
          </div>
        </div>
      )}

      {/* Connection Form */}
      <div className="bg-gray-800 p-6 rounded-xl mb-8">
        <h2 className="text-xl font-semibold mb-4">
          {botStatus?.connected ? "Update Bot Connection" : "Connect Your Discord Bot"}
        </h2>
        <p className="text-gray-400 mb-6">
          Enter your Discord bot token to connect and extract server data.
          Your token is encrypted before storage.
        </p>

        <form onSubmit={handleConnect} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Bot Token
            </label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Enter your Discord bot token"
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
              required
            />
            <p className="text-gray-500 text-sm mt-1">
              Get this from the Discord Developer Portal
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                Server (Guild) ID
              </label>
              <input
                type="text"
                value={guildId}
                onChange={(e) => setGuildId(e.target.value)}
                placeholder="e.g., 123456789012345678"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-2">
                Server Name
              </label>
              <input
                type="text"
                value={guildName}
                onChange={(e) => setGuildName(e.target.value)}
                placeholder="e.g., My Discord Server"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isConnecting}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-600 px-6 py-3 rounded-lg transition"
          >
            {isConnecting ? "Connecting..." : botStatus?.connected ? "Update Connection" : "Connect Bot"}
          </button>
        </form>
      </div>

      {/* Extraction Settings */}
      {botStatus?.connected && (
        <div className="bg-gray-800 p-6 rounded-xl mb-8">
          <h2 className="text-xl font-semibold mb-4">Start Extraction</h2>
          <p className="text-gray-400 mb-6">
            Choose how far back to extract message history.
          </p>

          <div className="mb-6">
            <label className="block text-sm text-gray-400 mb-2">
              Sync History (Days)
            </label>
            <select
              value={syncDays}
              onChange={(e) => setSyncDays(parseInt(e.target.value))}
              className="w-full md:w-64 bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value={180}>Last 180 days</option>
              <option value={365}>Last 365 days</option>
            </select>
            <p className="text-gray-500 text-sm mt-1">
              Free tier: up to 30 days | Pro: up to 365 days | Team: unlimited
            </p>
          </div>

          <button
            onClick={handleExtract}
            disabled={isExtracting || hasActiveExtraction}
            className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 px-6 py-3 rounded-lg transition"
          >
            {isExtracting ? "Starting..." : hasActiveExtraction ? "Extraction in Progress..." : "Start Extraction"}
          </button>
        </div>
      )}

      {/* Extraction Status Section */}
      {botStatus?.connected && extractionJobs.length > 0 && (
        <div className="bg-gray-800 p-6 rounded-xl mb-8">
          <h2 className="text-xl font-semibold mb-4">Extraction Status</h2>
          <div className="space-y-4">
            {extractionJobs.map((job) => (
              <div
                key={job.id}
                className={`border rounded-lg p-4 ${
                  job.status === "running" || job.status === "pending"
                    ? "border-blue-500/50 bg-blue-900/20"
                    : job.status === "completed"
                    ? "border-green-500/50 bg-green-900/20"
                    : job.status === "failed"
                    ? "border-red-500/50 bg-red-900/20"
                    : "border-gray-600 bg-gray-700/50"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <StatusIndicator status={job.status} />
                  <span className="text-sm text-gray-400">
                    {job.sync_days}-day extraction
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-400">Messages: </span>
                    <span className="font-medium text-white">
                      {job.messages_extracted.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400">Started: </span>
                    <span className="text-white">{timeAgo(job.started_at)}</span>
                  </div>
                  {job.completed_at && (
                    <div>
                      <span className="text-gray-400">Completed: </span>
                      <span className="text-white">{timeAgo(job.completed_at)}</span>
                    </div>
                  )}
                  {job.error_message && (
                    <div className="col-span-2">
                      <span className="text-red-400">Error: </span>
                      <span className="text-red-300">{job.error_message}</span>
                    </div>
                  )}
                </div>

                {(job.status === "pending" || job.status === "running") && (
                  <div className="mt-4">
                    <button
                      onClick={() => handleCancelExtraction(job.id)}
                      disabled={isCancelling === job.id}
                      className="bg-red-600/80 hover:bg-red-600 disabled:bg-gray-600 px-4 py-2 rounded text-sm transition"
                    >
                      {isCancelling === job.id ? "Cancelling..." : "Cancel"}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Help Section */}
      <div className="bg-gray-800 p-6 rounded-xl">
        <h2 className="text-xl font-semibold mb-4">How to Get Your Bot Token</h2>
        <ol className="list-decimal list-inside space-y-2 text-gray-300">
          <li>Go to the <a href="https://discord.com/developers/applications" target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:underline">Discord Developer Portal</a></li>
          <li>Create a new application or select an existing one</li>
          <li>Go to the &quot;Bot&quot; section and click &quot;Add Bot&quot;</li>
          <li>Click &quot;Reset Token&quot; and copy your bot token</li>
          <li>Enable &quot;Message Content Intent&quot; under Privileged Gateway Intents</li>
          <li>Invite the bot to your server with &quot;Read Messages&quot; permission</li>
        </ol>
      </div>
    </div>
  );
}
