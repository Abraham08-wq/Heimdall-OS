'use client';

import React, { createContext, useContext, useState } from 'react';

interface CommandContextType {
    selectedTarget: string | null;
    setSelectedTarget: (id: string | null) => void;
    isInterceptOpen: boolean;
    setInterceptOpen: (open: boolean) => void;
}

const CommandContext = createContext<CommandContextType | undefined>(undefined);

export function CommandProvider({ children }: { children: React.ReactNode }) {
    const [selectedTarget, setSelectedTarget] = useState<string | null>(null);
    const [isInterceptOpen, setInterceptOpen] = useState(false);

    return (
        <CommandContext.Provider value={{ selectedTarget, setSelectedTarget, isInterceptOpen, setInterceptOpen }}>
            {children}
        </CommandContext.Provider>
    );
}

export function useCommand() {
    const context = useContext(CommandContext);
    if (context === undefined) {
        throw new Error('useCommand must be used within a CommandProvider');
    }
    return context;
}
