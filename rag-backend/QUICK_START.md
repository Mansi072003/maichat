# RAG Backend - Quick Start Guide

## The Problem

If you're seeing:
- `gunicorn main:app ... Exit 3`
- `ModuleNotFoundError: No module named 'fastapi'`

This means **dependencies are not installed**.

## Solution: Choose Your Environment

### Option 1: Docker (Recommended - Production Ready)

Docker automatically installs all dependencies during build.

```bash
# From the maichat directory
cd /Users/mukesh/aroga/maichat

# Build and start the service
docker-compose build rag-backend
docker-compose up rag-backend

# Or rebuild and start in one command
docker-compose up --build rag-backend
```

**Why Docker works:**
- Dockerfile installs dependencies: `RUN pip install -r requirements.txt`
- Sets PYTHONPATH automatically: `ENV PYTHONPATH=/app`
- Isolated environment - no conflicts

### Option 2: Local Development with Virtual Environment

```bash
cd /Users/mukesh/aroga/maichat/rag-backend

# 1. Create virtual environment
python3 -m venv venv

# 2. Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR on Windows:
# venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run with run.sh (sets PYTHONPATH automatically)
./run.sh

# OR run manually
export PYTHONPATH=$(pwd)
python main.py
```

### Option 3: Quick Test (Not Recommended for Production)

```bash
cd /Users/mukesh/aroga/maichat/rag-backend

# Install dependencies globally
pip3 install -r requirements.txt

# Run
export PYTHONPATH=$(pwd)
python main.py
```

## Verifying Installation

Test if dependencies are installed:

```bash
cd /Users/mukesh/aroga/maichat/rag-backend
export PYTHONPATH=$(pwd)
python -c "from main import app; print('✅ App loaded successfully')"
```

If successful, you should see: `✅ App loaded successfully`

## Common Issues

### Issue 1: "ModuleNotFoundError: No module named 'fastapi'"
**Cause:** Dependencies not installed  
**Fix:** Run `pip install -r requirements.txt`

### Issue 2: "ModuleNotFoundError: No module named 'services'"
**Cause:** PYTHONPATH not set  
**Fix:** Use `./run.sh` or `export PYTHONPATH=$(pwd)`

### Issue 3: "gunicorn ... Exit 3"
**Cause:** Dependencies not installed OR PYTHONPATH not set  
**Fix:** 
1. Install dependencies: `pip install -r requirements.txt`
2. Set PYTHONPATH in Dockerfile (already done)
3. Use Docker: `docker-compose up --build rag-backend`

### Issue 4: Firebase authentication errors
**Cause:** Firebase credentials not configured  
**Fix:** Set `FIREBASE_CREDENTIALS_PATH` in `.env` file

## Environment Setup

Create a `.env` file (or use `scripts/.env`):

```bash
# Required
PINECONE_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here

# Firebase (for authentication)
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json

# Optional (has defaults)
MONGODB_URL=mongodb://mongodb:27017
EMBEDDING_MODEL_NAME=emilyalsentzer/Bio_ClinicalBERT
LOG_LEVEL=INFO
```

## Running the Application

### Docker (Recommended)
```bash
# Start all services
docker-compose up

# Or just rag-backend
docker-compose up rag-backend

# View logs
docker-compose logs -f rag-backend

# Rebuild after code changes
docker-compose up --build rag-backend
```

### Local Development
```bash
cd rag-backend

# Activate venv if using one
source venv/bin/activate

# Run
./run.sh

# Or with uvicorn directly (for hot-reload)
export PYTHONPATH=$(pwd)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Testing the API

Once running, test the endpoints:

```bash
# Health check (no auth required)
curl http://localhost:8000/health

# Chat endpoint (requires Firebase token)
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What medications am I taking?",
    "patient_id": "patient-123"
  }'
```

## Development Workflow

1. **Make code changes** in `rag-backend/`
2. **For Docker**: Restart container
   ```bash
   docker-compose restart rag-backend
   # Or rebuild if dependencies changed
   docker-compose up --build rag-backend
   ```
3. **For Local**: Code auto-reloads if using `uvicorn --reload`

## Troubleshooting Commands

```bash
# Check if packages are installed
pip list | grep fastapi

# Verify Python path
python -c "import sys; print('\n'.join(sys.path))"

# Test imports
cd rag-backend
export PYTHONPATH=$(pwd)
python -c "from services import EmbeddingService; print('Services OK')"
python -c "from main import app; print('Main OK')"

# Check Docker logs
docker-compose logs rag-backend

# Rebuild Docker from scratch
docker-compose build --no-cache rag-backend
```

## Next Steps

- Read [ARCHITECTURE.md](../ARCHITECTURE.md) for system overview
- Read [README_IMPORTS.md](./README_IMPORTS.md) for import resolution details
- Configure Firebase authentication
- Set up MongoDB and Pinecone
- Run the full stack with `docker-compose up`

