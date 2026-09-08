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

    // Allow images from any source (for avatars, logos, threat intel icons)
    images: {
        remotePatterns: [
            { protocol: "https", hostname: "**" },
            { protocol: "http", hostname: "**" },
        ],
    },
};

module.exports = nextConfig;
