#!/usr/bin/env python3
"""
Screener (Enrichment) Runner

Wrapper script to run the enrichment/screening flow from project root.
Ensures proper import paths.
"""

import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Run screener
from enrichment.screener import main

if __name__ == "__main__":
    main()
