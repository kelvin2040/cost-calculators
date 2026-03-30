#!/usr/bin/env python3
"""
cost_calc.py — Material + Labour Cost Calculator with Profit Margins & VAT

Usage:
    python cost_calc.py

Estimates and settings are saved to ~/.cost_calc/

This file now delegates to the modular main.py for execution.
"""

# Import from modular components
from main import main

if __name__ == "__main__":
    main()
