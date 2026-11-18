import {
  addQueuedOperation, listQueuedOperations, markOffline, markOnline, readCachedResponse,
  removeQueuedOperation, updateQueuedOperation, writeCachedResponse,
  type OfflineOperation, type OfflineOperationKind,
} from '../offline';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const API_ROOT = `${API_BASE}/api/v1`;

export interface ApiError extends Error { status?: number; payload?: unknown }
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }

let accessToken = sessionStorage.getItem('kawa.access');
let refreshToken = sessionStorage.getItem('kawa.refresh');
let selectedShopId: string | null = sessionStorage.getItem('kawa.shop');
let refreshPromise: Promise<boolean> | null = null;
const OFFLINE_CACHE_PATHS = new Set([
  'auth/me/',
  'shops/',
  'dashboard/summary/',
  'products/',
  'categories/',
  'stock/movements/',
  'sales/',
  'purchases/',
  'suppliers/',
  'members/',
  'reports/sales/',
  'reports/low-stock/',
]);
let queueSyncPromise: Promise<void> | null = null;

function normalizedPath(path: string) {
  const pathname = path.split('?')[0].replace(/^\/+|\/+$/g, '');
  return `${pathname}/`;
}

function offlineCacheKey(path: string) {
  const resource = normalizedPath(path);
  const userId = sessionStorage.getItem('kawa.userId');
  if (!userId || !OFFLINE_CACHE_PATHS.has(resource)) return null;
  const query = resource === 'dashboard/summary/' ? '' : path.split('?')[1] || '';
  const shopScope = resource === 'auth/me/' || resource === 'shops/' ? 'all-shops' : selectedShopId || 'no-shop';
  return [userId, shopScope, resource, query].join('|');
}

function rememberUserId(path: string, data: unknown) {
  if (normalizedPath(path) !== 'auth/me/' || !data || typeof data !== 'object' || !('id' in data)) return;
  sessionStorage.setItem('kawa.userId', String(data.id));
}

export function setTokens(access: string | null, refresh: string | null = refreshToken) {
  accessToken = access;
  refreshToken = refresh;
  access ? sessionStorage.setItem('kawa.access', access) : sessionStorage.removeItem('kawa.access');
  refresh ? sessionStorage.setItem('kawa.refresh', refresh) : sessionStorage.removeItem('kawa.refresh');
  if (!access) sessionStorage.removeItem('kawa.userId');
}
export function getToken() { return accessToken; }
export function setShop(id: string | null) {
  selectedShopId = id;
  id ? sessionStorage.setItem('kawa.shop', id) : sessionStorage.removeItem('kawa.shop');
}
export function getShop() { return selectedShopId; }

async function refreshAccess(): Promise<boolean> {
  if (!refreshToken) return false;
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_ROOT}/auth/token/refresh/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh: refreshToken }),
    }).then(async response => {
      if (!response.ok) { setTokens(null, null); return false; }
      const data = await response.json();
      setTokens(data.access, data.refresh || refreshToken);
      return true;
    }).catch(() => false).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

export async function request<T = unknown>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers || {});
  const method = (options.method || 'GET').toUpperCase();
  const cacheable = method === 'GET';
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  if (selectedShopId && !headers.has('X-Shop-ID')) headers.set('X-Shop-ID', selectedShopId);
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}/${path.replace(/^\//, '')}`, { ...options, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    markOffline();
    const key = cacheable ? offlineCacheKey(path) : null;
    if (key) {
      try {
        const cached = await readCachedResponse(key);
        if (cached) return cached.data as T;
      } catch (cacheError) {
        console.warn('Unable to read cached KawaStock data.', cacheError);
      }

    }
    throw error;
  }
  markOnline();
  if (response.status === 401 && retry && refreshToken && !path.startsWith('auth/')) {
    if (await refreshAccess()) return request<T>(path, options, false);
  }
  if (!response.ok) {
    let payload: unknown;
    try { payload = await response.json(); } catch { payload = await response.text(); }
    const message = typeof payload === 'string' ? payload : payload && typeof payload === 'object'
      ? Object.entries(payload as Record<string, unknown>).map(([key, value]) => `${key === 'detail' ? '' : `${key} : `}${Array.isArray(value) ? value.join(', ') : String(value)}`).join(' · ')
      : `Erreur ${response.status}`;
    const error = new Error(message || `Erreur ${response.status}`) as ApiError;
    error.status = response.status; error.payload = payload; throw error;
  }
  if (response.status === 204) return undefined as T;
  const type = response.headers.get('content-type') || '';
  if (type.includes('application/json')) {
    const data = await response.json() as T;
    rememberUserId(path, data);
    const key = cacheable ? offlineCacheKey(path) : null;
    if (key) {
      try {
        await writeCachedResponse(key, data);
      } catch (error) {
        console.warn('Unable to cache KawaStock data for offline use.', error);
      }
    }
    return data;
  }
  return response.text() as T;
}

async function sendQueuedOperation(operation: OfflineOperation): Promise<void> {
  let path: string;
  let payload = operation.payload;
  if (operation.kind === 'sale') path = 'sales/';
  else if (operation.kind === 'stock_adjustment') path = 'stock/adjustments/';
  else if (operation.kind === 'purchase_create') path = 'purchases/';
  else {
    path = `purchases/${String(operation.payload.purchaseId)}/receive/`;
    if (operation.dependsOn) {
      const dependency = (await listQueuedOperations()).find(item => item.id === operation.dependsOn);
      if (!dependency?.remoteId) {
        throw Object.assign(new Error(dependency?.error || 'La commande liée n’a pas pu être synchronisée.'), { status: 409 });
      }
      path = `purchases/${dependency.remoteId}/receive/`;
      payload = {};
    }
  }
  await post(path, payload);
}

export async function synchronizeOfflineQueue(): Promise<void> {
  if (queueSyncPromise) return queueSyncPromise;
  queueSyncPromise = (async () => {
    const userId = sessionStorage.getItem('kawa.userId');
    const shopId = selectedShopId;
    if (!isOnlineForQueue() || !userId || !shopId) return;
    const operations = await listQueuedOperations();
    for (const operation of operations) {
      if (operation.userId !== userId || operation.shopId !== shopId || operation.state !== 'pending') continue;
      try {
        let response: { id?: string } | undefined;
        if (operation.kind === 'purchase_receive') {
          await sendQueuedOperation(operation);
        } else {
          response = await request<{ id?: string }>(
            operation.kind === 'sale' ? 'sales/' :
              operation.kind === 'stock_adjustment' ? 'stock/adjustments/' : 'purchases/',
            { method: 'POST', body: JSON.stringify(operation.payload) },
          );
        }
        if (operation.kind === 'purchase_create' && response?.id && operation.retainForDependency) {
          await updateQueuedOperation({ ...operation, state: 'done', remoteId: response.id, error: undefined });
        } else {
          await removeQueuedOperation(operation.id);
        }
        if (operation.kind === 'purchase_receive' && operation.dependsOn) {
          const dependency = (await listQueuedOperations()).find(item => item.id === operation.dependsOn);
          if (dependency) await updateQueuedOperation({ ...dependency, retainForDependency: false });
        }
      } catch (error) {
        const status = (error as ApiError).status;
        if (!status || status >= 500 || status === 401) {
          await updateQueuedOperation({
            ...operation, state: 'pending',
            retainForDependency: operation.kind === 'purchase_create' || operation.retainForDependency,
            error: error instanceof Error ? error.message : 'Synchronisation interrompue.',
          });
          break;
        }
        await updateQueuedOperation({
          ...operation, state: 'conflict',
          error: error instanceof Error ? error.message : 'L’opération doit être vérifiée.',
        });
      }
    }
  })().finally(() => {
    queueSyncPromise = null;
    if (typeof window !== 'undefined') window.dispatchEvent(new Event('kawa:offline-queue-updated'));
  });
  return queueSyncPromise;
}

function isOnlineForQueue() {
  return typeof navigator === 'undefined' || navigator.onLine;
}

export async function queueOfflineAction(
  kind: OfflineOperationKind,
  payload: Record<string, unknown>,
  dependsOn?: string,
): Promise<OfflineOperation> {
  const userId = sessionStorage.getItem('kawa.userId');
  if (!userId || !selectedShopId) throw new Error('Choisissez un commerce et reconnectez-vous avant de mettre en attente.');
  const existingOperations = await listQueuedOperations();
  const createdAt = existingOperations.reduce(
    (latest, operation) => Math.max(latest, operation.createdAt + 1),
    Date.now(),
  );
  const id = crypto.randomUUID();
  const idempotencyKey = crypto.randomUUID();
  const body = kind === 'purchase_receive'
    ? payload
    : { ...payload, idempotency_key: idempotencyKey };
  const operation: OfflineOperation = {
    id, idempotencyKey, userId, shopId: selectedShopId, kind, payload: body,
    state: 'pending', createdAt, dependsOn,
    retainForDependency: kind === 'purchase_create' && !isOnlineForQueue(),
  };
  await addQueuedOperation(operation);
  if (isOnlineForQueue()) await synchronizeOfflineQueue();
  return (await listQueuedOperations()).find(item => item.id === id) || { ...operation, state: 'done' };
}

export async function retryQueuedOperation(id: string): Promise<void> {
  const operation = (await listQueuedOperations()).find(item => item.id === id);
  if (!operation) return;
  await updateQueuedOperation({ ...operation, state: 'pending', error: undefined });
  await synchronizeOfflineQueue();
}

export async function discardQueuedOperation(id: string): Promise<void> {
  await removeQueuedOperation(id);
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    void synchronizeOfflineQueue().catch(error => {
      console.error('Unable to synchronize the KawaStock offline queue.', error);
    });
  });
}

export async function list<T>(path: string, params: Record<string, string> = {}): Promise<T[]> {
  const query = new URLSearchParams(params).toString();
  const data = await request<T[] | Page<T>>(`${path}${query ? `?${query}` : ''}`);
  return Array.isArray(data) ? data : data.results || [];
}
export function get<T>(path: string, params: Record<string, string> = {}) {
  const query = new URLSearchParams(params).toString();
  return request<T>(`${path}${query ? `?${query}` : ''}`);
}
export function post<T>(path: string, body: unknown) {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) });
}
export function patch<T>(path: string, body: unknown) {
  return request<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
}
export function remove<T>(path: string) { return request<T>(path, { method: 'DELETE' }); }
export async function download(path: string, filename: string) {
  const headers = new Headers(); if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  if (selectedShopId) headers.set('X-Shop-ID', selectedShopId);
  const response = await fetch(`${API_ROOT}/${path.replace(/^\//, '')}`, { headers });
  if (!response.ok) throw new Error(`Export impossible (HTTP ${response.status})`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}
