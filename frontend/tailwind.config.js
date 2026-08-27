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
        background: "#F3F5EF",
        surface: "#FFFFFF",
        "surface-raised": "#EEF2EB",
        border: "#D7E1D8",
        "border-subtle": "#E7EEE8",
        primary: {
          50: "#EEF8F2",
          100: "#D7F0E0",
          400: "#5BBF8B",
          500: "#20946E",
          600: "#182A24",
        },
        accent: {
          cyan: "#39B7BE",
          emerald: "#18A57B",
          amber: "#D6A24D",
          rose: "#DB5B4B",
        }
      },
      fontFamily: {
        sans: ['Manrope', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['IBM Plex Mono', 'JetBrains Mono', 'Consolas', 'monospace'],
      },
      boxShadow: {
        soft: '0 18px 45px rgba(18, 32, 26, 0.08)',
      }
    },
  },
  plugins: [],
}
