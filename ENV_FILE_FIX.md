# Fix .env File Parse Error

## Problem

Docker Compose and the applications are failing with:
```
Python-dotenv could not parse statement starting at line 4
```

**Location**: `/Users/mukesh/aroga/maichat/scripts/.env`

## How to Fix

### Step 1: Check Line 4

```bash
# View the problematic line
sed -n '4p' /Users/mukesh/aroga/maichat/scripts/.env
```

### Step 2: Common .env Syntax Errors

#### ❌ Error 1: Values with spaces (no quotes)
```env
MY_VAR=value with spaces    # WRONG
```
**Fix:**
```env
MY_VAR="value with spaces"  # CORRECT
```

#### ❌ Error 2: Multiline values
```env
MY_VAR=line1
line2                       # WRONG - parser thinks this is line 4
```
**Fix:**
```env
MY_VAR="line1\nline2"       # CORRECT
```

#### ❌ Error 3: Special characters not escaped
```env
PASSWORD=p@ss$word!         # MIGHT FAIL
```
**Fix:**
```env
PASSWORD="p@ss$word!"       # CORRECT
```

#### ❌ Error 4: Empty value or no value
```env
MY_VAR=                     # MIGHT FAIL
```
**Fix:**
```env
MY_VAR=""                   # CORRECT
# Or just remove the line if not needed
```

#### ❌ Error 5: Comments in wrong place
```env
MY_VAR=value # comment      # MIGHT FAIL
```
**Fix:**
```env
# Comment on its own line
MY_VAR=value                # CORRECT
```

### Step 3: View Your .env File

```bash
# See the first 10 lines
head -10 /Users/mukesh/aroga/maichat/scripts/.env

# See with line numbers
cat -n /Users/mukesh/aroga/maichat/scripts/.env | head -10
```

### Step 4: Template for Correct .env

```env
# Line 1: Comment
# Line 2: Another comment
LINE3_VAR=simple_value
LINE4_VAR="value with spaces or special chars"
LINE5_VAR=/path/to/file

# Firebase
FIREBASE_CREDENTIALS_PATH="/var/app/config/arogarocks-cloudhealthcareapi.json"

# Pinecone
PINECONE_API_KEY="your-key-here"
PINECONE_INDEX_NAME=maichat-index

# MongoDB
MONGODB_URL="mongodb://mongodb:27017"

# OpenAI
OPENAI_API_KEY="sk-..."

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
```

## Quick Fix

If you can't find the issue, try:

### Option 1: Regenerate .env from template
```bash
cd /Users/mukesh/aroga/maichat/scripts

# Backup current .env
cp .env .env.backup

# Create new .env from examples
cat > .env << 'EOF'
# Pinecone
PINECONE_API_KEY=your-key-here
PINECONE_INDEX_NAME=maichat-index

# OpenAI
OPENAI_API_KEY=your-key-here
LLM_MODEL_NAME=gpt-4o

# MongoDB
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DATABASE=rag_medical_db

# Firebase
FIREBASE_CREDENTIALS_PATH=/var/app/config/arogarocks-cloudhealthcareapi.json

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Logging
LOG_LEVEL=INFO
EOF

# Then add your actual API keys
```

### Option 2: Validate .env file
```bash
# Check for syntax errors
python3 << 'EOF'
from dotenv import dotenv_values
try:
    values = dotenv_values("/Users/mukesh/aroga/maichat/scripts/.env")
    print("✅ .env file is valid")
    print(f"Loaded {len(values)} variables")
except Exception as e:
    print(f"❌ Error: {e}")
EOF
```

## Docker Compose Status

✅ **docker-compose.yml is now valid!**

The YAML syntax error is fixed. The only remaining issue is the `.env` file parse error.

## Next Steps

1. Fix line 4 in `/Users/mukesh/aroga/maichat/scripts/.env`
2. Restart Docker: `docker-compose up --build`
3. Verify services start successfully

## Testing

After fixing .env:
```bash
# Validate docker-compose
docker-compose config

# Start services
docker-compose up
```

