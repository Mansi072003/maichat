# Pinecone Backend - FHIR Data Consumer

A dedicated microservice for processing FHIR medical data, generating embeddings, and storing them in Pinecone vector database. This service acts as a consumer that listens to a Redis queue for incoming FHIR resources and automatically indexes them for semantic search.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Pinecone Backend                          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    Main Consumer Loop                   │ │
│  │                    (main.py)                           │ │
│  └───────────────┬────────────────────────────────────────┘ │
│                  │                                           │
│                  ▼                                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │               FHIR Processor                            │ │
│  │         (processors/fhir_processor.py)                 │ │
│  │                                                         │ │
│  │  • Validates FHIR message structure                    │ │
│  │  • Coordinates service calls                           │ │
│  │  • Handles error recovery                              │ │
│  └───┬─────────────┬─────────────┬────────────────────────┘ │
│      │             │             │                           │
│      ▼             ▼             ▼                           │
│  ┌─────────┐  ┌──────────┐  ┌──────────────┐               │
│  │ Redis   │  │Embedding │  │  Pinecone    │               │
│  │Service  │  │Service   │  │  Service     │               │
│  └─────────┘  └──────────┘  └──────────────┘               │
│      │             │             │                           │
└──────┼─────────────┼─────────────┼───────────────────────────┘
       │             │             │
       ▼             ▼             ▼
   ┌────────┐   ┌────────┐   ┌─────────┐
   │ Redis  │   │Clinical│   │Pinecone │
   │ Queue  │   │  BERT  │   │ Vector  │
   │        │   │ Model  │   │   DB    │
   └────────┘   └────────┘   └─────────┘
```

## Key Components

### 1. Main Consumer (`main.py`)

**Purpose**: Entry point that orchestrates the message consumption loop.

**Responsibilities**:
- Initializes configuration and validates environment variables
- Creates and initializes the FHIR processor
- Runs the main consumer loop with error handling
- Implements retry logic and backoff strategies

**Flow**:
```python
1. Validate configuration
2. Initialize FHIR processor
3. Start infinite loop:
   - Wait for message from Redis queue (30s timeout)
   - Process message through FHIR processor
   - Handle errors with exponential backoff
   - Track consecutive errors (max 5)
4. Graceful shutdown on interrupt
```

### 2. FHIR Processor (`processors/fhir_processor.py`)

**Purpose**: Core business logic for processing FHIR medical data.

**Responsibilities**:
- Validate incoming FHIR messages
- Extract patient and medical data
- Generate embeddings for medical text
- Store vectors in Pinecone with proper metadata

**Message Format**:
```json
{
  "patientId": "patient-123",
  "practitionerId": "practitioner-456",
  "resourceType": "Observation",
  "resourceId": "obs-789",
  "text": "Patient presented with chest pain. ECG shows normal sinus rhythm..."
}
```

**Processing Pipeline**:
```
1. Validate required fields (patientId, text)
2. Generate embedding from text using Clinical BERT
3. Store in Pinecone:
   - Namespace: patient-{patientId}
   - Vector ID: {resourceId}
   - Metadata: patientID, text, resourceType, practitionerId
```

### 3. Services Layer

#### Redis Service (`services/redis_service.py`)

**Purpose**: Manages Redis queue operations for message consumption.

**Key Features**:
- Blocking pop operation (`brpop`) for efficient message retrieval
- Automatic JSON deserialization
- Connection pooling and reconnection logic
- Health check endpoint

**Configuration**:
```python
REDIS_HOST: Redis server hostname (default: "redis")
REDIS_PORT: Redis server port (default: 6379)
REDIS_PASSWORD: Optional authentication
REDIS_DB: Database number (default: 0)
```

#### Embedding Service (`services/embedding_service.py`)

**Purpose**: Generates medical domain embeddings using Clinical BERT.

**Model**: `emilyalsentzer/Bio_ClinicalBERT`
- Pre-trained on clinical notes (MIMIC-III)
- 768-dimensional embeddings
- Optimized for medical terminology

**Process**:
1. Tokenize text (max 512 tokens)
2. Generate embeddings using [CLS] token
3. Return 768-dimensional vector
4. GPU acceleration when available

**Performance**:
- Device: Auto-detect CUDA or CPU
- Batch processing: Single text per call
- Average latency: ~50-200ms per embedding

#### Pinecone Service (`services/pinecone_service.py`)

**Purpose**: Manages vector storage in Pinecone database.

**Key Operations**:
- `upsert_vector()`: Store/update embeddings
- `health_check()`: Verify connection

**Data Structure**:
```python
Vector ID: resource_id (e.g., "obs-123", "rec-001")
Namespace: "patient-{patientId}"
Metadata:
  - patientID: Patient identifier
  - text: Original text content
  - resourceType: FHIR resource type
  - practitionerId: Associated practitioner
  - processed_at: Unix timestamp
```

**Why Namespaces?**
- Isolates patient data for privacy
- Enables efficient patient-specific queries
- Supports multi-tenancy

## Configuration

### Environment Variables

Create a `.env` file in the `pinecone-backend` directory:

```env
# Pinecone Configuration
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=maichat-index

# Embedding Model
EMBEDDING_MODEL_NAME=emilyalsentzer/Bio_ClinicalBERT

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Logging
LOG_LEVEL=INFO
```

### Configuration Validation

The service validates critical configuration on startup:
- `PINECONE_API_KEY`: Required for vector database access
- Model availability: Downloads Clinical BERT if not cached
- Redis connectivity: Pings Redis before starting

## Data Flow

### End-to-End Process

```
1. FHIR Resource Created
   └─> External system/API sends FHIR data to Redis queue

2. Message Queued
   └─> Redis queue: 'fhir_data'
   └─> Format: JSON with patientId, text, resourceType, etc.

3. Consumer Receives Message
   └─> Blocking pop from Redis (30s timeout)
   └─> JSON deserialization

4. FHIR Processor Validates
   └─> Check required fields: patientId, text
   └─> Generate resourceId if missing

5. Embedding Generation
   └─> Tokenize text (Clinical BERT tokenizer)
   └─> Generate 768-dim embedding
   └─> Extract [CLS] token representation

6. Vector Storage
   └─> Namespace: patient-{patientId}
   └─> Upsert to Pinecone with metadata
   └─> Log success/failure

7. Loop Continues
   └─> Wait for next message
```

### Error Handling

**Consecutive Error Tracking**:
- Tracks up to 5 consecutive errors
- Sleeps 30 seconds after 5 errors
- Exits after persistent failures

**Error Types**:
1. **Validation Errors**: Missing required fields → Log warning, skip message
2. **Connection Errors**: Redis/Pinecone timeout → Retry with backoff
3. **Processing Errors**: Embedding failure → Log error, continue
4. **Fatal Errors**: Configuration issues → Exit with error code

## Installation

### Prerequisites

- Python 3.9+
- Docker (for containerized deployment)
- Pinecone account with index created
- Redis server running

### Local Setup

```bash
# Navigate to pinecone-backend directory
cd pinecone-backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Run the service
python main.py
```

### Docker Deployment

```bash
# Build image
docker build -t pinecone-backend .

# Run container
docker run --env-file .env pinecone-backend
```

### Docker Compose

The service is included in the main `docker-compose.yml`:

```yaml
pinecone-backend:
  build: ./pinecone-backend
  depends_on:
    - redis
  environment:
    - PINECONE_API_KEY=${PINECONE_API_KEY}
    - REDIS_HOST=redis
```

## Monitoring & Health Checks

### Health Check

The FHIR processor includes a health check method:

```python
processor.health_check()
# Returns:
{
  "redis": True,
  "pinecone": True,
  "embedding": True
}
```

### Logging

**Log Levels**:
- `INFO`: Successful operations, message processing
- `WARNING`: Validation failures, skipped messages
- `ERROR`: Processing errors, connection issues
- `DEBUG`: Detailed message content, queue polling

**Log Format**:
```
2024-01-15 10:30:45 INFO - Processing record for patient: patient-123, resourceType: Observation
2024-01-15 10:30:45 INFO - Successfully upserted vector for namespace 'patient-123' (ID: obs-789)
```

## Performance Considerations

### Throughput

**Bottlenecks**:
1. **Embedding Generation**: ~50-200ms per message (CPU)
2. **Network I/O**: Pinecone upsert ~10-50ms
3. **Redis Pop**: Blocking, minimal overhead

**Optimization**:
- GPU acceleration for embeddings (5-10x faster)
- Batch processing (future enhancement)
- Connection pooling for Pinecone

### Scalability

**Horizontal Scaling**:
- Multiple consumer instances can run in parallel
- Redis queue ensures message distribution
- Each consumer processes independently

**Resource Requirements**:
- CPU: 1-2 cores (2-4 with GPU)
- RAM: 2-4 GB (model loading)
- Network: Low bandwidth, stable connection required

## Dependencies

```
redis==5.0.3              # Redis client for queue operations
pinecone-client==3.1.0    # Pinecone vector database
transformers==4.38.1      # Hugging Face transformers (BERT)
torch==2.2.1             # PyTorch for model inference
python-dotenv==1.0.1     # Environment variable management
numpy==1.24.3            # Numerical operations
```

## Troubleshooting

### Common Issues

**1. "Failed to connect to Redis"**
- Check `REDIS_HOST` and `REDIS_PORT` configuration
- Verify Redis server is running: `redis-cli ping`
- Check network connectivity in Docker

**2. "Error loading Clinical BERT model"**
- Ensure sufficient disk space (~500MB)
- Check internet connection for model download
- Verify Hugging Face is accessible

**3. "Error initializing Pinecone"**
- Validate `PINECONE_API_KEY`
- Ensure index exists: `PINECONE_INDEX_NAME`
- Check Pinecone dashboard for service status

**4. "Missing required environment variable"**
- Run `config.validate_config()` to identify missing vars
- Check `.env` file is in correct directory
- Ensure variables are exported in Docker

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python main.py
```

This will show:
- Message content details
- Embedding vector shapes
- Detailed error stack traces

## Best Practices

### Security

1. **Never commit `.env` files**: Use `.gitignore`
2. **Rotate API keys regularly**: Pinecone, Redis passwords
3. **Use environment variables**: Avoid hardcoding credentials
4. **Enable Redis authentication**: Set `REDIS_PASSWORD`

### Data Privacy

- Patient data is isolated by namespace
- HIPAA compliance: Encrypt data in transit (TLS)
- PHI handling: Ensure Pinecone deployment is compliant
- Audit logging: Track all data access

### Reliability

1. **Monitor queue depth**: Alert on backlog
2. **Track processing rate**: Metrics for throughput
3. **Set up alerts**: Health check failures
4. **Implement dead-letter queue**: For failed messages

## Future Enhancements

- [ ] Batch embedding generation for improved throughput
- [ ] Dead-letter queue for failed messages
- [ ] Prometheus metrics export
- [ ] Graceful shutdown handling
- [ ] Message deduplication
- [ ] Configurable retry strategies
- [ ] Multi-model embedding support

## Contributing

When contributing to this service:

1. Maintain backward compatibility with message format
2. Add tests for new processors
3. Update this README for architectural changes
4. Follow logging conventions

## License

[Your License]

## Support

For issues or questions:
- Check logs for detailed error messages
- Review configuration validation
- Contact the development team

