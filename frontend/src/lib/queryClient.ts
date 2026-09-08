import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';

function emitQueryError(detail: { source: 'query' | 'mutation'; key?: unknown; message: string }) {
    if (typeof window === 'undefined') {
        return;
    }

    window.dispatchEvent(new CustomEvent('projectxy:query-error', { detail }));
}

export const queryClient = new QueryClient({
    queryCache: new QueryCache({
        onError: (error, query) => {
            console.error('Query failed', query.queryKey, error);
            emitQueryError({
                source: 'query',
                key: query.queryKey,
                message: error instanceof Error ? error.message : 'Unknown query error',
            });
        },
    }),
    mutationCache: new MutationCache({
        onError: (error, _variables, _context, mutation) => {
            console.error('Mutation failed', mutation.options.mutationKey, error);
            emitQueryError({
                source: 'mutation',
                key: mutation.options.mutationKey,
                message: error instanceof Error ? error.message : 'Unknown mutation error',
            });
        },
    }),
    defaultOptions: {
        queries: {
            staleTime: 60_000,
            refetchOnWindowFocus: true,
            refetchOnReconnect: true,
            retry: 1,
        },
        mutations: {
            retry: 1,
        },
    },
});