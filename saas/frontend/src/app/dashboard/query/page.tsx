"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useApi, QueryResponse, SchemaResponse, TableInfo, ExampleQuery, ExampleQueriesResponse } from "@/lib/api";

// =============================================================================
// SQL Syntax Highlighting
// =============================================================================

const SQL_KEYWORDS = new Set([
  'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'IS', 'NULL', 'AS',
  'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS', 'ON',
  'GROUP', 'BY', 'ORDER', 'ASC', 'DESC', 'HAVING', 'LIMIT', 'OFFSET',
  'DISTINCT', 'ALL', 'UNION', 'INTERSECT', 'EXCEPT', 'CASE', 'WHEN', 'THEN',
  'ELSE', 'END', 'CAST', 'COALESCE', 'NULLIF', 'WITH', 'RECURSIVE', 'LIKE',
  'ILIKE', 'BETWEEN', 'EXISTS', 'ANY', 'SOME', 'TRUE', 'FALSE', 'OVER',
  'PARTITION', 'ROWS', 'RANGE', 'UNBOUNDED', 'PRECEDING', 'FOLLOWING', 'CURRENT', 'ROW',
  'FILTER', 'WITHIN', 'INTERVAL'
]);

const SQL_FUNCTIONS = new Set([
  'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'ROUND', 'FLOOR', 'CEIL', 'ABS',
  'LOWER', 'UPPER', 'TRIM', 'LENGTH', 'SUBSTRING', 'CONCAT', 'REPLACE',
  'NOW', 'DATE', 'EXTRACT', 'DATE_TRUNC', 'TO_CHAR', 'TO_DATE', 'AGE',
  'COALESCE', 'NULLIF', 'GREATEST', 'LEAST', 'ROW_NUMBER', 'RANK',
  'DENSE_RANK', 'LEAD', 'LAG', 'FIRST_VALUE', 'LAST_VALUE', 'NTH_VALUE',
  'STRING_AGG', 'ARRAY_AGG', 'JSON_AGG', 'JSONB_AGG'
]);

function tokenize(sql: string): Array<{ type: string; value: string }> {
  const tokens: Array<{ type: string; value: string }> = [];
  let i = 0;

  while (i < sql.length) {
    if (/\s/.test(sql[i])) {
      let ws = '';
      while (i < sql.length && /\s/.test(sql[i])) ws += sql[i++];
      tokens.push({ type: 'whitespace', value: ws });
      continue;
    }
    if (sql[i] === "'") {
      let str = "'";
      i++;
      while (i < sql.length && sql[i] !== "'") {
        if (sql[i] === "'" && sql[i + 1] === "'") { str += "''"; i += 2; }
        else str += sql[i++];
      }
      if (i < sql.length) str += sql[i++];
      tokens.push({ type: 'string', value: str });
      continue;
    }
    if (/\d/.test(sql[i]) || (sql[i] === '.' && /\d/.test(sql[i + 1]))) {
      let num = '';
      while (i < sql.length && /[\d.]/.test(sql[i])) num += sql[i++];
      tokens.push({ type: 'number', value: num });
      continue;
    }
    if (/[a-zA-Z_]/.test(sql[i])) {
      let word = '';
      while (i < sql.length && /[a-zA-Z0-9_]/.test(sql[i])) word += sql[i++];
      const upper = word.toUpperCase();
      if (SQL_KEYWORDS.has(upper)) tokens.push({ type: 'keyword', value: word });
      else if (SQL_FUNCTIONS.has(upper)) tokens.push({ type: 'function', value: word });
      else tokens.push({ type: 'identifier', value: word });
      continue;
    }
    if (sql[i] === '-' && sql[i + 1] === '-') {
      let comment = '--';
      i += 2;
      while (i < sql.length && sql[i] !== '\n') comment += sql[i++];
      tokens.push({ type: 'comment', value: comment });
      continue;
    }
    tokens.push({ type: 'operator', value: sql[i] });
    i++;
  }
  return tokens;
}

// Type color map for schema
const TYPE_COLORS: Record<string, string> = {
  'bigint': 'text-blue-400 bg-blue-400/10',
  'integer': 'text-blue-400 bg-blue-400/10',
  'smallint': 'text-blue-400 bg-blue-400/10',
  'text': 'text-green-400 bg-green-400/10',
  'character varying': 'text-green-400 bg-green-400/10',
  'boolean': 'text-purple-400 bg-purple-400/10',
  'timestamp with time zone': 'text-amber-400 bg-amber-400/10',
  'timestamp without time zone': 'text-amber-400 bg-amber-400/10',
  'uuid': 'text-cyan-400 bg-cyan-400/10',
  'json': 'text-pink-400 bg-pink-400/10',
  'jsonb': 'text-pink-400 bg-pink-400/10',
};

function getTypeColor(type: string): string {
  return TYPE_COLORS[type.toLowerCase()] || 'text-ink-500 bg-cream-500/10';
}

// =============================================================================
// Syntax Highlighted Editor Component
// =============================================================================

function SQLEditor({
  value,
  onChange,
  onExecute,
  placeholder = "-- Enter SQL query\nSELECT * FROM messages LIMIT 10;"
}: {
  value: string;
  onChange: (v: string) => void;
  onExecute: () => void;
  placeholder?: string;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const highlightRef = useRef<HTMLPreElement>(null);

  const tokens = useMemo(() => tokenize(value), [value]);

  const syncScroll = () => {
    if (textareaRef.current && highlightRef.current) {
      highlightRef.current.scrollTop = textareaRef.current.scrollTop;
      highlightRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      onExecute();
    }
    if (e.key === "Tab") {
      e.preventDefault();
      const start = textareaRef.current?.selectionStart || 0;
      const end = textareaRef.current?.selectionEnd || 0;
      const newValue = value.substring(0, start) + "  " + value.substring(end);
      onChange(newValue);
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.selectionStart = textareaRef.current.selectionEnd = start + 2;
        }
      }, 0);
    }
  };

  // Colors for light background
  return (
    <div className="relative font-mono text-sm leading-relaxed h-full">
      {/* Syntax highlighted overlay */}
      <pre
        ref={highlightRef}
        className="absolute inset-0 p-4 overflow-auto pointer-events-none whitespace-pre-wrap break-words m-0"
        aria-hidden="true"
      >
        {value ? tokens.map((token, i) => {
          let className = "text-slate-800";
          switch (token.type) {
            case 'keyword': className = "text-purple-700 font-semibold"; break;
            case 'function': className = "text-blue-600"; break;
            case 'string': className = "text-green-700"; break;
            case 'number': className = "text-orange-600"; break;
            case 'comment': className = "text-slate-400 italic"; break;
            case 'identifier': className = "text-slate-700"; break;
          }
          return <span key={i} className={className}>{token.value}</span>;
        }) : (
          <span className="text-slate-400">{placeholder}</span>
        )}
        {/* Extra space to ensure scrolling matches */}
        <br />
      </pre>

      {/* Actual textarea (invisible text, handles input) */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onScroll={syncScroll}
        className="relative w-full h-full p-4 bg-transparent text-transparent caret-purple-600 resize-none outline-none selection:bg-purple-200"
        spellCheck={false}
        autoCapitalize="off"
        autoComplete="off"
        autoCorrect="off"
      />
    </div>
  );
}

// =============================================================================
// Schema Panel Component
// =============================================================================

function SchemaPanel({
  schema,
  loading,
  onInsert
}: {
  schema: TableInfo[];
  loading: boolean;
  onInsert: (text: string) => void;
}) {
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");

  const toggleTable = (name: string) => {
    const next = new Set(expandedTables);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setExpandedTables(next);
  };

  const filteredSchema = useMemo(() => {
    if (!search) return schema;
    const lower = search.toLowerCase();
    return schema.filter(t =>
      t.name.toLowerCase().includes(lower) ||
      t.columns.some(c => c.name.toLowerCase().includes(lower))
    );
  }, [schema, search]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="w-5 h-5 border-2 border-gold-400/30 border-t-gold-400 rounded-full animate-spin" />
      </div>
    );
  }

  if (schema.length === 0) {
    return (
      <div className="text-center py-8 px-4">
        <div className="w-10 h-10 rounded-lg bg-surface-200 flex items-center justify-center mx-auto mb-3">
          <svg className="w-5 h-5 text-ink-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
        </div>
        <p className="text-ink-600 text-sm font-medium">No Data Yet</p>
        <p className="text-ink-400 text-xs mt-1">Extract Discord data to see schema</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="p-3 border-b border-surface-400">
        <div className="relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search tables..."
            className="w-full pl-8 pr-3 py-1.5 bg-surface-100 border border-surface-400 rounded-lg text-xs text-ink-600 placeholder-cream-600 focus:outline-none focus:border-gold-400/50"
          />
        </div>
      </div>

      {/* Tables */}
      <div className="flex-1 overflow-y-auto p-2">
        {filteredSchema.map((table) => (
          <div key={table.name} className="mb-1">
            {/* Table header */}
            <button
              onClick={() => toggleTable(table.name)}
              className="w-full flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-surface-200/50 transition-colors group"
            >
              <svg
                className={`w-3 h-3 text-ink-400 transition-transform ${expandedTables.has(table.name) ? 'rotate-90' : ''}`}
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <svg className="w-4 h-4 text-gold-600/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <span className="flex-1 text-left text-sm text-ink-700 font-medium truncate">{table.name}</span>
              <span className="text-[10px] text-ink-500 tabular-nums">{table.row_count.toLocaleString()}</span>
            </button>

            {/* Expanded columns */}
            {expandedTables.has(table.name) && (
              <div className="ml-5 pl-3 border-l border-surface-400 mt-1 mb-2">
                {/* Quick insert */}
                <button
                  onClick={() => onInsert(`SELECT * FROM ${table.name} LIMIT 10`)}
                  className="w-full text-left px-2 py-1.5 text-[11px] text-gold-600/80 hover:text-gold-600 hover:bg-surface-200/30 rounded transition-colors mb-1"
                >
                  SELECT * FROM {table.name}
                </button>

                {/* Columns */}
                {table.columns.map((col) => (
                  <button
                    key={col.name}
                    onClick={() => onInsert(col.name)}
                    className="w-full flex items-center justify-between px-2 py-1.5 hover:bg-surface-200/30 rounded transition-colors group"
                  >
                    <span className="text-xs text-ink-600 group-hover:text-ink-700 truncate">{col.name}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${getTypeColor(col.type)}`}>
                      {col.type.replace('character varying', 'varchar').replace('timestamp with time zone', 'timestamptz').replace('without time zone', '')}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Stats footer */}
      <div className="p-3 border-t border-surface-400 bg-surface-100/30">
        <div className="flex items-center justify-between text-[10px] text-ink-400">
          <span>{schema.length} tables</span>
          <span>{schema.reduce((sum, t) => sum + t.columns.length, 0)} columns</span>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Examples Panel Component (Visible at bottom)
// =============================================================================

function ExamplesPanel({
  examples,
  categories,
  onSelect
}: {
  examples: ExampleQuery[];
  categories: string[];
  onSelect: (sql: string) => void;
}) {
  const [activeCategory, setActiveCategory] = useState<string>("all");

  const filtered = activeCategory === 'all'
    ? examples
    : examples.filter(e => e.category === activeCategory);

  if (examples.length === 0) return null;

  return (
    <div className="border-t border-surface-400 bg-surface-100/50 flex-shrink-0">
      {/* Header with category tabs */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-surface-400/50">
        <svg className="w-4 h-4 text-gold-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        <span className="text-xs font-medium text-ink-700 flex-shrink-0">Examples</span>
        <div className="flex gap-1 overflow-x-auto ml-2">
          <button
            onClick={() => setActiveCategory('all')}
            className={`px-2 py-1 text-[10px] rounded-md whitespace-nowrap transition-colors ${
              activeCategory === 'all' ? 'bg-gold-400/20 text-gold-600' : 'text-ink-500 hover:text-ink-600'
            }`}
          >
            All
          </button>
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-2 py-1 text-[10px] rounded-md whitespace-nowrap transition-colors ${
                activeCategory === cat ? 'bg-gold-400/20 text-gold-600' : 'text-ink-500 hover:text-ink-600'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Horizontally scrollable example cards */}
      <div className="flex gap-2 p-3 overflow-x-auto">
        {filtered.map((example, i) => (
          <button
            key={i}
            onClick={() => onSelect(example.sql)}
            className="flex-shrink-0 w-56 text-left p-3 rounded-lg bg-surface-200/50 border border-surface-400 hover:border-gold-400/40 hover:bg-surface-200 transition-all group"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-ink-700 font-medium group-hover:text-gold-600 transition-colors truncate">
                {example.name}
              </span>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-surface-300 text-ink-500 ml-2 flex-shrink-0">
                {example.category}
              </span>
            </div>
            <p className="text-[10px] text-ink-400 line-clamp-2 leading-relaxed">{example.description}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Main Query Page
// =============================================================================

export default function QueryPage() {
  const { apiRequest } = useApi();
  const apiRequestRef = useRef(apiRequest);
  apiRequestRef.current = apiRequest;

  const [sql, setSql] = useState("");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [schema, setSchema] = useState<TableInfo[]>([]);
  const [examples, setExamples] = useState<ExampleQuery[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [schemaLoading, setSchemaLoading] = useState(true);
  const [error, setError] = useState<{ message: string; type: string; position?: number; hint?: string } | null>(null);
  const [showSchema, setShowSchema] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [schemaRes, examplesRes] = await Promise.all([
          apiRequestRef.current<SchemaResponse>("/api/query/schema"),
          apiRequestRef.current<ExampleQueriesResponse>("/api/query/examples")
        ]);
        setSchema(schemaRes.tables || []);
        setExamples(examplesRes.queries || []);
        setCategories(examplesRes.categories || []);
      } catch (err) {
        console.error("Failed to load data:", err);
      } finally {
        setSchemaLoading(false);
      }
    };
    fetchData();
  }, []);

  const parseError = useCallback((detail: string): { message: string; type: string; position?: number; hint?: string } => {
    const lower = detail.toLowerCase();

    // Extract position if present: "message (at position N)"
    let position: number | undefined;
    let cleanDetail = detail;
    const posMatch = detail.match(/\(at position (\d+)\)/);
    if (posMatch) {
      position = parseInt(posMatch[1], 10);
      cleanDetail = detail.replace(posMatch[0], '').trim();
    }

    // Extract hint if present: "message Hint: some hint"
    let hint: string | undefined;
    const hintMatch = cleanDetail.match(/Hint:\s*(.+)$/i);
    if (hintMatch) {
      hint = hintMatch[1].trim();
      cleanDetail = cleanDetail.replace(/Hint:\s*.+$/i, '').trim();
    }

    // Determine error type from the message
    if (lower.includes('syntax')) {
      return { message: cleanDetail, type: 'syntax', position, hint };
    }
    if (lower.includes('does not exist') || lower.includes('undefined')) {
      return { message: cleanDetail, type: 'syntax', position, hint };
    }
    if (lower.includes('column must appear') || lower.includes('grouping')) {
      return { message: cleanDetail, type: 'syntax', position, hint };
    }
    if (lower.includes('ambiguous')) {
      return { message: cleanDetail, type: 'syntax', position, hint };
    }
    if (lower.includes('permission') || lower.includes('forbidden') || lower.includes('access denied')) {
      return { message: cleanDetail, type: 'permission', position, hint };
    }
    if (lower.includes('timeout')) {
      return { message: cleanDetail, type: 'timeout', position, hint };
    }
    if (lower.includes('type') || lower.includes('convert') || lower.includes('coerce')) {
      return { message: cleanDetail, type: 'syntax', position, hint };
    }

    return { message: cleanDetail || detail, type: 'error', position, hint };
  }, []);

  const handleExecute = async () => {
    if (!sql.trim()) {
      setError({ message: "Enter a query first", type: 'error' });
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const data = await apiRequest<QueryResponse>("/api/query/execute", {
        method: "POST",
        body: { sql, limit: 1000 },
      });
      setResult(data);
    } catch (err) {
      const apiError = err as { detail?: string };
      setError(parseError(apiError.detail || "Query failed"));
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const insertText = (text: string) => {
    setSql(prev => prev ? `${prev}\n${text}` : text);
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] -m-8 overflow-hidden">
      {/* Schema Sidebar */}
      {showSchema && (
        <aside className="w-64 flex-shrink-0 bg-surface-100/50 border-r border-surface-400 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between p-3 border-b border-surface-400">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-gold-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
              </svg>
              <span className="text-sm font-semibold text-ink-800">Schema</span>
            </div>
            <button
              onClick={() => setShowSchema(false)}
              className="p-1 rounded hover:bg-surface-200 text-ink-500 hover:text-ink-600 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <SchemaPanel schema={schema} loading={schemaLoading} onInsert={insertText} />
        </aside>
      )}

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between gap-4 px-4 py-2 border-b border-surface-400 bg-surface-100 flex-shrink-0">
          <div className="flex items-center gap-2">
            {!showSchema && (
              <button
                onClick={() => setShowSchema(true)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-ink-600 hover:text-gold-600 bg-surface-200 rounded-lg transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                </svg>
                Schema
              </button>
            )}
            <span className="text-ink-500 text-xs">SQL Editor</span>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-ink-400 text-[10px] hidden sm:flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 bg-surface-200 rounded text-[9px]">Ctrl</kbd>
              <span>+</span>
              <kbd className="px-1.5 py-0.5 bg-surface-200 rounded text-[9px]">Enter</kbd>
            </span>
            <button
              onClick={handleExecute}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-1.5 bg-gold-400 hover:bg-gold-500 disabled:opacity-50 text-obsidian-900 font-medium text-xs rounded-lg transition-colors"
            >
              {loading ? (
                <div className="w-3.5 h-3.5 border-2 border-obsidian-900/30 border-t-obsidian-900 rounded-full animate-spin" />
              ) : (
                <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              )}
              Run
            </button>
          </div>
        </div>

        {/* Editor - White background for distinction */}
        <div className="h-44 flex-shrink-0 border-b border-surface-400 bg-white overflow-hidden">
          <SQLEditor value={sql} onChange={setSql} onExecute={handleExecute} />
        </div>

        {/* Results */}
        <div className="flex-1 overflow-auto p-4 min-h-0">
          {error && (
            <div className={`p-3 rounded-lg mb-4 ${
              error.type === 'syntax' ? 'bg-amber-500/10 border border-amber-500/20' :
              error.type === 'timeout' ? 'bg-orange-500/10 border border-orange-500/20' :
              error.type === 'permission' ? 'bg-red-500/10 border border-red-500/20' :
              'bg-red-500/10 border border-red-500/20'
            }`}>
              <div className="flex items-start gap-3">
                <svg className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
                  error.type === 'syntax' ? 'text-amber-400' :
                  error.type === 'timeout' ? 'text-orange-400' :
                  'text-red-400'
                }`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div className="flex-1">
                  <p className={`text-sm font-medium ${
                    error.type === 'syntax' ? 'text-amber-300' :
                    error.type === 'timeout' ? 'text-orange-300' :
                    'text-red-300'
                  }`}>{error.message}</p>
                  {/* Show position indicator */}
                  {error.position !== undefined && (
                    <p className="text-xs text-ink-500 mt-1">
                      Error at character position {error.position}
                    </p>
                  )}
                  {/* Show hint if available */}
                  {error.hint && (
                    <p className={`text-xs mt-1.5 ${
                      error.type === 'syntax' ? 'text-amber-400/70' :
                      error.type === 'timeout' ? 'text-orange-400/70' :
                      'text-red-400/70'
                    }`}>
                      <span className="font-medium">Hint:</span> {error.hint}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {result && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3 text-xs">
                  <span className="text-ink-600">
                    <span className="text-gold-600 font-semibold">{result.row_count.toLocaleString()}</span> rows
                    {result.truncated && <span className="text-ink-400 ml-1">(truncated)</span>}
                  </span>
                  <span className="text-ink-400">{result.execution_time_ms.toFixed(1)}ms</span>
                </div>
                <button
                  onClick={() => {
                    const csv = [
                      result.columns.map(c => c.name).join(','),
                      ...result.rows.map(row => row.map(cell =>
                        cell === null ? '' : typeof cell === 'string' && cell.includes(',') ? `"${cell}"` : String(cell)
                      ).join(','))
                    ].join('\n');
                    const blob = new Blob([csv], { type: 'text/csv' });
                    const a = document.createElement('a');
                    a.href = URL.createObjectURL(blob);
                    a.download = 'results.csv';
                    a.click();
                  }}
                  className="flex items-center gap-1.5 px-2.5 py-1 bg-surface-200 hover:bg-surface-300 text-ink-600 text-[10px] rounded-lg transition-colors"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  CSV
                </button>
              </div>

              <div className="rounded-lg border border-surface-400 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-surface-100">
                        {result.columns.map((col, i) => (
                          <th key={i} className="text-left px-3 py-2 font-medium text-ink-600 whitespace-nowrap border-b border-surface-400">
                            {col.name}
                            <span className="ml-1.5 text-[9px] text-ink-400 font-normal">{col.type}</span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-obsidian-800">
                      {result.rows.map((row, i) => (
                        <tr key={i} className="hover:bg-surface-100/30 transition-colors">
                          {row.map((cell, j) => (
                            <td key={j} className="px-3 py-2 text-ink-600 whitespace-nowrap max-w-xs truncate">
                              {cell === null ? (
                                <span className="text-ink-400 italic">null</span>
                              ) : typeof cell === "boolean" ? (
                                <span className={cell ? "text-emerald-400" : "text-red-400"}>{String(cell)}</span>
                              ) : typeof cell === "object" ? (
                                <span className="text-cyan-400 font-mono">{JSON.stringify(cell)}</span>
                              ) : (
                                String(cell)
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {!result && !error && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-12 h-12 rounded-xl bg-surface-100 border border-surface-400 flex items-center justify-center mb-3">
                <svg className="w-6 h-6 text-ink-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <p className="text-ink-600 text-sm font-medium">Ready to query</p>
              <p className="text-ink-400 text-xs mt-1">Write SQL or pick an example below</p>
            </div>
          )}
        </div>

        {/* Examples Panel at bottom */}
        <ExamplesPanel examples={examples} categories={categories} onSelect={setSql} />
      </div>
    </div>
  );
}
