"use client";

import { useState, useRef, useEffect } from "react";
import { QueryResponse } from "@/lib/api";

interface ExportButtonProps {
  result: QueryResponse;
}

export default function ExportButton({ result }: ExportButtonProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const exportToCSV = () => {
    const headers = result.columns.map((col) => col.name).join(",");
    const rows = result.rows
      .map((row) =>
        row
          .map((cell) => {
            if (cell === null) return "";
            const value = typeof cell === "object" ? JSON.stringify(cell) : String(cell);
            // Escape quotes and wrap in quotes if contains comma, quote, or newline
            if (value.includes(",") || value.includes('"') || value.includes("\n")) {
              return `"${value.replace(/"/g, '""')}"`;
            }
            return value;
          })
          .join(",")
      )
      .join("\n");

    const csv = `${headers}\n${rows}`;
    downloadFile(csv, "query_results.csv", "text/csv");
    setShowDropdown(false);
  };

  const exportToJSON = () => {
    const data = result.rows.map((row) =>
      result.columns.reduce((obj, col, i) => {
        obj[col.name] = row[i];
        return obj;
      }, {} as Record<string, unknown>)
    );

    const json = JSON.stringify(data, null, 2);
    downloadFile(json, "query_results.json", "application/json");
    setShowDropdown(false);
  };

  const exportToMarkdown = () => {
    const headers = `| ${result.columns.map((col) => col.name).join(" | ")} |`;
    const separator = `| ${result.columns.map(() => "---").join(" | ")} |`;
    const rows = result.rows
      .map(
        (row) =>
          `| ${row
            .map((cell) => {
              if (cell === null) return "_null_";
              const value = typeof cell === "object" ? JSON.stringify(cell) : String(cell);
              return value.replace(/\|/g, "\\|").replace(/\n/g, " ");
            })
            .join(" | ")} |`
      )
      .join("\n");

    const markdown = `${headers}\n${separator}\n${rows}`;
    downloadFile(markdown, "query_results.md", "text/markdown");
    setShowDropdown(false);
  };

  const copyToClipboard = async () => {
    const headers = result.columns.map((col) => col.name).join("\t");
    const rows = result.rows
      .map((row) =>
        row
          .map((cell) => {
            if (cell === null) return "";
            return typeof cell === "object" ? JSON.stringify(cell) : String(cell);
          })
          .join("\t")
      )
      .join("\n");

    const text = `${headers}\n${rows}`;
    await navigator.clipboard.writeText(text);
    setShowDropdown(false);
  };

  const downloadFile = (content: string, filename: string, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="btn-outline-gold px-4 py-2 rounded-lg text-sm flex items-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        Export
        <svg className={`w-4 h-4 transition-transform ${showDropdown ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {showDropdown && (
        <div className="absolute right-0 mt-2 w-56 rounded-xl bg-obsidian-800 border border-obsidian-700 shadow-xl z-50 overflow-hidden">
          <div className="p-2">
            <button
              onClick={exportToCSV}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-cream-300 hover:bg-obsidian-700 hover:text-gold-400 transition-colors"
            >
              <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <div className="text-left">
                <p className="text-sm font-medium">Export as CSV</p>
                <p className="text-xs text-cream-500">Spreadsheet format</p>
              </div>
            </button>

            <button
              onClick={exportToJSON}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-cream-300 hover:bg-obsidian-700 hover:text-gold-400 transition-colors"
            >
              <svg className="w-5 h-5 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              <div className="text-left">
                <p className="text-sm font-medium">Export as JSON</p>
                <p className="text-xs text-cream-500">Developer format</p>
              </div>
            </button>

            <button
              onClick={exportToMarkdown}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-cream-300 hover:bg-obsidian-700 hover:text-gold-400 transition-colors"
            >
              <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <div className="text-left">
                <p className="text-sm font-medium">Export as Markdown</p>
                <p className="text-xs text-cream-500">Documentation format</p>
              </div>
            </button>

            <div className="border-t border-obsidian-700 my-2" />

            <button
              onClick={copyToClipboard}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-cream-300 hover:bg-obsidian-700 hover:text-gold-400 transition-colors"
            >
              <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <div className="text-left">
                <p className="text-sm font-medium">Copy to Clipboard</p>
                <p className="text-xs text-cream-500">Tab-separated values</p>
              </div>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
