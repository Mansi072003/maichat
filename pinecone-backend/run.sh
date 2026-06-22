#!/bin/bash
# Run script for pinecone-backend with proper PYTHONPATH

# Set PYTHONPATH to include the current directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run the application
python main.py "$@"

