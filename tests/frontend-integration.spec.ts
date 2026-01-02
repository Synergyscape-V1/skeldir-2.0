import { test, expect } from '@playwright/test';

test.describe('SKELDIR Mock Server Integration', () => {
  const ATTRIBUTION_URL = 'http://127.0.0.1:4011/api/attribution/revenue/realtime';
  
  // Generate UUID for correlation ID
  function generateUUID(): string {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  // UUID validation regex
  const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  test('should return valid attribution revenue response with X-Correlation-ID propagation', async ({ request }) => {
    const correlationId = generateUUID();
    
    const response = await request.get(ATTRIBUTION_URL, {
      headers: {
        'Authorization': 'Bearer mock-token',
        'X-Correlation-ID': correlationId,
      },
    });

    // Assert response status is 200 or 401 (not 500, not connection refused)
    expect([200, 401]).toContain(response.status());
    expect(response.status()).not.toBe(500);

    // Assert response body is valid JSON
    const body = await response.json();
    expect(body).toBeDefined();
    expect(typeof body).toBe('object');

    // If status is 200, validate required fields
    if (response.status() === 200) {
      // Assert required fields exist with correct types
      expect(body).toHaveProperty('total_revenue');
      expect(typeof body.total_revenue).toBe('number');
      
      expect(body).toHaveProperty('verified');
      expect(typeof body.verified).toBe('boolean');
      
      expect(body).toHaveProperty('data_freshness_seconds');
      expect(typeof body.data_freshness_seconds).toBe('number');
      
      expect(body).toHaveProperty('tenant_id');
      expect(typeof body.tenant_id).toBe('string');
      expect(body.tenant_id).toMatch(UUID_REGEX);
    }

    // Assert X-Correlation-ID header is present in response
    const responseCorrelationId = response.headers()['x-correlation-id'];
    expect(responseCorrelationId).toBeDefined();
    expect(responseCorrelationId).toMatch(UUID_REGEX);

    // Assert Content-Type header is application/json
    const contentType = response.headers()['content-type'];
    expect(contentType).toContain('application/json');
  });

  test('should handle 401 Unauthorized response correctly', async ({ request }) => {
    const correlationId = generateUUID();
    
    // Request without Authorization header should return 401
    const response = await request.get(ATTRIBUTION_URL, {
      headers: {
        'X-Correlation-ID': correlationId,
      },
    });

    expect([400, 401]).toContain(response.status());

    // Assert response is RFC7807 Problem schema
    const body = await response.json();
    expect(body).toHaveProperty('type');
    expect(body).toHaveProperty('title');
    expect(body).toHaveProperty('status');
    expect([400, 401]).toContain(body.status);
    expect(body).toHaveProperty('detail');
    expect(body).toHaveProperty('correlation_id');
    expect(body.correlation_id).toMatch(UUID_REGEX);
  });
});







