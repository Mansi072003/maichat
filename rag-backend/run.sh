#!/bin/bash
# Run script for rag-backend with proper PYTHONPATH

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}Warning: No virtual environment detected${NC}"
    echo -e "Consider running: ${GREEN}python -m venv venv && source venv/bin/activate${NC}"
    echo ""
fi

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${RED}Error: Dependencies not installed!${NC}"
    echo -e "Run: ${GREEN}pip install -r requirements.txt${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Dependencies installed${NC}"

# Set PYTHONPATH to include the current directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
echo -e "${GREEN}✓ PYTHONPATH set to $(pwd)${NC}"

# Run the application
echo -e "${GREEN}Starting RAG Backend...${NC}"
python main.py "$@"

