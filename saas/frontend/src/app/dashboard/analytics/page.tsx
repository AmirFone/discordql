"use client";

import { useState, useEffect, useRef } from "react";
import { useApi, AnalyticsResponse } from "@/lib/api";

// Simple chart components that work without external dependencies
function SimpleLineChart({ data, title, color = "#D4AF37", height = 200 }: {
  data: { labels: string[]; values: number[] };
  title: string;
  color?: string;
  height?: number;
}) {
  const maxValue = Math.max(...data.values, 1);
  const points = data.values.map((v, i) => {
    const x = (i / Math.max(data.values.length - 1, 1)) * 100;
    const y = 100 - (v / maxValue) * 100;
    return `${x},${y}`;
  }).join(" ");

  return (
    <div className="premium-card rounded-xl p-6">
      <h3 className="font-display font-semibold text-cream-100 mb-4">{title}</h3>
      <div style={{ height }} className="relative">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
          <defs>
            <linearGradient id={`gradient-${title}`} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={color} stopOpacity="0.3" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <polygon
            points={`0,100 ${points} 100,100`}
            fill={`url(#gradient-${title})`}
          />
          <polyline
            points={points}
            fill="none"
            stroke={color}
            strokeWidth="0.5"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs text-cream-500 pt-2">
          {data.labels.filter((_, i) => i % Math.ceil(data.labels.length / 5) === 0).map((label, i) => (
            <span key={i}>{label}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function SimpleBarChart({ data, title, color = "#D4AF37", height = 200, horizontal = false }: {
  data: { labels: string[]; values: number[] };
  title: string;
  color?: string;
  height?: number;
  horizontal?: boolean;
}) {
  const maxValue = Math.max(...data.values, 1);

  if (horizontal) {
    return (
      <div className="premium-card rounded-xl p-6">
        <h3 className="font-display font-semibold text-cream-100 mb-4">{title}</h3>
        <div className="space-y-3">
          {data.labels.map((label, i) => (
            <div key={i} className="flex items-center gap-3">
              <span className="text-cream-400 text-sm w-24 truncate">{label}</span>
              <div className="flex-1 h-6 bg-obsidian-700 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${(data.values[i] / maxValue) * 100}%`,
                    background: `linear-gradient(90deg, ${color}, ${color}dd)`
                  }}
                />
              </div>
              <span className="text-cream-300 text-sm w-16 text-right">{data.values[i].toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="premium-card rounded-xl p-6">
      <h3 className="font-display font-semibold text-cream-100 mb-4">{title}</h3>
      <div style={{ height }} className="flex items-end gap-1">
        {data.values.map((value, i) => (
          <div key={i} className="flex-1 flex flex-col items-center">
            <div
              className="w-full rounded-t transition-all duration-300 hover:opacity-80"
              style={{
                height: `${(value / maxValue) * 100}%`,
                minHeight: value > 0 ? 4 : 0,
                background: `linear-gradient(180deg, ${color}, ${color}88)`
              }}
              title={`${data.labels[i]}: ${value.toLocaleString()}`}
            />
          </div>
        ))}
      </div>
      <div className="flex justify-between text-xs text-cream-500 mt-2">
        {data.labels.filter((_, i) => i % Math.ceil(data.labels.length / 6) === 0).map((label, i) => (
          <span key={i}>{label}</span>
        ))}
      </div>
    </div>
  );
}

function SimpleDonutChart({ data, title, size = 180 }: {
  data: { label: string; value: number; color: string }[];
  title: string;
  size?: number;
}) {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  let currentAngle = 0;

  const segments = data.map((d) => {
    const percentage = total > 0 ? d.value / total : 0;
    const startAngle = currentAngle;
    currentAngle += percentage * 360;
    return { ...d, percentage, startAngle, endAngle: currentAngle };
  });

  const createArc = (startAngle: number, endAngle: number, radius: number) => {
    const start = polarToCartesian(50, 50, radius, endAngle);
    const end = polarToCartesian(50, 50, radius, startAngle);
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 0 ${end.x} ${end.y}`;
  };

  const polarToCartesian = (cx: number, cy: number, r: number, angle: number) => {
    const rad = ((angle - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };

  return (
    <div className="premium-card rounded-xl p-6">
      <h3 className="font-display font-semibold text-cream-100 mb-4">{title}</h3>
      <div className="flex items-center gap-6">
        <svg width={size} height={size} viewBox="0 0 100 100">
          {segments.map((seg, i) => (
            <path
              key={i}
              d={createArc(seg.startAngle, seg.endAngle - 0.5, 40)}
              fill="none"
              stroke={seg.color}
              strokeWidth="15"
              strokeLinecap="round"
            />
          ))}
          <text x="50" y="50" textAnchor="middle" className="fill-cream-100 text-lg font-bold">
            {total.toLocaleString()}
          </text>
          <text x="50" y="62" textAnchor="middle" className="fill-cream-500 text-[8px]">
            total
          </text>
        </svg>
        <div className="flex-1 space-y-2">
          {segments.slice(0, 5).map((seg, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: seg.color }} />
              <span className="text-cream-400 truncate flex-1">{seg.label}</span>
              <span className="text-cream-300">{(seg.percentage * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, change, icon, suffix = "" }: {
  title: string;
  value: number | string;
  change?: number;
  icon: React.ReactNode;
  suffix?: string;
}) {
  return (
    <div className="premium-card rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="w-10 h-10 rounded-xl bg-gold-400/10 border border-gold-400/20 flex items-center justify-center text-gold-400">
          {icon}
        </div>
        {change !== undefined && (
          <span className={`text-sm px-2 py-1 rounded-full ${
            change >= 0
              ? "bg-green-500/10 text-green-400"
              : "bg-red-500/10 text-red-400"
          }`}>
            {change >= 0 ? "+" : ""}{change.toFixed(1)}%
          </span>
        )}
      </div>
      <div>
        <span className="font-display text-3xl font-bold text-cream-100">
          {typeof value === "number" ? value.toLocaleString() : value}
        </span>
        {suffix && <span className="text-cream-500 text-sm ml-1">{suffix}</span>}
      </div>
      <p className="text-cream-500 text-sm mt-1">{title}</p>
    </div>
  );
}

export default function AnalyticsPage() {
  const { apiRequest } = useApi();
  const apiRequestRef = useRef(apiRequest);
  apiRequestRef.current = apiRequest;

  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<7 | 30 | 90>(30);

  useEffect(() => {
    const fetchAnalytics = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await apiRequestRef.current<AnalyticsResponse>(
          `/api/analytics/overview?days=${timeRange}`
        );
        setData(response);
      } catch (err) {
        console.error("Failed to fetch analytics:", err);
        setError("Failed to load analytics. Please ensure you have extracted Discord data first.");
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, [timeRange]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loader-gold w-10 h-10" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-12">
        <div className="w-16 h-16 rounded-2xl bg-obsidian-800 border border-obsidian-700 flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-cream-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <p className="text-cream-400 mb-2">No Analytics Data Available</p>
        <p className="text-cream-500 text-sm mb-4">{error || "Extract Discord data first to see analytics."}</p>
        <a href="/dashboard/bot" className="btn-gold px-6 py-2.5 rounded-lg inline-block">
          Go to Bot Config
        </a>
      </div>
    );
  }

  const channelColors = ["#D4AF37", "#B8860B", "#FFD700", "#DAA520", "#F0E68C", "#BDB76B", "#8B7355", "#CD853F", "#DEB887", "#D2691E"];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold text-cream-100">Analytics</h1>
          <p className="text-cream-500 mt-1">Real insights from your Discord server data</p>
        </div>
        <div className="flex items-center gap-2">
          {([7, 30, 90] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                timeRange === range
                  ? "bg-gold-400/20 text-gold-400 border border-gold-400/30"
                  : "bg-obsidian-800 text-cream-400 border border-obsidian-700 hover:border-obsidian-600"
              }`}
            >
              {range} Days
            </button>
          ))}
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid md:grid-cols-4 gap-6">
        <StatCard
          title="Total Messages"
          value={data.overview.total_messages}
          change={data.overview.messages_change_percent}
          icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>}
        />
        <StatCard
          title="Active Users"
          value={data.overview.total_users}
          change={data.overview.users_change_percent}
          icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>}
        />
        <StatCard
          title="Active Channels"
          value={data.overview.total_channels}
          icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" />
          </svg>}
        />
        <StatCard
          title="Avg Messages/Day"
          value={data.overview.avg_messages_per_day.toFixed(0)}
          icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>}
        />
      </div>

      {/* Messages Over Time */}
      <SimpleLineChart
        data={{
          labels: data.messages_over_time.map(d => d.date.split("-").slice(1).join("/")),
          values: data.messages_over_time.map(d => d.count),
        }}
        title="Messages Over Time"
        height={250}
      />

      {/* Hourly & Day of Week Activity */}
      <div className="grid lg:grid-cols-2 gap-6">
        <SimpleBarChart
          data={{
            labels: data.hourly_activity.map(d => `${d.hour}:00`),
            values: data.hourly_activity.map(d => d.message_count),
          }}
          title="Activity by Hour"
          height={200}
        />
        <SimpleBarChart
          data={{
            labels: data.day_of_week_activity.map(d => d.day_name.substring(0, 3)),
            values: data.day_of_week_activity.map(d => d.message_count),
          }}
          title="Activity by Day of Week"
          height={200}
        />
      </div>

      {/* Top Channels & Users */}
      <div className="grid lg:grid-cols-2 gap-6">
        <SimpleDonutChart
          data={data.top_channels.slice(0, 6).map((c, i) => ({
            label: `#${c.channel_name}`,
            value: c.message_count,
            color: channelColors[i % channelColors.length],
          }))}
          title="Messages by Channel"
        />
        <SimpleBarChart
          data={{
            labels: data.top_users.slice(0, 8).map(u => u.username),
            values: data.top_users.slice(0, 8).map(u => u.message_count),
          }}
          title="Top Contributors"
          horizontal
        />
      </div>

      {/* Engagement Metrics */}
      <div className="grid md:grid-cols-4 gap-6">
        <StatCard
          title="Reply Rate"
          value={data.engagement_metrics.reply_rate}
          suffix="%"
          icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
          </svg>}
        />
        <StatCard
          title="Mention Rate"
          value={data.engagement_metrics.mention_rate}
          suffix="%"
          icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
          </svg>}
        />
        <StatCard
          title="Active User Ratio"
          value={data.engagement_metrics.active_user_ratio}
          suffix="%"
          icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>}
        />
        <StatCard
          title="Msgs/Active User"
          value={data.engagement_metrics.messages_per_active_user.toFixed(1)}
          icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>}
        />
      </div>

      {/* Content Metrics */}
      <div className="premium-card rounded-xl p-6">
        <h3 className="font-display font-semibold text-cream-100 mb-4">Content Analysis</h3>
        <div className="grid md:grid-cols-4 gap-6">
          <div className="text-center p-4 bg-obsidian-900/50 rounded-lg border border-obsidian-700">
            <p className="text-3xl font-bold text-gold-400">{data.content_metrics.total_words.toLocaleString()}</p>
            <p className="text-cream-500 text-sm mt-1">Total Words</p>
          </div>
          <div className="text-center p-4 bg-obsidian-900/50 rounded-lg border border-obsidian-700">
            <p className="text-3xl font-bold text-gold-400">{data.content_metrics.avg_words_per_message.toFixed(1)}</p>
            <p className="text-cream-500 text-sm mt-1">Avg Words/Message</p>
          </div>
          <div className="text-center p-4 bg-obsidian-900/50 rounded-lg border border-obsidian-700">
            <p className="text-3xl font-bold text-gold-400">{data.content_metrics.messages_with_attachments.toLocaleString()}</p>
            <p className="text-cream-500 text-sm mt-1">With Attachments</p>
          </div>
          <div className="text-center p-4 bg-obsidian-900/50 rounded-lg border border-obsidian-700">
            <p className="text-3xl font-bold text-gold-400">{data.content_metrics.pinned_messages}</p>
            <p className="text-cream-500 text-sm mt-1">Pinned Messages</p>
          </div>
        </div>
      </div>

      {/* Bot vs Human */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="premium-card rounded-xl p-6">
          <h3 className="font-display font-semibold text-cream-100 mb-4">Human vs Bot Activity</h3>
          <div className="flex items-center gap-8">
            <div className="flex-1">
              <div className="flex justify-between mb-2">
                <span className="text-cream-400">Human</span>
                <span className="text-cream-300">{data.bot_vs_human.human_percentage}%</span>
              </div>
              <div className="h-4 bg-obsidian-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-green-500 to-green-400 rounded-full"
                  style={{ width: `${data.bot_vs_human.human_percentage}%` }}
                />
              </div>
              <p className="text-cream-500 text-sm mt-1">{data.bot_vs_human.human_messages.toLocaleString()} messages</p>
            </div>
            <div className="flex-1">
              <div className="flex justify-between mb-2">
                <span className="text-cream-400">Bot</span>
                <span className="text-cream-300">{data.bot_vs_human.bot_percentage}%</span>
              </div>
              <div className="h-4 bg-obsidian-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-blue-400 rounded-full"
                  style={{ width: `${data.bot_vs_human.bot_percentage}%` }}
                />
              </div>
              <p className="text-cream-500 text-sm mt-1">{data.bot_vs_human.bot_messages.toLocaleString()} messages</p>
            </div>
          </div>
        </div>

        {/* Channel Growth */}
        <div className="premium-card rounded-xl p-6">
          <h3 className="font-display font-semibold text-cream-100 mb-4">Channel Growth</h3>
          <div className="space-y-3">
            {data.channel_growth.slice(0, 5).map((ch, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-cream-400">#{ch.channel_name}</span>
                <div className="flex items-center gap-3">
                  <span className="text-cream-500 text-sm">
                    {ch.previous_period} → {ch.current_period}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    ch.growth_percent >= 0
                      ? "bg-green-500/10 text-green-400"
                      : "bg-red-500/10 text-red-400"
                  }`}>
                    {ch.growth_percent >= 0 ? "+" : ""}{ch.growth_percent}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* User Interactions */}
      {data.user_interactions.length > 0 && (
        <div className="premium-card rounded-xl p-6">
          <h3 className="font-display font-semibold text-cream-100 mb-4">Top User Interactions</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-cream-500 text-sm border-b border-obsidian-700">
                  <th className="pb-3 font-medium">From</th>
                  <th className="pb-3 font-medium">To</th>
                  <th className="pb-3 font-medium text-right">Mentions</th>
                  <th className="pb-3 font-medium text-right">Replies</th>
                  <th className="pb-3 font-medium text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {data.user_interactions.slice(0, 10).map((interaction, i) => (
                  <tr key={i} className="border-b border-obsidian-800">
                    <td className="py-3 text-cream-300">{interaction.from_user}</td>
                    <td className="py-3 text-cream-300">{interaction.to_user}</td>
                    <td className="py-3 text-cream-400 text-right">{interaction.mention_count}</td>
                    <td className="py-3 text-cream-400 text-right">{interaction.reply_count}</td>
                    <td className="py-3 text-gold-400 text-right font-medium">
                      {interaction.mention_count + interaction.reply_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Quick Insights */}
      <div className="premium-card rounded-xl p-6">
        <h3 className="font-display font-semibold text-cream-100 mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-gold-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          Quick Insights
        </h3>
        <div className="grid md:grid-cols-4 gap-4">
          <div className="p-4 rounded-lg bg-obsidian-900/50 border border-obsidian-700">
            <p className="text-cream-500 text-sm mb-1">Peak Hour</p>
            <p className="text-cream-100 font-medium">
              {data.hourly_activity.reduce((max, h) => h.message_count > max.message_count ? h : max, data.hourly_activity[0]).hour}:00
            </p>
          </div>
          <div className="p-4 rounded-lg bg-obsidian-900/50 border border-obsidian-700">
            <p className="text-cream-500 text-sm mb-1">Busiest Day</p>
            <p className="text-cream-100 font-medium">
              {data.day_of_week_activity.reduce((max, d) => d.message_count > max.message_count ? d : max, data.day_of_week_activity[0]).day_name}
            </p>
          </div>
          <div className="p-4 rounded-lg bg-obsidian-900/50 border border-obsidian-700">
            <p className="text-cream-500 text-sm mb-1">Most Active Channel</p>
            <p className="text-cream-100 font-medium">
              #{data.top_channels[0]?.channel_name || "N/A"}
            </p>
          </div>
          <div className="p-4 rounded-lg bg-obsidian-900/50 border border-obsidian-700">
            <p className="text-cream-500 text-sm mb-1">Top Contributor</p>
            <p className="text-cream-100 font-medium">
              {data.top_users[0]?.username || "N/A"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
