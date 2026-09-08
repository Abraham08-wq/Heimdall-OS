
import { buildAuthenticatedWsUrl, getStoredAccessToken } from '@/lib/api';

type WebSocketCallback = (data: any) => void;

const BASE_RECONNECT_MS = 3_000;
const MAX_RECONNECT_MS = 30_000;
const MAX_RECONNECT_ATTEMPTS = 10;

class SocketClient {
    private socket: WebSocket | null = null;
    private listeners: Record<string, WebSocketCallback[]> = {};
    private reconnectAttempt: number = 0;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private onConnectCallback: (() => void) | null = null;
    private onDisconnectCallback: (() => void) | null = null;
    private connectionStatus: boolean = false;
    private _destroyed: boolean = false;

    constructor() {
        // Listen for auth token changes (e.g., after login) and reconnect with fresh token.
        if (typeof window !== 'undefined') {
            window.addEventListener('projectxy:auth-token-changed', () => {
                this.resetReconnect();
                // Only reconnect if we were previously connected or are mid-retry.
                if (this.connectionStatus || this.reconnectTimer !== null) {
                    console.log('[Socket] Auth token changed — reconnecting with fresh token.');
                    this.connect();
                }
            });
        }
    }

    /** Reset exponential-backoff state (call after successful login). */
    resetReconnect(): void {
        this.reconnectAttempt = 0;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }

    connect(): void {
        if (this._destroyed) return;

        if (
            this.socket &&
            (this.socket.readyState === WebSocket.OPEN ||
                this.socket.readyState === WebSocket.CONNECTING)
        ) {
            return;
        }

        // Build the URL here (not in constructor) so the token is always fresh.
        const url = buildAuthenticatedWsUrl('/api/v1/ws/terminal');
        console.log(`[Socket] Connecting to ${url}... (attempt ${this.reconnectAttempt + 1})`);
        this.socket = new WebSocket(url);

        this.socket.onopen = () => {
            console.log('[Socket] Connected to Situation Room');
            this.connectionStatus = true;
            this.reconnectAttempt = 0; // Reset on successful connection
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
            if (this.onConnectCallback) this.onConnectCallback();
        };

        this.socket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                // Handle clean server-side disconnect signals (e.g., 4003 auth rejection).
                if (message.type === 'SYSTEM_DISCONNECT') {
                    console.warn(`[Socket] Server disconnected: ${message.reason}`);
                    // Do not auto-reconnect on intentional auth rejections.
                    if (message.code === 4003) {
                        this._destroyed = true;
                        return;
                    }
                }
                if (message.type && message.data !== undefined) {
                    this.emit(message.type, message.data);
                } else {
                    this.emit('log_entry', message);
                }
            } catch {
                // Raw string log — not JSON
                this.emit('log_entry', {
                    id: Date.now(),
                    timestamp: new Date().toISOString(),
                    source: 'RAW_STREAM',
                    message: event.data,
                    level: 'INFO',
                });
            }
        };

        this.socket.onclose = () => {
            console.log('[Socket] Disconnected.');
            this.connectionStatus = false;
            if (this.onDisconnectCallback) this.onDisconnectCallback();

            if (this._destroyed) return;
            if (this.reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
                console.warn(`[Socket] Max reconnect attempts (${MAX_RECONNECT_ATTEMPTS}) reached. Giving up.`);
                return;
            }

            // Exponential backoff: 3s, 6s, 12s, 24s, capped at 30s.
            const delay = Math.min(BASE_RECONNECT_MS * 2 ** this.reconnectAttempt, MAX_RECONNECT_MS);
            console.log(`[Socket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempt + 1}/${MAX_RECONNECT_ATTEMPTS})...`);
            this.reconnectAttempt++;
            this.reconnectTimer = setTimeout(() => {
                this.reconnectTimer = null;
                this.connect();
            }, delay);
        };

        this.socket.onerror = (err) => {
            console.error('[Socket] Error:', err);
            this.socket?.close();
        };
    }

    disconnect(): void {
        this._destroyed = true;
        this.resetReconnect();
        this.socket?.close();
    }

    isConnected(): boolean {
        return this.connectionStatus;
    }

    onConnect(callback: () => void): void {
        this.onConnectCallback = callback;
    }

    onDisconnect(callback: () => void): void {
        this.onDisconnectCallback = callback;
    }

    subscribe(eventType: string, callback: WebSocketCallback): void {
        if (!this.listeners[eventType]) {
            this.listeners[eventType] = [];
        }
        this.listeners[eventType].push(callback);
    }

    unsubscribe(eventType: string, callback: WebSocketCallback): void {
        if (!this.listeners[eventType]) return;
        this.listeners[eventType] = this.listeners[eventType].filter((cb) => cb !== callback);
    }

    private emit(eventType: string, data: any): void {
        const typeListeners = this.listeners[eventType] || [];
        const allListeners = this.listeners['*'] || [];
        [...typeListeners, ...allListeners].forEach((cb) => cb(data));
    }
}

export const socketClient = new SocketClient();
