# MAIChat - Integration Architecture

Complete system architecture documentation for the Medical AI Chat application, covering both `pinecone-backend` and `rag-backend` integration.

## Table of Contents
- [System Overview](#system-overview)
- [Architecture Diagram](#architecture-diagram)
- [Data Flow](#data-flow)
- [Component Integration](#component-integration)
- [API Specifications](#api-specifications)
- [Security Architecture](#security-architecture)
- [Deployment Architecture](#deployment-architecture)
- [Monitoring & Observability](#monitoring--observability)

---

## System Overview

MAIChat is a modular RAG (Retrieval-Augmented Generation) system for medical conversations with two main backend services:

1. **Pinecone Backend** (Data Ingestion Service)
   - Consumes FHIR medical data from Redis queue
   - Generates embeddings using Clinical BERT
   - Stores vectors in Pinecone for semantic search

2. **RAG Backend** (Query & Response Service)
   - Exposes REST API for medical queries
   - Retrieves relevant medical context
   - Generates AI-powered responses
   - Manages conversation state
   - Firebase authentication

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          External Systems                                │
│                    (EMR/EHR, FHIR Servers, etc.)                        │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ FHIR Resources
                             ▼
                    ┌─────────────────┐
                    │   Redis Queue   │
                    │  (fhir_data)    │
                    └────────┬────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      PINECONE BACKEND                                  │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │              Main Consumer Loop (main.py)                        │ │
│  └──────────────────────┬───────────────────────────────────────────┘ │
│                         ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │           FHIR Processor (fhir_processor.py)                     │ │
│  │  • Validates FHIR messages                                       │ │
│  │  • Extracts patient data                                         │ │
│  │  • Coordinates embedding + storage                               │ │
│  └─────┬──────────────────┬──────────────────┬─────────────────────┘ │
│        │                  │                  │                        │
│        ▼                  ▼                  ▼                        │
│  ┌──────────┐      ┌─────────────┐    ┌──────────────┐             │
│  │  Redis   │      │  Embedding  │    │  Pinecone    │             │
│  │ Service  │      │   Service   │    │   Service    │             │
│  │          │      │ (Clinical   │    │  (Vector     │             │
│  │          │      │   BERT)     │    │   Storage)   │             │
│  └──────────┘      └─────────────┘    └──────────────┘             │
└───────────────────────────┬────────────────────────────────────────────┘
                            │
                            ▼
                  ┌──────────────────────┐
                  │   Pinecone Vector    │
                  │      Database        │
                  │                      │
                  │  Namespaces:         │
                  │  • patient-123       │
                  │  • patient-456       │
                  │  • patient-789       │
                  └──────────┬───────────┘
                             │
                             │ Vector Search
                             │
┌────────────────────────────┼────────────────────────────────────────────┐
│                      RAG BACKEND                                        │
│                             │                                           │
│  ┌──────────────────────────▼────────────────────────────┐             │
│  │              FastAPI Application (main.py)            │             │
│  │  • Firebase Authentication                            │             │
│  │  • REST API Endpoints                                 │             │
│  │  • CORS Middleware                                    │             │
│  └───┬──────────────────┬──────────────────┬────────────┘             │
│      │                  │                  │                           │
│      ▼                  ▼                  ▼                           │
│  ┌────────┐      ┌─────────────┐    ┌──────────────┐                 │
│  │ Chat   │      │  Sessions   │    │  Patients    │                 │
│  │ Router │      │   Router    │    │   Router     │                 │
│  └───┬────┘      └──────┬──────┘    └──────┬───────┘                 │
│      │                  │                   │                          │
│      └──────────────────┴───────────────────┘                          │
│                         │                                              │
│                         ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │              RAG Orchestrator (rag_orchestrator.py)              │ │
│  │  • Coordinates RAG pipeline                                      │ │
│  │  • Manages workflow between services                            │ │
│  └─────┬──────────────┬──────────────┬──────────────┬──────────────┘ │
│        │              │              │              │                 │
│        ▼              ▼              ▼              ▼                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │Embedding │  │Retrieval │  │Generation│  │ Context  │            │
│  │ Service  │  │ Service  │  │ Service  │  │ Service  │            │
│  └──────────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│                     │              │              │                   │
└─────────────────────┼──────────────┼──────────────┼───────────────────┘
                      │              │              │
                      ▼              ▼              ▼
            ┌──────────────┐  ┌──────────┐  ┌──────────────┐
            │  Pinecone    │  │  OpenAI  │  │  MongoDB     │
            │   (Read)     │  │   API    │  │  (Sessions,  │
            │              │  │  (GPT-4) │  │   Messages)  │
            └──────────────┘  └──────────┘  └──────────────┘
                      
                                 ▲
                                 │
                         ┌───────┴────────┐
                         │   Firebase     │
                         │ Authentication │
                         └────────────────┘
                                 ▲
                                 │
                         ┌───────┴────────┐
                         │  Client Apps   │
                         │ (Web/Mobile)   │
                         └────────────────┘
```

---

## Data Flow

### 1. Data Ingestion Flow (Pinecone Backend)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FHIR Data Ingestion Pipeline                      │
└─────────────────────────────────────────────────────────────────────┘

Step 1: FHIR Resource Created
   │
   ├─> External system pushes FHIR data to Redis queue
   │   Format: {patientId, practitionerId, resourceType, resourceId, text}
   │
   ▼
Step 2: Message Queued in Redis
   │
   ├─> Queue: 'fhir_data'
   ├─> Blocking RPOP with 30s timeout
   │
   ▼
Step 3: Consumer Receives & Validates
   │
   ├─> JSON deserialization
   ├─> Validate required fields (patientId, text)
   ├─> Generate resourceId if missing
   │
   ▼
Step 4: Text Embedding
   │
   ├─> Tokenize with Clinical BERT tokenizer
   ├─> Generate 768-dimensional embedding
   ├─> Extract [CLS] token representation
   │
   ▼
Step 5: Vector Storage
   │
   ├─> Namespace: "patient-{patientId}"
   ├─> Vector ID: {resourceId}
   ├─> Metadata: {patientID, text, resourceType, practitionerId, processed_at}
   ├─> Upsert to Pinecone
   │
   ▼
Step 6: Loop & Monitor
   │
   └─> Log success, track errors, continue loop
```

### 2. Query & Response Flow (RAG Backend)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RAG Query Processing Pipeline                     │
└─────────────────────────────────────────────────────────────────────┘

Step 1: Client Request
   │
   ├─> POST /chat with Firebase ID token
   ├─> Headers: Authorization: Bearer <token>
   ├─> Body: {query, patient_id/practitioner_id, session_id}
   │
   ▼
Step 2: Authentication
   │
   ├─> Verify Firebase ID token
   ├─> Extract user info (uid, email)
   ├─> Return 401 if invalid
   │
   ▼
Step 3: Session Management
   │
   ├─> Get or create session in MongoDB
   ├─> Store user message in messages collection
   │
   ▼
Step 4: Context Retrieval (Orchestrator)
   │
   ├─> Get short-term context (recent messages from MongoDB)
   ├─> Get long-term context (summary from MongoDB)
   │
   ▼
Step 5: Semantic Search
   │
   ├─> Generate query embedding (Clinical BERT)
   ├─> Query Pinecone by namespace(s):
   │   • Patient mode: single namespace (patient-123)
   │   • Practitioner mode: multiple namespaces (all patients)
   ├─> Filter by similarity threshold (default: 0.7)
   ├─> Return top-k results (default: 5)
   │
   ▼
Step 6: Context Assembly
   │
   ├─> Combine:
   │   • Retrieved medical records (Pinecone)
   │   • Short-term conversation history (MongoDB)
   │   • Long-term conversation summary (MongoDB)
   │
   ▼
Step 7: Answer Generation
   │
   ├─> Build prompt with all context
   ├─> Call OpenAI GPT-4 API
   ├─> Stream or return complete response
   │
   ▼
Step 8: Response Storage
   │
   ├─> Store assistant message in MongoDB
   ├─> Update session metadata
   ├─> Check if summarization needed
   │
   ▼
Step 9: Client Response
   │
   └─> Return: {answer, context_used, sources, metadata}
```

---

## Component Integration

### Shared Resources

#### 1. Pinecone Vector Database

**Purpose**: Shared vector storage for medical records

**Structure**:
```
Index: maichat-index
Dimension: 768 (Clinical BERT)
Metric: cosine similarity

Namespaces:
├─ patient-101 (Patient-specific data isolation)
├─ patient-102
└─ patient-103

Vector Format:
{
  id: "obs-123",
  values: [0.1, 0.2, ...],  // 768-dim embedding
  metadata: {
    patientID: "patient-123",
    text: "Patient presented with...",
    resourceType: "Observation",
    practitionerId: "prac-456",
    processed_at: 1234567890
  }
}
```

**Integration**:
- **Pinecone Backend**: Write-only (upsert vectors)
- **RAG Backend**: Read-only (query vectors)

#### 2. Embedding Model Consistency

**Model**: `emilyalsentzer/Bio_ClinicalBERT`

**Specification**:
- Input: Text (max 512 tokens)
- Output: 768-dimensional vector
- Method: [CLS] token embedding

**Critical**: Both backends MUST use the same:
- Model name/version
- Tokenization strategy
- Embedding extraction method

**Validation**:
```python
# Both services should produce identical embeddings for same text
text = "Patient has hypertension"
pinecone_embedding = pinecone_backend.generate_embedding(text)
rag_embedding = rag_backend.generate_embedding(text)
assert pinecone_embedding == rag_embedding
```

### Service Dependencies

#### Pinecone Backend Dependencies

```
Redis (Message Queue)
  └─> FHIR Processor
      ├─> Embedding Service (Clinical BERT)
      └─> Pinecone Service (Vector Storage)
```

**External Services**:
- Redis: Message queue for FHIR data
- Pinecone: Vector database storage
- HuggingFace: Model download

#### RAG Backend Dependencies

```
Firebase (Authentication)
  └─> FastAPI Routes
      └─> RAG Orchestrator
          ├─> MongoDB Service (Sessions, Messages)
          ├─> Embedding Service (Clinical BERT)
          ├─> Retrieval Service (Pinecone queries)
          ├─> Generation Service (OpenAI GPT-4)
          └─> Context Service (History management)
```

**External Services**:
- Firebase: User authentication
- MongoDB: Session and message storage
- Pinecone: Vector database queries
- OpenAI: LLM for generation
- HuggingFace: Model download

---

## API Specifications

### Pinecone Backend (Internal - No HTTP API)

**Message Queue Interface**:

```json
// Redis Queue: 'fhir_data'
// Message Format:
{
  "patientId": "patient-123",
  "practitionerId": "prac-456",
  "resourceType": "Observation",
  "resourceId": "obs-789",
  "text": "Patient presented with chest pain. ECG shows normal sinus rhythm. Vital signs stable."
}
```

### RAG Backend (REST API)

#### Authentication

All endpoints (except `/` and `/health`) require Firebase authentication:

```http
Authorization: Bearer <firebase-id-token>
```

#### Endpoints

##### 1. Chat

**Request**:
```http
POST /chat
Content-Type: application/json
Authorization: Bearer <token>

{
  "query": "What medications am I taking?",
  "patient_id": "patient-123",
  "session_id": "session-456"
}
```

**Response**:
```json
{
  "answer": "Based on your medical records, you are currently taking...",
  "context_used": [
    "Patient is prescribed Metformin 500mg BID...",
    "Recent lab results show HbA1c of 7.2%..."
  ],
  "sources": [
    {
      "id": "rec-123",
      "score": 0.89,
      "patient_id": "patient-123"
    }
  ],
  "metadata": {
    "patient_id": "patient-123",
    "retrieved_documents": 2,
    "model_used": "gpt-4o"
  }
}
```

##### 2. Sessions

**Create Session**:
```http
POST /chat/sessions/
Authorization: Bearer <token>

{
  "patientId": "patient-123",
  "sessionType": "ai"
}
```

**Get Session History**:
```http
GET /chat/sessions/{sessionId}/history?limit=50
Authorization: Bearer <token>
```

##### 3. Patients

**Get Patient Sessions**:
```http
GET /chat/patients/{patientId}/sessions?limit=50
Authorization: Bearer <token>
```

**Get/Update Preferences**:
```http
GET /chat/patients/{patientId}/preferences
PUT /chat/patients/{patientId}/preferences
Authorization: Bearer <token>
```

---

## Security Architecture

### Authentication Flow

```
┌──────────┐         ┌─────────────┐         ┌──────────────┐
│  Client  │────────>│  Firebase   │────────>│  RAG Backend │
│   App    │  Login  │    Auth     │  Verify │     API      │
└──────────┘         └─────────────┘  Token  └──────────────┘
     │                      │                        │
     │ 1. Sign in          │                        │
     ├──────────────────>  │                        │
     │                      │                        │
     │ 2. ID Token         │                        │
     │ <────────────────── │                        │
     │                      │                        │
     │ 3. API Request      │                        │
     │    (Bearer Token)   │                        │
     ├─────────────────────┼───────────────────────>│
     │                      │                        │
     │                      │ 4. Verify Token        │
     │                      │<───────────────────────│
     │                      │                        │
     │                      │ 5. Token Valid         │
     │                      │────────────────────────>│
     │                      │                        │
     │                      │                   6. Process
     │                      │                    Request
     │                      │                        │
     │ 7. Response         │                        │
     │<────────────────────┼────────────────────────│
```

### Data Isolation

**Patient Namespace Strategy**:
- Each patient's data stored in separate Pinecone namespace
- Format: `patient-{patientId}`
- Prevents cross-patient data leakage
- Enables efficient patient-specific queries

**Practitioner Access**:
- MongoDB stores practitioner-patient relationships
- Retrieval service queries multiple namespaces for practitioner
- RBAC enforced at API layer

### Security Checklist

- [x] Firebase authentication on all endpoints
- [x] Patient data isolated by namespace
- [x] HTTPS/TLS in production (configure)
- [x] API key rotation (manual)
- [ ] Rate limiting (TODO)
- [ ] Request validation & sanitization
- [ ] Audit logging (TODO)
- [ ] HIPAA compliance review (TODO)

---

## Deployment Architecture

### Docker Compose Setup

```yaml
services:
  rag-backend:
    build: ./rag-backend
    ports:
      - "8000:8000"
    environment:
      - PINECONE_API_KEY
      - OPENAI_API_KEY
      - MONGODB_URL
      - FIREBASE_CREDENTIALS_PATH
    depends_on:
      - mongodb
      - redis

  pinecone-backend:
    build: ./pinecone-backend
    environment:
      - PINECONE_API_KEY
      - REDIS_HOST=redis
    depends_on:
      - redis

  mongodb:
    image: mongo:7.0
    volumes:
      - mongodb_data:/data/db

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

### Environment Configuration

**Shared**:
```env
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=maichat-index
EMBEDDING_MODEL_NAME=emilyalsentzer/Bio_ClinicalBERT
LOG_LEVEL=INFO
```

**RAG Backend Only**:
```env
OPENAI_API_KEY=your-openai-api-key
MONGODB_URL=mongodb://mongodb:27017
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json
```

**Pinecone Backend Only**:
```env
REDIS_HOST=redis
REDIS_PORT=6379
```

### Scaling Considerations

**Horizontal Scaling**:

1. **Pinecone Backend**:
   - Multiple consumer instances can run in parallel
   - Redis queue distributes messages automatically
   - Each instance processes independently
   - No coordination required

2. **RAG Backend**:
   - Stateless API design allows multiple replicas
   - Load balancer distributes requests
   - Session state stored in MongoDB (shared)
   - No sticky sessions required

**Resource Requirements**:

| Service | CPU | RAM | Storage | Network |
|---------|-----|-----|---------|---------|
| Pinecone Backend | 2 cores | 4 GB | 10 GB | Low |
| RAG Backend | 2 cores | 4 GB | 10 GB | Medium |
| MongoDB | 2 cores | 2 GB | 50 GB | Low |
| Redis | 1 core | 512 MB | 5 GB | Low |

---

## Monitoring & Observability

### Health Checks

**Pinecone Backend**:
```python
processor.health_check()
# Returns:
{
  "redis": True,
  "pinecone": True,
  "embedding": True
}
```

**RAG Backend**:
```http
GET /health

Response:
{
  "status": "healthy",
  "services": {
    "mongodb": True,
    "embedding": True,
    "retrieval": True,
    "generation": True,
    "context": True,
    "overall": True
  }
}
```

### Key Metrics

**Pinecone Backend**:
- Messages processed per minute
- Embedding generation latency
- Pinecone upsert latency
- Queue depth (Redis)
- Error rate
- Consecutive errors count

**RAG Backend**:
- Request rate (requests/sec)
- Response latency (p50, p95, p99)
- Authentication failures
- Pinecone query latency
- OpenAI API latency
- MongoDB operation latency
- Cache hit rate (future)

### Logging Strategy

**Log Levels**:
- `DEBUG`: Detailed internal state, embeddings, tokens
- `INFO`: Request/response, processing status
- `WARNING`: Validation errors, retry attempts
- `ERROR`: Processing failures, connection errors
- `CRITICAL`: Service unavailable, fatal errors

**Log Format**:
```
2024-01-15 10:30:45 [INFO] [rag_orchestrator] Processing query for patient patient-123: What medications...
2024-01-15 10:30:45 [INFO] [retrieval_service] Retrieved 5 relevant contexts for patient patient-123
2024-01-15 10:30:46 [INFO] [generation_service] Generated response using model gpt-4o (1234 tokens)
```

### Alerts

**Critical**:
- Service down (health check fails)
- Firebase authentication unavailable
- Pinecone connection lost
- OpenAI API errors
- MongoDB connection lost

**Warning**:
- High error rate (>5%)
- Queue backlog growing
- High latency (p95 > 5s)
- Low embedding similarity scores

---

## Integration Patterns

### 1. Decoupled Architecture

**Benefits**:
- Services can scale independently
- Failures are isolated
- Technology stack flexibility
- Easy to test and develop

**Pattern**: Message queue (Redis) decouples ingestion from retrieval

### 2. Shared State Management

**MongoDB** (RAG Backend):
- Session management
- Message history
- User preferences
- Practitioner-patient relationships

**Pinecone** (Both Backends):
- Pinecone Backend: Write
- RAG Backend: Read
- No write conflicts

### 3. Consistency Model

**Eventual Consistency**:
- FHIR data → Pinecone (async, queue-based)
- New data available within seconds
- Acceptable for medical chat use case

**Strong Consistency**:
- Session state (MongoDB)
- User authentication (Firebase)
- Real-time message history

---

## Development Workflow

### Local Development

```bash
# Start dependencies
docker-compose up mongodb redis

# Terminal 1: RAG Backend
cd rag-backend
pip install -r requirements.txt
python main.py

# Terminal 2: Pinecone Backend
cd pinecone-backend
pip install -r requirements.txt
python main.py

# Terminal 3: Seed data
python scripts/seed_db.py
```

### Testing Integration

```bash
# 1. Send FHIR data to queue
redis-cli LPUSH fhir_data '{"patientId":"patient-123","text":"Test data","resourceId":"test-1"}'

# 2. Verify ingestion (check logs)
# pinecone-backend should process message

# 3. Query via API
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"test","patient_id":"patient-123"}'
```

---

## Troubleshooting

### Common Integration Issues

**1. Embedding Mismatch**
```
Symptom: Poor retrieval quality, low similarity scores
Cause: Different embedding models in backends
Fix: Ensure both use same EMBEDDING_MODEL_NAME
```

**2. Namespace Not Found**
```
Symptom: No results from Pinecone
Cause: Data not ingested or wrong namespace format
Fix: Check pinecone-backend logs, verify namespace format
```

**3. Authentication Fails**
```
Symptom: 401 Unauthorized
Cause: Firebase not configured or invalid token
Fix: Set FIREBASE_CREDENTIALS_PATH, get fresh token
```

**4. High Latency**
```
Symptom: Slow responses
Cause: Cold start, large context, API throttling
Fix: Warm up models, reduce context size, check quotas
```

---

## Future Enhancements

### Planned Improvements

- [ ] Batch processing in pinecone-backend
- [ ] Caching layer (Redis) for RAG backend
- [ ] Streaming responses (SSE)
- [ ] Multi-modal support (images, PDFs)
- [ ] Advanced RAG techniques (HyDE, RAG-Fusion)
- [ ] Prometheus metrics export
- [ ] Distributed tracing (OpenTelemetry)
- [ ] A/B testing framework

---

## References

### Documentation
- [Pinecone Backend README](./pinecone-backend/README.md)
- [RAG Backend README](./rag-backend/README.md)
- [API Documentation](./docs/api.md) (TODO)

### External Resources
- [Clinical BERT Paper](https://arxiv.org/abs/1904.03323)
- [Pinecone Documentation](https://docs.pinecone.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Firebase Auth Docs](https://firebase.google.com/docs/auth)

---

## Support & Contribution

### Getting Help
- Check service health endpoints
- Review logs for detailed errors
- Consult individual README files
- Contact development team

### Contributing
- Follow modular architecture
- Maintain backward compatibility
- Add tests for new features
- Update documentation
- Use conventional commits

---

## License

[Your License Here]

## Maintainers

[Your Team/Contact Info]

