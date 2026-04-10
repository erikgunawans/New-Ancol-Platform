import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ancol: {
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#1a237e",
          600: "#151c6a",
          700: "#101556",
          800: "#0b0e42",
          900: "#06072e",
        },
      },
    },
  },
  plugins: [],
};

export default config;
