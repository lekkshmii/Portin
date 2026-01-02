#!/usr/bin/env python3
"""
PORTIN DASHBOARD LAUNCHER
Runs the modern Glassmorphism dashboard.
"""
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dashboard.app import app

if __name__ == '__main__':
    print("\n🚀 Starting Portin Dashboard...")
    print("   Theme: Glassmorphism (Bayport Style)")
    print("   URL:   http://localhost:5000")
    print("\nPress Ctrl+C to stop.\n")
    app.run(debug=True, port=5000)
