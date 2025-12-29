"use client";

import { useState, useEffect, useRef } from "react";
import { useApi, QueryResponse, SchemaResponse, TableInfo } from "@/lib/api";

export default function QueryPage() {
  const { apiRequest } = useApi();
  const apiRequestRef = useRef(apiRequest);
  apiRequestRef.current = apiRequest;

  const [sql, setSql] = useState("SELECT * FROM messages LIMIT 10;");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [schema, setSchema] = useState<TableInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [schemaLoading, setSchemaLoading] = useState(true);
  const [error, setError] = useState("");
  const [showSchema, setShowSchema] = useState(true);

  // Fetch schema on load
  useEffect(() => {
    const fetchSchema = async () => {
      try {
        const response = await apiRequestRef.current<SchemaResponse>("/api/query/schema");
        setSchema(response.tables || []);
      } catch (err) {
        console.error("Failed to load schema:", err);
        // If schema fails to load, user may not have data yet
        setSchema([]);
      } finally {
        setSchemaLoading(false);
      }
    };
    fetchSchema();
  }, []);

  const handleExecute = async () => {
    setError("");
    setLoading(true);

    try {
      const data = await apiRequest<QueryResponse>("/api/query/execute", {
        method: "POST",
        body: { sql, limit: 1000 },
      });
      setResult(data);
    } catch (err) {
      const error = err as { detail?: string };
      setError(error.detail || "Query execution failed");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Ctrl+Enter or Cmd+Enter to execute
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      handleExecute();
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* Schema Sidebar */}
      {showSchema && (
        <aside className="w-64 bg-gray-800 border-r border-gray-700 overflow-y-auto">
          <div className="p-4 border-b border-gray-700 flex justify-between items-center">
            <h2 className="font-semibold">Schema</h2>
            <button
              onClick={() => setShowSchema(false)}
              className="text-gray-500 hover:text-white"
            >
              x
            </button>
          </div>
          <div className="p-4 space-y-4">
            {schemaLoading ? (
              <div className="text-gray-500 text-sm">Loading schema...</div>
            ) : schema.length === 0 ? (
              <div className="text-gray-500 text-sm">
                No tables found. Run an extraction first to populate your database.
              </div>
            ) : (
              schema.map((table) => (
                <div key={table.name}>
                  <div
                    className="flex items-center justify-between text-sm font-medium text-indigo-400 cursor-pointer hover:text-indigo-300"
                    onClick={() => setSql(`SELECT * FROM ${table.name} LIMIT 10;`)}
                  >
                    <span>{table.name}</span>
                    <span className="text-gray-500 text-xs">
                      {table.row_count.toLocaleString()}
                    </span>
                  </div>
                  <ul className="mt-1 space-y-1 ml-4">
                    {table.columns.map((col) => (
                      <li
                        key={col.name}
                        className="text-xs text-gray-400 flex justify-between"
                      >
                        <span>{col.name}</span>
                        <span className="text-gray-600">{col.type}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            )}
          </div>
        </aside>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Query Editor */}
        <div className="p-4 border-b border-gray-700">
          <div className="flex justify-between items-center mb-2">
            <div className="flex items-center gap-2">
              {!showSchema && (
                <button
                  onClick={() => setShowSchema(true)}
                  className="text-gray-400 hover:text-white text-sm"
                >
                  Show Schema
                </button>
              )}
              <span className="text-gray-500 text-sm">
                Press Ctrl+Enter to run
              </span>
            </div>
            <button
              onClick={handleExecute}
              disabled={loading}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-600 px-4 py-2 rounded-lg text-sm transition"
            >
              {loading ? "Running..." : "Run Query"}
            </button>
          </div>
          <textarea
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter your SQL query..."
            className="w-full h-32 bg-gray-800 border border-gray-600 rounded-lg px-4 py-3 text-white font-mono text-sm focus:outline-none focus:border-indigo-500 resize-y"
          />
        </div>

        {/* Results */}
        <div className="flex-1 overflow-auto p-4">
          {error && (
            <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded-lg mb-4">
              {error}
            </div>
          )}

          {result && (
            <div>
              <div className="flex justify-between items-center mb-4 text-sm text-gray-400">
                <span>
                  {result.row_count} rows
                  {result.truncated && " (truncated)"}
                </span>
                <span>Executed in {result.execution_time_ms.toFixed(2)}ms</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700">
                      {result.columns.map((col, i) => (
                        <th
                          key={i}
                          className="text-left px-4 py-2 text-gray-400 font-medium"
                        >
                          {col.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, i) => (
                      <tr
                        key={i}
                        className="border-b border-gray-800 hover:bg-gray-800"
                      >
                        {row.map((cell, j) => (
                          <td key={j} className="px-4 py-2 text-gray-300">
                            {cell === null ? (
                              <span className="text-gray-600">NULL</span>
                            ) : typeof cell === "object" ? (
                              JSON.stringify(cell)
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
          )}

          {!result && !error && (
            <div className="text-center text-gray-500 py-20">
              Run a query to see results
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
