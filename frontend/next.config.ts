import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a self-contained .next/standalone server bundle for docker.
  output: "standalone",
};

export default nextConfig;
