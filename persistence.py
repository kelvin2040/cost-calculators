"""
persistence.py — Data persistence functions for cost_calc.py

Handles saving, loading, and managing estimate files and data integrity.
"""

import copy
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from constants import SAVE_DIR, SYSTEM_FILES
from calculations import calc_totals

def _safe_filename(project_name: str) -> str:
    """
    Sanitize filename by removing path-traversal characters.

    Keeps only alphanumeric characters, spaces, hyphens, and underscores.

    Args:
        project_name: Original project name.

    Returns:
        Safe filename string.
    """
    safe = "".join(c for c in project_name if c.isalnum() or c in " _-")
    return safe.strip().lower().replace(" ", "_") or "unnamed"

def save_estimate(estimate: Dict[str, Any], filename: Optional[str] = None, force: bool = False) -> bool:
    """
    Save estimate to JSON file.

    Args:
        estimate: Estimate dictionary to save.
        filename: Optional custom filename. If None, generates from project name.
        force: If True, overwrite without confirmation.

    Returns:
        True if saved successfully, False otherwise.
    """
    if filename is None:
        filename = _safe_filename(estimate["project"]) + ".json"

    path = os.path.join(SAVE_DIR, filename)

    if not force and os.path.exists(path):
        # Confirmation would be handled in UI layer
        return False

    os.makedirs(SAVE_DIR, exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(estimate, f, indent=2)
        return True
    except IOError:
        return False

def list_saved() -> List[str]:
    """
    List all saved estimate filenames.

    Returns:
        Sorted list of estimate filenames (excluding system files).
    """
    if not os.path.exists(SAVE_DIR):
        return []

    return sorted(
        f for f in os.listdir(SAVE_DIR)
        if f.endswith(".json") and f not in SYSTEM_FILES
    )

def load_estimate(filename: str) -> Optional[Dict[str, Any]]:
    """
    Load estimate from JSON file.

    Args:
        filename: Estimate filename.

    Returns:
        Estimate dictionary if loaded successfully, None otherwise.
    """
    path = os.path.join(SAVE_DIR, filename)
    if not os.path.exists(path):
        return None

    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

def delete_estimate(filename: str) -> bool:
    """
    Delete an estimate file.

    Args:
        filename: Estimate filename to delete.

    Returns:
        True if deleted successfully, False otherwise.
    """
    path = os.path.join(SAVE_DIR, filename)
    if not os.path.exists(path):
        return False

    try:
        os.remove(path)
        return True
    except OSError:
        return False

def duplicate_estimate(original: Dict[str, Any], new_name: str) -> Dict[str, Any]:
    """
    Create a duplicate of an estimate with new name and current date.

    Args:
        original: Original estimate dictionary.
        new_name: New project name.

    Returns:
        New estimate dictionary.
    """
    new_est = copy.deepcopy(original)
    new_est["project"] = new_name
    new_est["date"] = datetime.now().strftime("%Y-%m-%d")
    return new_est

# ── Display helpers for saved estimates ───────────────────────────────────────

def get_estimate_summary(filename: str) -> Optional[Dict[str, Any]]:
    """
    Get summary information for a saved estimate.

    Args:
        filename: Estimate filename.

    Returns:
        Dict with project, date, currency, sell_price, or None if error.
    """
    estimate = load_estimate(filename)
    if estimate is None:
        return None

    totals = calc_totals(estimate)
    return {
        "project": estimate.get("project", "Unknown"),
        "date": estimate.get("date", "N/A"),
        "currency": estimate.get("currency", "N/A"),
        "sell_price": totals["sell_price"],
    }