"""
calculations.py — Core calculation functions for cost_calc.py

Contains all business logic for cost calculations, material quantity calculations,
and specialized calculators for pipes, handrails, and volume conversions.
"""

import math
from typing import Dict, Any, Optional, Tuple, Union

from config import get_vat_rate

# ── Financial totals helper ───────────────────────────────────────────────────

def calc_totals(estimate: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate all cost, profit, VAT, and selling price totals.

    This is the single source of truth for all financial calculations.

    Args:
        estimate: Estimate dictionary with materials, labour, margin, and vat_rate.

    Returns:
        Dict with calculated totals: mat_total, lab_total, cost_total, profit_amt,
        subtotal, vat_amt, sell_price.
    """
    materials = estimate["materials"]
    labour = estimate["labour"]
    margin = estimate["margin"]
    vat_rate = estimate.get("vat_rate", get_vat_rate())

    mat_total = sum(item["qty"] * item["unit_price"] for item in materials)
    lab_total = sum(item["hours"] * item["rate"] for item in labour)
    cost_total = mat_total + lab_total
    profit_amt = cost_total * (margin / 100)
    subtotal = cost_total + profit_amt
    vat_amt = subtotal * (vat_rate / 100)
    sell_price = subtotal + vat_amt

    return {
        "mat_total": mat_total,
        "lab_total": lab_total,
        "cost_total": cost_total,
        "profit_amt": profit_amt,
        "subtotal": subtotal,
        "vat_amt": vat_amt,
        "sell_price": sell_price,
    }

# ── Window pipe calculator ────────────────────────────────────────────────────

def calc_pipes_for_window(num_windows: int, win_height: float, win_width: float,
                         spacing: float, pipe_std_len: float) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Calculate pipe requirements for window grills/burglar bars.

    Args:
        num_windows: Number of windows.
        win_height: Window height in mm.
        win_width: Window width in mm.
        spacing: Distance between pipes in mm.
        pipe_std_len: Standard pipe length in mm.

    Returns:
        Tuple of (material_dict_or_None, calculation_dict).
        material_dict contains name, qty, unit_price if user wants to add as material.
        calculation_dict contains all calculation details.
    """
    # Horizontal bars run across the width, spaced along the height
    h_bars = math.floor(win_height / spacing) + 1
    # Vertical bars run along the height, spaced across the width
    v_bars = math.floor(win_width / spacing) + 1

    total_h_len = h_bars * win_width
    total_v_len = v_bars * win_height
    pipe_len_each = total_h_len + total_v_len  # Total pipe length per window (mm)
    pipes_per_win = math.ceil(pipe_len_each / pipe_std_len)
    total_pipes = pipes_per_win * num_windows

    calc = {
        "num_windows": num_windows,
        "win_height": win_height,
        "win_width": win_width,
        "spacing": spacing,
        "pipe_std_len": pipe_std_len,
        "h_bars": h_bars,
        "v_bars": v_bars,
        "pipe_len_each": pipe_len_each,
        "pipes_per_win": pipes_per_win,
        "total_pipes": total_pipes,
    }

    return None, calc  # Material dict returned by caller if needed

# ── Stair handrail calculator ─────────────────────────────────────────────────

def calc_handrail_for_stairs(num_steps: int, tread_depth: float, riser_height: float,
                           num_sides: int, rail_height: float, rail_width: float,
                           pipe_std_len: float, baluster_sp: float) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Calculate stair handrail pipe requirements.

    Args:
        num_steps: Number of steps.
        tread_depth: Horizontal tread depth in mm.
        riser_height: Vertical riser height in mm.
        num_sides: Number of handrail sides (1 or 2).
        rail_height: Handrail height from floor in mm.
        rail_width: Stair width between handrail sides in mm.
        pipe_std_len: Standard pipe length in mm.
        baluster_sp: Baluster spacing in mm.

    Returns:
        Tuple of (material_dict_or_None, calculation_dict).
    """
    horiz_run = num_steps * tread_depth
    total_rise = num_steps * riser_height
    slant_len = math.sqrt(horiz_run ** 2 + total_rise ** 2)
    angle_deg = math.degrees(math.atan2(total_rise, horiz_run))

    # Top rail pipes (along the slant)
    pipes_per_side = math.ceil(slant_len / pipe_std_len)
    total_rail_pipes = pipes_per_side * num_sides

    # Baluster posts (vertical, each = rail_height mm)
    balusters_per_side = math.floor(slant_len / baluster_sp) + 1
    total_balusters = balusters_per_side * num_sides
    baluster_pipe_total = total_balusters * rail_height
    baluster_pipes = math.ceil(baluster_pipe_total / pipe_std_len)

    # Cross pieces — 1 at top + 1 at bottom, each = rail_width mm
    cross_pipes = math.ceil((2 * rail_width) / pipe_std_len)

    # Grand total
    grand_total_pipes = total_rail_pipes + baluster_pipes + cross_pipes

    calc = {
        "num_steps": num_steps,
        "tread_depth": tread_depth,
        "riser_height": riser_height,
        "num_sides": num_sides,
        "rail_height": rail_height,
        "rail_width": rail_width,
        "pipe_std_len": pipe_std_len,
        "baluster_sp": baluster_sp,
        "horiz_run": horiz_run,
        "total_rise": total_rise,
        "slant_len": slant_len,
        "angle_deg": angle_deg,
        "pipes_per_side": pipes_per_side,
        "total_rail_pipes": total_rail_pipes,
        "balusters_per_side": balusters_per_side,
        "total_balusters": total_balusters,
        "baluster_pipes": baluster_pipes,
        "cross_pipes": cross_pipes,
        "total_pipes": grand_total_pipes,
    }

    return None, calc

# ── Volume converters ─────────────────────────────────────────────────────────

def conv_area_to_liters(area: float, thickness: float, thickness_unit: str, wastage_pct: float) -> Dict[str, float]:
    """
    Calculate liters needed from area × thickness.

    Args:
        area: Area in square meters.
        thickness: Thickness value.
        thickness_unit: Unit of thickness ('mm', 'cm', 'm').
        wastage_pct: Wastage percentage.

    Returns:
        Dict with volume_m3, volume_L, wastage_L, total_L.
    """
    if thickness_unit == "mm":
        thickness_m = thickness / 1000
    elif thickness_unit == "cm":
        thickness_m = thickness / 100
    else:  # meters
        thickness_m = thickness

    volume_m3 = area * thickness_m
    volume_L = volume_m3 * 1000
    wastage_L = volume_L * wastage_pct / 100
    total_L = volume_L + wastage_L

    return {
        "volume_m3": volume_m3,
        "volume_L": volume_L,
        "wastage_L": wastage_L,
        "total_L": total_L,
    }

def conv_dimensions_to_liters(length: float, width: float, height: float) -> Dict[str, float]:
    """
    Calculate volume in liters from L × W × H dimensions.

    Args:
        length: Length in meters.
        width: Width in meters.
        height: Height/depth in meters.

    Returns:
        Dict with volume_m3, volume_L.
    """
    volume_m3 = length * width * height
    volume_L = volume_m3 * 1000

    return {
        "volume_m3": volume_m3,
        "volume_L": volume_L,
    }

def conv_m3_to_liters(volume_m3: float) -> float:
    """
    Convert cubic meters to liters.

    Args:
        volume_m3: Volume in cubic meters.

    Returns:
        Volume in liters.
    """
    return volume_m3 * 1000

def conv_liters_to_m3(volume_L: float) -> float:
    """
    Convert liters to cubic meters.

    Args:
        volume_L: Volume in liters.

    Returns:
        Volume in cubic meters.
    """
    return volume_L / 1000

# ── Material quantity calculations ────────────────────────────────────────────

def calc_area_quantity(total_area: float, mat_length: float, mat_width: float, wastage_pct: float) -> int:
    """
    Calculate quantity needed for area coverage.

    Args:
        total_area: Total area to cover in mm².
        mat_length: Material length per piece in mm.
        mat_width: Material width per piece in mm.
        wastage_pct: Wastage percentage.

    Returns:
        Total quantity to order.
    """
    mat_area = mat_length * mat_width
    base_qty = math.ceil(total_area / mat_area)
    wastage_qty = math.ceil(base_qty * wastage_pct / 100)
    return base_qty + wastage_qty

def calc_linear_quantity(total_length: float, mat_length: float, wastage_pct: float) -> int:
    """
    Calculate quantity needed for linear coverage.

    Args:
        total_length: Total length to cover in mm.
        mat_length: Material length per piece in mm.
        wastage_pct: Wastage percentage.

    Returns:
        Total quantity to order.
    """
    base_qty = math.ceil(total_length / mat_length)
    wastage_qty = math.ceil(base_qty * wastage_pct / 100)
    return base_qty + wastage_qty