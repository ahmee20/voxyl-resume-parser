/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: "#E9E5DE",
        surface: "#F7F4EE",
        "surface-raised": "#DED8CF",
        border: "#B9B2A8",
        "border-subtle": "#D2CCC3",
        primary: {
          50: "#EFECE6",
          100: "#D8D3CB",
          400: "#77716A",
          500: "#494541",
          600: "#1D1C1A",
        },
        accent: {
          cyan: "#557377",
          emerald: "#4F745F",
          amber: "#A06F32",
          rose: "#D55335",
        }
      },
      fontFamily: {
        sans: ['DM Sans', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        display: ['Space Grotesk', 'DM Sans', 'sans-serif'],
        mono: ['IBM Plex Mono', 'JetBrains Mono', 'Consolas', 'monospace'],
      },
      boxShadow: {
        soft: '5px 5px 0 rgba(29, 28, 26, 0.12)',
      }
    },
  },
  plugins: [],
}
