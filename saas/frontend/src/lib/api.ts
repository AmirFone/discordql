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
  guild_id: string;  // Use string to preserve precision for large Discord snowflake IDs
  guild_name: string;
}

export interface BotConnectResponse {
  id: string;
  guild_id: string;  // Use string to preserve precision for large Discord snowflake IDs
  guild_name: string;
  connected_at: string;
  last_sync_at: string | null;
}

export interface BotStatusResponse {
  connected: boolean;
  guild_id: string | null;  // Use string to preserve precision for large Discord snowflake IDs
  guild_name: string | null;
  last_sync_at: string | null;
}

export interface ExtractionStartRequest {
  guild_id: string;  // Use string to preserve precision for large Discord snowflake IDs
  sync_days: number;
}

export interface ExtractionJobResponse {
  id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  guild_id: string;  // Use string to preserve precision for large Discord snowflake IDs
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

export interface ExampleQuery {
  name: string;
  description: string;
  category: string;
  sql: string;
}

export interface ExampleQueriesResponse {
  queries: ExampleQuery[];
  categories: string[];
}

export interface SubscriptionResponse {
  tier: "free" | "pro" | "team";
  current_period_end: string | null;
  storage_used_bytes: number;
  storage_limit_bytes: number;
  queries_this_month: number;
  queries_limit: number;
}

// Analytics Types
export interface OverviewStats {
  total_messages: number;
  total_users: number;
  total_channels: number;
  total_mentions: number;
  messages_change_percent: number;
  users_change_percent: number;
  avg_messages_per_day: number;
  avg_message_length: number;
}

export interface TimeSeriesPoint {
  date: string;
  count: number;
}

export interface ChannelStats {
  channel_id: string;
  channel_name: string;
  message_count: number;
  unique_users: number;
  avg_message_length: number;
}

export interface UserStats {
  user_id: string;
  username: string;
  message_count: number;
  mention_count: number;
  reply_count: number;
  avg_message_length: number;
  is_bot: boolean;
}

export interface HourlyActivity {
  hour: number;
  message_count: number;
  unique_users: number;
}

export interface DayOfWeekActivity {
  day: number;
  day_name: string;
  message_count: number;
}

export interface UserInteraction {
  from_user: string;
  to_user: string;
  mention_count: number;
  reply_count: number;
}

export interface ContentMetrics {
  total_words: number;
  total_characters: number;
  avg_words_per_message: number;
  messages_with_attachments: number;
  messages_with_embeds: number;
  messages_with_mentions: number;
  pinned_messages: number;
}

export interface EngagementMetrics {
  reply_rate: number;
  mention_rate: number;
  active_user_ratio: number;
  messages_per_active_user: number;
}

export interface ChannelGrowth {
  channel_name: string;
  current_period: number;
  previous_period: number;
  growth_percent: number;
}

export interface BotVsHuman {
  human_messages: number;
  bot_messages: number;
  human_percentage: number;
  bot_percentage: number;
}

export interface AnalyticsResponse {
  overview: OverviewStats;
  messages_over_time: TimeSeriesPoint[];
  hourly_activity: HourlyActivity[];
  day_of_week_activity: DayOfWeekActivity[];
  top_channels: ChannelStats[];
  top_users: UserStats[];
  user_interactions: UserInteraction[];
  content_metrics: ContentMetrics;
  engagement_metrics: EngagementMetrics;
  channel_growth: ChannelGrowth[];
  bot_vs_human: BotVsHuman;
  time_range_days: number;
}
