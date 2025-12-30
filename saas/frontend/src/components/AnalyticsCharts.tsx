"use client";

import { useEffect, useRef, useState } from "react";

interface ChartData {
  labels: string[];
  values: number[];
}

interface LineChartProps {
  data: ChartData;
  title: string;
  color?: string;
  height?: number;
}

export function LineChart({ data, title, color = "#D4AF37", height = 200 }: LineChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    const width = rect.width;
    const chartHeight = rect.height;
    const padding = { top: 20, right: 20, bottom: 30, left: 50 };

    // Clear canvas
    ctx.clearRect(0, 0, width, chartHeight);

    if (data.values.length === 0) return;

    // Calculate scales
    const maxValue = Math.max(...data.values) * 1.1;
    const minValue = 0;
    const xStep = (width - padding.left - padding.right) / (data.values.length - 1 || 1);
    const yScale = (chartHeight - padding.top - padding.bottom) / (maxValue - minValue || 1);

    // Draw grid lines
    ctx.strokeStyle = "#2E2E2E";
    ctx.lineWidth = 1;
    const gridLines = 5;
    for (let i = 0; i <= gridLines; i++) {
      const y = padding.top + (i * (chartHeight - padding.top - padding.bottom)) / gridLines;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      // Y-axis labels
      const value = maxValue - (i * (maxValue - minValue)) / gridLines;
      ctx.fillStyle = "#8A8477";
      ctx.font = "11px DM Sans";
      ctx.textAlign = "right";
      ctx.fillText(Math.round(value).toLocaleString(), padding.left - 10, y + 4);
    }

    // Draw line
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();

    data.values.forEach((value, i) => {
      const x = padding.left + i * xStep;
      const y = padding.top + (maxValue - value) * yScale;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();

    // Draw gradient fill
    const gradient = ctx.createLinearGradient(0, padding.top, 0, chartHeight - padding.bottom);
    gradient.addColorStop(0, color + "40");
    gradient.addColorStop(1, color + "00");

    ctx.fillStyle = gradient;
    ctx.beginPath();
    data.values.forEach((value, i) => {
      const x = padding.left + i * xStep;
      const y = padding.top + (maxValue - value) * yScale;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.lineTo(padding.left + (data.values.length - 1) * xStep, chartHeight - padding.bottom);
    ctx.lineTo(padding.left, chartHeight - padding.bottom);
    ctx.closePath();
    ctx.fill();

    // Draw data points
    ctx.fillStyle = color;
    data.values.forEach((value, i) => {
      const x = padding.left + i * xStep;
      const y = padding.top + (maxValue - value) * yScale;

      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
    });

    // Draw x-axis labels (showing every nth label to avoid overlap)
    ctx.fillStyle = "#8A8477";
    ctx.font = "10px DM Sans";
    ctx.textAlign = "center";
    const labelStep = Math.ceil(data.labels.length / 7);
    data.labels.forEach((label, i) => {
      if (i % labelStep === 0 || i === data.labels.length - 1) {
        const x = padding.left + i * xStep;
        ctx.fillText(label, x, chartHeight - 10);
      }
    });
  }, [data, color, height]);

  return (
    <div className="premium-card rounded-xl p-6">
      <h3 className="font-display font-semibold text-cream-100 mb-4">{title}</h3>
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: `${height}px` }}
      />
    </div>
  );
}

interface BarChartProps {
  data: ChartData;
  title: string;
  color?: string;
  height?: number;
}

export function BarChart({ data, title, color = "#D4AF37", height = 200 }: BarChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    const width = rect.width;
    const chartHeight = rect.height;
    const padding = { top: 20, right: 20, bottom: 40, left: 50 };

    ctx.clearRect(0, 0, width, chartHeight);

    if (data.values.length === 0) return;

    const maxValue = Math.max(...data.values) * 1.1;
    const barWidth = (width - padding.left - padding.right) / data.values.length - 8;
    const yScale = (chartHeight - padding.top - padding.bottom) / (maxValue || 1);

    // Draw grid lines
    ctx.strokeStyle = "#2E2E2E";
    ctx.lineWidth = 1;
    const gridLines = 5;
    for (let i = 0; i <= gridLines; i++) {
      const y = padding.top + (i * (chartHeight - padding.top - padding.bottom)) / gridLines;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      const value = maxValue - (i * maxValue) / gridLines;
      ctx.fillStyle = "#8A8477";
      ctx.font = "11px DM Sans";
      ctx.textAlign = "right";
      ctx.fillText(Math.round(value).toLocaleString(), padding.left - 10, y + 4);
    }

    // Draw bars
    data.values.forEach((value, i) => {
      const x = padding.left + i * ((width - padding.left - padding.right) / data.values.length) + 4;
      const barHeight = value * yScale;
      const y = chartHeight - padding.bottom - barHeight;

      // Create gradient for bar
      const gradient = ctx.createLinearGradient(x, y, x, chartHeight - padding.bottom);
      gradient.addColorStop(0, color);
      gradient.addColorStop(1, color + "60");

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, barHeight, [4, 4, 0, 0]);
      ctx.fill();
    });

    // Draw x-axis labels
    ctx.fillStyle = "#8A8477";
    ctx.font = "10px DM Sans";
    ctx.textAlign = "center";
    data.labels.forEach((label, i) => {
      const x = padding.left + i * ((width - padding.left - padding.right) / data.values.length) + barWidth / 2 + 4;
      ctx.fillText(label.slice(0, 8), x, chartHeight - 10);
    });
  }, [data, color, height]);

  return (
    <div className="premium-card rounded-xl p-6">
      <h3 className="font-display font-semibold text-cream-100 mb-4">{title}</h3>
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: `${height}px` }}
      />
    </div>
  );
}

interface DonutChartProps {
  data: { label: string; value: number; color: string }[];
  title: string;
  size?: number;
}

export function DonutChart({ data, title, size = 180 }: DonutChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = size * window.devicePixelRatio;
    canvas.height = size * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    ctx.clearRect(0, 0, size, size);

    if (data.length === 0) return;

    const total = data.reduce((sum, item) => sum + item.value, 0);
    const centerX = size / 2;
    const centerY = size / 2;
    const radius = size / 2 - 10;
    const innerRadius = radius * 0.6;

    let startAngle = -Math.PI / 2;

    data.forEach((item, i) => {
      const sliceAngle = (item.value / total) * Math.PI * 2;
      const endAngle = startAngle + sliceAngle;

      ctx.beginPath();
      ctx.arc(centerX, centerY, hoveredIndex === i ? radius + 5 : radius, startAngle, endAngle);
      ctx.arc(centerX, centerY, innerRadius, endAngle, startAngle, true);
      ctx.closePath();

      ctx.fillStyle = item.color + (hoveredIndex === i ? "" : "CC");
      ctx.fill();

      startAngle = endAngle;
    });

    // Draw center text
    ctx.fillStyle = "#F5F5F0";
    ctx.font = "bold 24px Playfair Display";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(total.toLocaleString(), centerX, centerY - 8);

    ctx.fillStyle = "#8A8477";
    ctx.font = "12px DM Sans";
    ctx.fillText("Total", centerX, centerY + 12);
  }, [data, size, hoveredIndex]);

  return (
    <div className="premium-card rounded-xl p-6">
      <h3 className="font-display font-semibold text-cream-100 mb-4">{title}</h3>
      <div className="flex items-center justify-between">
        <canvas
          ref={canvasRef}
          style={{ width: `${size}px`, height: `${size}px` }}
        />
        <div className="flex-1 ml-6 space-y-2">
          {data.map((item, i) => (
            <div
              key={i}
              className="flex items-center justify-between text-sm cursor-pointer group"
              onMouseEnter={() => setHoveredIndex(i)}
              onMouseLeave={() => setHoveredIndex(null)}
            >
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-cream-300 group-hover:text-gold-400 transition-colors">
                  {item.label}
                </span>
              </div>
              <span className="font-mono text-cream-500">
                {item.value.toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: React.ReactNode;
}

export function StatCard({ title, value, change, icon }: StatCardProps) {
  return (
    <div className="premium-card rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="w-10 h-10 rounded-xl bg-gold-400/10 border border-gold-400/20 flex items-center justify-center text-gold-400">
          {icon}
        </div>
        {change !== undefined && (
          <div
            className={`flex items-center gap-1 text-sm px-2 py-0.5 rounded-md ${
              change >= 0
                ? "text-green-400 bg-green-500/10"
                : "text-red-400 bg-red-500/10"
            }`}
          >
            <svg
              className={`w-3 h-3 ${change >= 0 ? "" : "rotate-180"}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
            </svg>
            {Math.abs(change)}%
          </div>
        )}
      </div>
      <p className="text-cream-500 text-sm mb-1">{title}</p>
      <p className="font-display text-2xl font-bold text-cream-100">
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
    </div>
  );
}
