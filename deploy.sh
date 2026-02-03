#!/bin/bash

set -euo pipefail

APPS_SCRIPT_DIR="apps-script"
APPS_SCRIPT_PROJECT_ID="1_Ph_bUS6lbFpWPIlhDZQUjIT7QZyGVZRG0todZ1o2GYhgj1Y0-OCDbJF"
APPS_SCRIPT_DEPLOYMENT_ID="AKfycbz2T-xieiHlll6pCUfHaoP9GQHACdcJhDD52Z5pCoSCj1S09vhzRZfL2kNJHJ-l8kL9cA"

echo ""
echo "================================"
echo "🚀 Apps Script Deploy"
echo "================================"
echo ""

if ! command -v clasp >/dev/null 2>&1; then
  echo "clasp not installed. Install: npm i -g @google/clasp"
  exit 1
fi

if [[ ! -f ".clasp.json" ]]; then
  echo "Missing .clasp.json in repo root."
  echo "Run: clasp clone \"$APPS_SCRIPT_PROJECT_ID\" --rootDir \"$APPS_SCRIPT_DIR\""
  exit 1
fi

echo "Pushing local Apps Script..."
clasp push

echo "Deploying..."
clasp deploy -i "$APPS_SCRIPT_DEPLOYMENT_ID" -d "Manual deploy $(date +"%Y-%m-%d %H:%M:%S")"

echo "Done."
echo ""
