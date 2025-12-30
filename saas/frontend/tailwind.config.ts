import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Obsidian Black Palette
        obsidian: {
          950: "#050505",
          900: "#0A0A0A",
          800: "#111111",
          700: "#1A1A1A",
          600: "#242424",
          500: "#2E2E2E",
          400: "#404040",
          300: "#525252",
        },
        // Antique Gold Palette
        gold: {
          50: "#FDF8E7",
          100: "#F9EFC9",
          200: "#F3E093",
          300: "#E8C85C",
          400: "#D4AF37",
          500: "#B8960F",
          600: "#9A7B0A",
          700: "#7A6108",
          800: "#5C4906",
          900: "#3D3004",
        },
        // Off-White/Cream Palette
        cream: {
          50: "#FEFEF9",
          100: "#FDFCF4",
          200: "#F8F5E8",
          300: "#F0EBD8",
          400: "#E5DFC4",
          500: "#D4CCB0",
        },
        // Semantic colors
        background: "var(--background)",
        foreground: "var(--foreground)",
        surface: "var(--surface)",
        "surface-elevated": "var(--surface-elevated)",
        border: "var(--border)",
        accent: "var(--accent)",
      },
      fontFamily: {
        display: ["Playfair Display", "Georgia", "serif"],
        sans: ["DM Sans", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      boxShadow: {
        gold: "0 0 20px rgba(212, 175, 55, 0.15), 0 0 40px rgba(212, 175, 55, 0.05)",
        "gold-sm": "0 0 10px rgba(212, 175, 55, 0.1), 0 0 20px rgba(212, 175, 55, 0.03)",
        "gold-lg": "0 0 30px rgba(212, 175, 55, 0.2), 0 0 60px rgba(212, 175, 55, 0.1)",
        "inner-gold": "inset 0 1px 0 rgba(212, 175, 55, 0.1)",
      },
      backgroundImage: {
        "gold-gradient": "linear-gradient(135deg, #D4AF37 0%, #B8960F 100%)",
        "gold-gradient-light": "linear-gradient(135deg, #E8C85C 0%, #D4AF37 100%)",
        "obsidian-gradient": "linear-gradient(145deg, #111111 0%, #0A0A0A 100%)",
        "radial-gold": "radial-gradient(circle at center, rgba(212, 175, 55, 0.15) 0%, transparent 70%)",
      },
      animation: {
        "fade-in-up": "fadeInUp 0.6s ease-out forwards",
        shimmer: "shimmer 1.5s infinite",
        "pulse-gold": "pulse-gold 2s infinite",
        "spin-slow": "spin 3s linear infinite",
      },
      keyframes: {
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-gold": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(212, 175, 55, 0.4)" },
          "50%": { boxShadow: "0 0 0 8px rgba(212, 175, 55, 0)" },
        },
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
    },
  },
  plugins: [],
};

export default config;
