import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brown: {
          950: "#2A1810",
          900: "#3D2314",
          700: "#5C3A21",
        },
        cream: "#FAF7F2",
        amber: {
          DEFAULT: "#D97706",
          500: "#D97706",
          400: "#F59E0B",
          300: "#FBBF24",
        },
      },
      fontFamily: {
        sans: ["var(--font-manrope)", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
