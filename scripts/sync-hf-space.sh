#!/bin/bash

set -e

SOURCE="/Users/project/smart-study-assistant-rag/deploy/hf-space/"
TARGET="/Users/project/smart-study-assistant-demo/"

echo "Syncing Hugging Face deployment..."

rsync -av --delete \
  --exclude=".git" \
  --exclude=".gitattributes" \
  --exclude="README.md" \
  --exclude=".kilo" \
  --exclude=".DS_Store" \
  "$SOURCE" "$TARGET"

echo ""
echo "Sync complete."
echo ""
echo "Hugging Face repo status:"

cd "$TARGET"
git status
