#!/usr/bin/env python3
"""
Lead Researcher (Intake) Runner

Wrapper script to run the interview/intake flow from project root.
Ensures proper import paths.
"""

import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Run lead researcher
from intake.lead_researcher import main

if __name__ == "__main__":
    main()
