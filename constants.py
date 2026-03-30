"""
constants.py — Constants and configuration defaults for cost_calc.py

This module contains all hardcoded values, default settings, and configurable constants
used throughout the cost calculation application.
"""

import os

# ── Version ────────────────────────────────────────────────────────────────────

VERSION = "2.0.0"  # Modular refactor

# ── File Paths ──────────────────────────────────────────────────────────────────

SAVE_DIR = os.path.expanduser("~/.cost_calc")
CONFIG_FILE = os.path.join(SAVE_DIR, "config.json")
VAT_RATES_FILE = os.path.join(SAVE_DIR, "vat_rates.json")

# ── Default Values ──────────────────────────────────────────────────────────────

DEFAULT_CURRENCY = "NGN"
DEFAULT_VAT_ENABLED = True
DEFAULT_VAT_RATE = None  # Use country default

# ── UI Constants ────────────────────────────────────────────────────────────────

TABLE_WIDTH = 62  # Characters for estimate table display
HR_CHAR = "─"  # Horizontal rule character
HR_WIDTH = 52  # Default width for horizontal rules

# ── Network Constants ───────────────────────────────────────────────────────────

VAT_UPDATE_TIMEOUT = 10  # Seconds for remote VAT rate fetch

# ── Calculation Constants ───────────────────────────────────────────────────────

# Default pipe length for calculators (mm)
DEFAULT_PIPE_LENGTH = 6000

# ── System Files ────────────────────────────────────────────────────────────────

SYSTEM_FILES = {"config.json", "vat_rates.json"}