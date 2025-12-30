"use client";

import { useState, useEffect } from "react";

interface ApiKey {
  id: string;
  name: string;
  key: string;
  createdAt: string;
  lastUsed: string | null;
  permissions: ("read" | "write" | "admin")[];
}

interface ApiKeyManagerProps {
  onCreateKey?: (name: string, permissions: string[]) => Promise<ApiKey>;
  onRevokeKey?: (id: string) => Promise<void>;
}

export default function ApiKeyManager({ onCreateKey, onRevokeKey }: ApiKeyManagerProps) {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyPermissions, setNewKeyPermissions] = useState<string[]>(["read"]);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    // In a real app, fetch keys from API
    // For demo, use mock data
    setKeys([
      {
        id: "key_1",
        name: "Production API",
        key: "sk_live_xxxxxxxxxxxxxxxxxxxx",
        createdAt: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
        lastUsed: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        permissions: ["read", "write"],
      },
      {
        id: "key_2",
        name: "Development",
        key: "sk_test_xxxxxxxxxxxxxxxxxxxx",
        createdAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
        lastUsed: null,
        permissions: ["read"],
      },
    ]);
  }, []);

  const handleCreateKey = async () => {
    setLoading(true);
    try {
      if (onCreateKey) {
        const newKey = await onCreateKey(newKeyName, newKeyPermissions);
        setKeys((prev) => [newKey, ...prev]);
        setNewlyCreatedKey(newKey.key);
      } else {
        // Mock creation
        const mockKey: ApiKey = {
          id: `key_${Date.now()}`,
          name: newKeyName,
          key: `sk_live_${Math.random().toString(36).substring(2, 34)}`,
          createdAt: new Date().toISOString(),
          lastUsed: null,
          permissions: newKeyPermissions as ApiKey["permissions"],
        };
        setKeys((prev) => [mockKey, ...prev]);
        setNewlyCreatedKey(mockKey.key);
      }
      setNewKeyName("");
      setNewKeyPermissions(["read"]);
    } finally {
      setLoading(false);
    }
  };

  const handleRevokeKey = async (id: string) => {
    if (!confirm("Are you sure you want to revoke this API key? This action cannot be undone.")) {
      return;
    }

    setLoading(true);
    try {
      if (onRevokeKey) {
        await onRevokeKey(id);
      }
      setKeys((prev) => prev.filter((k) => k.id !== id));
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never";
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const togglePermission = (permission: string) => {
    setNewKeyPermissions((prev) =>
      prev.includes(permission)
        ? prev.filter((p) => p !== permission)
        : [...prev, permission]
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-xl font-semibold text-cream-100">API Keys</h2>
          <p className="text-cream-500 text-sm mt-1">
            Manage your API keys for programmatic access
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-gold px-4 py-2 rounded-lg text-sm flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Create API Key
        </button>
      </div>

      {/* Newly Created Key Warning */}
      {newlyCreatedKey && (
        <div className="p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/20">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div className="flex-1">
              <p className="font-medium text-yellow-300">Copy your API key now!</p>
              <p className="text-yellow-400/80 text-sm mt-1">
                This key will only be shown once. Please copy and store it securely.
              </p>
              <div className="flex items-center gap-2 mt-3">
                <code className="flex-1 px-3 py-2 bg-obsidian-800 rounded-lg font-mono text-sm text-cream-200 select-all">
                  {newlyCreatedKey}
                </code>
                <button
                  onClick={() => {
                    copyToClipboard(newlyCreatedKey, "new");
                    setTimeout(() => setNewlyCreatedKey(null), 2000);
                  }}
                  className="btn-gold px-4 py-2 rounded-lg text-sm"
                >
                  {copiedId === "new" ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Keys List */}
      <div className="premium-card rounded-xl overflow-hidden">
        {keys.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 rounded-2xl bg-obsidian-700 border border-obsidian-600 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-cream-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </div>
            <p className="text-cream-400 mb-2">No API keys created</p>
            <p className="text-cream-600 text-sm">Create your first API key to get started</p>
          </div>
        ) : (
          <div className="divide-y divide-obsidian-700">
            {keys.map((apiKey) => (
              <div key={apiKey.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-gold-400/10 border border-gold-400/20 flex items-center justify-center">
                    <svg className="w-5 h-5 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                    </svg>
                  </div>
                  <div>
                    <p className="font-medium text-cream-100">{apiKey.name}</p>
                    <div className="flex items-center gap-3 mt-1">
                      <code className="text-xs font-mono text-cream-500">
                        {apiKey.key.slice(0, 12)}...{apiKey.key.slice(-4)}
                      </code>
                      <div className="flex gap-1">
                        {apiKey.permissions.map((perm) => (
                          <span
                            key={perm}
                            className="text-xs px-2 py-0.5 rounded-md bg-obsidian-700 text-cream-400"
                          >
                            {perm}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right text-sm">
                    <p className="text-cream-500">Created {formatDate(apiKey.createdAt)}</p>
                    <p className="text-cream-600 text-xs">Last used: {formatDate(apiKey.lastUsed)}</p>
                  </div>
                  <button
                    onClick={() => handleRevokeKey(apiKey.id)}
                    disabled={loading}
                    className="px-3 py-1.5 rounded-lg text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                  >
                    Revoke
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-obsidian-900/80 backdrop-blur-sm">
          <div className="bg-obsidian-800 border border-obsidian-700 rounded-2xl w-full max-w-md p-6 shadow-2xl">
            <h3 className="font-display text-xl font-semibold text-cream-100 mb-4">
              Create API Key
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-cream-400 mb-2">Key Name</label>
                <input
                  type="text"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="e.g., Production API"
                  className="w-full input-dark px-4 py-2.5 rounded-xl text-sm"
                />
              </div>

              <div>
                <label className="block text-sm text-cream-400 mb-2">Permissions</label>
                <div className="flex gap-2">
                  {["read", "write", "admin"].map((perm) => (
                    <button
                      key={perm}
                      onClick={() => togglePermission(perm)}
                      className={`px-4 py-2 rounded-lg text-sm capitalize transition-colors ${
                        newKeyPermissions.includes(perm)
                          ? "bg-gold-400/20 text-gold-400 border border-gold-400/30"
                          : "bg-obsidian-700 text-cream-400 border border-obsidian-600 hover:border-obsidian-500"
                      }`}
                    >
                      {perm}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setNewKeyName("");
                  setNewKeyPermissions(["read"]);
                }}
                className="px-4 py-2 rounded-lg text-sm text-cream-400 hover:text-cream-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  handleCreateKey();
                  setShowCreateModal(false);
                }}
                disabled={!newKeyName.trim() || newKeyPermissions.length === 0 || loading}
                className="btn-gold px-4 py-2 rounded-lg text-sm disabled:opacity-50"
              >
                Create Key
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
