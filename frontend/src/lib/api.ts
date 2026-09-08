// ─────────────────────────────────────────────────────────────────────────
// API Client — Schema-First, Proxy-First, No CORS
// ─────────────────────────────────────────────────────────────────────────

const API_URL = typeof window === 'undefined'
    ? (process.env.BACKEND_URL || 'http://localhost:8000') + '/api/v1'
    : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1');

const AUTH_TOKEN_STORAGE_KEY = 'projectxy.access_token';

function notifyAuthTokenChange() {
    if (typeof window === 'undefined') {
        return;
    }

    window.dispatchEvent(new Event('projectxy:auth-token-changed'));
}

export function getStoredAccessToken(): string | null {
    if (typeof window === 'undefined') {
        return null;
    }

    return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
}

export function setStoredAccessToken(token: string) {
    if (typeof window === 'undefined') {
        return;
    }

    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
    notifyAuthTokenChange();
}

export function clearStoredAccessToken() {
    if (typeof window === 'undefined') {
        return;
    }

    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    notifyAuthTokenChange();
}

export function buildAuthenticatedWsUrl(path: string): string {
    const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const hostname = typeof window !== 'undefined' ? window.location.host : 'localhost';
    const wsUrl = new URL(`${protocol}//${hostname}${path}`);
    const token = getStoredAccessToken();

    if (token) {
        wsUrl.searchParams.set('token', token);
    }

    return wsUrl.toString();
}

export function createWsTerminal(): WebSocket {
    return new WebSocket(buildAuthenticatedWsUrl('/api/v1/ws/terminal'));
}

export interface User { email: string; full_name: string; role: string; }
export interface Entity { id: string; canonical_name: string; type: string; risk_score: number; attributes: any[]; }
export interface AuthResponse { access_token: string; token_type: string; }

export interface DeviceType {
    key: string;
    label: string;
    icon: string;
    color: string;
}

export interface SimulationType {
    key: string;
    label: string;
    severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
    mitre: string;
}

export interface GhostSession {
    beacon_id: string;
    name?: string;
    ip?: string;
    os?: string;
    status?: string;
    last_seen?: string;
    privilege?: string;
    metadata?: Record<string, any>;
}

export interface GhostPayload {
    id: string;
    name: string;
    lang: string;
    tag: string;
    color: string;
    code: string;
    description?: string;
}

export interface OffensiveTool {
    key: string;
    label: string;
    category: string;
    risk: string;
}

export interface SocPlaybook {
    key: string;
    label: string;
    steps: string[];
    auto_isolate: boolean;
}

/**
 * Device — matches backend/app/schemas/device.py Device schema.
 * Keep in sync with the PostgreSQL Device model (models.py).
 */
export interface Device {
    id: string;
    tenant_id?: string;
    owner_id?: string;
    // Core identification
    name: string;
    hostname?: string;
    ip?: string;
    mac?: string;
    // Categorisation
    type?: string;          // Server | Workstation | Network | IoT | Mobile | OT/ICS | Cloud
    os?: string;
    department?: string;
    tags?: string[];
    // Posture
    risk_score?: number;
    status?: string;        // online | offline | quarantined
    // Discovery data
    ports?: number[];
    services?: string[];
    cves?: string[];
    // Geo
    latitude?: number;
    longitude?: number;
    accuracy_radius?: number;
    // Meta
    active_trace?: boolean;
    last_seen?: string;
    created_at?: string;
}

export interface DeviceCreate {
    name: string;
    hostname?: string;
    ip?: string;
    mac?: string;
    type?: string;
    os?: string;
    department?: string;
    tags?: string[];
    risk_score?: number;
    status?: string;
    ports?: number[];
    services?: string[];
    cves?: string[];
    latitude?: number;
    longitude?: number;
    accuracy_radius?: number;
    owner_id?: string;
}



class ApiClient {
    // ── Core Request Logic (Global Interceptor) ──
    private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        const controller = new AbortController();
        const timeoutMs = 8000; // 8s global timeout to avoid hanging requests
        const timeout = setTimeout(() => controller.abort(), timeoutMs);
        const customHeaders = (options.headers as Record<string, string>) || {};
        const hasContentType = Object.keys(customHeaders).some(key => key.toLowerCase() === 'content-type');
        const storedToken = typeof window !== 'undefined' ? getStoredAccessToken() : null;
        const hasAuthorization = Object.keys(customHeaders).some(key => key.toLowerCase() === 'authorization');
        const isLoginRequest = endpoint.includes('/auth/access-token');
        const isAuthPage = typeof window !== 'undefined' && window.location.pathname.startsWith('/login');

        const headers: Record<string, string> = {
            ...(hasContentType ? {} : { 'Content-Type': 'application/json' }),
            ...(storedToken && !hasAuthorization ? { Authorization: `Bearer ${storedToken}` } : {}),
            ...customHeaders,
        };

        const rawUrl = `${API_URL}${endpoint}`;
        const sanitizedUrl = rawUrl.replace(/([^:]\/)\/+/g, `$1`);

        const response = await fetch(sanitizedUrl, {
            ...options,
            credentials: 'include', // Handles HttpOnly cookies automatically
            headers,
            signal: controller.signal,
        }).finally(() => clearTimeout(timeout));

        // ── [GLOBAL SECURITY INTERCEPTOR] ────────────────────────────────────
        if (!response.ok) {
            let errorDetail = response.statusText;

            try {
                const errorPayload = await response.clone().json();
                if (typeof errorPayload?.detail === 'string' && errorPayload.detail.trim()) {
                    errorDetail = errorPayload.detail;
                }
            } catch {
                try {
                    const errorText = await response.clone().text();
                    if (errorText.trim()) {
                        errorDetail = errorText;
                    }
                } catch {
                    // Keep the HTTP status text as the fallback message.
                }
            }

            if (response.status === 401) {
                console.warn("Unauthorized: Token may be expired.");
                // Only redirect for authenticated routes; login failures should stay on the form.
                if (process.env.NEXT_PUBLIC_DEV_MODE !== 'true' && !isLoginRequest && !isAuthPage) {
                    window.location.href = '/login';
                }
            }

            throw new Error(`API Error (${response.status}): ${errorDetail}`);
        }
        
        // ─────────────────────────────────────────────────────────────────────

        return response.json();
    }

    // ── Auth ──
    async login(username: string, password: string): Promise<AuthResponse> {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        const response = await this.request<AuthResponse>('/auth/access-token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData.toString(),
        });

        setStoredAccessToken(response.access_token);
        return response;
    }

    async getCurrentUser(): Promise<User> { return this.request<User>('/auth/me'); }
    async logout(): Promise<void> {
        try {
            await this.request<{ status: string }>('/auth/logout', { method: 'POST' });
        } finally {
            clearStoredAccessToken();
        }
    }

    // ── Entities ──
    async getEntities(type?: string): Promise<Entity[]> { return this.request<Entity[]>(`/entities/${type ? `?type=${type}` : ''}`); }
    async getEntity(id: string): Promise<Entity> { return this.request<Entity>(`/entities/${id}`); }

    // ── Devices ──
    async updateDevice(id: string, data: any): Promise<any> { return this.request<any>(`/devices/${id}`, { method: 'PUT', body: JSON.stringify(data) }); }
    async getDevices(): Promise<any[]> { return this.request<any[]>('/devices/'); }
    async getDevicesByType(type: string): Promise<any[]> { return this.request<any[]>(`/devices/?type=${encodeURIComponent(type)}`); }

    // ── Config (dynamic constants — replaces all hardcoded frontend arrays) ──
    async getDeviceTypes(): Promise<DeviceType[]> { return this.request<DeviceType[]>('/config/device-types'); }
    async getDeviceTypeLabels(): Promise<string[]> { return this.request<string[]>('/config/device-types/labels'); }
    async getSimulationTypes(): Promise<SimulationType[]> { return this.request<SimulationType[]>('/config/simulation-types'); }
    async getOffensiveTools(): Promise<OffensiveTool[]> { return this.request<OffensiveTool[]>('/config/offensive-tools'); }
    async getSocPlaybooks(): Promise<SocPlaybook[]> { return this.request<SocPlaybook[]>('/config/soc-playbooks'); }

    // ── Analysis ──
    async getRiskAnalysis(id: string): Promise<any> { return this.request<any>(`/analysis/risk/${id}`); }
    async getGraphNeighborhood(id: string): Promise<any> { return this.request<any>(`/analysis/graph/neighborhood/${id}`); }
    async getGraph(): Promise<any> { return this.request<any>(`/analysis/graph/full`); }
    async getAISummary(id: string): Promise<{ summary: string }> { return this.request<{ summary: string }>(`/analysis/ai/summary/${id}`); }
    async synthesizeExploit(req: { ip: string, target_cve: string }): Promise<any> { return this.request<any>('/analysis/exploit/synthesize', { method: 'POST', body: JSON.stringify(req) }); }
    async getThreatActorProfile(actorName: string): Promise<any> { return this.request<any>(`/intel/radar/threat-actor/${actorName}`); }
    async getRadarSnapshot(): Promise<any> { return this.request<any>('/intel/radar/snapshot'); }
    async getActiveThreats(): Promise<any> { return this.request<any>('/intel/soc/active-threats'); }

    // ── War Room ──
    async correlateWarRoomIndicators(indicators: string[]): Promise<any> {
        return this.request<any>('/warroom/attribution/correlate', {
            method: 'POST',
            body: JSON.stringify({
                indicators,
                metadata: { note: 'War Room initiated correlation' }
            })
        });
    }

    async isolateWarRoomHost(hostIdentifier: string, severity: number): Promise<any> {
        return this.request<any>('/warroom/containment/isolate', {
            method: 'POST',
            body: JSON.stringify({
                host_identifier: hostIdentifier,
                severity,
                reason: 'War Room initiated isolation'
            })
        });
    }

    // ── Stats ──
    async getStats(): Promise<any> { return this.request<any>('/stats/'); }

    // ── Tactical AI ──
    async getSentinelStatus(): Promise<any> { return this.request<any>('/ai/sentinel/status'); }
    async generateScenario(difficulty: string): Promise<any> { return this.request<any>(`/ai/nemesis/generate-scenario?difficulty=${difficulty}`, { method: 'POST' }); }
    async getTacticalFeed(): Promise<any[]> { return this.request<any[]>('/ai/feed/merged'); }

    // ── AI Analyst ──
    async chatWithAnalyst(entityId: string, question: string): Promise<{ response: string }> { return this.request<{ response: string }>('/analyst/chat', { method: 'POST', body: JSON.stringify({ entity_id: entityId, question }) }); }
    async investigateEntity(entityId: string): Promise<any> { return this.request<any>(`/analyst/investigate/${entityId}`); }
    async chatWithOracle(prompt: string, context: string, role: string): Promise<{ reply: string }> {
        return this.request<{ reply: string }>('/ai/chat', {
            method: 'POST',
            body: JSON.stringify({ prompt, context, role })
        });
    }

    // ── Global Connectors ──
    async searchOSINT(query: string): Promise<any[]> { return this.request<any[]>(`/connectors/osint/search?query=${encodeURIComponent(query)}`); }
    async search(query: string): Promise<any> { return this.request<any>('/analysis/search', { method: 'POST', body: JSON.stringify({ query }) }); }

    // ── Guardian IoT ──
    async getIoTDevices(): Promise<any[]> { return this.request<any[]>('/guardian/devices'); }
    async sendIoTCommand(deviceId: string, command: string): Promise<any> { return this.request<any>('/guardian/command', { method: 'POST', body: JSON.stringify({ device_id: deviceId, command }) }); }

    // ── Audit ──
    async getAuditLogs(skip = 0, limit = 100): Promise<any[]> { return this.request<any[]>(`/audit/logs?skip=${skip}&limit=${limit}`); }
    async verifyAuditChain(): Promise<any> { return this.request<any>('/audit/verify', { method: 'POST' }); }

    // ── Mission Chain ──
    async launchMission(target: string): Promise<any> { return this.request<any>('/missions/launch', { method: 'POST', body: JSON.stringify({ target }) }); }
    async getMission(missionId: string): Promise<any> { return this.request<any>(`/missions/${missionId}`); }
    async listMissions(): Promise<any> { return this.request<any>('/missions'); }
    async abortMission(missionId: string): Promise<any> { return this.request<any>(`/missions/${missionId}`, { method: 'DELETE' }); }

    // ── Vanguard Cyber Command ──
    async scanOmniProbe(targetCidr: string): Promise<any> { return this.request<any>('/recon/scan', { method: 'POST', body: JSON.stringify({ target_cidr: targetCidr, scan_type: 'FULL_SPECTRUM' }) }); }
    async quarantineNode(targetIp: string): Promise<any> { return this.request<any>('/sandbox/quarantine', { method: 'POST', body: JSON.stringify({ target_ip: targetIp }) }); }
    async generatePQCKeys(): Promise<any> { return this.request<any>('/forge/pqc/generate'); }
    async predictThreats(): Promise<any> { return this.request<any>('/oracle/predict_threats', { method: 'POST', body: JSON.stringify({ region: 'GLOBAL', timeframe_hours: 72 }) }); }
    async distributeVaccine(vaccineId: string): Promise<any> { return this.request<any>(`/intel/hivemind/distribute-vaccine/${vaccineId}`, { method: 'POST' }); }
    async blackholeIp(ip: string): Promise<any> { return this.request<any>(`/intel/soc/blackhole/${ip}`, { method: 'POST' }); }

    // ── Ghost Shell (C2 Sessions + Payloads) ──
    async getGhostSessions(): Promise<{ sessions: GhostSession[]; count: number }> { return this.request('/ghost/sessions'); }
    async getPayloadLibrary(lang?: string, tag?: string): Promise<{ payloads: GhostPayload[]; count: number }> {
        const params = new URLSearchParams();
        if (lang) params.set('lang', lang);
        if (tag) params.set('tag', tag);
        const qs = params.toString() ? `?${params.toString()}` : '';
        return this.request(`/ghost/payloads${qs}`);
    }


    // ── Cognitive Shield Passthrough ──
    async apiRequest<T = any>(endpoint: string, options: RequestInit = {}): Promise<T> { return this.request<T>(endpoint, options); }

    // ── Firewall & Forensic ──
    async firewallStats(tenantId = 'default'): Promise<any> { return this.request<any>(`/stats/`); }
    async firewallRecentThreats(limit = 50): Promise<any[]> { return this.request<any[]>(`/firewall/threats/recent?limit=${limit}`); }
    async forensicHunt(payload: any): Promise<any> { return this.request<any>('/forensic/hunt/similarity', { method: 'POST', body: JSON.stringify(payload) }); }
    async forensicEntityTimeline(entityId: string, tenantId = 'default', limit = 100): Promise<any> { return this.request<any>(`/forensic/hunt/entity/${entityId}?tenant_id=${tenantId}&limit=${limit}`); }
    async forensicHealth(): Promise<any> { return this.request<any>('/forensic/hunt/health'); }

    // ── Proxy Evaluation ──
    async agentSessions(tenantId = 'default'): Promise<any> { return this.request<any>(`/agent/proxy/sessions?tenant_id=${tenantId}`); }
    async agentEvaluate(payload: any): Promise<any> { return this.request<any>('/agent/proxy/evaluate', { method: 'POST', body: JSON.stringify(payload) }); }
    async agentIssueSession(payload: any): Promise<any> { return this.request<any>('/agent/proxy/session', { method: 'POST', body: JSON.stringify(payload) }); }
    async agentRevokeSession(agentId: string, tenantId = 'default'): Promise<any> { return this.request<any>(`/agent/proxy/session/${agentId}?tenant_id=${tenantId}`, { method: 'DELETE' }); }
}

export const api = new ApiClient();

/** Extended options for standalone apiRequest — supports ?params appended to URL */
export interface ApiRequestOptions extends Omit<RequestInit, 'body'> {
    params?: Record<string, string | number | boolean>;
    body?: BodyInit | Record<string, any> | null;
}

export async function apiRequest<T = any>(endpoint: string, options: ApiRequestOptions = {}): Promise<T> {
    const { params, body, ...fetchOptions } = options;

    // Build URL with query params
    let url = endpoint;
    if (params && Object.keys(params).length > 0) {
        const qs = new URLSearchParams(
            Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)]))
        ).toString();
        url = `${endpoint}${endpoint.includes('?') ? '&' : '?'}${qs}`;
    }

    // Serialize body
    let serializedBody: BodyInit | null | undefined;
    let extraHeaders: Record<string, string> = {};
    if (body !== undefined && body !== null) {
        if (typeof body === 'object' && !(body instanceof FormData) && !(body instanceof Blob)) {
            serializedBody = JSON.stringify(body);
            extraHeaders['Content-Type'] = 'application/json';
        } else {
            serializedBody = body as BodyInit;
        }
    }

    return api.apiRequest<T>(url, {
        ...fetchOptions,
        ...(serializedBody !== undefined ? { body: serializedBody } : {}),
        headers: { ...extraHeaders, ...fetchOptions.headers },
    });
}