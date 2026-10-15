/** @type {import('next').NextConfig} */
const nextConfig = {
    output: "standalone",

    // ESLint warnings are suppressed during Docker builds (run `eslint` locally).
    // TypeScript errors will still fail the build — fix them before pushing.
    eslint: { ignoreDuringBuilds: true },
    typescript: { ignoreBuildErrors: false },

    // ── DEFINITIVE CORS FIX ────────────────────────────────────────────────
    // All /api/* requests go through the Next.js server, which proxies them
    // to the backend container. The browser NEVER directly hits :8000.
    // This eliminates all CORS errors and HttpOnly cookie issues permanently.
    async rewrites() {
        const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
        return [
            // WebSocket telemetry & terminal
            {
                source: "/api/v1/ws/:path*",
                destination: `${backendUrl}/api/v1/ws/:path*`,
            },
            // REST API → FastAPI backend
            {
                source: "/api/:path*",
                destination: `${backendUrl}/api/:path*`,
            },
            // WebSocket terminal — Next.js rewrites support WS upgrade
            {
                source: "/ws/:path*",
                destination: `${backendUrl}/api/v1/ws/:path*`,
            },
        ];
    },

    async redirects() {
        return [
            {
                source: "/",
                destination: "/dashboard",
                permanent: false,
            },
        ];
    },

    // FIXED: CVE-2025-59471 — self-hosted Next.js apps with wildcard
    // remotePatterns are vulnerable to memory-exhaustion DoS via /_next/image,
    // since the optimizer loads external images fully into memory with no
    // size cap. No 14.x patch exists (fixed only in 15.5.10+/16.1.5+, a major
    // upgrade requiring its own migration). Since this platform legitimately
    // needs to load images from arbitrary domains (threat-actor
    // infrastructure, OSINT sources), a fixed allowlist isn't realistic here
    // — so `unoptimized: true` disables the vulnerable resize/optimize
    // pipeline entirely. Images still render via next/image, just served as
    // originals rather than resized/re-encoded server-side. Revert this once
    // you've done a deliberate Next.js 16.1.5+ upgrade.
    images: {
        unoptimized: true,
        remotePatterns: [
            { protocol: "https", hostname: "**" },
            { protocol: "http", hostname: "**" },
        ],
    },
};

module.exports = nextConfig;
