/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Layered navy/charcoal surfaces - deepest to most elevated.
        base: {
          950: "#04070d", // page background
          925: "#070b13",
          900: "#0a0f19", // sidebar / topbar surface
          850: "#0d1420", // panel surface
          800: "#111a29", // elevated panel / hover surface
          750: "#152034",
          700: "#1c2a3f", // borders
          600: "#2a3b54", // stronger borders / dividers
          500: "#3d5271",
        },
        accent: {
          300: "#8ff5e6",
          400: "#5eead4",
          500: "#2dd4bf", // primary electric teal
          600: "#14b8a6",
          700: "#0f9488",
        },
        info: {
          400: "#7dd3fc",
          500: "#38bdf8",
          600: "#0ea5e9",
        },
        success: {
          400: "#4ade80",
          500: "#22c55e",
          600: "#16a34a",
        },
        warn: {
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
        },
        danger: {
          400: "#f87171",
          500: "#ef4444",
          600: "#dc2626",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.04em" }],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(45, 212, 191, 0.15), 0 8px 24px -8px rgba(45, 212, 191, 0.35)",
        panel: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 12px 32px -16px rgba(0,0,0,0.5)",
        elevated: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 16px 40px -12px rgba(0,0,0,0.6)",
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(to right, rgba(148,163,184,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(148,163,184,0.06) 1px, transparent 1px)",
        "radial-glow": "radial-gradient(600px circle at var(--glow-x,50%) var(--glow-y,0%), rgba(45,212,191,0.10), transparent 65%)",
      },
      backgroundSize: {
        grid: "28px 28px",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
        fadeIn: {
          "0%": { opacity: 0, transform: "translateY(4px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
        slideInRight: {
          "0%": { opacity: 0, transform: "translateX(12px)" },
          "100%": { opacity: 1, transform: "translateX(0)" },
        },
        slideInLeft: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(0)" },
        },
        pulseDot: {
          "0%, 100%": { opacity: 1 },
          "50%": { opacity: 0.35 },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s ease-in-out infinite",
        fadeIn: "fadeIn 0.35s ease-out both",
        slideInRight: "slideInRight 0.25s ease-out both",
        slideInLeft: "slideInLeft 0.2s ease-out both",
        pulseDot: "pulseDot 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
