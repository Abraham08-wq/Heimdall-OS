'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { api, clearStoredAccessToken, setStoredAccessToken, User } from '@/lib/api';

interface AuthContextType {
    user: User | null;
    login: (_token: string) => Promise<void>;
    logout: () => Promise<void>;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    login: async () => { },
    logout: async () => { },
    isLoading: true,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const router = useRouter();
    const pathname = usePathname();
    const isAuthRoute = pathname?.startsWith('/login');

    useEffect(() => {
        const initAuth = async () => {
            setIsLoading(true);
            try {
                const currentUser = await api.getCurrentUser();
                setUser(currentUser);
            } catch {
                setUser(null);
            } finally {
                setIsLoading(false);
            }
        };
        void initAuth();
    }, []);

    const login = async (_token: string) => {
        try {
            if (_token) {
                setStoredAccessToken(_token);
            }

            const currentUser = await api.getCurrentUser();
            setUser(currentUser);
            router.push('/dashboard');
        } catch (error) {
            clearStoredAccessToken();
            setUser(null);
            throw error;
        }
    };

    const logout = async () => {
        try {
            await api.logout();
        } catch {
            // Ignore transport errors on logout; local session state still clears.
        } finally {
            setUser(null);
            router.push('/login');
        }
    };

    // Protect Routes
    useEffect(() => {
        if (!isLoading && !user && pathname?.startsWith('/dashboard')) {
            router.replace('/login');
        }
    }, [user, isLoading, pathname, router]);

    return (
        <AuthContext.Provider value={{ user, login, logout, isLoading }}>
            {isLoading && !isAuthRoute ? (
                <div className="fixed inset-0 bg-[#050505] flex items-center justify-center z-50">
                    <div className="text-cyan-500 font-mono tracking-widest animate-pulse text-sm">
                        [ VERIFYING SECURE SESSION... ]
                    </div>
                </div>
            ) : (
                children
            )}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
