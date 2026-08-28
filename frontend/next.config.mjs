const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
// "static" (real-data GitHub Pages snapshot) and "demo" (sample fixtures)
// both ship with no backend behind them, so both need a static export.
// Only "api" (the default) runs as a normal Next.js server.
const isStaticExport = process.env.NEXT_PUBLIC_DATA_MODE === "static" || process.env.NEXT_PUBLIC_DATA_MODE === "demo";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // GitHub Pages only serves static files -- the demo build exports plain
  // HTML/CSS/JS instead of running a Node server. Local dev and a "real
  // backend" build both skip this and run normally.
  ...(isStaticExport && {
    output: "export",
    trailingSlash: true,
    images: { unoptimized: true },
  }),
  // GitHub Pages project sites are served under /<repo-name>/, not /.
  basePath,
  assetPrefix: basePath ? `${basePath}/` : undefined,
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
  },
};

export default nextConfig;
