"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

// SECURITY: Get API URL from environment
// In production, this MUST be an HTTPS URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Warn in development if production URL doesn't use HTTPS
if (
  process.env.NODE_ENV === "production" &&
  API_BASE_URL &&
  !API_BASE_URL.startsWith("https://")
) {
  console.error(
    "SECURITY WARNING: API URL should use HTTPS in production:",
    API_BASE_URL
  );
}

interface ApiOptions extends Omit<RequestInit, "body"> {
  body?: Record<string, unknown>;
}

interface ApiError {
  detail: string;
  status: number;
}

/**
 * Custom hook for making authenticated API requests.
 * Automatically adds Authorization header with Clerk JWT token.
 *
 * Usage:
 * ```tsx
 * const { apiRequest } = useApi();
 *
 * const data = await apiRequest('/api/bot/status');
 * const result = await apiRequest('/api/bot/connect', {
 *   method: 'POST',
 *   body: { token: '...', guild_id: 123 }
 * });
 * ```
 */
export function useApi() {
  const { getToken } = useAuth();

  const apiRequest = useCallback(
    async <T = unknown>(endpoint: string, options: ApiOptions = {}): Promise<T> => {
      const token = await getToken();

      if (!token) {
        throw new Error("Not authenticated");
      }

      const { body, ...restOptions } = options;

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...restOptions,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          ...restOptions.headers,
        },
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        let errorDetail = "Request failed";
        try {
          const errorData = await response.json();
          errorDetail = errorData.detail || errorData.message || errorDetail;
        } catch {
          errorDetail = response.statusText || errorDetail;
        }

        const error: ApiError = {
          detail: errorDetail,
          status: response.status,
        };
        throw error;
      }

      // Handle empty responses
      const contentType = response.headers.get("content-type");
      if (!contentType || !contentType.includes("application/json")) {
        return {} as T;
      }

      return response.json();
    },
    [getToken]
  );

  return { apiRequest };
}

/**
 * Type-safe API response types
 */
export interface BotConnectRequest {
  token: string;
  guild_id: number;
  guild_name: string;
}

export interface BotConnectResponse {
  id: string;
  guild_id: number;
  guild_name: string;
  connected_at: string;
  last_sync_at: string | null;
}

export interface BotStatusResponse {
  connected: boolean;
  guild_id: number | null;
  guild_name: string | null;
  last_sync_at: string | null;
}

export interface ExtractionStartRequest {
  guild_id: number;
  sync_days: number;
}

export interface ExtractionJobResponse {
  id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  guild_id: number;
  sync_days: number;
  messages_extracted: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface QueryRequest {
  sql: string;
  limit?: number;
}

export interface QueryColumn {
  name: string;
  type: string;
}

export interface QueryResponse {
  columns: QueryColumn[];
  rows: unknown[][];
  row_count: number;
  execution_time_ms: number;
  truncated: boolean;
}

export interface TableInfo {
  name: string;
  columns: QueryColumn[];
  row_count: number;
}

export interface SchemaResponse {
  tables: TableInfo[];
}

export interface SubscriptionResponse {
  tier: "free" | "pro" | "team";
  stripe_customer_id: string | null;
  current_period_end: string | null;
  storage_used_bytes: number;
  storage_limit_bytes: number;
  queries_this_month: number;
  queries_limit: number;
}
