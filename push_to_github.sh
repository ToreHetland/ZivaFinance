#!/bin/bash

# Navigate to the project directory (optional if you run it from the folder)
# cd /path/to/your/ziva/folder

echo "🚀 Starting GitHub Update..."

# 1. Add all changes (respecting your .gitignore)
git add .

# 2. Ask for a commit message
echo "Enter a brief description of what you changed:"
read commit_message

# 3. Commit the changes
git commit -m "$commit_message"

# 4. Push to GitHub
echo "📤 Pushing to GitHub..."
git push origin main

echo "✅ Done! Your app should be updating on Streamlit Cloud now."
