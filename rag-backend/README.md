# RAG Medical Assistant Backend

A production-ready **Retrieval-Augmented Generation (RAG)** backend for medical AI chat applications, built with FastAPI and designed for healthcare environments.

## 🎯 Overview

This system provides intelligent, context-aware medical assistance through a modular RAG pipeline that combines:
- **Vector-based document retrieval** from patient medical records
- **Large Language Models** for natural language understanding
- **Conversation memory management** for contextual responses
- **Multi-role support** for patients and healthcare practitioners
- **Firebase authentication** for secure access
- **FHIR-compatible** data models

## 🏗️ Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Chat Router  │  │Session Router│  │Patient Router│          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┴──────────────────┘                  │
│                            │                                     │
│                    ┌───────▼────────┐                           │
│                    │ RAG Orchestrator│                           │
│                    └───────┬────────┘                           │
│         ┌──────────────────┼──────────────────┐                 │
│         │                  │                  │                  │
│  ┌──────▼─────┐    ┌──────▼─────┐    ┌──────▼─────┐           │
│  │  Context   │    │ Retrieval  │    │ Generation │           │
│  │  Service   │    │  Service   │    │  Service   │           │
│  └──────┬─────┘    └──────┬─────┘    └──────┬─────┘           │
│         │                  │                  │                  │
│  ┌──────▼─────┐    ┌──────▼─────┐    ┌──────▼─────┐           │
│  │  MongoDB   │    │ Embedding  │    │  OpenAI    │           │
│  │  Service   │    │  Service   │    │   GPT-4    │           │
│  └────────────┘    └──────┬─────┘    └────────────┘           │
│                            │                                     │
│                    ┌───────▼────────┐                           │
│                    │    Pinecone    │                           │
│                    │  Vector Store  │                           │
│                    └────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

### Service Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Service Layer                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  MongoDBService                 EmbeddingService                │
│  ├─ Session Management          ├─ Clinical BERT                │
│  ├─ Message Persistence         ├─ 768-dim Vectors              │
│  ├─ Chat History                ├─ Batch Processing             │
│  └─ Preferences Storage         └─ GPU Acceleration             │
│                                                                  │
│  RetrievalService               GenerationService               │
│  ├─ Pinecone Integration        ├─ OpenAI GPT-4                 │
│  ├─ Patient Namespaces          ├─ Context-aware Prompts        │
│  ├─ Similarity Search           ├─ Conversation Summarization   │
│  └─ Cross-patient Queries       └─ Temperature Control          │
│                                                                  │
│  ContextService                                                  │
│  ├─ Short-term Memory (10 msgs)                                 │
│  ├─ Long-term Summaries                                         │
│  ├─ Automatic Summarization                                     │
│  └─ Context Statistics                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### RAG Pipeline Flow

```
User Query
    ↓
┌───────────────────────────────────────┐
│ 1. Authentication (Firebase)          │
└───────────┬───────────────────────────┘
            ↓
┌───────────────────────────────────────┐
│ 2. Add Query to Context               │
│    - Store user message               │
│    - Update session                   │
└───────────┬───────────────────────────┘
            ↓
┌───────────────────────────────────────┐
│ 3. Retrieve Conversation Context      │
│    - Short-term: Last 10 messages     │
│    - Long-term: Conversation summary  │
└───────────┬───────────────────────────┘
            ↓
┌───────────────────────────────────────┐
│ 4. Vector Similarity Search           │
│    - Embed query (Clinical BERT)      │
│    - Search Pinecone namespace        │
│    - Filter by similarity threshold   │
└───────────┬───────────────────────────┘
            ↓
┌───────────────────────────────────────┐
│ 5. Generate Answer (GPT-4)            │
│    - Retrieved documents              │
│    - Conversation context             │
│    - Medical knowledge                │
└───────────┬───────────────────────────┘
            ↓
┌───────────────────────────────────────┐
│ 6. Store Response & Return            │
│    - Persist assistant message        │
│    - Include sources & metadata       │
└───────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- MongoDB 4.4+
- GPU (optional, for faster embeddings)
- Pinecone account
- OpenAI API key
- Firebase project (for authentication)

### Installation

1. **Clone the repository**
```bash
cd /path/to/maichat/rag-backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
```

Edit `.env` with your configuration:
```env
# Pinecone Configuration
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=maichat-index

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key
LLM_MODEL_NAME=gpt-4o
OPENAI_BASE_URL=  # Optional, for compatible APIs

# Embedding Model
EMBEDDING_MODEL_NAME=emilyalsentzer/Bio_ClinicalBERT

# MongoDB Configuration
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=rag_medical_db
MONGODB_USERNAME=  # Optional
MONGODB_PASSWORD=  # Optional

# Collections
SESSIONS_COLLECTION=sessions
MESSAGES_COLLECTION=messages
SUMMARIES_COLLECTION=chat_summaries
PRACTITIONER_COLLECTION=practitioners

# Context Management
MAX_SHORT_TERM_MESSAGES=10
MESSAGES_TO_SUMMARIZE=5
MAX_CONTEXT_LENGTH=4000

# Retrieval Settings
TOP_K_RETRIEVAL=5
SIMILARITY_THRESHOLD=0.7

# Firebase Configuration
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json
FIREBASE_PROJECT_ID=your-project-id

# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Model Settings
GENERATION_TEMPERATURE=0.2
SUMMARIZATION_TEMPERATURE=0.3
TOKENIZERS_PARALLELISM=false
```

5. **Run the application**
```bash
# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

6. **Access the API**
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Interactive UI: http://localhost:8000/

## 📡 API Endpoints

### Authentication
All endpoints (except `/`, `/health`) require Firebase authentication via Bearer token:
```
Authorization: Bearer <firebase-id-token>
```

### Core Endpoints

#### Chat
```http
POST /chat
Content-Type: application/json

{
  "query": "What medications is the patient currently taking?",
  "patient_id": "patient-123",
  "session_id": "session-456"
}
```

**Response:**
```json
{
  "answer": "Based on the patient's medical records...",
  "context_used": ["snippet1", "snippet2"],
  "sources": [
    {
      "id": "record-123",
      "score": 0.89,
      "patient_id": "patient-123"
    }
  ],
  "metadata": {
    "patient_id": "patient-123",
    "session_id": "session-456",
    "retrieved_documents": 2,
    "model_used": "gpt-4o"
  }
}
```

#### Sessions

**Create Session**
```http
POST /chat/sessions
{
  "patientId": "patient-123",
  "sessionType": "ai"
}
```

**Get Session History**
```http
GET /chat/sessions/{sessionId}/history?limit=50
```

**Update Session**
```http
PUT /chat/sessions/{sessionId}
{
  "status": "active",
  "metadata": {}
}
```

**End Session**
```http
POST /chat/sessions/{sessionId}/end
```

#### Patients

**Get Patient Sessions**
```http
GET /chat/patients/{patientId}/sessions?limit=50
```

**Get Patient Preferences**
```http
GET /chat/patients/{patientId}/preferences
```

**Update Patient Preferences**
```http
PUT /chat/patients/{patientId}/preferences
{
  "language": "en",
  "notifications": true
}
```

#### Chat History

**Get Chat History**
```http
GET /chat-history/{patient_id}?limit=10
```

**Clear Chat History**
```http
DELETE /chat-history/{patient_id}
```

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "mongodb": true,
    "embedding": true,
    "retrieval": true,
    "generation": true,
    "context": true,
    "overall": true
  }
}
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PINECONE_API_KEY` | - | **Required** Pinecone API key |
| `PINECONE_INDEX_NAME` | `maichat-index` | Pinecone index name |
| `OPENAI_API_KEY` | - | **Required** OpenAI API key |
| `LLM_MODEL_NAME` | `gpt-4o` | OpenAI model to use |
| `EMBEDDING_MODEL_NAME` | `emilyalsentzer/Bio_ClinicalBERT` | HuggingFace embedding model |
| `MONGODB_URL` | `mongodb://mongodb:27017` | MongoDB connection URL |
| `MONGODB_DATABASE` | `rag_medical_db` | Database name |
| `MAX_SHORT_TERM_MESSAGES` | `10` | Messages in short-term context |
| `TOP_K_RETRIEVAL` | `5` | Number of documents to retrieve |
| `SIMILARITY_THRESHOLD` | `0.7` | Minimum similarity score (0-1) |
| `FIREBASE_CREDENTIALS_PATH` | - | Path to Firebase credentials JSON |
| `CHAT_RELAX_PATIENT_SESSION_ACCESS` | `true` | When `true`, any authenticated user may call `GET /v1/chat/patients/{patientUuid}/sessions` (patient FHIR id ≠ Firebase uid). Set `false` and use Firebase custom claims for stricter production. |
| `API_PORT` | `8000` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level |

### Model Configuration

**Embedding Model**: Clinical BERT is optimized for medical text
- Dimensions: 768
- Max tokens: 512
- GPU-accelerated when available

**LLM Model**: Configurable OpenAI model
- Default: GPT-4o
- Temperature: 0.2 (factual responses)
- Supports custom base URLs (e.g., Mistral AI)

### Context Management

**Short-term Memory**: Stores recent conversation messages
- Default: Last 10 messages
- Provides immediate context

**Long-term Memory**: Automatic summarization
- Triggers after 5+ messages (configurable)
- Preserves conversation continuity
- Reduces token usage

## 🐳 Docker Deployment

### Using Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  rag-backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - PINECONE_API_KEY=${PINECONE_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MONGODB_URL=mongodb://mongodb:27017
      - FIREBASE_CREDENTIALS_PATH=/app/credentials/firebase.json
    volumes:
      - ./credentials:/app/credentials
    depends_on:
      - mongodb

  mongodb:
    image: mongo:7.0
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      - MONGO_INITDB_DATABASE=rag_medical_db

volumes:
  mongodb_data:
```

**Run:**
```bash
docker-compose up -d
```

### Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🧪 Testing

### Manual Testing

```bash
# Test health check
curl http://localhost:8000/health

# Test chat (with Firebase token)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -d '{
    "query": "What are the symptoms of diabetes?",
    "patient_id": "patient-123",
    "session_id": "test-session"
  }'
```

### Unit Tests (Future)

```bash
pytest tests/ -v
```

## 📊 Monitoring

### Health Checks

The `/health` endpoint provides service status:
- MongoDB connectivity
- Embedding model status
- Pinecone connection
- OpenAI API availability
- Context service health

### Logging

Structured logging with configurable levels:
```python
# config.py
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

Logs include:
- Request/response details
- Service initialization
- Error traces
- Performance metrics

## 🔐 Security

### Authentication
- **Firebase JWT tokens** for all protected endpoints
- Token verification on every request
- User information extraction from tokens

### Data Isolation
- **Patient-specific namespaces** in Pinecone
- Session-based conversation tracking
- No cross-patient data leakage

### Best Practices
- Environment variable management
- Secure credential storage
- CORS configuration for production
- Input validation via Pydantic

## 📈 Performance

### Optimization Strategies
- **Async/await** throughout the codebase
- **Connection pooling** for MongoDB (10-50 connections)
- **GPU acceleration** for embeddings
- **Batch processing** for multiple documents
- **Lazy loading** of ML models

### Scalability
- **Stateless design** for horizontal scaling
- **Singleton services** for resource efficiency
- **Vector database** for fast retrieval
- **Caching-ready** architecture

## 🛠️ Development

### Project Structure

```
rag-backend/
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration management
├── dependencies.py        # Dependency injection setup
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
│
├── routers/              # API route handlers
│   ├── chat_router.py
│   ├── sessions_router.py
│   └── patients_router.py
│
├── services/             # Business logic layer
│   ├── mongodb_service.py
│   ├── embedding_service.py
│   ├── retrieval_service.py
│   ├── generation_service.py
│   └── context_service.py
│
├── pipeline/             # RAG orchestration
│   └── rag_orchestrator.py
│
├── models/               # Pydantic schemas
│   └── schemas.py
│
├── utils/                # Utilities
│   ├── logger.py
│   └── auth.py
│
└── static/               # Static files
    ├── index.html
    └── app.js
```

### Adding New Features

1. **New Service**: Create in `services/`, add to `dependencies.py`
2. **New Endpoint**: Add router in `routers/`, include in `main.py`
3. **New Schema**: Define in `models/schemas.py`
4. **Configuration**: Add to `config.py` and `.env`

### Code Style

- Follow PEP 8 guidelines
- Use type hints
- Add docstrings to functions
- Use async/await for I/O operations

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is proprietary and confidential.

## 🆘 Troubleshooting

### Common Issues

**MongoDB Connection Failed**
```bash
# Check MongoDB is running
docker ps | grep mongo

# Check connection string
echo $MONGODB_URL
```

**Embedding Model Not Loading**
```bash
# Download model manually
python -c "from transformers import AutoModel; AutoModel.from_pretrained('emilyalsentzer/Bio_ClinicalBERT')"
```

**Pinecone Index Not Found**
```bash
# Verify index exists and matches config
# Check PINECONE_INDEX_NAME in .env
```

**Firebase Authentication Errors**
```bash
# Verify credentials file exists
ls -la /path/to/firebase-credentials.json

# Check FIREBASE_CREDENTIALS_PATH in .env
```

## 📞 Support

For issues and questions:
- Create an issue in the repository
- Contact the development team
- Check API documentation at `/docs`

## 🗺️ Roadmap

- [ ] WebSocket support for streaming responses
- [ ] Redis caching layer
- [ ] Multi-language support
- [ ] Voice input/output
- [ ] FHIR resource integration
- [ ] Advanced analytics dashboard
- [ ] Rate limiting
- [ ] API versioning
- [ ] Comprehensive test suite
- [ ] Performance benchmarks

---

**Built with ❤️ for Healthcare AI**

