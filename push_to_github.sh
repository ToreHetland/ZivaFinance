#!/bin/bash
set -euo pipefail

echo "🚀 Starting GitHub Update..."

# Ensure we're in a git repo
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "❌ Not inside a git repository."
  exit 1
}

# Add changes
git add .

# If nothing staged, exit nicely
if git diff --cached --quiet; then
  echo "✅ No changes to commit."
  exit 0
fi

# Ask for commit message
echo "Enter a brief description of what you changed:"
read -r commit_message

if [[ -z "${commit_message// }" ]]; then
  commit_message="Update"
fi

# Commit
git commit -m "$commit_message"

# Push current branch
branch="$(git rev-parse --abbrev-ref HEAD)"
echo "📤 Pushing to GitHub (branch: $branch)..."
git push origin "$branch"

echo "✅ Done! Streamlit Cloud will redeploy if it's connected to this repo/branch."
