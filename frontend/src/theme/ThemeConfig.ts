export const ThemeConfig = {
    colors: {
        // Matrix-Black Backgrounds
        bg: {
            primary: '#050505',
            secondary: '#0a0a0a',
            tertiary: '#111111',
            panel: '#0f0f0f',
        },
        // Neon Accents
        cyan: {
            DEFAULT: '#00f3ff',
            glow: 'rgba(0, 243, 255, 0.2)',
            dim: '#008f96',
        },
        red: {
            DEFAULT: '#ff2a2a',
            alert: '#ff0000',
            dim: '#8f0000',
        },
        orange: {
            DEFAULT: '#ff8c00',
            warning: '#ffa500',
            dim: '#8f4f00'
        },
        // Text
        text: {
            primary: '#e0e0e0',
            secondary: '#a0a0a0',
            muted: '#505050',
            code: '#00ff41', // Classic Matrix Green for terminals
        },
        borders: {
            subtle: '#1f1f1f',
            active: '#333333',
            highlight: '#555555'
        }
    },
    // Tactical Animations
    animations: {
        pulse: 'animate-pulse',
        ping: 'animate-ping',
        scanline: 'animate-scanline', // Custom CSS needed
    }
};
