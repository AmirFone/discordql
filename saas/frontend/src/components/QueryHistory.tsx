"use client";

import { useState, useEffect } from "react";

interface SavedQuery {
  id: string;
  sql: string;
  executedAt: string;
  rowCount: number;
  executionTime: number;
}

interface QueryHistoryProps {
  onSelect: (sql: string) => void;
  currentQuery?: string;
}

const STORAGE_KEY = "discord_analytics_query_history";
const MAX_HISTORY_SIZE = 50;

export function useQueryHistory() {
  const [history, setHistory] = useState<SavedQuery[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        setHistory(JSON.parse(stored));
      } catch {
        setHistory([]);
      }
    }
  }, []);

  const addToHistory = (sql: string, rowCount: number, executionTime: number) => {
    const newEntry: SavedQuery = {
      id: Date.now().toString(),
      sql: sql.trim(),
      executedAt: new Date().toISOString(),
      rowCount,
      executionTime,
    };

    setHistory((prev) => {
      // Don't add duplicate consecutive queries
      if (prev.length > 0 && prev[0].sql === newEntry.sql) {
        return prev;
      }

      const updated = [newEntry, ...prev].slice(0, MAX_HISTORY_SIZE);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    });
  };

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem(STORAGE_KEY);
  };

  const removeFromHistory = (id: string) => {
    setHistory((prev) => {
      const updated = prev.filter((q) => q.id !== id);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    });
  };

  return { history, addToHistory, clearHistory, removeFromHistory };
}

export default function QueryHistory({ onSelect, currentQuery }: QueryHistoryProps) {
  const { history, clearHistory, removeFromHistory } = useQueryHistory();
  const [showAll, setShowAll] = useState(false);

  const displayedHistory = showAll ? history : history.slice(0, 5);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (history.length === 0) {
    return (
      <div className="premium-card rounded-xl p-6">
        <h3 className="font-display font-semibold text-cream-100 mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Query History
        </h3>
        <div className="text-center py-8">
          <div className="w-12 h-12 rounded-xl bg-obsidian-700 border border-obsidian-600 flex items-center justify-center mx-auto mb-3">
            <svg className="w-6 h-6 text-cream-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <p className="text-cream-500 text-sm">No query history yet</p>
          <p className="text-cream-600 text-xs mt-1">Run queries to build your history</p>
        </div>
      </div>
    );
  }

  return (
    <div className="premium-card rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display font-semibold text-cream-100 flex items-center gap-2">
          <svg className="w-5 h-5 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Query History
        </h3>
        <button
          onClick={clearHistory}
          className="text-xs text-cream-500 hover:text-red-400 transition-colors"
        >
          Clear All
        </button>
      </div>

      <div className="space-y-2">
        {displayedHistory.map((query) => (
          <div
            key={query.id}
            className={`group relative p-3 rounded-lg border transition-all cursor-pointer ${
              currentQuery === query.sql
                ? "bg-gold-400/10 border-gold-400/30"
                : "bg-obsidian-900/50 border-obsidian-700 hover:border-obsidian-600"
            }`}
            onClick={() => onSelect(query.sql)}
          >
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeFromHistory(query.id);
              }}
              className="absolute top-2 right-2 w-6 h-6 rounded-md bg-obsidian-700 text-cream-500 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <pre className="font-mono text-xs text-cream-300 overflow-hidden whitespace-nowrap text-ellipsis mb-2">
              {query.sql.length > 60 ? query.sql.slice(0, 60) + "..." : query.sql}
            </pre>

            <div className="flex items-center gap-3 text-xs text-cream-500">
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {formatDate(query.executedAt)}
              </span>
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7" />
                </svg>
                {query.rowCount} rows
              </span>
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                {query.executionTime.toFixed(1)}ms
              </span>
            </div>
          </div>
        ))}
      </div>

      {history.length > 5 && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="w-full mt-4 text-sm text-gold-400 hover:text-gold-300 transition-colors flex items-center justify-center gap-2"
        >
          {showAll ? (
            <>
              Show Less
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
            </>
          ) : (
            <>
              Show All ({history.length})
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </>
          )}
        </button>
      )}
    </div>
  );
}
