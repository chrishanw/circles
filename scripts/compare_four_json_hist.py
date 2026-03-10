#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare four timing JSONs (e.g. menu versions 1.0, 1.1, 1.2, 1.3) using a grouping
JSON and plot bar charts. The 4th JSON is the baseline.

Example (menu versions 1.0–1.3, baseline = 1.3):

  python compare_four_json_hist.py \\
    timing_1.0.json timing_1.1.json timing_1.2.json timing_1.3.json \\
    --map grouping.json \\
    --name-a 1.0 --name-b 1.1 --name-c 1.2 --name-d 1.3 \\
    --save comparison_four.png
"""

import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb, to_hex
from matplotlib.patches import Patch


# ------------------------
# Mapping / augmentation
# ------------------------
def augment_json(input_data, group_data, debug):
    """
    Augment input json with 'expanded' key from grouping. Unmapped modules -> "Unassigned".
    """
    groups = []
    for raw_pattern, group in group_data.items():
        pattern = str(raw_pattern)
        ctype, sep, label = pattern.partition("|")
        if sep == "":
            ctype = ""
            label = pattern
        ctype = ctype.strip()
        label = label.strip()
        ctype = (
            re.compile(ctype.replace("?", ".").replace("*", ".*") + "$")
            if ctype
            else None
        )
        label = (
            re.compile(label.replace("?", ".").replace("*", ".*") + "$")
            if label
            else None
        )
        groups.append([ctype, label, str(group)])

    for module in input_data.get("modules", []):
        found = False
        mtype = module.get("type", "")
        mlabel = module.get("label", "")
        for ctype_rx, label_rx, group in groups:
            if (ctype_rx is None or ctype_rx.match(mtype)) and (
                label_rx is None or label_rx.match(mlabel)
            ):
                module["expanded"] = "|".join([group, mtype, mlabel])
                found = True
                break
        if not found:
            if debug:
                print(f"Failed to parse {module}")
            module["expanded"] = "|".join(["Unassigned", mtype, mlabel])

    return input_data


# ------------------------
# I/O helpers
# ------------------------
def load_full_json(path: Path) -> Dict:
    with path.open("r") as f:
        data = json.load(f)
    if "modules" not in data or not isinstance(data["modules"], list):
        raise ValueError(f"{path} does not contain a top-level 'modules' list")
    return data


def load_grouping(path: Path) -> Dict:
    with path.open("r") as f:
        return json.load(f)


def load_colors(path: Optional[Path]) -> Dict[str, str]:
    if not path:
        return {}
    with path.open("r") as f:
        raw = json.load(f)
    return {str(k): str(v) for k, v in raw.items()}


def get_total_events(data: Dict) -> float:
    try:
        tot = data.get("total", {})
        ev = float(tot.get("events", 0))
        return ev if ev > 0 else 1.0
    except Exception:
        return 1.0


# ------------------------
# Metric & keys
# ------------------------
def numeric_metric(
    m: Dict, metric: str, per_event: bool, total_events: float
) -> Optional[float]:
    if metric not in m:
        return None
    try:
        val = float(m[metric])
    except Exception:
        return None
    if per_event and total_events > 0:
        val = val / total_events
    return val


def package_from_expanded(m: Dict) -> str:
    exp = m.get("expanded", "")
    return exp.split("|", 1)[0] if "|" in exp else "Unassigned"


def key_for_level(m: Dict, level: str) -> str:
    if level == "label":
        return str(m.get("label", ""))
    if level == "type":
        return str(m.get("type", ""))
    if level == "package":
        return package_from_expanded(m)
    if level == "expanded":
        return str(m.get("expanded", "Unassigned|?|?"))
    raise ValueError("level must be one of: package, type, label, expanded")


# ------------------------
# Aggregation & alignment
# ------------------------
def aggregate(
    mods: List[Dict], metric: str, per_event: bool, level: str, total_events: float
) -> Dict[str, float]:
    agg: Dict[str, float] = {}
    for m in mods:
        v = numeric_metric(m, metric, per_event, total_events)
        if v is None:
            continue
        k = key_for_level(m, level)
        agg[k] = agg.get(k, 0.0) + v
    return agg


def align_for_bars4(
    agg_a: Dict[str, float],
    agg_b: Dict[str, float],
    agg_c: Dict[str, float],
    agg_d: Dict[str, float],
) -> Tuple[List[str], List[float], List[float], List[float], List[float]]:
    cats = sorted(
        set(agg_a.keys()) | set(agg_b.keys()) | set(agg_c.keys()) | set(agg_d.keys())
    )
    A = [agg_a.get(c, 0.0) for c in cats]
    B = [agg_b.get(c, 0.0) for c in cats]
    C = [agg_c.get(c, 0.0) for c in cats]
    D = [agg_d.get(c, 0.0) for c in cats]
    return cats, A, B, C, D


# ------------------------
# Colors
# ------------------------
def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def adjust_lightness(hex_color: str, factor: float) -> str:
    r, g, b = to_rgb(hex_color)
    if factor >= 1:
        r = r + (1 - r) * (factor - 1)
        g = g + (1 - g) * (factor - 1)
        b = b + (1 - b) * (factor - 1)
    else:
        r, g, b = r * factor, g * factor, b * factor
    return to_hex((_clamp01(r), _clamp01(g), _clamp01(b)))


def pick_base_color(package: str, cmap: Dict[str, str]) -> str:
    return cmap.get(package, cmap.get("others", "#cccccc"))


def cat_to_package_4(
    cats: List[str],
    level: str,
    mods_a: List[Dict],
    mods_b: List[Dict],
    mods_c: List[Dict],
    mods_d: List[Dict],
    metric: str,
    per_event: bool,
    total_events_a: float,
    total_events_b: float,
    total_events_c: float,
    total_events_d: float,
) -> Dict[str, str]:
    mapping: Dict[str, Dict[str, float]] = {c: {} for c in cats}

    def _accumulate(mods: List[Dict], total_events: float):
        for m in mods:
            v = numeric_metric(m, metric, per_event, total_events)
            if v is None:
                continue
            k = key_for_level(m, level)
            if k not in mapping:
                continue
            pkg = package_from_expanded(m)
            mapping[k][pkg] = mapping[k].get(pkg, 0.0) + v

    _accumulate(mods_a, total_events_a)
    _accumulate(mods_b, total_events_b)
    _accumulate(mods_c, total_events_c)
    _accumulate(mods_d, total_events_d)

    out: Dict[str, str] = {}
    for k, d in mapping.items():
        out[k] = max(d.items(), key=lambda x: x[1])[0] if d else "Unassigned"
    return out


def color_for_category(
    cat: str, level: str, pkg_of_cat: str, colors: Dict[str, str]
) -> str:
    base = pick_base_color(pkg_of_cat, colors)
    if level == "package":
        return base
    h = abs(hash(cat)) % 997
    factor = 0.85 + (h / 997.0) * 0.40
    return adjust_lightness(base, factor)


# ------------------------
# Sorting / trimming
# ------------------------
def sort_indices4(
    cats: List[str],
    A: List[float],
    B: List[float],
    C: List[float],
    D: List[float],
    how: str,
    compare: str,
) -> List[int]:
    # baseline is D
    def dA(i):
        return A[i] - D[i]

    def dB(i):
        return B[i] - D[i]

    def dC(i):
        return C[i] - D[i]

    def rA(i):
        return (A[i] / D[i]) if D[i] != 0 else float("inf")

    def rB(i):
        return (B[i] / D[i]) if D[i] != 0 else float("inf")

    def rC(i):
        return (C[i] / D[i]) if D[i] != 0 else float("inf")

    if compare == "ratio":
        key_funcs = {
            "A": lambda i: rA(i),
            "B": lambda i: rB(i),
            "C": lambda i: rC(i),
            "D": lambda i: D[i],
            "diffA": lambda i: abs(rA(i) - 1.0),
            "diffB": lambda i: abs(rB(i) - 1.0),
            "diffC": lambda i: abs(rC(i) - 1.0),
            "max": lambda i: max(rA(i), rB(i), rC(i), 1.0),
            "sum": lambda i: rA(i) + rB(i) + rC(i),
        }
    else:
        key_funcs = {
            "A": lambda i: A[i],
            "B": lambda i: B[i],
            "C": lambda i: C[i],
            "D": lambda i: D[i],
            "diffA": lambda i: abs(dA(i)),
            "diffB": lambda i: abs(dB(i)),
            "diffC": lambda i: abs(dC(i)),
            "max": lambda i: max(A[i], B[i], C[i], D[i]),
            "sum": lambda i: A[i] + B[i] + C[i] + D[i],
        }

    keyf = key_funcs.get(how, key_funcs["D"])
    return sorted(range(len(cats)), key=keyf, reverse=True)


def maybe_truncate(names: List[str], n: Optional[int]) -> List[str]:
    if not n or n <= 0:
        return names
    return [s if len(s) <= n else s[: max(0, n - 1)] + "…" for s in names]


def apply_top4(
    cats: List[str],
    A: List[float],
    B: List[float],
    C: List[float],
    D: List[float],
    order: List[int],
    top: Optional[int],
):
    idxs = order[:top] if (top and top > 0) else order
    return (
        [cats[i] for i in idxs],
        [A[i] for i in idxs],
        [B[i] for i in idxs],
        [C[i] for i in idxs],
        [D[i] for i in idxs],
    )


# ------------------------
# Plotting
# ------------------------
def plot_four(
    cats: List[str],
    A: List[float],
    B: List[float],
    C: List[float],
    D: List[float],
    colors_fill: List[str],
    edge_colors: List[str],
    metric_label: str,
    title: Optional[str],
    subtitle: Optional[str],
    name_a: str,
    name_b: str,
    name_c: str,
    name_d: str,
    rotate: int,
    truncate: Optional[int],
    fontsize: int,
    style: str,
    level: str,
    package_top: str,
    outline_width: float,
    stack_key: str,
    compare: str,
    save: Optional[Path],
    show: bool,
):
    if not cats:
        print("No categories to plot after filtering.")
        return

    x = list(range(len(cats)))
    # Baseline is D
    dA = [a - d for a, d in zip(A, D)]
    dB = [b - d for b, d in zip(B, D)]
    dC = [c - d for c, d in zip(C, D)]
    rA = [(a / d) if d != 0 else float("inf") for a, d in zip(A, D)]
    rB = [(b / d) if d != 0 else float("inf") for b, d in zip(B, D)]
    rC = [(c / d) if d != 0 else float("inf") for c, d in zip(C, D)]

    single_panel = compare in ("diff", "ratio")

    if single_panel:
        fig = plt.figure(figsize=(max(10, len(cats) * 0.5), 6))
        ax = fig.add_subplot(1, 1, 1)
        # Three series vs baseline: A-D, B-D, C-D
        width = 0.26
        offs = (-width, 0.0, +width)
        if compare == "diff":
            y1, y2, y3 = dA, dB, dC
            ylabel = f"Δ(•−baseline) {metric_label}"
            ref = 0.0
        else:
            y1, y2, y3 = rA, rB, rC
            ylabel = f"ratio(•/baseline) {metric_label}"
            ref = 1.0

        if style == "outline":
            ax.bar(
                [i + offs[0] for i in x],
                y1,
                width=width,
                facecolor="white",
                edgecolor=edge_colors,
                linewidth=outline_width,
                label=f"A−D: {name_a} vs {name_d}" if compare == "diff" else f"A/D: {name_a} / {name_d}",
            )
            ax.bar(
                [i + offs[1] for i in x],
                y2,
                width=width,
                color=colors_fill,
                edgecolor="none",
                label=f"B−D: {name_b} vs {name_d}" if compare == "diff" else f"B/D: {name_b} / {name_d}",
            )
            ax.bar(
                [i + offs[2] for i in x],
                y3,
                width=width,
                facecolor="white",
                edgecolor="black",
                linewidth=0.6,
                label=f"C−D: {name_c} vs {name_d}" if compare == "diff" else f"C/D: {name_c} / {name_d}",
            )
        else:
            ax.bar(
                [i + offs[0] for i in x], y1, width=width, color=colors_fill,
                hatch="///", edgecolor="black",
                label=f"A−D: {name_a}" if compare == "diff" else f"A/D: {name_a}",
            )
            ax.bar(
                [i + offs[1] for i in x], y2, width=width, color=colors_fill,
                hatch="\\\\\\\\", edgecolor="black",
                label=f"B−D: {name_b}" if compare == "diff" else f"B/D: {name_b}",
            )
            ax.bar(
                [i + offs[2] for i in x], y3, width=width, color=colors_fill,
                hatch="xx", edgecolor="black",
                label=f"C−D: {name_c}" if compare == "diff" else f"C/D: {name_c}",
            )

        ax.axhline(ref, linestyle="--", linewidth=1)
        ax.set_ylabel(ylabel)
        ax.set_xticks(x)
        ax.set_xticklabels(
            maybe_truncate(cats, truncate), rotation=rotate, ha="right", fontsize=fontsize
        )
        ax.grid(axis="y", linestyle=":", alpha=0.5)
        ax.legend(loc="best")
        if title:
            fig.suptitle(title)
        if subtitle:
            fig.text(0.5, 0.01, subtitle, ha="center")
        if save:
            save.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(save, dpi=150, bbox_inches="tight")
            print(f"Saved figure to: {save}")
        if show and not save:
            plt.show()
        return

    # ---- absolute: two panels ----
    fig = plt.figure(figsize=(max(10, len(cats) * 0.5), 7.5))
    gs = fig.add_gridspec(2, 1, height_ratios=[2, 1.2], hspace=0.28)
    ax1 = fig.add_subplot(gs[0, 0])

    if level == "package" and package_top == "stacked":
        x4 = [0, 1, 2, 3]
        ax1.set_xticks(x4)
        ax1.set_xticklabels(
            [name_a, name_b, name_c, name_d], rotation=0, ha="center", fontsize=fontsize
        )
        bottomA = bottomB = bottomC = bottomD = 0.0

        def _key_for(i):
            if stack_key == "A":
                return A[i]
            if stack_key == "B":
                return B[i]
            if stack_key == "C":
                return C[i]
            if stack_key == "D":
                return D[i]
            if stack_key == "max":
                return max(A[i], B[i], C[i], D[i])
            if stack_key == "sum":
                return A[i] + B[i] + C[i] + D[i]
            return max(abs(A[i] - D[i]), abs(B[i] - D[i]), abs(C[i] - D[i]))

        stack_order = sorted(range(len(cats)), key=_key_for)
        for i in stack_order:
            seg_fill = colors_fill[i]
            ax1.bar(0, A[i], bottom=bottomA, width=0.5, color=seg_fill, edgecolor="black", linewidth=0.4)
            ax1.bar(1, B[i], bottom=bottomB, width=0.5, color=seg_fill, edgecolor="black", linewidth=0.4)
            ax1.bar(2, C[i], bottom=bottomC, width=0.5, color=seg_fill, edgecolor="black", linewidth=0.4)
            ax1.bar(3, D[i], bottom=bottomD, width=0.5, color=seg_fill, edgecolor="black", linewidth=0.4)
            bottomA += A[i]
            bottomB += B[i]
            bottomC += C[i]
            bottomD += D[i]

        max_height = max(bottomA, bottomB, bottomC, bottomD)
        ax1.set_ylim(0, max_height * 1.15)
        ax1.set_ylabel(metric_label)
        ax1.grid(axis="y", linestyle=":", alpha=0.5)
        pkg_handles = [
            Patch(facecolor=colors_fill[i], edgecolor="black", label=cats[i])
            for i in range(len(cats))
        ]
        ax1.legend(handles=pkg_handles, loc="center left", bbox_to_anchor=(1, 0.5))
    else:
        width = 0.2
        offs = (-1.5 * width, -0.5 * width, 0.5 * width, 1.5 * width)
        if style == "outline":
            ax1.bar(
                [i + offs[0] for i in x], A, width=width,
                facecolor="white", edgecolor=edge_colors, linewidth=outline_width,
                label=f"A: {name_a}",
            )
            ax1.bar(
                [i + offs[1] for i in x], B, width=width,
                color=colors_fill, edgecolor="none",
                label=f"B: {name_b}",
            )
            ax1.bar(
                [i + offs[2] for i in x], C, width=width,
                facecolor="white", edgecolor=edge_colors, linewidth=outline_width,
                label=f"C: {name_c}",
            )
            ax1.bar(
                [i + offs[3] for i in x], D, width=width,
                facecolor="white", edgecolor="black", linewidth=0.6,
                label=f"baseline (D): {name_d}",
            )
        else:
            ax1.bar([i + offs[0] for i in x], A, width=width, color=colors_fill, hatch="///", edgecolor="black", label=f"A: {name_a}")
            ax1.bar([i + offs[1] for i in x], B, width=width, color=colors_fill, hatch="\\\\\\\\", edgecolor="black", label=f"B: {name_b}")
            ax1.bar([i + offs[2] for i in x], C, width=width, color=colors_fill, hatch="xx", edgecolor="black", label=f"C: {name_c}")
            ax1.bar([i + offs[3] for i in x], D, width=width, color="white", hatch="++", edgecolor="black", label=f"baseline (D): {name_d}")

        ax1.set_ylabel(metric_label)
        ax1.set_xticks(x)
        ax1.set_xticklabels(maybe_truncate(cats, truncate), rotation=rotate, ha="right", fontsize=fontsize)
        ax1.grid(axis="y", linestyle=":", alpha=0.5)
        ax1.legend(loc="best")

    ax2 = fig.add_subplot(gs[1, 0])
    width = 0.26
    offs = (-width, 0.0, +width)
    ax2.bar([i + offs[0] for i in x], dA, width=width, facecolor="white", edgecolor=edge_colors, linewidth=outline_width, label=f"A−D: {name_a} vs {name_d}")
    ax2.bar([i + offs[1] for i in x], dB, width=width, color=colors_fill, edgecolor="none", label=f"B−D: {name_b} vs {name_d}")
    ax2.bar([i + offs[2] for i in x], dC, width=width, facecolor="white", edgecolor="black", linewidth=0.6, label=f"C−D: {name_c} vs {name_d}")
    ax2.axhline(0, linestyle="--", linewidth=1)
    ax2.set_ylabel(f"Δ(•−baseline) {metric_label}")
    ax2.set_xticks(x)
    ax2.set_xticklabels(maybe_truncate(cats, truncate), rotation=rotate, ha="right", fontsize=fontsize)
    ax2.grid(axis="y", linestyle=":", alpha=0.5)
    ax2.legend(loc="best")

    if title:
        fig.suptitle(title)
    if subtitle:
        fig.text(0.5, 0.01, subtitle, ha="center")
    if save:
        save.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save, dpi=150, bbox_inches="tight")
        print(f"Saved figure to: {save}")
    if show and not save:
        plt.show()


# ------------------------
# CLI
# ------------------------
def main():
    p = argparse.ArgumentParser(
        description="Compare four timing JSONs (e.g. menu 1.0, 1.1, 1.2, 1.3) using a grouping JSON. The 4th JSON is the baseline."
    )
    p.add_argument("json_a", type=Path, help="First timing JSON (e.g. menu 1.0)")
    p.add_argument("json_b", type=Path, help="Second timing JSON (e.g. menu 1.1)")
    p.add_argument("json_c", type=Path, help="Third timing JSON (e.g. menu 1.2)")
    p.add_argument("json_d", type=Path, help="Fourth timing JSON / baseline (e.g. menu 1.3)")

    p.add_argument("--map", type=Path, required=True, help="Grouping JSON (TypeGlob|LabelGlob -> Package)")
    p.add_argument("--colors", type=Path, default=None, help="Colors JSON: Package -> HEX")
    p.add_argument("--debug-map", action="store_true", help="Print unmapped modules.")

    p.add_argument(
        "--compare",
        choices=["absolute", "diff", "ratio"],
        default="absolute",
        help="absolute (two panels), diff (single: A−D,B−D,C−D), ratio (single: A/D,B/D,C/D). Baseline = 4th JSON.",
    )
    p.add_argument("-m", "--metric", default="time_real", help="Metric (default: time_real)")
    p.add_argument("--per-event", action="store_true", help="Normalize by file total events.")
    p.add_argument(
        "--level",
        choices=["package", "type", "label", "expanded"],
        default="label",
        help="X-axis categories (default: label)",
    )
    p.add_argument("--package", default=None, help="Keep only this package")
    p.add_argument("--package-regex", default=None, help="Keep modules whose package matches regex")
    p.add_argument("--require-map", action="store_true", help="Drop 'Unassigned' modules.")

    p.add_argument(
        "--sort-by",
        choices=["A", "B", "C", "D", "diffA", "diffB", "diffC", "max", "sum"],
        default="D",
        help="Sort categories by this key (default: D/baseline).",
    )
    p.add_argument("--top", type=int, default=None, help="Show only top N categories")
    p.add_argument("--truncate", type=int, default=48, help="Truncate tick labels (0=off)")
    p.add_argument("--rotate", type=int, default=60, help="Rotate x labels (degrees)")
    p.add_argument("--label-fontsize", type=int, default=9, help="X tick font size")

    p.add_argument("--style", choices=["outline", "hatch"], default="outline")
    p.add_argument("--outline-width", type=float, default=0.8)
    p.add_argument(
        "--package-top",
        choices=["stacked", "grouped"],
        default="stacked",
        help="When level=package: stacked bars per menu or grouped.",
    )
    p.add_argument(
        "--stack-sort-by",
        choices=["diff", "A", "B", "C", "D", "max", "sum"],
        default="diff",
        help="Stack order (default: diff vs baseline).",
    )
    p.add_argument("--title", default=None)
    p.add_argument("--save", type=Path, default=None, help="Output figure path")
    p.add_argument("--no-show", action="store_true")

    p.add_argument("--name-a", type=str, default=None, help="Label for 1st JSON (e.g. 1.0)")
    p.add_argument("--name-b", type=str, default=None, help="Label for 2nd JSON (e.g. 1.1)")
    p.add_argument("--name-c", type=str, default=None, help="Label for 3rd JSON (e.g. 1.2)")
    p.add_argument("--name-d", type=str, default=None, help="Label for 4th JSON/baseline (e.g. 1.3)")

    args = p.parse_args()

    data_a = load_full_json(args.json_a)
    data_b = load_full_json(args.json_b)
    data_c = load_full_json(args.json_c)
    data_d = load_full_json(args.json_d)
    group_data = load_grouping(args.map)
    color_map = load_colors(args.colors)

    total_events_a = get_total_events(data_a)
    total_events_b = get_total_events(data_b)
    total_events_c = get_total_events(data_c)
    total_events_d = get_total_events(data_d)

    data_a = augment_json(data_a, group_data, args.debug_map)
    data_b = augment_json(data_b, group_data, args.debug_map)
    data_c = augment_json(data_c, group_data, args.debug_map)
    data_d = augment_json(data_d, group_data, args.debug_map)

    mods_a, mods_b = data_a["modules"], data_b["modules"]
    mods_c, mods_d = data_c["modules"], data_d["modules"]

    if args.require_map:
        mods_a = [m for m in mods_a if package_from_expanded(m) != "Unassigned"]
        mods_b = [m for m in mods_b if package_from_expanded(m) != "Unassigned"]
        mods_c = [m for m in mods_c if package_from_expanded(m) != "Unassigned"]
        mods_d = [m for m in mods_d if package_from_expanded(m) != "Unassigned"]
    if args.package:
        mods_a = [m for m in mods_a if package_from_expanded(m) == args.package]
        mods_b = [m for m in mods_b if package_from_expanded(m) == args.package]
        mods_c = [m for m in mods_c if package_from_expanded(m) == args.package]
        mods_d = [m for m in mods_d if package_from_expanded(m) == args.package]
    if args.package_regex:
        rx = re.compile(args.package_regex)
        mods_a = [m for m in mods_a if rx.search(package_from_expanded(m))]
        mods_b = [m for m in mods_b if rx.search(package_from_expanded(m))]
        mods_c = [m for m in mods_c if rx.search(package_from_expanded(m))]
        mods_d = [m for m in mods_d if rx.search(package_from_expanded(m))]

    agg_a = aggregate(mods_a, args.metric, args.per_event, args.level, total_events_a)
    agg_b = aggregate(mods_b, args.metric, args.per_event, args.level, total_events_b)
    agg_c = aggregate(mods_c, args.metric, args.per_event, args.level, total_events_c)
    agg_d = aggregate(mods_d, args.metric, args.per_event, args.level, total_events_d)

    cats, Avals, Bvals, Cvals, Dvals = align_for_bars4(agg_a, agg_b, agg_c, agg_d)
    order = sort_indices4(cats, Avals, Bvals, Cvals, Dvals, args.sort_by, args.compare)
    cats, Avals, Bvals, Cvals, Dvals = apply_top4(
        cats, Avals, Bvals, Cvals, Dvals, order, args.top
    )

    if args.level == "package":
        pkg_for_cat = {c: c for c in cats}
    else:
        pkg_for_cat = cat_to_package_4(
            cats, args.level,
            mods_a, mods_b, mods_c, mods_d,
            args.metric, args.per_event,
            total_events_a, total_events_b, total_events_c, total_events_d,
        )

    colors_fill, edge_colors = [], []
    for c in cats:
        base_pkg = pkg_for_cat.get(c, "others")
        base_hex = pick_base_color(base_pkg, color_map)
        varied_hex = color_for_category(c, args.level, base_pkg, color_map)
        colors_fill.append(varied_hex)
        edge_colors.append(base_hex)

    metric_label = args.metric + (" (per event)" if args.per_event else "")
    subtitle_bits = [
        f"level={args.level}",
        f"baseline={args.json_d.name}",
        f"compare={args.compare}",
    ]
    if args.package:
        subtitle_bits.append(f"package == {args.package!r}")
    if args.package_regex:
        subtitle_bits.append(f"package ~ /{args.package_regex}/")
    if args.require_map:
        subtitle_bits.append("require_map")
    subtitle = "; ".join(subtitle_bits)

    plot_four(
        cats, Avals, Bvals, Cvals, Dvals,
        colors_fill=colors_fill,
        edge_colors=edge_colors,
        metric_label=metric_label,
        title=args.title,
        subtitle=subtitle,
        name_a=args.name_a or args.json_a.name,
        name_b=args.name_b or args.json_b.name,
        name_c=args.name_c or args.json_c.name,
        name_d=args.name_d or args.json_d.name,
        rotate=args.rotate,
        truncate=None if args.truncate == 0 else args.truncate,
        fontsize=args.label_fontsize,
        style=args.style,
        level=args.level,
        package_top=args.package_top,
        outline_width=args.outline_width,
        stack_key=args.stack_sort_by,
        compare=args.compare,
        save=args.save,
        show=not args.no_show,
    )


if __name__ == "__main__":
    main()
