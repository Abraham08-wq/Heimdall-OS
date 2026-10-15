import type { Metadata } from 'next';
import './globals.css';
import { Providers } from './providers';
import { DashboardShell } from '@/components/Layout/DashboardShell';

export const metadata: Metadata = {
    title: 'ProjectXY | Omni-Threat Orchestrator',
    description: 'Advanced Threat Intelligence, AI Guardrails & Red Team Operations',
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" className="font-sans font-mono">
            <head>
                {/* System font fallbacks for the font variables used across the app */}
                <style
                    dangerouslySetInnerHTML={{
                        __html: `
                            :root {
                                --font-grotesk: system-ui, -apple-system, sans-serif;
                                --font-jetbrains: ui-monospace, monospace;
                            }
                        `,
                    }}
                />
            </head>
            {/* No overflow-hidden here: DashboardShell relies on normal document scrolling */}
            <body className="font-sans antialiased bg-[#0d1117] text-[#c9d1d9]">
                <Providers>
                    <DashboardShell>{children}</DashboardShell>
                </Providers>
            </body>
        </html>
    );
}