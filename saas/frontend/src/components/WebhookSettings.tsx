"use client";

import { useState, useEffect } from "react";

interface Webhook {
  id: string;
  url: string;
  events: string[];
  enabled: boolean;
  createdAt: string;
  lastTriggered: string | null;
  failureCount: number;
}

const availableEvents = [
  { id: "extraction.started", label: "Extraction Started", description: "When a new data extraction begins" },
  { id: "extraction.completed", label: "Extraction Completed", description: "When extraction finishes successfully" },
  { id: "extraction.failed", label: "Extraction Failed", description: "When extraction encounters an error" },
  { id: "query.executed", label: "Query Executed", description: "When a SQL query is run" },
  { id: "storage.threshold", label: "Storage Threshold", description: "When storage usage exceeds 80%" },
  { id: "bot.connected", label: "Bot Connected", description: "When a Discord bot connects" },
  { id: "bot.disconnected", label: "Bot Disconnected", description: "When a Discord bot disconnects" },
];

interface WebhookSettingsProps {
  onSaveWebhook?: (webhook: Partial<Webhook>) => Promise<Webhook>;
  onDeleteWebhook?: (id: string) => Promise<void>;
  onTestWebhook?: (id: string) => Promise<boolean>;
}

export default function WebhookSettings({
  onSaveWebhook,
  onDeleteWebhook,
  onTestWebhook,
}: WebhookSettingsProps) {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<Webhook | null>(null);
  const [newUrl, setNewUrl] = useState("");
  const [newEvents, setNewEvents] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [testResult, setTestResult] = useState<{ id: string; success: boolean } | null>(null);

  useEffect(() => {
    // In a real app, fetch webhooks from API
    setWebhooks([
      {
        id: "wh_1",
        url: "https://hooks.slack.com/services/xxx/yyy/zzz",
        events: ["extraction.completed", "extraction.failed"],
        enabled: true,
        createdAt: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
        lastTriggered: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        failureCount: 0,
      },
    ]);
  }, []);

  const handleSaveWebhook = async () => {
    if (!newUrl.trim() || newEvents.length === 0) return;

    setLoading(true);
    try {
      const webhookData: Partial<Webhook> = {
        url: newUrl,
        events: newEvents,
        enabled: true,
      };

      if (editingWebhook) {
        webhookData.id = editingWebhook.id;
      }

      if (onSaveWebhook) {
        const saved = await onSaveWebhook(webhookData);
        setWebhooks((prev) =>
          editingWebhook
            ? prev.map((w) => (w.id === saved.id ? saved : w))
            : [saved, ...prev]
        );
      } else {
        // Mock save
        const newWebhook: Webhook = {
          id: editingWebhook?.id || `wh_${Date.now()}`,
          url: newUrl,
          events: newEvents,
          enabled: true,
          createdAt: editingWebhook?.createdAt || new Date().toISOString(),
          lastTriggered: editingWebhook?.lastTriggered || null,
          failureCount: editingWebhook?.failureCount || 0,
        };
        setWebhooks((prev) =>
          editingWebhook
            ? prev.map((w) => (w.id === newWebhook.id ? newWebhook : w))
            : [newWebhook, ...prev]
        );
      }

      setShowAddModal(false);
      setEditingWebhook(null);
      setNewUrl("");
      setNewEvents([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteWebhook = async (id: string) => {
    if (!confirm("Are you sure you want to delete this webhook?")) return;

    setLoading(true);
    try {
      if (onDeleteWebhook) {
        await onDeleteWebhook(id);
      }
      setWebhooks((prev) => prev.filter((w) => w.id !== id));
    } finally {
      setLoading(false);
    }
  };

  const handleToggleWebhook = (id: string) => {
    setWebhooks((prev) =>
      prev.map((w) => (w.id === id ? { ...w, enabled: !w.enabled } : w))
    );
  };

  const handleTestWebhook = async (id: string) => {
    setLoading(true);
    try {
      let success = true;
      if (onTestWebhook) {
        success = await onTestWebhook(id);
      }
      setTestResult({ id, success });
      setTimeout(() => setTestResult(null), 3000);
    } finally {
      setLoading(false);
    }
  };

  const handleEditWebhook = (webhook: Webhook) => {
    setEditingWebhook(webhook);
    setNewUrl(webhook.url);
    setNewEvents(webhook.events);
    setShowAddModal(true);
  };

  const toggleEvent = (eventId: string) => {
    setNewEvents((prev) =>
      prev.includes(eventId)
        ? prev.filter((e) => e !== eventId)
        : [...prev, eventId]
    );
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never";
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-xl font-semibold text-cream-100">Webhooks</h2>
          <p className="text-cream-500 text-sm mt-1">
            Get notified when events happen in your account
          </p>
        </div>
        <button
          onClick={() => {
            setEditingWebhook(null);
            setNewUrl("");
            setNewEvents([]);
            setShowAddModal(true);
          }}
          className="btn-gold px-4 py-2 rounded-lg text-sm flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Webhook
        </button>
      </div>

      {/* Webhooks List */}
      <div className="premium-card rounded-xl overflow-hidden">
        {webhooks.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 rounded-2xl bg-obsidian-700 border border-obsidian-600 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-cream-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            </div>
            <p className="text-cream-400 mb-2">No webhooks configured</p>
            <p className="text-cream-600 text-sm">Add a webhook to receive event notifications</p>
          </div>
        ) : (
          <div className="divide-y divide-obsidian-700">
            {webhooks.map((webhook) => (
              <div key={webhook.id} className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div
                      className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                        webhook.enabled
                          ? "bg-green-500/10 border border-green-500/20"
                          : "bg-obsidian-700 border border-obsidian-600"
                      }`}
                    >
                      <svg
                        className={`w-5 h-5 ${webhook.enabled ? "text-green-400" : "text-cream-500"}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                      </svg>
                    </div>
                    <div>
                      <code className="text-sm font-mono text-cream-200 break-all">
                        {webhook.url}
                      </code>
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {webhook.events.map((event) => (
                          <span
                            key={event}
                            className="text-xs px-2 py-0.5 rounded-md bg-obsidian-700 text-cream-400"
                          >
                            {availableEvents.find((e) => e.id === event)?.label || event}
                          </span>
                        ))}
                      </div>
                      <div className="flex items-center gap-4 mt-2 text-xs text-cream-500">
                        <span>Last triggered: {formatDate(webhook.lastTriggered)}</span>
                        {webhook.failureCount > 0 && (
                          <span className="text-red-400">
                            {webhook.failureCount} failures
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {testResult?.id === webhook.id && (
                      <span
                        className={`text-xs px-2 py-1 rounded-md ${
                          testResult.success
                            ? "bg-green-500/10 text-green-400"
                            : "bg-red-500/10 text-red-400"
                        }`}
                      >
                        {testResult.success ? "Success!" : "Failed"}
                      </span>
                    )}
                    <button
                      onClick={() => handleTestWebhook(webhook.id)}
                      disabled={loading || !webhook.enabled}
                      className="px-3 py-1.5 rounded-lg text-sm text-cream-400 hover:bg-obsidian-700 transition-colors disabled:opacity-50"
                    >
                      Test
                    </button>
                    <button
                      onClick={() => handleEditWebhook(webhook)}
                      className="px-3 py-1.5 rounded-lg text-sm text-cream-400 hover:bg-obsidian-700 transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleToggleWebhook(webhook.id)}
                      className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                        webhook.enabled
                          ? "text-yellow-400 hover:bg-yellow-500/10"
                          : "text-green-400 hover:bg-green-500/10"
                      }`}
                    >
                      {webhook.enabled ? "Disable" : "Enable"}
                    </button>
                    <button
                      onClick={() => handleDeleteWebhook(webhook.id)}
                      disabled={loading}
                      className="px-3 py-1.5 rounded-lg text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add/Edit Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-obsidian-900/80 backdrop-blur-sm">
          <div className="bg-obsidian-800 border border-obsidian-700 rounded-2xl w-full max-w-lg p-6 shadow-2xl">
            <h3 className="font-display text-xl font-semibold text-cream-100 mb-4">
              {editingWebhook ? "Edit Webhook" : "Add Webhook"}
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-cream-400 mb-2">Webhook URL</label>
                <input
                  type="url"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="https://your-webhook-url.com/endpoint"
                  className="w-full input-dark px-4 py-2.5 rounded-xl text-sm"
                />
              </div>

              <div>
                <label className="block text-sm text-cream-400 mb-2">Events</label>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {availableEvents.map((event) => (
                    <button
                      key={event.id}
                      onClick={() => toggleEvent(event.id)}
                      className={`w-full flex items-center justify-between p-3 rounded-lg transition-colors ${
                        newEvents.includes(event.id)
                          ? "bg-gold-400/10 border border-gold-400/30"
                          : "bg-obsidian-900/50 border border-obsidian-700 hover:border-obsidian-600"
                      }`}
                    >
                      <div className="text-left">
                        <p className="text-sm font-medium text-cream-200">{event.label}</p>
                        <p className="text-xs text-cream-500">{event.description}</p>
                      </div>
                      <div
                        className={`w-5 h-5 rounded-md border flex items-center justify-center ${
                          newEvents.includes(event.id)
                            ? "bg-gold-400 border-gold-400"
                            : "border-obsidian-600"
                        }`}
                      >
                        {newEvents.includes(event.id) && (
                          <svg className="w-3 h-3 text-obsidian-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowAddModal(false);
                  setEditingWebhook(null);
                  setNewUrl("");
                  setNewEvents([]);
                }}
                className="px-4 py-2 rounded-lg text-sm text-cream-400 hover:text-cream-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveWebhook}
                disabled={!newUrl.trim() || newEvents.length === 0 || loading}
                className="btn-gold px-4 py-2 rounded-lg text-sm disabled:opacity-50"
              >
                {editingWebhook ? "Save Changes" : "Add Webhook"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
