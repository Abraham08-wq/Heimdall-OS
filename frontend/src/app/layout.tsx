import type { Metadata } from 'next';
import './globals.css';
import { Providers } from './providers';
import { DashboardShell } from '@/components/Layout/DashboardShell';

// Stub out the variables matching your original names exactly to avoid downstream crashes
const spaceGrotesk = {
  variable: 'font-sans'
};

const jetbrainsMono = {
  variable: 'font-mono'
};

export const metadata: Metadata = {
    title: 'ProjectXY | Omni-Threat Orchestrator',
    description: 'Advanced Threat Intelligence, AI Guardrails & Red Team Operations',
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en" className={`${spaceGrotesk.variable} ${jetbrainsMono.variable}`}>
            <head>
                {/* Fallback override styles ensuring standard fonts map to your variables */}
                <style dangerouslySetInnerHTML={{__html: `
                    :root {
                        --font-grotesk: system-ui, -apple-system, sans-serif;
                        --font-jetbrains: ui-monospace, monospace;
                    }
                `}} />
            </head>
            <body className="font-sans overflow-hidden antialiased bg-[#0d1117] text-[#c9d1d9]">
                <Providers>
                    <DashboardShell>{children}</DashboardShell>
                </Providers>
            </body>
        </html>
    );
}
