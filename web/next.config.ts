import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    config.resolve ??= {};
    config.resolve.alias = {
      ...(config.resolve.alias ?? {}),
      konva$: require.resolve("konva/lib/index.js"),
    };
    return config;
  },
};

export default nextConfig;
