import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                background: "#0B0F19", // Deep Obsidian
                surface: "#111827",    // Slightly lighter for panels
                "surface-border": "#1f2937", // Cyber grid border
                primary: "#00e5ff",    // Electric Cyan
                alert: "#ffab00",      // Amber for alerts
                critical: "#ff003c",   // Crimson for critical threats
                success: "#00ff41",    // Terminal Green
                muted: "#9ca3af",      // Inactive gray
            },
            fontFamily: {
                mono: ["var(--font-jetbrains)", "monospace"],
                sans: ["var(--font-grotesk)", "sans-serif"],
            },
            borderRadius: {
                DEFAULT: "0px",
                none: "0px",
                sm: "0px",
                md: "0px",
                lg: "0px",
                xl: "0px",
                "2xl": "0px",
                "3xl": "0px",
                full: "0px",
            },
            animation: {
                "scan-line": "scanLine 4s linear infinite",
                blink: "blink 1s step-start infinite",
            },
            keyframes: {
                scanLine: {
                    "0%": { top: "0%", opacity: "0" },
                    "5%": { opacity: "1" },
                    "95%": { opacity: "1" },
                    "100%": { top: "100%", opacity: "0" },
                },
                blink: {
                    "50%": { opacity: "0" }
                }
            }
        },
    },
    plugins: [],
};
export default config;
