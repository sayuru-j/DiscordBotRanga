#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Starting Discord Bot with Hot Reload..."
echo "Press Ctrl+C to stop"
echo ""

python dev.py
