#!/bin/bash

# Configuration - Use absolute paths where possible
PROJECT_ROOT="/home/sasarmandarius/PycharmProjects/SameSong"
MUSIC_DIR="$PROJECT_ROOT/data/music"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python3"
INSERT_SCRIPT="$PROJECT_ROOT/ingestion/manual_insert.py"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}==========================================================${NC}"
echo -e "${BLUE}      SameSong - Batch Music Ingestion Script             ${NC}"
echo -e "${BLUE}==========================================================${NC}"

# 1. Validation Checks
if [ ! -d "$MUSIC_DIR" ]; then
    echo -e "${RED}Error: Music directory not found at $MUSIC_DIR${NC}"
    exit 1
fi

if [ ! -x "$VENV_PYTHON" ]; then
    echo -e "${RED}Error: Python executable not found or not executable at $VENV_PYTHON${NC}"
    exit 1
fi

# 2. Scanning for files (Handles spaces/special characters correctly)
echo -e "${BLUE}Scanning for audio files in $MUSIC_DIR...${NC}"
FILES=()
while IFS=  read -r -d $'\0'; do
    FILES+=("$REPLY")
done < <(find "$MUSIC_DIR" -type f \( -name "*.mp3" -o -name "*.wav" -o -name "*.flac" -o -name "*.m4a" -o -name "*.ogg" \) -print0)

TOTAL=${#FILES[@]}
echo -e "${GREEN}Found $TOTAL audio files.${NC}"

if [ $TOTAL -eq 0 ]; then
    echo -e "${RED}No audio files found. Exiting.${NC}"
    exit 0
fi

# 3. Batch Processing
index=1
for file in "${FILES[@]}"; do
    echo -e "\n${BLUE}[$index/$TOTAL] Processing: ${NC}$(basename "$file")"

    # Wrap $file in quotes to handle spaces in names
    # Using 'python3 -u' to ensure output isn't buffered (shows progress in real-time)
    "$VENV_PYTHON" -u "$INSERT_SCRIPT" "$file" --direct

    # Capture the exit status of the python command
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Successfully processed: $(basename "$file")${NC}"
    else
        echo -e "${RED}✗ Failed to process: $(basename "$file")${NC}"
    fi

    ((index++))
done

echo -e "\n${BLUE}==========================================================${NC}"
echo -e "${GREEN}Batch ingestion complete!${NC}"
echo -e "${BLUE}==========================================================${NC}"