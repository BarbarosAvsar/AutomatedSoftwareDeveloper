import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0b0f1a",
        panel: "#121829",
        accent: "#7c5cff",
        neon: "#39f0ff"
      }
    }
  },
  plugins: []
};

export default config;
