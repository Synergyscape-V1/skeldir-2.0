# ETag Caching Pattern - Usage Guide

## Overview

The `useEtagCache` hook implements HTTP ETag conditional request pattern per Frontend Architecture Guide Section 4.5: "ETag Handling - 304 Response Optimization".

## Key Benefits

- **Reduced Bandwidth**: 304 Not Modified responses skip data transfer
- **Improved Performance**: Avoid unnecessary re-renders when data unchanged
- **Server Load**: Reduce server processing for unchanged resources
- **Type-Safe**: Full TypeScript support with clear API

## Hook API

```typescript
const { 
  etag,           // Current cached ETag value (or null)
  getHeaders,     // Returns If-None-Match header object
  handleResponse, // Process response and extract ETag
  clearEtag,      // Manually clear cached ETag
  setEtag         // Manually set ETag value
} = useEtagCache();
```

## Usage Pattern

### Basic Fetch Example

```typescript
import { useEtagCache } from '@/hooks/use-etag-cache';

function MyPollingComponent() {
  const { getHeaders, handleResponse } = useEtagCache();
  const [data, setData] = useState(null);

  const fetchData = async () => {
    // Include ETag headers in request
    const response = await fetch('/api/data', {
      headers: {
        ...getHeaders(), // Adds If-None-Match if ETag exists
      },
    });

    // Check if data changed
    const dataChanged = handleResponse(response);
    
    if (dataChanged) {
      // Only update state if data actually changed (200 OK)
      const newData = await response.json();
      setData(newData);
    }
    // On 304 Not Modified, dataChanged=false, skip state update
  };

  return <div>{/* Render data */}</div>;
}
```

### With usePollingManager

```typescript
import { usePollingManager } from '@/hooks/use-polling-manager';
import { useEtagCache } from '@/hooks/use-etag-cache';

function PollingComponent() {
  const { getHeaders, handleResponse } = useEtagCache();
  const [data, setData] = useState(null);

  const handlePoll = useCallback(async () => {
    const response = await fetch('/api/polling-endpoint', {
      headers: getHeaders(),
    });

    if (handleResponse(response)) {
      const newData = await response.json();
      setData(newData);
    }
  }, [getHeaders, handleResponse]);

  usePollingManager({
    intervalMs: 30000,
    onPoll: handlePoll,
  });

  return <div>{/* Render data */}</div>;
}
```

### With API Service Layer

```typescript
// In service layer (attribution.service.ts)
export async function fetchRevenueMetrics(
  apiClient: ApiClient,
  etagHeaders?: Record<string, string>
): Promise<ApiResponse<RevenueMetric[]>> {
  return apiClient.get<RevenueMetric[]>('/api/attribution/revenue', {
    headers: etagHeaders,
  });
}

// In component
function RevenueComponent() {
  const { getHeaders, handleResponse } = useEtagCache();
  const apiClient = useApiClient();

  const fetchRevenue = async () => {
    const response = await fetchRevenueMetrics(apiClient, getHeaders());
    
    // handleResponse works with ApiResponse<T> objects too
    const dataChanged = handleResponse(response.status, response.headers?.get?.('ETag'));
    
    if (dataChanged && response.data) {
      // Update state with new data
    }
  };

  return <div>{/* Render */}</div>;
}
```

## Important Implementation Details

### 2xx-Only Caching

The hook **only caches ETags from successful 2xx responses**. This prevents:
- Pinning an ETag from an error response (4xx, 5xx)
- Breaking future requests with stale error ETags
- Cache pollution from transient failures

```typescript
// ✅ GOOD: ETag cached only on 2xx success
if (status >= 200 && status < 300) {
  const responseEtag = response.headers.get('ETag');
  if (responseEtag) setEtag(responseEtag);
}

// ❌ BAD: Would cache ETag even on 500 error
const responseEtag = response.headers.get('ETag');
if (responseEtag) setEtag(responseEtag);
```

### Case-Insensitive Header Extraction

The hook handles both `ETag` and `etag` header names:

```typescript
const responseEtag = response.headers.get('ETag') || response.headers.get('etag');
```

### Manual ETag Management

```typescript
const { clearEtag, setEtag } = useEtagCache();

// Clear on logout or cache invalidation
const handleLogout = () => {
  clearEtag();
  // ... other logout logic
};

// Manually set ETag (rare use case)
const handleManualSync = (etagFromWebSocket: string) => {
  setEtag(etagFromWebSocket);
};
```

## Backend Requirements

The backend must support ETags for this pattern to work:

1. **Send ETag header** on successful responses:
   ```
   HTTP/1.1 200 OK
   ETag: "a1b2c3d4e5"
   Content-Type: application/json
   ```

2. **Handle If-None-Match** header from client:
   ```
   GET /api/data
   If-None-Match: "a1b2c3d4e5"
   ```

3. **Return 304 Not Modified** when data unchanged:
   ```
   HTTP/1.1 304 Not Modified
   ETag: "a1b2c3d4e5"
   ```

## Testing

### Manual Testing

1. Open browser DevTools → Network tab
2. Trigger first request → Verify **no If-None-Match header**
3. Trigger second request → Verify **If-None-Match header present**
4. Verify 304 responses → Check **no component re-render**
5. Verify 200 responses → Check **component updates with new data**

### Integration Testing

```typescript
import { renderHook, act } from '@testing-library/react';
import { useEtagCache } from '@/hooks/use-etag-cache';

test('caches ETag from 200 response', () => {
  const { result } = renderHook(() => useEtagCache());
  
  const mockResponse = new Response(null, {
    status: 200,
    headers: { 'ETag': '"abc123"' },
  });
  
  act(() => {
    result.current.handleResponse(mockResponse);
  });
  
  expect(result.current.etag).toBe('"abc123"');
  expect(result.current.getHeaders()).toEqual({ 'If-None-Match': '"abc123"' });
});

test('does not cache ETag from 500 error', () => {
  const { result } = renderHook(() => useEtagCache());
  
  const mockError = new Response(null, {
    status: 500,
    headers: { 'ETag': '"error-etag"' },
  });
  
  act(() => {
    result.current.handleResponse(mockError);
  });
  
  expect(result.current.etag).toBeNull();
});
```

## Common Pitfalls

### ❌ Forgetting to check handleResponse return value

```typescript
// BAD: Always updates state, even on 304
const response = await fetch('/api/data', { headers: getHeaders() });
handleResponse(response);
const data = await response.json(); // Error on 304!
setData(data);
```

```typescript
// GOOD: Only updates on data change
const response = await fetch('/api/data', { headers: getHeaders() });
if (handleResponse(response)) {
  const data = await response.json();
  setData(data);
}
```

### ❌ Not handling 304 empty body

```typescript
// BAD: response.json() fails on 304 (no body)
const response = await fetch('/api/data', { headers: getHeaders() });
const data = await response.json(); // Throws on 304!
```

```typescript
// GOOD: Check before parsing
if (handleResponse(response)) {
  const data = await response.json();
  setData(data);
}
```

## Architecture Compliance

This implementation satisfies Frontend Architecture Guide requirements:

- ✅ **FE-4.5**: ETag handling with 304 response optimization
- ✅ **DRY Principle**: Reusable hook across all polling contexts
- ✅ **Type Safety**: Full TypeScript support
- ✅ **Error Resilience**: 2xx-only caching prevents error ETag pollution
- ✅ **Performance**: Reduces unnecessary state updates and re-renders

## Future Enhancements

When backend implements ETags:

1. **Integrate with all polling hooks**:
   - `use-dashboard-polling.ts`
   - `DataReconciliationStatus.tsx`
   - `DualRevenueCard.tsx`
   - Any custom polling implementations

2. **Add metrics tracking**:
   - 304 hit rate
   - Bandwidth saved
   - Performance improvements

3. **Consider IndexedDB persistence** for ETags across sessions (advanced)

## References

- Frontend Architecture Guide Section 4.5
- [HTTP ETag Specification (RFC 7232)](https://datatracker.ietf.org/doc/html/rfc7232)
- [MDN: ETag](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag)
