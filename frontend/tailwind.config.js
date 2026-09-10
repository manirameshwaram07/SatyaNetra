/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        night: {
          950: "#050A14",
          900: "#0B1220",
          800: "#111B2E",
          700: "#1B2740",
        },
        neon: {
          cyan: "#22D3EE",
          blue: "#3B82F6",
          green: "#34D399",
          amber: "#FBBF24",
          red: "#F87171",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Consolas", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "scan-line": "scan 2.2s linear infinite",
      },
      keyframes: {
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(400%)" },
        },
      },
    },
  },
  plugins: [],
};