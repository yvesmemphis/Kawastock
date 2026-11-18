import 'fake-indexeddb/auto';
import { beforeEach, describe, expect, it, vi } from 'vitest';

function jsonResponse(status: number, data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function setOnline(online: boolean) {
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: online });
}

describe('offline operation queue', () => {
  let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;
  let offline: typeof import('../offline');
  let api: typeof import('./http');

  function requestAt(index: number) {
    const request = fetchMock.mock.calls[index];
    if (!request || !request[1]) throw new Error(`Expected request ${index + 1} to be sent.`);
    return { url: request[0], options: request[1] };
  }

  beforeEach(async () => {
    vi.resetModules();
    sessionStorage.clear();
    sessionStorage.setItem('kawa.userId', 'test-user-a');
    sessionStorage.setItem('kawa.shop', 'test-shop-a');
    setOnline(false);
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
    offline = await import('../offline');
    api = await import('./http');
    await offline.clearCachedResponses();
    await offline.clearQueuedOperations();
  });

  it('queues sales, stock adjustments, purchases and dependent receipts in order', async () => {
    const sale = await api.queueOfflineAction('sale', { items: [{ product_id: 'p-1', quantity: '2' }] });
    const adjustment = await api.queueOfflineAction('stock_adjustment', {
      product_id: 'p-1', quantity_delta: '3', movement_type: 'adjustment', reason: 'Stock count',
    });
    const purchase = await api.queueOfflineAction('purchase_create', {
      supplier_id: 's-1', items: [{ product_id: 'p-1', quantity_ordered: '4', unit_cost: '2.50' }],
    });
    const receipt = await api.queueOfflineAction(
      'purchase_receive',
      { purchaseId: `local:${purchase.id}` },
      purchase.id,
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect((await offline.listQueuedOperations()).map(operation => operation.id)).toEqual([
      sale.id, adjustment.id, purchase.id, receipt.id,
    ]);
    expect(sale.payload.idempotency_key).toBe(sale.idempotencyKey);
    expect(adjustment.payload.idempotency_key).toBe(adjustment.idempotencyKey);
    expect(purchase.payload.idempotency_key).toBe(purchase.idempotencyKey);

    fetchMock
      .mockResolvedValueOnce(jsonResponse(201, { id: 'sale-1' }))
      .mockResolvedValueOnce(jsonResponse(201, { id: 'movement-1' }))
      .mockResolvedValueOnce(jsonResponse(201, { id: 'server-purchase-42' }))
      .mockResolvedValueOnce(jsonResponse(200, { id: 'server-purchase-42' }));
    setOnline(true);
    offline.markOnline();

    await api.synchronizeOfflineQueue();

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/v1/sales/',
      '/api/v1/stock/adjustments/',
      '/api/v1/purchases/',
      '/api/v1/purchases/server-purchase-42/receive/',
    ]);
  });

  it('sends a dependent receipt after creation using the server-assigned purchase ID', async () => {
    const purchase = await api.queueOfflineAction('purchase_create', {
      supplier_id: 's-1', items: [{ product_id: 'p-1', quantity_ordered: '4', unit_cost: '2.50' }],
    });
    const receipt = await api.queueOfflineAction(
      'purchase_receive',
      { purchaseId: `local:${purchase.id}` },
      purchase.id,
    );
    expect((await offline.listQueuedOperations()).map(operation => operation.id)).toEqual([purchase.id, receipt.id]);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(201, { id: 'server-purchase-42' }))
      .mockResolvedValueOnce(jsonResponse(200, { id: 'server-purchase-42' }));
    setOnline(true);
    offline.markOnline();

    await api.synchronizeOfflineQueue();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const createRequest = requestAt(0);
    const receiveRequest = requestAt(1);
    expect(createRequest.url).toBe('/api/v1/purchases/');
    expect(receiveRequest.url).toBe('/api/v1/purchases/server-purchase-42/receive/');
    expect(new Headers(createRequest.options.headers).get('X-Shop-ID')).toBe('test-shop-a');
    expect(JSON.parse(String(receiveRequest.options.body))).toEqual({});
    expect((await offline.listQueuedOperations()).some(operation => operation.state === 'pending')).toBe(false);
  });

  it('keeps 4xx conflicts visible and leaves 5xx failures pending', async () => {
    await api.queueOfflineAction('stock_adjustment', {
      product_id: 'p-1', quantity_delta: '1', movement_type: 'adjustment', reason: 'First',
    });
    await api.queueOfflineAction('stock_adjustment', {
      product_id: 'p-1', quantity_delta: '1', movement_type: 'adjustment', reason: 'Second',
    });
    fetchMock
      .mockResolvedValueOnce(jsonResponse(409, { detail: 'Stock conflict' }))
      .mockResolvedValueOnce(jsonResponse(503, { detail: 'Service unavailable' }));
    setOnline(true);
    offline.markOnline();

    await api.synchronizeOfflineQueue();

    const operations = await offline.listQueuedOperations();
    expect(operations.map(operation => operation.state)).toEqual(['conflict', 'pending']);
    expect(operations[0].error).toContain('Stock conflict');
    expect(operations[1].error).toContain('Service unavailable');
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('retries a transient failure with the same idempotency key', async () => {
    await api.queueOfflineAction('sale', {
      items: [{ product_id: 'p-1', quantity: '1' }],
    });
    fetchMock
      .mockResolvedValueOnce(jsonResponse(503, { detail: 'Service unavailable' }))
      .mockResolvedValueOnce(jsonResponse(201, { id: 'sale-1' }));
    setOnline(true);
    offline.markOnline();

    await api.synchronizeOfflineQueue();
    const pending = (await offline.listQueuedOperations())[0];
    const firstBody = JSON.parse(String(requestAt(0).options.body));
    expect(pending.state).toBe('pending');
    expect(firstBody.idempotency_key).toBe(pending.idempotencyKey);

    await api.synchronizeOfflineQueue();

    const secondBody = JSON.parse(String(requestAt(1).options.body));
    expect(secondBody.idempotency_key).toBe(firstBody.idempotency_key);
    expect(await offline.listQueuedOperations()).toHaveLength(0);
  });

  it('synchronizes only operations for the active user and shop', async () => {
    await api.queueOfflineAction('sale', { items: [{ product_id: 'p-1', quantity: '1' }] });
    api.setShop('test-shop-b');
    sessionStorage.setItem('kawa.userId', 'test-user-b');
    await api.queueOfflineAction('sale', { items: [{ product_id: 'p-2', quantity: '1' }] });
    fetchMock.mockImplementation(async () => jsonResponse(201, { id: 'sale' }));
    setOnline(true);
    offline.markOnline();

    await api.synchronizeOfflineQueue();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(new Headers(requestAt(0).options.headers).get('X-Shop-ID')).toBe('test-shop-b');
    expect((await offline.listQueuedOperations()).map(operation => operation.state)).toEqual(['pending']);

    api.setShop('test-shop-a');
    sessionStorage.setItem('kawa.userId', 'test-user-a');
    await api.synchronizeOfflineQueue();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(new Headers(requestAt(1).options.headers).get('X-Shop-ID')).toBe('test-shop-a');
    expect(await offline.listQueuedOperations()).toHaveLength(0);
  });
});
