"""
ui.py — User interface functions for cost_calc.py

Contains all terminal display, input handling, and menu navigation logic.
"""

import math
import os
import subprocess
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional

from constants import TABLE_WIDTH, HR_CHAR, HR_WIDTH, SAVE_DIR
from config import load_config, save_config, get_currency, get_vat_rate, vat_enabled, CURRENCIES
from calculations import calc_totals, calc_area_quantity, calc_linear_quantity
from persistence import save_estimate, list_saved, load_estimate, delete_estimate, duplicate_estimate, get_estimate_summary

# ── Navigation signals ────────────────────────────────────────────────────────

class QuitApp(Exception):
    """Raised anywhere to exit the program immediately."""

class BackToMain(Exception):
    """Raised inside a sub-flow to return to the main menu."""

# ── Colors ────────────────────────────────────────────────────────────────────

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_CYAN = "\033[96m"
    WHITE = "\033[97m"

def clr(text: str, *codes: str) -> str:
    """
    Apply ANSI color codes to text.

    Args:
        text: Text to color.
        *codes: Color code names (e.g., 'bold', 'red').

    Returns:
        Colored text string.
    """
    code_map = {
        "reset": C.RESET,
        "bold": C.BOLD,
        "dim": C.DIM,
        "green": C.GREEN,
        "yellow": C.YELLOW,
        "cyan": C.CYAN,
        "bright_green": C.BRIGHT_GREEN,
        "bright_cyan": C.BRIGHT_CYAN,
        "white": C.WHITE,
    }
    ansi_codes = "".join(code_map.get(code, "") for code in codes)
    return ansi_codes + str(text) + C.RESET

# ── Display helpers ───────────────────────────────────────────────────────────

def hr(char: str = HR_CHAR, width: int = HR_WIDTH, color: str = "dim") -> None:
    """
    Print a horizontal rule.

    Args:
        char: Character to repeat.
        width: Width of the rule.
        color: Color name.
    """
    print(clr("  " + char * width, color))

def fmt_currency(amount: float) -> str:
    """
    Format amount as currency string.

    Args:
        amount: Numeric amount.

    Returns:
        Formatted currency string.
    """
    sym = get_currency()["symbol"]
    return f"{sym}{amount:,.2f}"

def _clr_col(text: str, width: int, align: str, *codes: str) -> str:
    """
    Pad text to width then apply color (avoids ANSI inflating width).

    Args:
        text: Text to format.
        width: Field width.
        align: Alignment ('<' left, '>' right, '^' center).
        *codes: Color codes.

    Returns:
        Formatted colored string.
    """
    padded = f"{str(text):{align}{width}}"
    return "".join(codes) + padded + C.RESET

def header(title: str) -> None:
    """
    Print a section header with borders.

    Args:
        title: Header title.
    """
    print()
    hr("═", color="cyan")
    print(clr(f"  {title}", "bold", "bright_cyan"))
    hr("═", color="cyan")

# ── Input helpers ─────────────────────────────────────────────────────────────

def ask_text(prompt: str) -> str:
    """
    Get text input from user with quit/back handling.

    Args:
        prompt: Input prompt.

    Returns:
        User input string.

    Raises:
        QuitApp: If user types 'q'.
        BackToMain: If user types 'b'.
    """
    while True:
        value = input(f"  {prompt}: ").strip()
        if value.lower() == 'q':
            raise QuitApp
        if value.lower() == 'b':
            raise BackToMain
        if value:
            return value
        print(clr("  ⚠  This field cannot be empty.", "yellow"))

def ask_number(prompt: str, allow_zero: bool = False) -> float:
    """
    Get numeric input from user with validation.

    Args:
        prompt: Input prompt.
        allow_zero: Whether zero is acceptable.

    Returns:
        Numeric value.

    Raises:
        QuitApp: If user types 'q'.
        BackToMain: If user types 'b'.
    """
    while True:
        raw = input(f"  {prompt}: ").strip()
        if raw.lower() == 'q':
            raise QuitApp
        if raw.lower() == 'b':
            raise BackToMain
        try:
            value = float(raw)
            if value < 0:
                print(clr("  ⚠  Please enter a positive number.", "yellow"))
            elif value == 0 and not allow_zero:
                print(clr("  ⚠  Value must be greater than zero.", "yellow"))
            else:
                return value
        except ValueError:
            print(clr("  ⚠  Please enter a valid number (e.g. 12 or 3.50).", "yellow"))

# ── Core UI workflows ─────────────────────────────────────────────────────────

def collect_materials() -> List[Dict[str, Any]]:
    """
    Interactive material collection workflow.

    Returns:
        List of material dictionaries.
    """
    sym = get_currency()["symbol"]
    header("MATERIALS")
    print(clr("  All area / length measurements are in millimetres (mm).\n", "dim"))
    print("  Enter each material. Press Enter with no name when done.")
    print(clr("  Type 'u' to undo the last item added, 'b' to go back.\n", "dim"))

    items = []
    while True:
        name = input("  Material name (or Enter to finish): ").strip()
        if name.lower() == 'b':
            raise BackToMain
        if not name:
            if not items:
                print("  (No materials added.)")
            break

        if name.lower() == 'u':
            if items:
                removed = items.pop()
                print(clr(f"  ↩  Removed '{removed['name']}'.\n", "dim"))
            else:
                print(clr("  ⚠  Nothing to undo.\n", "yellow"))
            continue

        print(clr(f"\n  How do you want to enter the quantity for '{name}'?", "dim"))
        print(f"  {clr('1.', 'cyan')}  Area coverage   {clr('(L × W in mm — tiles, flooring, roofing)', 'dim')}")
        print(f"  {clr('2.', 'cyan')}  Linear length   {clr('(mm — pipes, rods, skirting, planks)', 'dim')}")
        print(f"  {clr('3.', 'cyan')}  Enter quantity directly")
        print(f"  {clr('0.', 'dim')}  Cancel (skip this material)")
        print(f"  {clr('b.', 'dim')}  Go back")
        mode = input("  Choose (0–3, b): ").strip()

        if mode.lower() == 'b':
            raise BackToMain

        if mode == "0":
            print(clr(f"  Skipped '{name}'.\n", "dim"))
            continue

        elif mode == "1":
            # Area mode
            print()
            print(clr("  Total area to cover:", "dim"))
            area_length = ask_number("  Area length (mm)")
            area_width = ask_number("  Area width  (mm)")
            total_area = area_length * area_width

            print(clr("\n  Material size (one piece / tile / sheet):", "dim"))
            mat_length = ask_number("  Material length (mm)")
            mat_width = ask_number("  Material width  (mm)")
            mat_area = mat_length * mat_width

            wastage = ask_number("  Wastage % (0 for none)", allow_zero=True)

            qty = calc_area_quantity(total_area, mat_length, mat_width, wastage)

            print()
            hr()
            print(f"  Area to cover     {area_length:.0f} mm x {area_width:.0f} mm = {total_area:,.0f} mm²")
            print(f"  Material size     {mat_length:.0f} mm x {mat_width:.0f} mm = {mat_area:,.0f} mm²")
            print(f"  Base quantity     {qty - math.ceil((qty - math.ceil(total_area / mat_area)))}")
            if wastage > 0:
                base_qty = math.ceil(total_area / mat_area)
                wastage_qty = math.ceil(base_qty * wastage / 100)
                print(f"  Wastage ({wastage:.0f}%)    +{wastage_qty}")
            hr()
            print(clr(f"  Quantity to order  {qty} units", "bright_green"))
            hr()
            print()

        elif mode == "2":
            # Linear mode
            print()
            total_length = ask_number("  Total length to cover (mm)")
            mat_length = ask_number("  Length of one unit / piece (mm)")
            wastage = ask_number("  Wastage % (0 for none)", allow_zero=True)

            qty = calc_linear_quantity(total_length, mat_length, wastage)

            print()
            hr()
            print(f"  Total length      {total_length:>10,.0f} mm")
            print(f"  Unit length       {mat_length:>10,.0f} mm")
            base_qty = math.ceil(total_length / mat_length)
            wastage_qty = math.ceil(base_qty * wastage / 100)
            print(f"  Base quantity     {base_qty:>10}")
            if wastage > 0:
                print(f"  Wastage ({wastage:.0f}%)    +{wastage_qty:>9}")
            hr()
            print(clr(f"  Quantity to order  {qty:>9} units", "bright_green"))
            hr()
            print()

        else:
            qty = ask_number("  Quantity")

        price = ask_number(f"  Unit price ({sym})")
        total = qty * price

        items.append({"name": name, "qty": qty, "unit_price": price})
        print(clr(f"  ✓  {name} — {qty} × {fmt_currency(price)} = {fmt_currency(total)}", "bright_green") + "\n")

    return items

def collect_labour() -> List[Dict[str, Any]]:
    """
    Interactive labour collection workflow.

    Returns:
        List of labour dictionaries.
    """
    sym = get_currency()["symbol"]
    header("LABOUR")
    print("  Enter each labour item. Press Enter with no name when done.")
    print(clr("  Type 'u' to undo the last item added, 'b' to go back.\n", "dim"))

    items = []
    while True:
        name = input("  Labour description (or Enter to finish): ").strip()
        if name.lower() == 'b':
            raise BackToMain
        if not name:
            if not items:
                print("  (No labour added.)")
            break

        if name.lower() == 'u':
            if items:
                removed = items.pop()
                print(clr(f"  ↩  Removed '{removed['name']}'.\n", "dim"))
            else:
                print(clr("  ⚠  Nothing to undo.\n", "yellow"))
            continue

        hours = ask_number("  Hours")
        rate = ask_number(f"  Rate per hour ({sym})")
        total = hours * rate

        items.append({"name": name, "hours": hours, "rate": rate})
        print(clr(f"  ✓  {name} — {hours}h × {fmt_currency(rate)}/h = {fmt_currency(total)}", "bright_green") + "\n")

    return items

def new_estimate() -> None:
    """
    Create a new estimate with step-by-step input and back navigation.
    """
    project = None
    materials = []
    labour = []
    margin = None
    step = 0

    while True:
        try:
            if step == 0:
                header("NEW ESTIMATE — PROJECT NAME")
                print(clr("  Type 'b' to cancel and return to main menu.\n", "dim"))
                project = ask_text("Project name")
                step = 1
            elif step == 1:
                materials = collect_materials()
                step = 2
            elif step == 2:
                labour = collect_labour()
                step = 3
            elif step == 3:
                header("NEW ESTIMATE — PROFIT MARGIN")
                print(clr("  Type 'b' to go back to labour input.\n", "dim"))
                margin = ask_number("Profit margin (%)", allow_zero=True)
                step = 4
            elif step == 4:
                estimate = {
                    "project": project,
                    "materials": materials,
                    "labour": labour,
                    "margin": margin,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "currency": get_currency()["code"],
                    "vat_rate": get_vat_rate(),
                }
                show_summary(estimate)
                post_estimate_menu(estimate)
                return
        except BackToMain:
            if step > 0:
                step -= 1
            else:
                return

def show_summary(estimate: Dict[str, Any]) -> None:
    """
    Display estimate summary with all calculations.

    Args:
        estimate: Estimate dictionary.
    """
    project = estimate["project"]
    materials = estimate["materials"]
    labour = estimate["labour"]
    margin = estimate["margin"]
    date = estimate.get("date", "N/A")
    currency = estimate.get("currency", get_currency()["code"])
    vat_rate = estimate.get("vat_rate", get_vat_rate())

    t = calc_totals(estimate)
    vat_label = f"VAT ({vat_rate:.1f}%)" if vat_rate > 0 else "VAT"

    header(f"ESTIMATE SUMMARY — {project}")
    vat_status = f"VAT {vat_rate:.1f}%" if vat_rate > 0 else "VAT off"
    print(clr(f"  Date: {date}  |  Currency: {currency}  |  {vat_status}", "dim"))

    # Materials breakdown
    if materials:
        print()
        print(clr("  MATERIALS", "bold", "yellow"))
        hr()
        for item in materials:
            line = item["qty"] * item["unit_price"]
            print(f"  {_clr_col(item['name'][:28], 28, '<', 'white')}  "
                  f"{item['qty']:>6} ×  {fmt_currency(item['unit_price']):>14}  =  "
                  f"{_clr_col(fmt_currency(line), 14, '>', 'bold')}")
        hr()
        print(f"  {'Material Subtotal':<38}  {_clr_col(fmt_currency(t['mat_total']), 14, '>', 'bold', 'white')}")

    # Labour breakdown
    if labour:
        print()
        print(clr("  LABOUR", "bold", "yellow"))
        hr()
        for item in labour:
            line = item["hours"] * item["rate"]
            print(f"  {_clr_col(item['name'][:28], 28, '<', 'white')}  "
                  f"{item['hours']:>5}h ×  {fmt_currency(item['rate']):>14}/h =  "
                  f"{_clr_col(fmt_currency(line), 14, '>', 'bold')}")
        hr()
        print(f"  {'Labour Subtotal':<38}  {_clr_col(fmt_currency(t['lab_total']), 14, '>', 'bold', 'white')}")

    # Totals
    print()
    hr("-")
    print(f"  {'Total Cost':<38}  {_clr_col(fmt_currency(t['cost_total']), 14, '>', 'bold', 'white')}")
    print(f"  {'Profit Margin':<38}  {_clr_col(f'{margin:.1f}%', 14, '>', 'yellow')}")
    print(f"  {'Profit Amount':<38}  {_clr_col(fmt_currency(t['profit_amt']), 14, '>', 'green')}")
    hr("-")
    print(f"  {'Subtotal (before VAT)':<38}  {_clr_col(fmt_currency(t['subtotal']), 14, '>', 'white')}")

    if vat_rate > 0:
        print(f"  {vat_label:<38}  {_clr_col(fmt_currency(t['vat_amt']), 14, '>', 'yellow')}")

    hr("═", color="cyan")
    print(f"  {_clr_col('SELLING PRICE', 38, '<', 'bold', 'bright_green')}  "
          f"{_clr_col(fmt_currency(t['sell_price']), 14, '>', 'bold', 'bright_green')}")
    hr("═", color="cyan")
    print()

# ── Table view ────────────────────────────────────────────────────────────────

def print_estimate_table(estimate: Dict[str, Any]) -> None:
    """
    Print estimate as formatted Unicode table.

    Args:
        estimate: Estimate dictionary.
    """
    project = estimate["project"]
    materials = estimate["materials"]
    labour = estimate["labour"]
    margin = estimate["margin"]
    date = estimate.get("date", "N/A")
    currency = estimate.get("currency", get_currency()["code"])
    vat_rate = estimate.get("vat_rate", get_vat_rate())

    t = calc_totals(estimate)
    mat_total = t["mat_total"]
    lab_total = t["lab_total"]
    cost_total = t["cost_total"]
    profit_amt = t["profit_amt"]
    subtotal = t["subtotal"]
    vat_amt = t["vat_amt"]
    sell_price = t["sell_price"]

    W = TABLE_WIDTH

    def trow(*cols, widths, sep="│"):
        parts = [f" {str(c):<{w}} " for c, w in zip(cols, widths)]
        return "│" + sep.join(parts) + "│"

    def top(widths=None):
        if widths is None:
            return "┌" + "─" * W + "┐"
        return "┌" + "┬".join("─" * (w + 2) for w in widths) + "┐"

    def mid(widths, open_=False):
        l, m, r = ("├", "┼", "┤") if not open_ else ("├", "┬", "┤")
        return l + m.join("─" * (w + 2) for w in widths) + r

    def bottom(widths):
        return "└" + "┴".join("─" * (w + 2) for w in widths) + "┘"

    print()
    print(clr(f"ESTIMATE TABLE — {project}", "bold", "bright_cyan"))
    print(clr(f"Date: {date}  |  Currency: {currency}  |  VAT: {vat_rate:.1f}%", "dim"))
    print()

    # Materials table
    if materials:
        print(top())
        print(trow("MATERIALS", widths=[W]))
        print(mid([W], open_=True))
        for item in materials:
            line = item["qty"] * item["unit_price"]
            qty = int(item["qty"]) if item["qty"] == int(item["qty"]) else item["qty"]
            print(trow(f"{item['name'][:40]}", f"{qty} × {fmt_currency(item['unit_price'])} = {fmt_currency(line)}", widths=[40, W-42]))
        print(mid([40, W-42]))
        print(trow("Material Subtotal", fmt_currency(mat_total), widths=[40, W-42]))
        print(bottom([40, W-42]))
        print()

    # Labour table
    if labour:
        print(top())
        print(trow("LABOUR", widths=[W]))
        print(mid([W], open_=True))
        for item in labour:
            line = item["hours"] * item["rate"]
            print(trow(f"{item['name'][:40]}", f"{item['hours']}h × {fmt_currency(item['rate'])}/h = {fmt_currency(line)}", widths=[40, W-42]))
        print(mid([40, W-42]))
        print(trow("Labour Subtotal", fmt_currency(lab_total), widths=[40, W-42]))
        print(bottom([40, W-42]))
        print()

    # Totals table
    print(top([30, W-32]))
    print(trow("TOTALS", "", widths=[30, W-32]))
    print(mid([30, W-32], open_=True))
    print(trow("Total Cost", fmt_currency(cost_total), widths=[30, W-32]))
    print(trow(f"Profit Margin ({margin:.1f}%)", fmt_currency(profit_amt), widths=[30, W-32]))
    print(trow("Subtotal (before VAT)", fmt_currency(subtotal), widths=[30, W-32]))
    if vat_rate > 0:
        print(trow(f"VAT ({vat_rate:.1f}%)", fmt_currency(vat_amt), widths=[30, W-32]))
    print(mid([30, W-32]))
    print(trow("SELLING PRICE", fmt_currency(sell_price), widths=[30, W-32]))
    print(bottom([30, W-32]))
    print()

# ── PDF Export ────────────────────────────────────────────────────────────────

def export_pdf(estimate: Dict[str, Any]) -> None:
    """
    Export estimate to PDF using fpdf2.

    Args:
        estimate: Estimate dictionary.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        print(clr("  ✗  PDF export requires 'fpdf2' package. Install with: pip install fpdf2", "yellow"))
        return

    project = estimate["project"]
    materials = estimate["materials"]
    labour = estimate["labour"]
    margin = estimate["margin"]
    date = estimate.get("date", "N/A")
    currency = estimate.get("currency", get_currency()["code"])
    vat_rate = estimate.get("vat_rate", get_vat_rate())

    t = calc_totals(estimate)
    mat_total = t["mat_total"]
    lab_total = t["lab_total"]
    cost_total = t["cost_total"]
    profit_amt = t["profit_amt"]
    subtotal = t["subtotal"]
    vat_amt = t["vat_amt"]
    sell_price = t["sell_price"]
    sym = get_currency()["symbol"]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15, 15)
    pw = pdf.w - 30  # usable page width

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_fill_color(30, 30, 30)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(pw, 10, "COST ESTIMATE", align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(pw, 6, f"Project: {project}    Date: {date}    Currency: {currency}    VAT: {vat_rate:.1f}%",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    def section_header(title):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(50, 50, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(pw, 7, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    def table_header(*cols, widths):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(220, 220, 220)
        for col, w in zip(cols, widths):
            pdf.cell(w, 6, col, border=1, fill=True, align="C")
        pdf.ln()

    def table_row(*cols, widths, aligns=None):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_fill_color(255, 255, 255)
        if aligns is None:
            aligns = ["L"] * len(cols)
        for col, w, a in zip(cols, widths, aligns):
            pdf.cell(w, 6, str(col), border=1, align=a)
        pdf.ln()

    def subtotal_row(label, value, widths):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(sum(widths[:-1]), 6, label, border=1, fill=True, align="R")
        pdf.cell(widths[-1], 6, value, border=1, fill=True, align="R")
        pdf.ln()

    # Materials
    if materials:
        section_header("MATERIALS")
        pdf.ln(1)
        cw = [pw * 0.40, pw * 0.12, pw * 0.24, pw * 0.24]
        table_header("Item", "Qty", "Unit Price", "Total", widths=cw)
        for item in materials:
            line = item["qty"] * item["unit_price"]
            qty = int(item["qty"]) if item["qty"] == int(item["qty"]) else item["qty"]
            table_row(
                item["name"][:40], qty,
                f"{sym}{item['unit_price']:,.2f}", f"{sym}{line:,.2f}",
                widths=cw, aligns=["L", "C", "R", "R"]
            )
        subtotal_row("Material Subtotal", f"{sym}{mat_total:,.2f}", cw)
        pdf.ln(4)

    # Labour
    if labour:
        section_header("LABOUR")
        pdf.ln(1)
        lw = [pw * 0.40, pw * 0.12, pw * 0.24, pw * 0.24]
        table_header("Description", "Hours", "Rate/hr", "Total", widths=lw)
        for item in labour:
            line = item["hours"] * item["rate"]
            table_row(
                item["name"][:40], item["hours"],
                f"{sym}{item['rate']:,.2f}", f"{sym}{line:,.2f}",
                widths=lw, aligns=["L", "C", "R", "R"]
            )
        subtotal_row("Labour Subtotal", f"{sym}{lab_total:,.2f}", lw)
        pdf.ln(4)

    # Totals
    section_header("TOTALS")
    pdf.ln(1)
    tw = [pw * 0.76, pw * 0.24]
    table_row("Total Cost", f"{sym}{cost_total:,.2f}", widths=tw, aligns=["L", "R"])
    table_row(f"Profit Margin ({margin:.1f}%)", f"{sym}{profit_amt:,.2f}", widths=tw, aligns=["L", "R"])
    table_row("Subtotal (before VAT)", f"{sym}{subtotal:,.2f}", widths=tw, aligns=["L", "R"])
    if vat_rate > 0:
        table_row(f"VAT ({vat_rate:.1f}%)", f"{sym}{vat_amt:,.2f}", widths=tw, aligns=["L", "R"])

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(30, 30, 30)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(tw[0], 8, "SELLING PRICE", border=1, fill=True, align="L")
    pdf.cell(tw[1], 8, f"{sym}{sell_price:,.2f}", border=1, fill=True, align="R")
    pdf.ln()

    # Save file
    downloads = os.path.expanduser("~/Downloads")
    out_dir = downloads if os.path.isdir(downloads) else SAVE_DIR
    filename = project.lower().replace(" ", "_") + "_estimate.pdf"
    path = os.path.join(out_dir, filename)
    pdf.output(path)
    print(clr(f"\n  ✓  PDF saved → {path}\n", "bright_green"))

    # Offer to open
    open_it = input("  Open PDF now? (y/n): ").strip().lower()
    if open_it == "y":
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ── Post-estimate actions ─────────────────────────────────────────────────────

def post_estimate_menu(estimate: Dict[str, Any]) -> None:
    """
    Menu for actions after estimate display.

    Args:
        estimate: Estimate dictionary.
    """
    while True:
        print()
        print(f"  {clr('1.', 'cyan')}  View as formatted table")
        print(f"  {clr('2.', 'cyan')}  Export as PDF")
        print(f"  {clr('0.', 'dim')}  Back to main menu")
        print(f"  {clr('b.', 'dim')}  Back to main menu")
        print(f"  {clr('q.', 'dim')}  Quit")
        print()

        choice = input("  Choose (0–2, b): ").strip().lower()

        if choice == "1":
            print_estimate_table(estimate)
        elif choice == "2":
            export_pdf(estimate)
        elif choice in ("0", "b"):
            break
        elif choice == "q":
            raise QuitApp
        else:
            print(clr("  ⚠  Please enter 0–2, b or q.", "yellow"))

# ── Settings ──────────────────────────────────────────────────────────────────

def settings_menu() -> None:
    """
    Settings configuration menu.
    """
    while True:
        cfg = load_config()
        cur = get_currency()
        vat_on = vat_enabled()
        vat_rate = get_vat_rate()
        custom = cfg.get("vat_rate")

        header("SETTINGS")
        print(f"  Currency  :  {clr(cur['name'] + ' (' + cur['symbol'] + ')', 'bright_green')}")
        vat_display = clr(f"{vat_rate:.1f}%", "bright_green") if vat_on else clr("off", "dim")
        custom_note = clr(" (custom)", "dim") if custom is not None else clr(f" (country default for {cur['code']})", "dim")
        print(f"  VAT       :  {vat_display}{custom_note if vat_on else ''}")
        print()
        print(f"  {clr('1.', 'cyan')}  Change currency")
        print(f"  {clr('2.', 'cyan')}  Toggle VAT on / off")
        print(f"  {clr('3.', 'cyan')}  Set custom VAT rate")
        print(f"  {clr('4.', 'cyan')}  Reset VAT to country default")
        print(f"  {clr('5.', 'cyan')}  Check for VAT rate updates  {clr('(fetch from verified source)', 'dim')}")
        print(f"  {clr('6.', 'cyan')}  Set VAT update source URL")
        print(f"  {clr('0.', 'dim')}  Back")
        print(f"  {clr('b.', 'dim')}  Back")
        print(f"  {clr('q.', 'dim')}  Quit")
        print()

        choice = input("  Choose: ").strip().lower()

        if choice == "1":
            change_currency()
        elif choice == "2":
            cfg["vat_enabled"] = not vat_on
            save_config(cfg)
            state = clr("ON", "bright_green") if cfg["vat_enabled"] else clr("OFF", "dim")
            print(clr(f"\n  ✓  VAT turned {state.strip()}\n", "bright_green"))
        elif choice == "3":
            print()
            new_rate = ask_number("  Enter VAT rate (%)", allow_zero=True)
            cfg["vat_rate"] = new_rate
            cfg["vat_enabled"] = True
            save_config(cfg)
            print(clr(f"\n  ✓  VAT rate set to {new_rate:.1f}%\n", "bright_green"))
        elif choice == "4":
            cfg.pop("vat_rate", None)
            save_config(cfg)
            default = get_currency()["vat"]
            print(clr(f"\n  ✓  VAT reset to country default ({default:.1f}%)\n", "bright_green"))
        elif choice == "5":
            from config import check_vat_updates
            check_vat_updates()
        elif choice == "6":
            from config import set_vat_update_url
            set_vat_update_url()
        elif choice in ("0", "b"):
            break
        elif choice == "q":
            raise QuitApp
        else:
            print(clr("  ⚠  Please enter 0–6, b or q.", "yellow"))

def change_currency() -> None:
    """
    Currency selection menu.
    """
    cfg = load_config()
    cur = get_currency()

    print()
    print(clr("  SELECT CURRENCY", "bold", "yellow"))
    hr()
    for i, c in enumerate(CURRENCIES.values(), 1):
        marker = clr(" ◀ active", "bright_green") if c["code"] == cur["code"] else ""
        vat_note = clr(f"  VAT {c['vat']}%", "dim")
        print(f"  {clr(i, 'cyan')}.  {c['symbol']:<5}  {c['code']:<5}  {c['name']:<26}{vat_note}{marker}")
    hr()
    print(f"  {clr('0.', 'dim')}  Cancel")
    print(f"  {clr('b.', 'dim')}  Cancel")
    print()

    raw = input("  Choose currency (0, b to cancel): ").strip()
    if raw.lower() == 'b' or (raw.isdigit() and int(raw) == 0):
        return
    idx = int(raw)
    if 1 <= idx <= len(CURRENCIES):
        chosen = list(CURRENCIES.values())[idx - 1]
        cfg["currency"] = chosen["code"]
        cfg.pop("vat_rate", None)  # reset custom VAT when currency changes
        save_config(cfg)
        print(clr(f"\n  ✓  Currency set to {chosen['name']} ({chosen['symbol']})  |  VAT default: {chosen['vat']}%\n", "bright_green"))
    else:
        print(clr("  ⚠  Invalid choice.", "yellow"))

# ── Persistence UI ────────────────────────────────────────────────────────────

def show_saved_list() -> List[str]:
    """
    Display list of saved estimates.

    Returns:
        List of filenames.
    """
    files = list_saved()
    if not files:
        print(clr("\n  No saved estimates yet.\n", "dim"))
        return []

    print()
    print(clr("  SAVED ESTIMATES", "bold", "yellow"))
    hr()
    for idx, filename in enumerate(files, 1):
        summary = get_estimate_summary(filename)
        if summary:
            print(f"  {clr(idx, 'cyan')}.  {summary['project']:<25}  {clr(summary['date'], 'dim'):<23}  "
                  f"{clr(summary['currency'], 'dim'):<5}  Sell: {clr(fmt_currency(summary['sell_price']), 'bright_green')}")
        else:
            print(f"  {clr(idx, 'cyan')}.  {filename}  {clr('(error loading)', 'yellow')}")
    print()
    return files

def load_estimate() -> None:
    """
    Load and display a saved estimate.
    """
    files = show_saved_list()
    if not files:
        return

    raw = input(f"  Load which estimate? (1–{len(files)}, 0 to cancel): ").strip()
    if not raw.isdigit() or raw == "0":
        return
    choice = int(raw)
    if not (1 <= choice <= len(files)):
        print(clr(f"  ⚠  Enter a number between 1 and {len(files)}, or 0 to cancel.", "yellow"))
        return

    estimate = load_estimate(files[choice - 1])
    if estimate:
        show_summary(estimate)
        post_estimate_menu(estimate)
    else:
        print(clr("  ✗  Failed to load estimate.", "yellow"))

def edit_estimate() -> None:
    """
    Edit a saved estimate.
    """
    files = show_saved_list()
    if not files:
        return
    raw = input(f"  Edit which estimate? (1–{len(files)}, 0 to cancel): ").strip()
    if not raw.isdigit() or raw == "0":
        return
    choice = int(raw)
    if not (1 <= choice <= len(files)):
        print(clr(f"  ⚠  Enter a number between 1 and {len(files)}, or 0 to cancel.", "yellow"))
        return

    estimate = load_estimate(files[choice - 1])
    if not estimate:
        print(clr("  ✗  Failed to load estimate.", "yellow"))
        return

    sym = get_currency()["symbol"]

    while True:
        header(f"EDIT — {estimate['project']}")
        t = calc_totals(estimate)
        print(clr(f"  Materials: {len(estimate['materials'])}  |  Labour: {len(estimate['labour'])}  |  "
                  f"Margin: {estimate['margin']:.1f}%  |  Sell: {fmt_currency(t['sell_price'])}", "dim"))
        print()
        print(f"  {clr('1.', 'cyan')}  Add material")
        print(f"  {clr('2.', 'cyan')}  Remove material")
        print(f"  {clr('3.', 'cyan')}  Edit material price")
        print(f"  {clr('4.', 'cyan')}  Add labour item")
        print(f"  {clr('5.', 'cyan')}  Remove labour item")
        print(f"  {clr('6.', 'cyan')}  Edit labour rate")
        print(f"  {clr('7.', 'cyan')}  Change profit margin")
        print(f"  {clr('8.', 'cyan')}  Preview summary")
        print(f"  {clr('9.', 'cyan')}  Save & exit")
        print(f"  {clr('0.', 'dim')}  Discard & exit")
        print()
        action = input("  Choose (0–9): ").strip()

        if action == "1":
            # Add material
            name = input("  Material name: ").strip()
            if not name:
                continue
            print(f"  {clr('1.', 'cyan')}  Area coverage (mm)")
            print(f"  {clr('2.', 'cyan')}  Linear length (mm)")
            print(f"  {clr('3.', 'cyan')}  Enter quantity directly")
            mode = input("  Choose (1–3): ").strip()
            if mode == "1":
                al = ask_number("  Area length (mm)")
                aw = ask_number("  Area width  (mm)")
                ml = ask_number("  Material length (mm)")
                mw = ask_number("  Material width  (mm)")
                wp = ask_number("  Wastage %", allow_zero=True)
                bq = math.ceil((al * aw) / (ml * mw))
                qty = bq + math.ceil(bq * wp / 100)
                print(clr(f"  → {qty} units", "bright_green"))
            elif mode == "2":
                tl = ask_number("  Total length (mm)")
                ul = ask_number("  Unit length  (mm)")
                wp = ask_number("  Wastage %", allow_zero=True)
                bq = math.ceil(tl / ul)
                qty = bq + math.ceil(bq * wp / 100)
                print(clr(f"  → {qty} units", "bright_green"))
            else:
                qty = ask_number("  Quantity")
            price = ask_number(f"  Unit price ({sym})")
            estimate["materials"].append({"name": name, "qty": qty, "unit_price": price})
            print(clr(f"  ✓  Added '{name}'.\n", "bright_green"))

        elif action == "2":
            # Remove material
            if not estimate["materials"]:
                print(clr("  ⚠  No materials to remove.\n", "yellow"))
                continue
            for i, m in enumerate(estimate["materials"], 1):
                print(f"  {clr(i, 'cyan')}.  {m['name'][:30]}  {m['qty']} × {sym}{m['unit_price']:,.2f}")
            r = input(f"  Remove which? (1–{len(estimate['materials'])}, 0 to cancel): ").strip()
            if r.isdigit() and 1 <= int(r) <= len(estimate["materials"]):
                removed = estimate["materials"].pop(int(r) - 1)
                print(clr(f"  ✓  Removed '{removed['name']}'.\n", "bright_green"))

        elif action == "3":
            # Edit material price
            if not estimate["materials"]:
                print(clr("  ⚠  No materials.\n", "yellow"))
                continue
            for i, m in enumerate(estimate["materials"], 1):
                print(f"  {clr(i, 'cyan')}.  {m['name'][:30]}  current: {sym}{m['unit_price']:,.2f}")
            r = input(f"  Edit which? (1–{len(estimate['materials'])}, 0 to cancel): ").strip()
            if r.isdigit() and 1 <= int(r) <= len(estimate["materials"]):
                item = estimate["materials"][int(r) - 1]
                new_p = ask_number(f"  New unit price for '{item['name'][:28]}' ({sym})")
                item["unit_price"] = new_p
                print(clr(f"  ✓  Updated.\n", "bright_green"))

        elif action == "4":
            # Add labour
            name = input("  Labour description: ").strip()
            if not name:
                continue
            hours = ask_number("  Hours")
            rate = ask_number(f"  Rate per hour ({sym})")
            estimate["labour"].append({"name": name, "hours": hours, "rate": rate})
            print(clr(f"  ✓  Added '{name}'.\n", "bright_green"))

        elif action == "5":
            # Remove labour
            if not estimate["labour"]:
                print(clr("  ⚠  No labour items to remove.\n", "yellow"))
                continue
            for i, lb in enumerate(estimate["labour"], 1):
                print(f"  {clr(i, 'cyan')}.  {lb['name'][:30]}  {lb['hours']}h × {sym}{lb['rate']:,.2f}/h")
            r = input(f"  Remove which? (1–{len(estimate['labour'])}, 0 to cancel): ").strip()
            if r.isdigit() and 1 <= int(r) <= len(estimate["labour"]):
                removed = estimate["labour"].pop(int(r) - 1)
                print(clr(f"  ✓  Removed '{removed['name']}'.\n", "bright_green"))

        elif action == "6":
            # Edit labour rate
            if not estimate["labour"]:
                print(clr("  ⚠  No labour items.\n", "yellow"))
                continue
            for i, lb in enumerate(estimate["labour"], 1):
                print(f"  {clr(i, 'cyan')}.  {lb['name'][:30]}  current: {sym}{lb['rate']:,.2f}/h")
            r = input(f"  Edit which? (1–{len(estimate['labour'])}, 0 to cancel): ").strip()
            if r.isdigit() and 1 <= int(r) <= len(estimate["labour"]):
                item = estimate["labour"][int(r) - 1]
                new_r = ask_number(f"  New rate for '{item['name'][:28]}' ({sym}/h)")
                item["rate"] = new_r
                print(clr(f"  ✓  Updated.\n", "bright_green"))

        elif action == "7":
            estimate["margin"] = ask_number("  New profit margin (%)", allow_zero=True)
            print(clr(f"  ✓  Margin set to {estimate['margin']:.1f}%.\n", "bright_green"))

        elif action == "8":
            show_summary(estimate)

        elif action == "9":
            estimate["date"] = datetime.now().strftime("%Y-%m-%d")
            if save_estimate(estimate, force=True):
                show_summary(estimate)
                post_estimate_menu(estimate)
            break

        elif action == "0":
            print(clr("  Changes discarded.\n", "dim"))
            break

def delete_estimate() -> None:
    """
    Delete a saved estimate.
    """
    files = show_saved_list()
    if not files:
        return
    raw = input(f"  Delete which estimate? (1–{len(files)}, 0 to cancel): ").strip()
    if not raw.isdigit() or raw == "0":
        return
    choice = int(raw)
    if not (1 <= choice <= len(files)):
        print(clr(f"  ⚠  Enter a number between 1 and {len(files)}, or 0 to cancel.", "yellow"))
        return
    filename = files[choice - 1]
    summary = get_estimate_summary(filename)
    if summary:
        confirm = input(f"  Delete '{summary['project']}'? This cannot be undone. (y/n): ").strip().lower()
    else:
        confirm = input(f"  Delete '{filename}'? This cannot be undone. (y/n): ").strip().lower()
    if confirm == "y":
        if delete_estimate(filename):
            print(clr(f"  ✓  Deleted.\n", "bright_green"))
        else:
            print(clr("  ✗  Failed to delete.", "yellow"))
    else:
        print(clr("  Cancelled.\n", "dim"))

def duplicate_estimate() -> None:
    """
    Duplicate a saved estimate with new name.
    """
    files = show_saved_list()
    if not files:
        return
    raw = input(f"  Duplicate which estimate? (1–{len(files)}, 0 to cancel): ").strip()
    if not raw.isdigit() or raw == "0":
        return
    choice = int(raw)
    if not (1 <= choice <= len(files)):
        print(clr(f"  ⚠  Enter a number between 1 and {len(files)}, or 0 to cancel.", "yellow"))
        return

    original = load_estimate(files[choice - 1])
    if not original:
        print(clr("  ✗  Failed to load estimate.", "yellow"))
        return

    print()
    new_name = input(f"  New project name (was '{original['project']}'): ").strip()
    if not new_name:
        print(clr("  Cancelled.\n", "dim"))
        return

    new_est = duplicate_estimate(original, new_name)

    # Offer to update prices
    sym = get_currency()["symbol"]
    do_reprice = input("  Update material/labour prices now? (y/n): ").strip().lower()
    if do_reprice == "y":
        print()
        print(clr("  MATERIALS — enter new price or press Enter to keep current", "dim"))
        hr()
        for item in new_est["materials"]:
            raw = input(f"  {item['name'][:28]}  (current {sym}{item['unit_price']:,.2f}) — new price: ").strip()
            if raw:
                try:
                    new_price = float(raw)
                    if new_price > 0:
                        item["unit_price"] = new_price
                    else:
                        print(clr("  ⚠  Invalid price, kept original.", "yellow"))
                except ValueError:
                    print(clr("  ⚠  Invalid input, kept original.", "yellow"))

        if new_est["labour"]:
            print()
            print(clr("  LABOUR — enter new rate or press Enter to keep current", "dim"))
            hr()
            for item in new_est["labour"]:
                raw = input(f"  {item['name'][:28]}  (current {sym}{item['rate']:,.2f}/h) — new rate: ").strip()
                if raw:
                    try:
                        new_rate = float(raw)
                        if new_rate > 0:
                            item["rate"] = new_rate
                        else:
                            print(clr("  ⚠  Invalid rate, kept original.", "yellow"))
                    except ValueError:
                        print(clr("  ⚠  Invalid input, kept original.", "yellow"))

        new_est["margin"] = ask_number(
            f"  Profit margin % (current {new_est['margin']:.1f}%, Enter new or type same)",
            allow_zero=True
        )
        print()

    if save_estimate(new_est):
        show_summary(new_est)
        post_estimate_menu(new_est)

# ── Calculators ───────────────────────────────────────────────────────────────

def converter_menu() -> None:
    """
    Volume conversion calculator menu.
    """
    while True:
        header("CONVERTER")
        print(f"  {clr('1.', 'cyan')}  Area + thickness  →  Liters")
        print(f"       {clr('e.g. paint, adhesive, screed, concrete', 'dim')}")
        print(f"  {clr('2.', 'cyan')}  Dimensions (L × W × H)  →  Liters")
        print(f"       {clr('e.g. tank, pool, trench volume', 'dim')}")
        print(f"  {clr('3.', 'cyan')}  Cubic meters  →  Liters  {clr('(direct)', 'dim')}")
        print(f"  {clr('0.', 'dim')}  Back")
        print(f"  {clr('b.', 'dim')}  Back")
        print(f"  {clr('q.', 'dim')}  Quit")
        print()

        choice = input("  Choose: ").strip().lower()

        if choice == "1":
            conv_area_to_liters()
        elif choice == "2":
            conv_dimensions_to_liters()
        elif choice == "3":
            conv_m3_to_liters()
        elif choice in ("0", "b"):
            break
        elif choice == "q":
            raise QuitApp
        else:
            print(clr("  ⚠  Please enter 0–3, b or q.", "yellow"))

def conv_area_to_liters() -> None:
    """
    Calculate liters from area and thickness.
    """
    from calculations import conv_area_to_liters as calc_conv

    header("AREA + THICKNESS → LITERS")
    print(clr("  Useful for: paint, primer, adhesive, screed, concrete slab\n", "dim"))

    area = ask_number("  Area to cover (m²)")

    print(clr("\n  Enter thickness in:", "dim"))
    print(f"  {clr('1.', 'cyan')}  Millimetres (mm)  — common for paint, adhesive")
    print(f"  {clr('2.', 'cyan')}  Centimetres (cm)  — common for screed, render")
    print(f"  {clr('3.', 'cyan')}  Metres (m)        — common for concrete, fill")
    print(f"  {clr('0.', 'dim')}  Back")
    print()
    unit_choice = input("  Choose unit (0–3): ").strip()

    if unit_choice == "0":
        return

    if unit_choice == "1":
        thickness_raw = ask_number("  Thickness (mm)")
        thickness_m = thickness_raw / 1000
        unit_label = f"{thickness_raw:.2f} mm"
    elif unit_choice == "2":
        thickness_raw = ask_number("  Thickness (cm)")
        thickness_m = thickness_raw / 100
        unit_label = f"{thickness_raw:.2f} cm"
    else:
        thickness_m = ask_number("  Thickness (m)")
        unit_label = f"{thickness_m:.4f} m"

    wastage = ask_number("  Wastage % (0 for none)", allow_zero=True)

    result = calc_conv(area, thickness_m, unit_choice, wastage)

    print()
    hr("-")
    print(f"  {'Area':<30}  {area:>10.2f} m²")
    print(f"  {'Thickness':<30}  {unit_label:>10}")
    print(f"  {'Volume':<30}  {result['volume_m3']:>10.4f} m³")
    hr("-")
    print(f"  {'Base volume':<30}  {result['volume_L']:>10.2f} L")
    if wastage > 0:
        print(f"  {'Wastage (' + str(wastage) + '%)':<30}  +{result['wastage_L']:>9.2f} L")
    hr("═", color="cyan")
    print(f"  {clr('Total to order', 'bold', 'bright_green'):<49}  {clr(f'{result['total_L']:,.2f} L', 'bold', 'bright_green'):>12}")
    hr("═", color="cyan")
    print()

    tip = math.ceil(result['total_L'])
    print(clr(f"  Tip: order {tip} litres  ({math.ceil(tip / 5)} × 5L tins  |  {math.ceil(tip / 20)} × 20L drums)", "dim"))
    print()

def conv_dimensions_to_liters() -> None:
    """
    Calculate liters from dimensions.
    """
    from calculations import conv_dimensions_to_liters as calc_conv

    header("DIMENSIONS → LITERS")
    print(clr("  Useful for: tanks, pools, trenches, pits, footings\n", "dim"))

    length = ask_number("  Length (m)")
    width = ask_number("  Width  (m)")
    height = ask_number("  Height / Depth (m)")

    result = calc_conv(length, width, height)

    print()
    hr("-")
    print(f"  {'Length':<30}  {length:>10.3f} m")
    print(f"  {'Width':<30}  {width:>10.3f} m")
    print(f"  {'Height / Depth':<30}  {height:>10.3f} m")
    hr("-")
    print(f"  {'Volume':<30}  {result['volume_m3']:>10.4f} m³")
    hr("═", color="cyan")
    print(f"  {clr('Total volume', 'bold', 'bright_green'):<49}  {clr(f'{result['volume_L']:,.2f} L', 'bold', 'bright_green'):>12}")
    hr("═", color="cyan")
    print()

def conv_m3_to_liters() -> None:
    """
    Convert between m³ and liters.
    """
    from calculations import conv_m3_to_liters, conv_liters_to_m3

    while True:
        print(f"  {clr('1.', 'cyan')}  m³  →  Liters")
        print(f"  {clr('2.', 'cyan')}  Liters  →  m³")
        print(f"  {clr('0.', 'dim')}  Back")
        print(f"  {clr('b.', 'dim')}  Back")
        print()
        direction = input("  Choose: ").strip()

        if direction == "1":
            m3 = ask_number("  Volume (m³)")
            liters = conv_m3_to_liters(m3)
            print()
            print(f"  {clr(f'{m3:,.4f} m³', 'white')}  =  {clr(f'{liters:,.2f} L', 'bold', 'bright_green')}")
            print()
        elif direction == "2":
            liters = ask_number("  Volume (Liters)")
            m3 = conv_liters_to_m3(liters)
            print()
            print(f"  {clr(f'{liters:,.2f} L', 'white')}  =  {clr(f'{m3:,.6f} m³', 'bold', 'bright_green')}")
            print()
        elif direction in ("0", "b"):
            break
        else:
            print(clr("  ⚠  Please enter 0, 1, 2 or b.", "yellow"))

def pipe_calculator_menu() -> None:
    """
    Window pipe calculator menu.
    """
    from calculations import calc_pipes_for_window

    header("WINDOW PIPE CALCULATOR")
    print(clr("  All measurements in millimetres (mm).\n", "dim"))

    num_windows = int(ask_number("  Number of windows"))
    win_height = ask_number("  Window height / length (mm)  [e.g. 1200]")
    win_width = ask_number("  Window width (mm)            [e.g. 900]")
    spacing = ask_number("  Distance between pipes (mm)  [e.g. 150]")
    pipe_std_len = ask_number("  Standard pipe length (mm)    [e.g. 6000]")

    _, calc = calc_pipes_for_window(num_windows, win_height, win_width, spacing, pipe_std_len)

    print()
    hr()
    print(f"  {'Windows':<32}  {calc['num_windows']:>8}")
    print(f"  {'Window size':<32}  {calc['win_height']:.0f} mm x {calc['win_width']:.0f} mm")
    print(f"  {'Pipe spacing (distance)':<32}  {calc['spacing']:.0f} mm")
    print()
    print(f"  {'Horizontal bars per window':<32}  {calc['h_bars']:>8}  (x {calc['win_width']:.0f} mm wide)")
    print(f"  {'Vertical bars per window':<32}  {calc['v_bars']:>8}  (x {calc['win_height']:.0f} mm tall)")
    print(f"  {'Total pipe length per window':<32}  {calc['pipe_len_each']:>7,.0f} mm")
    print(f"  {'Pipes per window ({:.0f}mm each)'.format(calc['pipe_std_len']):<32}  {calc['pipes_per_win']:>8}")
    hr()
    print(clr(f"  Total pipes for {calc['num_windows']} window(s)   {calc['total_pipes']:>8}", "bright_green"))
    hr()
    print()

    sym = get_currency()["symbol"]
    add = input("  Add pipes as a material in this estimate? (y/n): ").strip().lower()
    if add == "y":
        price = ask_number(f"  Unit price per pipe ({sym})")
        name = f"Pipes ({pipe_std_len:.0f}mm)"
        total = calc['total_pipes'] * price
        print(clr(f"  ✓  {name} — {calc['total_pipes']} × {fmt_currency(price)} = {fmt_currency(total)}", "bright_green") + "\n")
        # Note: In full app, this would add to current estimate

    input(clr("  Press Enter to return to main menu...", "dim"))

def stair_handrail_menu() -> None:
    """
    Stair handrail calculator menu.
    """
    from calculations import calc_handrail_for_stairs

    header("STAIR HANDRAIL CALCULATOR")
    print(clr("  All measurements in millimetres (mm).\n", "dim"))

    num_steps = int(ask_number("  Number of steps"))
    tread_depth = ask_number("  Tread depth (mm)          [horizontal, e.g. 250]")
    riser_height = ask_number("  Riser height (mm)         [vertical,   e.g. 175]")
    num_sides = int(ask_number("  Number of handrail sides  [1 or 2]"))
    rail_height = ask_number("  Handrail height (mm)      [floor to top rail, e.g. 1000]")
    rail_width = ask_number("  Stair width (mm)          [between handrail sides, e.g. 1200]")
    pipe_std_len = ask_number("  Standard pipe length (mm) [e.g. 6000]")
    baluster_sp = ask_number("  Baluster spacing (mm)     [e.g. 150]")

    _, calc = calc_handrail_for_stairs(num_steps, tread_depth, riser_height, num_sides,
                                      rail_height, rail_width, pipe_std_len, baluster_sp)

    print()
    hr()
    print(f"  {'Steps':<36}  {calc['num_steps']:>8}")
    print(f"  {'Tread depth':<36}  {calc['tread_depth']:>6,.0f} mm")
    print(f"  {'Riser height':<36}  {calc['riser_height']:>6,.0f} mm")
    print(f"  {'Handrail height':<36}  {calc['rail_height']:>6,.0f} mm")
    print(f"  {'Stair width':<36}  {calc['rail_width']:>6,.0f} mm")
    print(f"  {'Handrail sides':<36}  {calc['num_sides']:>8}")
    print()
    print(f"  {'Horizontal run':<36}  {calc['horiz_run']:>6,.0f} mm")
    print(f"  {'Total rise':<36}  {calc['total_rise']:>6,.0f} mm")
    print(f"  {'Stair angle':<36}  {calc['angle_deg']:>7.1f} °")
    print(f"  {'Handrail slant length':<36}  {calc['slant_len']:>6,.0f} mm")
    print()
    print(clr("  TOP RAIL:", "dim"))
    print(f"  {'Pipes per side ({:.0f}mm each)'.format(calc['pipe_std_len']):<36}  {calc['pipes_per_side']:>8}")
    print(f"  {'Top rail pipes total':<36}  {calc['total_rail_pipes']:>8}")
    print()
    print(clr("  BALUSTER POSTS:", "dim"))
    print(f"  {'Baluster spacing':<36}  {calc['baluster_sp']:>6,.0f} mm")
    print(f"  {'Balusters per side':<36}  {calc['balusters_per_side']:>8}")
    print(f"  {'Total balusters':<36}  {calc['total_balusters']:>8}")
    print(f"  {'Post height':<36}  {calc['rail_height']:>6,.0f} mm")
    print(f"  {'Pipes for posts ({:.0f}mm each)'.format(calc['pipe_std_len']):<36}  {calc['baluster_pipes']:>8}")
    print()
    print(clr("  CROSS PIECES (top & bottom):", "dim"))
    print(f"  {'Stair width':<36}  {calc['rail_width']:>6,.0f} mm")
    print(f"  {'Cross pieces':<36}  {'2':>8}  (top + bottom)")
    print(f"  {'Pipes for cross pieces':<36}  {calc['cross_pipes']:>8}")
    print()
    hr()
    print(clr(f"  {'GRAND TOTAL PIPES':<36}  {calc['total_pipes']:>8}", "bright_green"))
    print(clr(f"  {'Total balusters':<36}  {calc['total_balusters']:>8}", "bright_green"))
    hr()
    print()

    input(clr("  Press Enter to return to main menu...", "dim"))