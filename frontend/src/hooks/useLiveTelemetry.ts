'use client';

import { useEffect, useMemo, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { TelemetryMessage, useTelemetry } from '@/components/providers/TelemetryProvider';

type UseLiveTelemetryOptions<TPayload = Record<string, unknown>> = {
    maxItems?: number;
    eventTypes?: string[];
    select?: (message: TelemetryMessage<TPayload>) => TelemetryMessage<TPayload>;
};

export function useLiveTelemetry<TPayload = Record<string, unknown>>(
    channel: string,
    options?: UseLiveTelemetryOptions<TPayload>,
) {
    const { subscribe, connectionState } = useTelemetry();
    const queryClient = useQueryClient();
    const maxItems = options?.maxItems ?? 100;
    const eventTypes = options?.eventTypes;
    const select = options?.select;
    const queryKey = useMemo(() => ['telemetry', channel], [channel]);
    const lastEventTimestampRef = useRef<string | null>(null);
    const prevConnectionState = useRef<string | null>(null);
    const pendingIdsRef = useRef<Set<string>>(new Set());

    const { data } = useQuery<TelemetryMessage<TPayload>[]>({
        queryKey,
        queryFn: () => Promise.resolve([]),
        staleTime: Infinity,
        gcTime: Infinity,
        initialData: [],
    });

    useEffect(() => {
        const unsubscribe = subscribe(
            (incoming) => {
                const transformed = select
                    ? select(incoming as TelemetryMessage<TPayload>)
                    : (incoming as TelemetryMessage<TPayload>);

                // dedupe rapid events
                if (pendingIdsRef.current.has(transformed.id)) return;
                pendingIdsRef.current.add(transformed.id);

                // update last seen timestamp
                try {
                    lastEventTimestampRef.current = transformed.timestamp || new Date().toISOString();
                } catch (e) {
                    lastEventTimestampRef.current = new Date().toISOString();
                }

                queryClient.setQueryData<TelemetryMessage<TPayload>[]>(queryKey, (current) => {
                    const currentItems = current ?? [];

                    // Merge while preserving stable order; newest first
                    const combined = [transformed, ...currentItems];
                    const seen = new Set<string>();
                    const deduped = [] as TelemetryMessage<TPayload>[];
                    for (const it of combined) {
                        if (!it || !it.id) continue;
                        if (seen.has(it.id)) continue;
                        seen.add(it.id);
                        deduped.push(it);
                    }

                    // Keep bounded length
                    return deduped.slice(0, maxItems);
                });

                // release pending id after a short delay to allow other subscribers to dedupe
                setTimeout(() => pendingIdsRef.current.delete(transformed.id), 2500);
            },
            {
                channel,
                eventTypes,
            },
        );

        return unsubscribe;
    }, [channel, eventTypes, maxItems, queryClient, queryKey, select, subscribe]);

    // handle reconnection recovery: fetch missed events since last timestamp
    useEffect(() => {
        const prev = prevConnectionState.current;
        if (connectionState === 'open' && prev && prev !== 'open') {
            // on reconnect: try to recover missed events
            (async () => {
                try {
                    const since = lastEventTimestampRef.current;
                    if (!since) return;

                    const url = `/api/v1/events/sync?since=${encodeURIComponent(since)}`;
                    const res = await fetch(url, { credentials: 'include' });
                    if (!res.ok) return;
                    const recovered = (await res.json()) as TelemetryMessage<TPayload>[];
                    if (!Array.isArray(recovered) || recovered.length === 0) return;

                    // Merge recovered events into cache without causing UI leap:
                    // - Build a map of existing IDs to ignore duplicates
                    queryClient.setQueryData<TelemetryMessage<TPayload>[]>(queryKey, (current) => {
                        const currentItems = current ?? [];
                        const existingIds = new Set(currentItems.map((i) => i.id));

                        // Only insert recovered events that are not already present
                        const toInsert = recovered.filter((r) => r && r.id && !existingIds.has(r.id));

                        // Sort recovered by timestamp ascending so older recovered events are appended
                        toInsert.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

                        // Append older recovered events after the current list to avoid visual jump for newest items
                        const merged = [...currentItems, ...toInsert];

                        // Final stable sort by timestamp descending but preserve relative ordering for identical timestamps
                        merged.sort((a, b) => {
                            const ta = new Date(a.timestamp).getTime();
                            const tb = new Date(b.timestamp).getTime();
                            return tb - ta;
                        });

                        // Deduplicate and bound length
                        const seen = new Set<string>();
                        const deduped: TelemetryMessage<TPayload>[] = [];
                        for (const it of merged) {
                            if (!it || !it.id) continue;
                            if (seen.has(it.id)) continue;
                            seen.add(it.id);
                            deduped.push(it);
                        }

                        return deduped.slice(0, maxItems);
                    });
                } catch (err) {
                    // ignore recovery errors; normal live stream will fill gaps
                    console.warn('telemetry recovery failed', err);
                }
            })();
        }

        prevConnectionState.current = connectionState;
    }, [connectionState, queryClient, queryKey, maxItems]);

    const items = data ?? [];

    return {
        items,
        connectionState,
    };
}
