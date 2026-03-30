"""
config.py — Configuration management for cost_calc.py

Handles loading, saving, and managing application configuration including
currency settings, VAT rates, and remote updates.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Dict, Optional, Any, Tuple

from constants import (
    SAVE_DIR, CONFIG_FILE, VAT_RATES_FILE, DEFAULT_CURRENCY,
    DEFAULT_VAT_ENABLED, DEFAULT_VAT_RATE, VAT_UPDATE_TIMEOUT
)

# ── Currencies & VAT rates ────────────────────────────────────────────────────

CURRENCIES: Dict[str, Dict[str, Any]] = {
    "NGN": {"name": "Nigerian Naira",         "symbol": "₦",   "code": "NGN", "vat": 7.5},
    "USD": {"name": "US Dollar",              "symbol": "$",   "code": "USD", "vat": 0.0},
    "GBP": {"name": "British Pound",          "symbol": "£",   "code": "GBP", "vat": 20.0},
    "EUR": {"name": "Euro",                   "symbol": "€",   "code": "EUR", "vat": 21.0},  # EU avg ~21%; varies by country (19% DE, 20% FR, 22% IT, 27% HU)
    "GHS": {"name": "Ghanaian Cedi",          "symbol": "₵",   "code": "GHS", "vat": 20.0},  # increased from 15% → 20% Jan 2026
    "KES": {"name": "Kenyan Shilling",        "symbol": "KSh", "code": "KES", "vat": 16.0},
    "ZAR": {"name": "South African Rand",     "symbol": "R",   "code": "ZAR", "vat": 16.0},  # increased from 15% → 15.5% May 2025; → 16% Apr 2026
    "EGP": {"name": "Egyptian Pound",         "symbol": "E£",  "code": "EGP", "vat": 14.0},
    "XOF": {"name": "West African CFA Franc", "symbol": "CFA", "code": "XOF", "vat": 18.0},
    "INR": {"name": "Indian Rupee",           "symbol": "₹",   "code": "INR", "vat": 18.0},
}

# ── Config Cache ──────────────────────────────────────────────────────────────

_config_cache: Optional[Dict[str, Any]] = None

def load_config() -> Dict[str, Any]:
    """
    Load configuration from JSON file.

    Returns a dictionary with currency, VAT settings, and other config options.
    Creates default config if file doesn't exist.

    Returns:
        Dict containing configuration values.
    """
    global _config_cache
    if _config_cache is None:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    _config_cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                # Corrupted file, use defaults
                _config_cache = _create_default_config()
        else:
            _config_cache = _create_default_config()
    return _config_cache.copy()

def _create_default_config() -> Dict[str, Any]:
    """Create default configuration dictionary."""
    return {
        "currency": DEFAULT_CURRENCY,
        "vat_enabled": DEFAULT_VAT_ENABLED,
        "vat_rate": DEFAULT_VAT_RATE
    }

def save_config(config: Dict[str, Any]) -> None:
    """
    Save configuration to JSON file.

    Args:
        config: Configuration dictionary to save.
    """
    global _config_cache
    _config_cache = config.copy()
    os.makedirs(SAVE_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except IOError:
        # Handle write errors gracefully
        pass

def get_currency() -> Dict[str, Any]:
    """
    Get current currency configuration.

    Returns:
        Currency dictionary with name, symbol, code, and VAT rate.
    """
    code = load_config().get("currency", DEFAULT_CURRENCY)
    return CURRENCIES.get(code, CURRENCIES[DEFAULT_CURRENCY])

def get_vat_rate() -> float:
    """
    Get active VAT rate.

    Returns the custom rate if set, otherwise the country default for current currency.

    Returns:
        VAT rate as percentage (0.0 to 100.0).
    """
    cfg = load_config()
    if not cfg.get("vat_enabled", DEFAULT_VAT_ENABLED):
        return 0.0
    custom = cfg.get("vat_rate")
    if custom is not None:
        return float(custom)
    return get_currency()["vat"]

def vat_enabled() -> bool:
    """
    Check if VAT is enabled.

    Returns:
        True if VAT calculations are enabled, False otherwise.
    """
    return load_config().get("vat_enabled", DEFAULT_VAT_ENABLED)

# ── VAT Overrides ─────────────────────────────────────────────────────────────

def load_vat_overrides() -> Dict[str, Dict[str, Any]]:
    """
    Load locally saved VAT rate overrides.

    Returns:
        Dict mapping currency codes to override data with rate, note, and updated date.
    """
    if os.path.exists(VAT_RATES_FILE):
        try:
            with open(VAT_RATES_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_vat_overrides(overrides: Dict[str, Dict[str, Any]]) -> None:
    """
    Save VAT rate overrides to file.

    Args:
        overrides: Dict of currency code to override data.
    """
    os.makedirs(SAVE_DIR, exist_ok=True)
    try:
        with open(VAT_RATES_FILE, "w") as f:
            json.dump(overrides, f, indent=2)
    except IOError:
        pass

def apply_vat_overrides() -> None:
    """
    Apply locally saved VAT overrides to the CURRENCIES dictionary.

    This patches the global CURRENCIES dict with verified rates.
    """
    for code, data in load_vat_overrides().items():
        if code in CURRENCIES:
            CURRENCIES[code]["vat"] = data["rate"]

def check_vat_updates() -> None:
    """
    Fetch remote VAT rates and offer to apply updates.

    Downloads JSON from configured URL and prompts user to apply changes.
    Expected remote format: {"rates": {"CODE": {"rate": float, "note": str}}, "updated": str}
    """
    from ui import clr, hr  # Import here to avoid circular imports

    cfg = load_config()
    url = cfg.get("vat_update_url", "").strip()

    if not url:
        print(clr("\n  ⚠  No update URL configured.", "yellow"))
        print(clr("     Go to Settings → Set VAT update source URL first.\n", "dim"))
        return

    print(clr(f"\n  Fetching VAT rates from:\n  {url}\n", "dim"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cost_calc/1.0"})
        with urllib.request.urlopen(req, timeout=VAT_UPDATE_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, ValueError) as e:
        print(clr(f"  ✗  Failed to fetch or parse update data: {e}\n", "yellow"))
        return

    remote_rates = data.get("rates", {})
    updated_on = data.get("updated", "unknown date")

    if not remote_rates:
        print(clr("  ⚠  No rate data found in the response.\n", "yellow"))
        return

    hr()
    print(clr(f"  Source  : {data.get('source', url)}", "dim"))
    print(clr(f"  Updated : {updated_on}", "dim"))
    hr()

    overrides = load_vat_overrides()
    changes: list = []

    for code, entry in remote_rates.items():
        if code not in CURRENCIES:
            continue
        new_rate = float(entry["rate"])
        cur_rate = CURRENCIES[code]["vat"]
        if abs(new_rate - cur_rate) >= 0.01:
            changes.append((code, cur_rate, new_rate, entry.get("note", "")))

    if not changes:
        print(clr("  ✓  All VAT rates are already up to date.\n", "bright_green"))
        return

    print(clr(f"  {len(changes)} change(s) detected:\n", "yellow"))
    for code, old, new, note in changes:
        name = CURRENCIES[code]["name"]
        print(f"  {clr(code, 'cyan')}  {name}")
        print(f"       {clr(f'{old:.1f}%', 'dim')}  →  {clr(f'{new:.1f}%', 'bright_green')}")
        if note:
            print(f"       {clr(note, 'dim')}")
        print()

    confirm = input("  Apply all these updates? (y/n): ").strip().lower()
    if confirm != "y":
        print(clr("  Cancelled — no rates were changed.\n", "dim"))
        return

    for code, _, new_rate, note in changes:
        overrides[code] = {
            "rate": new_rate,
            "note": note,
            "updated": updated_on,
        }
        CURRENCIES[code]["vat"] = new_rate

    save_vat_overrides(overrides)
    print(clr(f"\n  ✓  {len(changes)} VAT rate(s) updated and saved.\n", "bright_green"))

def set_vat_update_url() -> None:
    """
    Allow user to configure the remote VAT rates JSON URL.
    """
    from ui import clr  # Avoid circular import

    cfg = load_config()
    current = cfg.get("vat_update_url", "")
    print()
    if current:
        print(clr(f"  Current URL: {current}", "dim"))
    else:
        print(clr("  No URL set yet.", "dim"))
    print()
    print("  Enter the URL of a trusted JSON file with verified VAT rates.")
    print(clr("  Leave blank to cancel.\n", "dim"))

    new_url = input("  URL: ").strip()
    if not new_url:
        print(clr("  Cancelled.\n", "dim"))
        return

    cfg["vat_update_url"] = new_url
    save_config(cfg)
    print(clr(f"\n  ✓  Update URL saved.\n", "bright_green"))