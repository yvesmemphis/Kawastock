import { ref } from 'vue';

const DATABASE_NAME = 'kawastock-offline';
const DATABASE_VERSION = 2;
const RESPONSE_STORE = 'api-responses';
const QUEUE_STORE = 'queued-operations';

export type OfflineOperationKind = 'sale' | 'stock_adjustment' | 'purchase_create' | 'purchase_receive';
export type OfflineOperationState = 'pending' | 'conflict' | 'done';

export interface OfflineOperation {
  id: string;
  idempotencyKey: string;
  userId: string;
  shopId: string;
  kind: OfflineOperationKind;
  payload: Record<string, unknown>;
  state: OfflineOperationState;
  createdAt: number;
  error?: string;
  remoteId?: string;
  dependsOn?: string;
  retainForDependency?: boolean;
}

export interface CachedApiResponse {
  key: string;
  data: unknown;
  cachedAt: number;
}

export const isOnline = ref(typeof navigator === 'undefined' || navigator.onLine);

let databasePromise: Promise<IDBDatabase> | null = null;

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => { isOnline.value = true; });
  window.addEventListener('offline', () => { isOnline.value = false; });
}

export function markOffline() {
  isOnline.value = false;
}

export function markOnline() {
  isOnline.value = true;
}

function openDatabase(): Promise<IDBDatabase> {
  if (typeof indexedDB === 'undefined') {
    return Promise.reject(new Error('IndexedDB is unavailable in this browser.'));
  }
  if (databasePromise) return databasePromise;

  databasePromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(RESPONSE_STORE)) {
        database.createObjectStore(RESPONSE_STORE, { keyPath: 'key' });
      }
      if (!database.objectStoreNames.contains(QUEUE_STORE)) {
        database.createObjectStore(QUEUE_STORE, { keyPath: 'id' });
      }
    };
    request.onsuccess = () => {
      request.result.onversionchange = () => {
        request.result.close();
        databasePromise = null;
      };
      resolve(request.result);
    };
    request.onerror = () => {
      databasePromise = null;
      reject(request.error || new Error('Unable to open the offline cache.'));
    };
    request.onblocked = () => {
      databasePromise = null;
      reject(new Error('The offline cache is blocked by another browser tab.'));
    };
  });
  return databasePromise;
}

export async function readCachedResponse(key: string): Promise<CachedApiResponse | null> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const request = database.transaction(RESPONSE_STORE, 'readonly').objectStore(RESPONSE_STORE).get(key);
    request.onsuccess = () => resolve((request.result as CachedApiResponse | undefined) || null);
    request.onerror = () => reject(request.error || new Error('Unable to read the offline cache.'));
  });
}

export async function writeCachedResponse(key: string, data: unknown): Promise<void> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(RESPONSE_STORE, 'readwrite');
    transaction.objectStore(RESPONSE_STORE).put({ key, data, cachedAt: Date.now() } satisfies CachedApiResponse);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error('Unable to update the offline cache.'));
    transaction.onabort = () => reject(transaction.error || new Error('The offline cache update was aborted.'));
  });
}

export async function clearCachedResponses(): Promise<void> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(RESPONSE_STORE, 'readwrite');
    transaction.objectStore(RESPONSE_STORE).clear();
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error('Unable to clear the offline cache.'));
    transaction.onabort = () => reject(transaction.error || new Error('The offline cache cleanup was aborted.'));
  });
}

export async function listQueuedOperations(): Promise<OfflineOperation[]> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const request = database.transaction(QUEUE_STORE, 'readonly').objectStore(QUEUE_STORE).getAll();
    request.onsuccess = () => resolve((request.result as OfflineOperation[]).sort((a, b) => a.createdAt - b.createdAt));
    request.onerror = () => reject(request.error || new Error('Unable to read queued operations.'));
  });
}

export async function addQueuedOperation(operation: OfflineOperation): Promise<void> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(QUEUE_STORE, 'readwrite');
    transaction.objectStore(QUEUE_STORE).add(operation);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error('Unable to queue the operation.'));
    transaction.onabort = () => reject(transaction.error || new Error('The operation could not be queued.'));
  });
}

export async function updateQueuedOperation(operation: OfflineOperation): Promise<void> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(QUEUE_STORE, 'readwrite');
    transaction.objectStore(QUEUE_STORE).put(operation);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error('Unable to update the queued operation.'));
    transaction.onabort = () => reject(transaction.error || new Error('The queued operation update was aborted.'));
  });
}

export async function removeQueuedOperation(id: string): Promise<void> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(QUEUE_STORE, 'readwrite');
    transaction.objectStore(QUEUE_STORE).delete(id);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error('Unable to remove the queued operation.'));
    transaction.onabort = () => reject(transaction.error || new Error('The queued operation removal was aborted.'));
  });
}

export async function clearQueuedOperations(): Promise<void> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(QUEUE_STORE, 'readwrite');
    transaction.objectStore(QUEUE_STORE).clear();
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error('Unable to clear queued operations.'));
    transaction.onabort = () => reject(transaction.error || new Error('The queued operation cleanup was aborted.'));
  });
}
