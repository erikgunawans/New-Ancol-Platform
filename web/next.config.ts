import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  env: {
    API_BASE_URL: process.env.API_BASE_URL || "http://localhost:8080",
  },
};

export default nextConfig;
