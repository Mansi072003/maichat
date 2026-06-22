# Import Resolution Guide

## Problem

Python modules in subdirectories (`pipeline/`, `services/`, etc.) cannot resolve imports to sibling directories without the project root in `PYTHONPATH`.

## Solution

The `rag-backend` uses absolute imports from the project root. Ensure the project root is in `PYTHONPATH`.

## Running the Application

### Option 1: Using run.sh (Recommended for local development)

```bash
chmod +x run.sh
./run.sh
```

This automatically sets `PYTHONPATH` to include the current directory.

### Option 2: Manual PYTHONPATH

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python main.py
```

### Option 3: Using Python module execution

```bash
cd /path/to/maichat
python -m rag-backend.main
```

### Option 4: Docker (Production)

The Dockerfile automatically sets `PYTHONPATH=/app`, so no manual configuration needed:

```bash
docker-compose up rag-backend
```

## Import Structure

The project uses **absolute imports** from the project root:

```python
# ✅ Correct - Absolute imports from project root
from services import EmbeddingService
from services.mongodb_service import MongoDBService
from utils.logger import get_logger
from pipeline.rag_orchestrator import RAGOrchestrator

# ❌ Incorrect - Relative imports won't work across packages
from ..services import EmbeddingService  # Wrong!
```

## Directory Structure

```
rag-backend/
├── __init__.py           # Makes rag-backend a package
├── main.py               # Entry point
├── config.py
├── dependencies.py
├── services/
│   ├── __init__.py       # Exports: EmbeddingService, etc.
│   ├── embedding_service.py
│   ├── retrieval_service.py
│   └── ...
├── pipeline/
│   ├── __init__.py       # Exports: RAGOrchestrator
│   └── rag_orchestrator.py
├── routers/
│   ├── __init__.py       # Exports: chat_router, etc.
│   └── ...
├── utils/
│   ├── __init__.py       # Exports: get_logger, etc.
│   └── ...
└── models/
    ├── __init__.py       # Exports: ChatRequest, etc.
    └── schemas.py
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'services'"

**Cause**: Project root not in `PYTHONPATH`

**Fix**:
```bash
# Option 1: Export PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/path/to/rag-backend"
python main.py

# Option 2: Use run.sh
./run.sh

# Option 3: Run as module
cd /path/to/maichat
python -m rag-backend.main
```

### "ImportError: attempted relative import with no known parent package"

**Cause**: Using relative imports (`from ..services import ...`)

**Fix**: Use absolute imports instead:
```python
# Change this:
from ..services.mongodb_service import MongoDBService

# To this:
from services.mongodb_service import MongoDBService
```

## IDE Configuration

### VS Code

Add to `.vscode/settings.json`:
```json
{
  "python.analysis.extraPaths": ["${workspaceFolder}/rag-backend"],
  "terminal.integrated.env.linux": {
    "PYTHONPATH": "${workspaceFolder}/rag-backend"
  },
  "terminal.integrated.env.osx": {
    "PYTHONPATH": "${workspaceFolder}/rag-backend"
  },
  "terminal.integrated.env.windows": {
    "PYTHONPATH": "${workspaceFolder}/rag-backend"
  }
}
```

### PyCharm

1. Right-click `rag-backend` folder
2. Select "Mark Directory as" → "Sources Root"

## Why This Structure?

1. **Clarity**: Absolute imports are easier to understand
2. **Consistency**: Same import style throughout the project
3. **Docker-friendly**: Works seamlessly in containers
4. **IDE support**: Better autocomplete and type checking

## Quick Reference

| Scenario | Command |
|----------|---------|
| Local dev | `./run.sh` or `export PYTHONPATH=$(pwd) && python main.py` |
| Docker | `docker-compose up rag-backend` (automatic) |
| Testing | `PYTHONPATH=$(pwd) pytest` |
| Linting | `PYTHONPATH=$(pwd) pylint services/` |

