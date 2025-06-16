#!/bin/bash

# Git Subtree Push All Helper Script
# This script pushes changes back to all subtree repositories

echo "📤 Pushing all subtrees..."

# UI Repository
echo "📱 Pushing UI changes..."
git subtree push --prefix=ui ui-origin main

# API Repository
echo "🚀 Pushing API changes..."
git subtree push --prefix=api api-origin main

echo "✅ All subtrees pushed!"
echo "🎯 Individual repositories have been updated" 