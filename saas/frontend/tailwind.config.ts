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
        // Warm Off-White Background Palette
        base: {
          50: "#FFFDF8",   // Lightest - page background
          100: "#FBF9F3",  // Slightly warmer
          200: "#F5F2EA",  // Card backgrounds
          300: "#EDE9DD",  // Hover states
          400: "#E4DFD0",  // Borders
          500: "#D6D0C1",  // Muted elements
        },
        // Soft Gray Surface Palette (for cards and elevated elements)
        surface: {
          50: "#F8F6F2",   // Card background
          100: "#F0EDE6",  // Elevated card
          200: "#E8E4DA",  // Hover
          300: "#D9D4C8",  // Active
          400: "#C5BFB0",  // Border
          500: "#A8A196",  // Muted
        },
        // Text colors for light backgrounds
        ink: {
          900: "#1A1814",  // Primary text
          800: "#2D2A23",  // Headings
          700: "#3F3B31",  // Strong text
          600: "#5C5850",  // Body text
          500: "#7A756A",  // Secondary text
          400: "#9A9488",  // Muted text
          300: "#B5AFA3",  // Placeholder
        },
        // Antique Gold Palette (kept from original)
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
        // Legacy obsidian (for code blocks and dark elements)
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
        // Legacy cream (for compatibility)
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
        "surface-color": "var(--surface)",
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
        // Light theme shadows
        "soft": "0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.03)",
        "soft-md": "0 4px 16px rgba(0, 0, 0, 0.06), 0 1px 4px rgba(0, 0, 0, 0.04)",
        "soft-lg": "0 8px 32px rgba(0, 0, 0, 0.08), 0 2px 8px rgba(0, 0, 0, 0.04)",
        "inner-light": "inset 0 1px 0 rgba(255, 255, 255, 0.5)",
      },
      backgroundImage: {
        "gold-gradient": "linear-gradient(135deg, #D4AF37 0%, #B8960F 100%)",
        "gold-gradient-light": "linear-gradient(135deg, #E8C85C 0%, #D4AF37 100%)",
        "base-gradient": "linear-gradient(145deg, #FFFDF8 0%, #F8F6F2 100%)",
        "surface-gradient": "linear-gradient(145deg, #F8F6F2 0%, #F0EDE6 100%)",
        "radial-gold": "radial-gradient(circle at center, rgba(212, 175, 55, 0.08) 0%, transparent 70%)",
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
