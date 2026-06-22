# API Versioning Guide

## Version Prefix

All API endpoints are now prefixed with `/v1/` for version 1 of the API.

## Endpoint Mapping

### Before (No Version)
```
GET  /
GET  /health
POST /chat
POST /chat/suggestions
POST /chat/stream
POST /chat/sessions/
GET  /chat/sessions/{sessionId}/history
PUT  /chat/sessions/{sessionId}
POST /chat/sessions/{sessionId}/end
GET  /chat/patients/{patientId}/sessions
GET  /chat/patients/{patientId}/preferences
PUT  /chat/patients/{patientId}/preferences
GET  /chat-history/{patient_id}
DELETE /chat-history/{patient_id}
```

### After (Version 1)
```
GET  /                                          (unchanged - root/static)
GET  /v1/health                                 ✓ versioned
POST /v1/chat                                   ✓ versioned
POST /v1/chat/suggestions                       ✓ versioned
POST /v1/chat/stream                            ✓ versioned
POST /v1/chat/sessions/                         ✓ versioned
GET  /v1/chat/sessions/{sessionId}/history      ✓ versioned
PUT  /v1/chat/sessions/{sessionId}              ✓ versioned
POST /v1/chat/sessions/{sessionId}/end          ✓ versioned
GET  /v1/chat/patients/{patientId}/sessions     ✓ versioned
GET  /v1/chat/patients/{patientId}/preferences  ✓ versioned
PUT  /v1/chat/patients/{patientId}/preferences  ✓ versioned
GET  /v1/chat-history/{patient_id}              ✓ versioned
DELETE /v1/chat-history/{patient_id}            ✓ versioned
```

## Example Usage

### Health Check
```bash
# Old
curl http://localhost:8000/health

# New
curl http://localhost:8000/v1/health
```

### Chat Endpoint
```bash
# Old
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "patient_id": "patient-123"}'

# New
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "patient_id": "patient-123"}'
```

### Session Management
```bash
# Old
POST http://localhost:8000/chat/sessions/

# New
POST http://localhost:8000/v1/chat/sessions/
```

## Benefits of API Versioning

1. **Backward Compatibility**: Can maintain v1 while developing v2
2. **Clear Migration Path**: Clients know which version they're using
3. **Easier Deprecation**: Can sunset old versions gracefully
4. **Better Documentation**: Clear separation between API versions

## Future Versions

When creating v2:
1. Copy router files or create new ones
2. Include with prefix `/v2/`
3. Keep v1 running for backward compatibility
4. Document migration guide

Example:
```python
# v2 routers
app.include_router(chat_router_v2, prefix="/v2/chat", tags=["chat-v2"])

# v1 still available
app.include_router(chat_router, prefix="/v1/chat", tags=["chat"])
```

## Client Updates Required

Update all frontend/client code to use the new `/v1/` prefix:

```javascript
// Before
const response = await fetch('http://localhost:8000/chat', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(data)
});

// After
const response = await fetch('http://localhost:8000/v1/chat', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(data)
});
```

## Testing

### Verify All Endpoints
```bash
# Health check (public)
curl http://localhost:8000/v1/health

# Get API docs
open http://localhost:8000/docs

# Check swagger UI for v1 endpoints
```

### Update Integration Tests
Make sure to update all test files to use `/v1/` prefix:
- Update curl commands
- Update test scripts
- Update client libraries
- Update documentation

## Notes

- Root endpoint `/` remains unchanged (serves static files)
- All API endpoints now require `/v1/` prefix
- Documentation auto-updates in Swagger UI
- No breaking changes to response formats, only URL paths

