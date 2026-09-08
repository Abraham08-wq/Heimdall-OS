'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { getStoredAccessToken } from '@/lib/api';

export type TelemetrySeverity = 'low' | 'medium' | 'high' | 'critical';

export interface TelemetryMessage<TPayload = Record<string, unknown>> {
    id: string;
    event_type: string;
    channel: string;
    severity?: TelemetrySeverity;
    timestamp: string;
    payload: TPayload;
}

type TelemetryListener = (message: TelemetryMessage) => void;

type SubscribeOptions = {
    channel?: string;
    eventTypes?: string[];
};

type TelemetryConnectionState = 'connecting' | 'open' | 'closed' | 'error';

type TelemetryContextType = {
    connectionState: TelemetryConnectionState;
    subscribe: (listener: TelemetryListener, options?: SubscribeOptions) => () => void;
};

type Subscriber = {
    id: number;
    listener: TelemetryListener;
    channel?: string;
    eventTypes?: Set<string>;
};

const TelemetryContext = createContext<TelemetryContextType>({
    connectionState: 'closed',
    subscribe: () => () => undefined,
});

const BASE_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;

function inferChannel(eventType: string) {
    const normalized = eventType.toUpperCase();

    if (normalized.includes('THREAT')) {
        return 'threats';
    }

    if (normalized.includes('AUTH')) {
        return 'auth_events';
    }

    if (normalized.includes('OPS') || normalized.includes('EXECUTION')) {
        return 'ops_execution';
    }

    return 'telemetry';
}

function buildTelemetryUrl() {
    if (process.env.NEXT_PUBLIC_TELEMETRY_WS_URL) {
        const wsUrl = new URL(process.env.NEXT_PUBLIC_TELEMETRY_WS_URL);
        const token = getStoredAccessToken();

        if (token) {
            wsUrl.searchParams.set('token', token);
        }

        return wsUrl.toString();
    }

    if (typeof window === 'undefined') {
        return 'wss://localhost/api/v1/ws/telemetry';
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = new URL(`${protocol}//${window.location.host}/api/v1/ws/telemetry`);
    const token = getStoredAccessToken();

    if (token) {
        wsUrl.searchParams.set('token', token);
    }

    return wsUrl.toString();
 }

export function TelemetryProvider({ children }: { children: React.ReactNode }) {
    const socketRef = useRef<WebSocket | null>(null);
    const retryCountRef = useRef(0);
    const reconnectTimerRef = useRef<number | null>(null);
    const subscribersRef = useRef<Subscriber[]>([]);
    const subscriberIdRef = useRef(0);
    const [connectionState, setConnectionState] = useState<TelemetryConnectionState>('connecting');

    const broadcast = useCallback((message: TelemetryMessage) => {
        subscribersRef.current.forEach((subscriber) => {
            if (subscriber.channel && subscriber.channel !== message.channel) {
                return;
            }

            if (subscriber.eventTypes && !subscriber.eventTypes.has(message.event_type)) {
                return;
            }

            subscriber.listener(message);
        });
    }, []);

    const connect = useCallback(() => {
        if (typeof window === 'undefined') {
            return;
        }

        if (!getStoredAccessToken() && !process.env.NEXT_PUBLIC_TELEMETRY_WS_URL) {
            setConnectionState('closed');
            return;
        }

        const existing = socketRef.current;
        if (existing && (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)) {
            return;
        }

        setConnectionState('connecting');

        const wsUrl = new URL(buildTelemetryUrl());

        const socket = new WebSocket(wsUrl.toString());
        socketRef.current = socket;

        socket.onopen = () => {
            retryCountRef.current = 0;
            setConnectionState('open');
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data) as Partial<TelemetryMessage>;
                const eventType = data.event_type ?? 'UNKNOWN';
                const timestamp = data.timestamp ?? new Date().toISOString();
                const payload = (data.payload ?? {}) as Record<string, unknown>;
                const channel = data.channel ?? inferChannel(eventType);
                const message: TelemetryMessage = {
                    id: data.id ?? `${eventType}-${timestamp}-${Math.random().toString(36).slice(2, 8)}`,
                    event_type: eventType,
                    channel,
                    severity: data.severity,
                    timestamp,
                    payload,
                };

                broadcast(message);
            } catch (error) {
                console.error('Telemetry parse error', error);
            }
        };

        socket.onclose = () => {
            setConnectionState('closed');
            retryCountRef.current += 1;

            const retryDelay = Math.min(BASE_BACKOFF_MS * 2 ** (retryCountRef.current - 1), MAX_BACKOFF_MS);
            reconnectTimerRef.current = window.setTimeout(() => {
                connect();
            }, retryDelay);
        };

        socket.onerror = () => {
            setConnectionState('error');
            socket.close();
        };
    }, [broadcast]);

    useEffect(() => {
        connect();

        const handleAuthTokenChange = () => {
            if (reconnectTimerRef.current) {
                window.clearTimeout(reconnectTimerRef.current);
                reconnectTimerRef.current = null;
            }

            if (socketRef.current) {
                socketRef.current.close();
                socketRef.current = null;
            }

            connect();
        };

        window.addEventListener('projectxy:auth-token-changed', handleAuthTokenChange);

        return () => {
            window.removeEventListener('projectxy:auth-token-changed', handleAuthTokenChange);

            if (reconnectTimerRef.current) {
                window.clearTimeout(reconnectTimerRef.current);
            }

            if (socketRef.current) {
                socketRef.current.close();
                socketRef.current = null;
            }
        };
    }, [connect]);

    const subscribe = useCallback((listener: TelemetryListener, options?: SubscribeOptions) => {
        const id = subscriberIdRef.current;
        subscriberIdRef.current += 1;

        subscribersRef.current = [
            ...subscribersRef.current,
            {
                id,
                listener,
                channel: options?.channel,
                eventTypes: options?.eventTypes ? new Set(options.eventTypes) : undefined,
            },
        ];

        return () => {
            subscribersRef.current = subscribersRef.current.filter((subscriber) => subscriber.id !== id);
        };
    }, []);

    const value = useMemo(
        () => ({
            connectionState,
            subscribe,
        }),
        [connectionState, subscribe],
    );

    return <TelemetryContext.Provider value={value}>{children}</TelemetryContext.Provider>;
}

export function useTelemetry() {
    return useContext(TelemetryContext);
}
