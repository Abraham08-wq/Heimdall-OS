import { create } from 'zustand';

type Tab = 'payloads' | 'ghost' | 'iot' | 'intel';

interface UIState {
    isInterceptOpen: boolean;
    activeTab: Tab;
    securityPulse: number; // 0-100
    isEmergencyLockdown: boolean;

    // Actions
    toggleIntercept: (isOpen?: boolean) => void;
    setActiveTab: (tab: Tab) => void;
    setSecurityPulse: (score: number) => void;
    triggerLockdown: () => void;
}

export const useUIStore = create<UIState>((set) => ({
    isInterceptOpen: false,
    activeTab: 'intel',
    securityPulse: 98,
    isEmergencyLockdown: false,

    toggleIntercept: (isOpen) => set((state) => ({
        isInterceptOpen: isOpen !== undefined ? isOpen : !state.isInterceptOpen
    })),

    setActiveTab: (tab) => set({ activeTab: tab }),

    setSecurityPulse: (score) => set({ securityPulse: score }),

    triggerLockdown: () => set({ isEmergencyLockdown: true, securityPulse: 0 }),
}));
