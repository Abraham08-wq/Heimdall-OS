'use client';

import { Search, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export default function SearchBar() {
    const router = useRouter();
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSearch = async (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && query.trim()) {
            setLoading(true);
            try {
                // Call Natural Language Search API
                const result = await api.search(query);

                if (result.type === 'search_results' && result.data.length > 0) {
                    // Navigate to first match for MVP
                    router.push(`/dashboard/entity/${result.data[0].id}`);
                } else if (result.type === 'text') {
                    alert(`AI Response: ${result.message}`);
                } else {
                    alert("No entities found or query not understood.");
                }

            } catch (err) {
                console.error("Search failed", err);
                alert("Search system offline.");
            } finally {
                setLoading(false);
            }
        }
    };

    return (
        <div className="w-full max-w-4xl mx-auto relative group">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                {loading ? (
                    <Loader2 className="h-5 w-5 text-primary animate-spin" />
                ) : (
                    <Search className="h-5 w-5 text-primary opacity-70 group-focus-within:opacity-100 transition-opacity" />
                )}
            </div>
            <input
                type="text"
                className="w-full bg-surface/50 border border-white/10 rounded-xl py-4 pl-12 pr-4 
                   text-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary/50 
                   focus:ring-2 focus:ring-primary/20 transition-all font-mono backdrop-blur-sm"
                placeholder={"Enter Entity Name (e.g., \"Target_Alpha\") or ID and press Enter..."}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleSearch}
                disabled={loading}
            />

            {/* Search Hints */}
            <div className="absolute -bottom-6 left-2 flex gap-4 text-xs text-gray-400 font-mono">
                <span>Try: &quot;admin&quot;</span>
                <span>•</span>
                <span>or an existing ID</span>
            </div>
        </div>
    );
}
