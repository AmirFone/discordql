"use client";

import { useState } from "react";

interface QueryTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  sql: string;
}

const queryTemplates: QueryTemplate[] = [
  // User Analytics
  {
    id: "most-active-users",
    name: "Most Active Users",
    description: "Find users with the most messages",
    category: "User Analytics",
    sql: `SELECT
  u.username,
  u.display_name,
  COUNT(m.id) as message_count
FROM users u
JOIN messages m ON u.id = m.author_id
GROUP BY u.id, u.username, u.display_name
ORDER BY message_count DESC
LIMIT 20;`,
  },
  {
    id: "user-activity-by-hour",
    name: "User Activity by Hour",
    description: "See when users are most active",
    category: "User Analytics",
    sql: `SELECT
  EXTRACT(HOUR FROM m.created_at) as hour_of_day,
  COUNT(*) as message_count
FROM messages m
GROUP BY hour_of_day
ORDER BY hour_of_day;`,
  },
  {
    id: "new-users-by-day",
    name: "New Users by Day",
    description: "Track new user signups over time",
    category: "User Analytics",
    sql: `SELECT
  DATE(joined_at) as join_date,
  COUNT(*) as new_users
FROM server_members
GROUP BY join_date
ORDER BY join_date DESC
LIMIT 30;`,
  },

  // Message Analytics
  {
    id: "messages-by-channel",
    name: "Messages by Channel",
    description: "Message distribution across channels",
    category: "Message Analytics",
    sql: `SELECT
  c.name as channel_name,
  COUNT(m.id) as message_count
FROM channels c
LEFT JOIN messages m ON c.id = m.channel_id
GROUP BY c.id, c.name
ORDER BY message_count DESC;`,
  },
  {
    id: "daily-message-trends",
    name: "Daily Message Trends",
    description: "Track message volume over time",
    category: "Message Analytics",
    sql: `SELECT
  DATE(created_at) as date,
  COUNT(*) as message_count
FROM messages
GROUP BY date
ORDER BY date DESC
LIMIT 30;`,
  },
  {
    id: "longest-messages",
    name: "Longest Messages",
    description: "Find the most detailed messages",
    category: "Message Analytics",
    sql: `SELECT
  u.username,
  LENGTH(m.content) as content_length,
  LEFT(m.content, 100) as preview,
  m.created_at
FROM messages m
JOIN users u ON m.author_id = u.id
WHERE m.content IS NOT NULL
ORDER BY content_length DESC
LIMIT 20;`,
  },

  // Engagement Analytics
  {
    id: "most-reacted-messages",
    name: "Most Reacted Messages",
    description: "Find messages with the most reactions",
    category: "Engagement",
    sql: `SELECT
  m.id,
  LEFT(m.content, 50) as preview,
  u.username as author,
  COUNT(r.id) as reaction_count
FROM messages m
JOIN users u ON m.author_id = u.id
LEFT JOIN reactions r ON m.id = r.message_id
GROUP BY m.id, m.content, u.username
ORDER BY reaction_count DESC
LIMIT 20;`,
  },
  {
    id: "popular-emojis",
    name: "Popular Emojis",
    description: "Most used emojis in reactions",
    category: "Engagement",
    sql: `SELECT
  e.name as emoji_name,
  COUNT(*) as usage_count
FROM reactions r
JOIN emojis e ON r.emoji_id = e.id
GROUP BY e.id, e.name
ORDER BY usage_count DESC
LIMIT 20;`,
  },
  {
    id: "mention-network",
    name: "User Mention Network",
    description: "Who mentions whom the most",
    category: "Engagement",
    sql: `SELECT
  author.username as mentioner,
  mentioned.username as mentioned_user,
  COUNT(*) as mention_count
FROM message_mentions mm
JOIN messages m ON mm.message_id = m.id
JOIN users author ON m.author_id = author.id
JOIN users mentioned ON mm.user_id = mentioned.id
GROUP BY author.id, mentioned.id, author.username, mentioned.username
ORDER BY mention_count DESC
LIMIT 20;`,
  },

  // Channel Analytics
  {
    id: "channel-growth",
    name: "Channel Growth",
    description: "Track channel activity over time",
    category: "Channel Analytics",
    sql: `SELECT
  c.name as channel_name,
  DATE(m.created_at) as date,
  COUNT(*) as daily_messages
FROM channels c
JOIN messages m ON c.id = m.channel_id
GROUP BY c.id, c.name, date
ORDER BY date DESC, daily_messages DESC
LIMIT 100;`,
  },
  {
    id: "quiet-channels",
    name: "Quiet Channels",
    description: "Find inactive channels",
    category: "Channel Analytics",
    sql: `SELECT
  c.name,
  c.type,
  MAX(m.created_at) as last_message_at,
  COUNT(m.id) as total_messages
FROM channels c
LEFT JOIN messages m ON c.id = m.channel_id
GROUP BY c.id, c.name, c.type
HAVING COUNT(m.id) < 10
ORDER BY total_messages ASC;`,
  },

  // Time-Based Analytics
  {
    id: "weekly-activity",
    name: "Weekly Activity Pattern",
    description: "Activity by day of week",
    category: "Time Analytics",
    sql: `SELECT
  EXTRACT(DOW FROM created_at) as day_of_week,
  CASE EXTRACT(DOW FROM created_at)
    WHEN 0 THEN 'Sunday'
    WHEN 1 THEN 'Monday'
    WHEN 2 THEN 'Tuesday'
    WHEN 3 THEN 'Wednesday'
    WHEN 4 THEN 'Thursday'
    WHEN 5 THEN 'Friday'
    WHEN 6 THEN 'Saturday'
  END as day_name,
  COUNT(*) as message_count
FROM messages
GROUP BY day_of_week
ORDER BY day_of_week;`,
  },
  {
    id: "peak-hours",
    name: "Peak Activity Hours",
    description: "Find the busiest hours",
    category: "Time Analytics",
    sql: `SELECT
  EXTRACT(HOUR FROM created_at) as hour,
  COUNT(*) as message_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM messages
GROUP BY hour
ORDER BY hour;`,
  },
];

const categories = Array.from(new Set(queryTemplates.map((t) => t.category)));

interface QueryTemplatesProps {
  onSelect: (sql: string) => void;
  onClose: () => void;
}

export default function QueryTemplates({ onSelect, onClose }: QueryTemplatesProps) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const filteredTemplates = queryTemplates.filter((t) => {
    const matchesCategory = !selectedCategory || t.category === selectedCategory;
    const matchesSearch =
      !searchQuery ||
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-obsidian-900/80 backdrop-blur-sm">
      <div className="bg-obsidian-800 border border-obsidian-700 rounded-2xl w-full max-w-4xl max-h-[80vh] overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="p-6 border-b border-obsidian-700">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-display text-xl font-semibold text-cream-100">
                Query Templates
              </h2>
              <p className="text-cream-500 text-sm mt-1">
                Pre-built queries for common analytics
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-10 h-10 rounded-xl bg-obsidian-700 hover:bg-obsidian-600 flex items-center justify-center text-cream-400 hover:text-cream-200 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Search */}
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-cream-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search templates..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 input-dark rounded-xl text-sm"
            />
          </div>
        </div>

        {/* Categories */}
        <div className="p-4 border-b border-obsidian-700 flex gap-2 overflow-x-auto">
          <button
            onClick={() => setSelectedCategory(null)}
            className={`px-4 py-1.5 rounded-lg text-sm whitespace-nowrap transition-colors ${
              !selectedCategory
                ? "bg-gold-400/20 text-gold-400 border border-gold-400/30"
                : "bg-obsidian-700 text-cream-400 hover:bg-obsidian-600"
            }`}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-1.5 rounded-lg text-sm whitespace-nowrap transition-colors ${
                selectedCategory === cat
                  ? "bg-gold-400/20 text-gold-400 border border-gold-400/30"
                  : "bg-obsidian-700 text-cream-400 hover:bg-obsidian-600"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Templates Grid */}
        <div className="p-6 overflow-y-auto max-h-[50vh]">
          <div className="grid md:grid-cols-2 gap-4">
            {filteredTemplates.map((template) => (
              <button
                key={template.id}
                onClick={() => {
                  onSelect(template.sql);
                  onClose();
                }}
                className="text-left p-4 rounded-xl bg-obsidian-900/50 border border-obsidian-700 hover:border-gold-400/30 transition-all group"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-medium text-cream-100 group-hover:text-gold-400 transition-colors">
                    {template.name}
                  </h3>
                  <span className="text-xs bg-obsidian-700 px-2 py-0.5 rounded-md text-cream-500">
                    {template.category}
                  </span>
                </div>
                <p className="text-sm text-cream-500 mb-3">{template.description}</p>
                <pre className="text-xs font-mono text-cream-600 bg-obsidian-800 p-2 rounded-lg overflow-hidden max-h-20">
                  {template.sql.slice(0, 150)}...
                </pre>
              </button>
            ))}
          </div>

          {filteredTemplates.length === 0 && (
            <div className="text-center py-12">
              <p className="text-cream-500">No templates match your search</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
