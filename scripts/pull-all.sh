#!/bin/bash

# Git Subtree Pull All Helper Script
# This script pulls updates from all subtree repositories

echo "🔄 Pulling all subtrees..."

# UI Repository
echo "📱 Updating UI..."
git subtree pull --prefix=ui ui-origin main --squash

# API Repository  
echo "🚀 Updating API..."
git subtree pull --prefix=api api-origin main --squash

echo "✅ All subtrees updated!"
echo "🎯 Run 'git status' to see any changes" 