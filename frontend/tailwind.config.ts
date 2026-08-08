import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "var(--page)",
        surface: "var(--surface)",
        ink: "var(--ink)",
        ink2: "var(--ink-2)",
        muted: "var(--muted)",
        grid: "var(--grid)",
        baseline: "var(--baseline)",
        series: "var(--series-1)",
        hairline: "var(--border)",
      },
    },
  },
  plugins: [],
};

export default config;
