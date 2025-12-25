#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "--- Installing Backend Dependencies ---"
pip install -r requirements.txt

echo "--- Installing Frontend Dependencies ---"
# Navigate to the frontend folder
cd frontend
npm install

echo "--- Building Frontend ---"
npm run build

echo "--- Moving Build Artifacts ---"
# Go back to the root folder
cd ..
# Remove old build folder if it exists
rm -rf build
# Move the new React build folder to the root so Flask can find it
mv frontend/build build