'use client';

import { useState, useEffect } from 'react';
import InterceptModal from '@/components/ui/InterceptModal';

export default function InterceptWrapper() {
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.ctrlKey && e.code === 'Space') {
                e.preventDefault();
                setIsModalOpen(prev => !prev);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

    if (!mounted) return null;

    return (
        <InterceptModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    );
}
