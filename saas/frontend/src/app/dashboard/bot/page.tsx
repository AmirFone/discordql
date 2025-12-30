"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useApi, BotStatusResponse, BotConnectResponse, ExtractionJobResponse } from "@/lib/api";

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  const utcDateStr = dateStr.endsWith('Z') ? dateStr : dateStr.replace(' ', 'T') + 'Z';
  const date = new Date(utcDateStr);
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 0) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function StatusIndicator({ status }: { status: ExtractionJobResponse["status"] }) {
  const statusConfig = {
    pending: { color: "bg-yellow-500", ringColor: "ring-yellow-500/30", label: "Starting...", pulse: true },
    running: { color: "bg-blue-500", ringColor: "ring-blue-500/30", label: "Running", pulse: true },
    completed: { color: "bg-green-500", ringColor: "ring-green-500/30", label: "Completed", pulse: false },
    failed: { color: "bg-red-500", ringColor: "ring-red-500/30", label: "Failed", pulse: false },
    cancelled: { color: "bg-cream-600", ringColor: "ring-cream-600/30", label: "Cancelled", pulse: false },
  };
  const config = statusConfig[status];
  return (
    <div className="flex items-center gap-2">
      <span className={`w-2.5 h-2.5 rounded-full ${config.color} ring-4 ${config.ringColor} ${config.pulse ? "animate-pulse" : ""}`} />
      <span className="text-sm font-medium text-ink-700">{config.label}</span>
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

  const [extractionJobs, setExtractionJobs] = useState<ExtractionJobResponse[]>([]);
  const [isCancelling, setIsCancelling] = useState<string | null>(null);

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

  const handleCancelExtraction = async (jobId: string) => {
    setIsCancelling(jobId);
    try {
      await apiRequest(`/api/extraction/cancel/${jobId}`, { method: "POST" });
      await fetchExtractionHistory();
      setSuccess("Extraction cancelled successfully");
    } catch (err) {
      const error = err as { detail?: string };
      setError(error.detail || "Failed to cancel extraction");
    } finally {
      setIsCancelling(null);
    }
  };

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const status = await apiRequestRef.current<BotStatusResponse>("/api/bot/status");
        setBotStatus(status);
        if (status.connected && status.guild_id) {
          setGuildId(status.guild_id);  // Already a string from API
          setGuildName(status.guild_name || "");
        }
      } catch (err) {
        console.log("No bot connected:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchStatus();
    fetchExtractionHistory();
  }, [fetchExtractionHistory]);

  useEffect(() => {
    const hasActiveJob = extractionJobs.some(
      (job) => job.status === "pending" || job.status === "running"
    );
    if (!hasActiveJob) return;

    const pollInterval = setInterval(async () => {
      const updatedJobs = await fetchExtractionHistory();
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
    }, 3000);

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
        body: { token, guild_id: guildId, guild_name: guildName },
      });

      setBotStatus({
        connected: true,
        guild_id: response.guild_id,
        guild_name: response.guild_name,
        last_sync_at: response.last_sync_at,
      });
      setSuccess("Bot connected successfully!");
      setToken("");
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
        body: { guild_id: guildId, sync_days: syncDays },
      });
      setExtractionJobs((prev) => [response, ...prev]);
      setSuccess(`Extraction started! Tracking progress below.`);
    } catch (err) {
      const error = err as { detail?: string };
      setError(error.detail || "Failed to start extraction");
    } finally {
      setIsExtracting(false);
    }
  };

  const hasActiveExtraction = extractionJobs.some(
    (job) => job.status === "pending" || job.status === "running"
  );

  const handleDisconnect = async () => {
    if (!botStatus?.guild_id) return;
    try {
      await apiRequest(`/api/bot/disconnect?guild_id=${botStatus.guild_id}`, { method: "DELETE" });
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
        <div className="loader-gold w-10 h-10" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-display text-3xl font-bold text-ink-800">Bot Configuration</h1>
        <p className="text-ink-500 mt-1">Connect and manage your Discord bot</p>
      </div>

      {/* Messages */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20">
          <svg className="w-5 h-5 text-red-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-red-300">{error}</span>
        </div>
      )}
      {success && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-green-500/10 border border-green-500/20">
          <svg className="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-green-300">{success}</span>
        </div>
      )}

      {/* Current Connection Status */}
      {botStatus?.connected && (
        <div className="gold-accent-card p-6 rounded-2xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gold-400/20 flex items-center justify-center">
                <svg className="w-6 h-6 text-gold-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  <span className="font-semibold text-gold-600">Bot Connected</span>
                </div>
                <p className="text-ink-600 mt-0.5">
                  {botStatus.guild_name} <span className="text-ink-500">({botStatus.guild_id})</span>
                </p>
                {botStatus.last_sync_at && (
                  <p className="text-ink-500 text-sm mt-1">
                    Last synced: {new Date(botStatus.last_sync_at).toLocaleString()}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={handleDisconnect}
              className="px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-colors text-sm font-medium"
            >
              Disconnect
            </button>
          </div>
        </div>
      )}

      {/* Connection Form */}
      <div className="premium-card p-6 rounded-2xl">
        <div className="mb-6">
          <h2 className="font-display text-xl font-semibold text-ink-800">
            {botStatus?.connected ? "Update Bot Connection" : "Connect Your Discord Bot"}
          </h2>
          <p className="text-ink-500 text-sm mt-1">
            Enter your Discord bot token to connect and extract server data. Your token is encrypted before storage.
          </p>
        </div>

        <form onSubmit={handleConnect} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-ink-600 mb-2">Bot Token</label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Enter your Discord bot token"
              className="input-dark w-full px-4 py-3 rounded-xl"
              required
            />
            <p className="text-ink-500 text-xs mt-2">
              Get this from the <a href="https://discord.com/developers/applications" target="_blank" rel="noopener noreferrer" className="text-gold-600 hover:text-gold-600 underline">Discord Developer Portal</a>
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-ink-600 mb-2">Server (Guild) ID</label>
              <input
                type="text"
                value={guildId}
                onChange={(e) => setGuildId(e.target.value)}
                placeholder="e.g., 123456789012345678"
                className="input-dark w-full px-4 py-3 rounded-xl"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-ink-600 mb-2">Server Name</label>
              <input
                type="text"
                value={guildName}
                onChange={(e) => setGuildName(e.target.value)}
                placeholder="e.g., My Discord Server"
                className="input-dark w-full px-4 py-3 rounded-xl"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isConnecting}
            className="btn-gold px-6 py-3 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isConnecting ? (
              <span className="flex items-center gap-2">
                <div className="loader-gold w-4 h-4" />
                Connecting...
              </span>
            ) : botStatus?.connected ? (
              "Update Connection"
            ) : (
              "Connect Bot"
            )}
          </button>
        </form>
      </div>

      {/* Extraction Settings */}
      {botStatus?.connected && (
        <div className="premium-card p-6 rounded-2xl">
          <div className="mb-6">
            <h2 className="font-display text-xl font-semibold text-ink-800">Start Extraction</h2>
            <p className="text-ink-500 text-sm mt-1">Choose how far back to extract message history.</p>
          </div>

          <div className="flex flex-wrap items-end gap-4">
            <div className="flex-1 min-w-48">
              <label className="block text-sm font-medium text-ink-600 mb-2">Sync History</label>
              <select
                value={syncDays}
                onChange={(e) => setSyncDays(parseInt(e.target.value))}
                className="input-dark w-full px-4 py-3 rounded-xl appearance-none cursor-pointer"
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
                <option value={180}>Last 180 days</option>
                <option value={365}>Last 365 days</option>
              </select>
            </div>
            <button
              onClick={handleExtract}
              disabled={isExtracting || hasActiveExtraction}
              className="btn-gold px-6 py-3 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isExtracting || hasActiveExtraction ? (
                <>
                  <div className="loader-gold w-4 h-4" />
                  {isExtracting ? "Starting..." : "In Progress..."}
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  Start Extraction
                </>
              )}
            </button>
          </div>

          <p className="text-ink-500 text-xs mt-4">
            Free tier: up to 30 days • Pro: up to 365 days • Enterprise: unlimited
          </p>
        </div>
      )}

      {/* Extraction History */}
      {botStatus?.connected && extractionJobs.length > 0 && (
        <div className="premium-card p-6 rounded-2xl">
          <h2 className="font-display text-xl font-semibold text-ink-800 mb-6">Extraction History</h2>
          <div className="space-y-4">
            {extractionJobs.map((job) => (
              <div
                key={job.id}
                className={`p-4 rounded-xl border ${
                  job.status === "running" || job.status === "pending"
                    ? "bg-blue-500/5 border-blue-500/20"
                    : job.status === "completed"
                    ? "bg-green-500/5 border-green-500/20"
                    : job.status === "failed"
                    ? "bg-red-500/5 border-red-500/20"
                    : "bg-surface-200/50 border-surface-400"
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <StatusIndicator status={job.status} />
                  <span className="text-sm text-ink-500">{job.sync_days}-day extraction</span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="text-ink-500">Messages</span>
                    <p className="font-semibold text-ink-800">{job.messages_extracted.toLocaleString()}</p>
                  </div>
                  <div>
                    <span className="text-ink-500">Started</span>
                    <p className="text-ink-700">{timeAgo(job.started_at)}</p>
                  </div>
                  {job.completed_at && (
                    <div>
                      <span className="text-ink-500">Completed</span>
                      <p className="text-ink-700">{timeAgo(job.completed_at)}</p>
                    </div>
                  )}
                  {job.error_message && (
                    <div className="col-span-2 md:col-span-4">
                      <span className="text-red-400">Error: </span>
                      <span className="text-red-300">{job.error_message}</span>
                    </div>
                  )}
                </div>

                {(job.status === "pending" || job.status === "running") && (
                  <div className="mt-4 pt-4 border-t border-surface-400">
                    <button
                      onClick={() => handleCancelExtraction(job.id)}
                      disabled={isCancelling === job.id}
                      className="text-sm px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                    >
                      {isCancelling === job.id ? "Cancelling..." : "Cancel Extraction"}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Help Section */}
      <div className="premium-card p-6 rounded-2xl">
        <h2 className="font-display text-xl font-semibold text-ink-800 mb-4">Getting Started</h2>
        <div className="space-y-4">
          {[
            { step: 1, text: "Go to the Discord Developer Portal", link: "https://discord.com/developers/applications" },
            { step: 2, text: "Create a new application or select an existing one" },
            { step: 3, text: 'Go to the "Bot" section and click "Add Bot"' },
            { step: 4, text: 'Click "Reset Token" and copy your bot token' },
            { step: 5, text: 'Enable "Message Content Intent" under Privileged Gateway Intents' },
            { step: 6, text: 'Invite the bot to your server with "Read Messages" permission' },
          ].map((item) => (
            <div key={item.step} className="flex items-start gap-4">
              <div className="w-8 h-8 rounded-lg bg-gold-400/10 border border-gold-400/20 flex items-center justify-center flex-shrink-0">
                <span className="text-gold-600 font-semibold text-sm">{item.step}</span>
              </div>
              <p className="text-ink-600 pt-1.5">
                {item.link ? (
                  <a href={item.link} target="_blank" rel="noopener noreferrer" className="text-gold-600 hover:text-gold-600 underline">
                    {item.text}
                  </a>
                ) : (
                  item.text
                )}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
