"""
Charts for NHS GP Cloud Based Telephony, drawn from the Gold CSVs.

Run after src/pipeline/gold_build.py. Writes PNGs to docs/charts/. Every chart is
read from data/gold/ (the table view of each chart), so nothing here computes a
new figure.

Palette: the dataviz reference palette (categorical slots 1-4, sequential blue),
validated light-mode adjacent: worst CVD dE 9.1, normal-vision dE 22.9. Slots 3-4
are below 3:1 on the surface, so every chart carries a legend and direct labels.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

REPO = Path(__file__).resolve().parents[2]
GOLD = REPO / "data" / "gold"
OUT = REPO / "docs" / "charts"
OUT.mkdir(parents=True, exist_ok=True)
MONTH = "2026-08"

SURFACE = "#fcfcfb"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SOURCE = "Source: NHS England, Cloud Based Telephony Data in General Practice; Patients Registered at a GP Practice, 1 Aug 2026."

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10, "text.color": INK, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": INK_2, "axes.edgecolor": AXIS,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
})


def titles(fig, title, subtitle):
    fig.text(0.02, 0.97, title, fontsize=14, fontweight="semibold", color=INK, va="top")
    fig.text(0.02, 0.915, subtitle, fontsize=10, color=INK_2, va="top")


def footer(fig, text=SOURCE):
    fig.text(0.02, 0.02, text, fontsize=8, color=MUTED, va="bottom")


def quiet(ax, grid_axis="x"):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.spines["bottom"].set_linewidth(1)
    ax.tick_params(length=0)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=1)
        ax.set_axisbelow(True)


def fits(ax, text, width_data, fontsize=9, pad_px=6):
    """True if `text` fits inside a horizontal span of `width_data` (x data units) with padding."""
    fig = ax.figure
    renderer = fig.canvas.get_renderer()
    t = ax.text(0, 0, text, fontsize=fontsize)
    w = t.get_window_extent(renderer).width
    t.remove()
    x0, x1 = ax.transData.transform([(0, 0), (width_data, 0)])[:, 0]
    return (x1 - x0) >= w + 2 * pad_px


# ---------------------------------------------------------------- 1. week heatmap
def week_heatmap():
    g = pd.read_csv(GOLD / f"day_band_grid_{MONTH}.csv", index_col=0)
    bands = [c for c in g.columns if c != "days"]
    edges = [0, 6, 8, 10, 12, 14, 16, 18, 18.5, 24]
    hours = np.diff(edges)
    per_hour = g[bands].div(hours, axis=1)
    rows = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Monday (bank holiday)"]
    per_hour = per_hour.reindex(rows)

    fig, ax = plt.subplots(figsize=(11, 5.6))
    fig.subplots_adjust(left=0.2, right=0.9, top=0.8, bottom=0.17)
    cmap = LinearSegmentedColormap.from_list("blue", BLUE_RAMP)
    y_edges = [0, 1, 2, 3, 4, 5, 6, 7, 7.35, 8.35]  # gap before the bank-holiday row
    vmax = per_hour.values.max()
    for i, day in enumerate(rows):
        y0 = y_edges[i] if i < 7 else y_edges[8]
        for j in range(len(bands)):
            ax.add_patch(plt.Rectangle((edges[j], y0), hours[j], 1, facecolor=cmap(per_hour.iloc[i, j] / vmax),
                                       edgecolor=SURFACE, linewidth=2))
    ax.set_xlim(0, 24)
    ax.set_ylim(y_edges[-1], 0)
    centres = [y_edges[i] + 0.5 if i < 7 else y_edges[8] + 0.5 for i in range(len(rows))]
    ax.set_yticks(centres, ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
                            "Mon 31 Aug (bank holiday)"])
    ax.set_xticks([0, 6, 8, 10, 12, 14, 16, 18, 24], ["00:00", "06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "24:00"])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)

    peak = per_hour.loc["Monday", "08:00-09:59"]
    ax.text(9, 0.5, f"{peak / 1000:,.0f}k\nper hour", ha="center", va="center", fontsize=9, color="#ffffff",
            fontweight="semibold")
    tue_fri = per_hour.loc[["Tuesday", "Wednesday", "Thursday", "Friday"], "08:00-09:59"].mean()
    ax.text(8, -0.25, f"Ordinary Mondays 08:00–10:00: {peak / tue_fri:.2f}× the Tuesday–Friday average for the same band",
            ha="left", va="bottom", fontsize=9, color=INK_2)

    cax = fig.add_axes([0.92, 0.17, 0.015, 0.63])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, vmax))
    cb = fig.colorbar(sm, cax=cax)
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=0, labelsize=8, colors=MUTED)
    cb.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1000:,.0f}k"))
    cb.set_label("Average inbound calls per hour", color=INK_2, fontsize=9)

    titles(fig, "The Monday 8am rush: when calls reach GP practices, August 2026",
           "Average inbound calls per hour in each 2-hour band (cell width = band length). "
           "Ordinary days averaged; the bank holiday shown separately.")
    footer(fig, SOURCE.replace("; Patients Registered at a GP Practice, 1 Aug 2026", "")
           + " Calls from all 5,327 included practices, incl. shared accounts.")
    fig.savefig(OUT / "week_heatmap_2026-08.png", dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------- 2. coverage by region
def coverage_by_region():
    c = pd.read_csv(GOLD / f"coverage_by_region_{MONTH}.csv", index_col=0)
    eng = c.loc[["ENGLAND"]]
    reg = c.drop("ENGLAND").sort_values("patient_coverage")
    c = pd.concat([eng, reg])  # England at the bottom, regions above it
    labels = [n.title().replace(" And ", " and ").replace("Of ", "of ") for n in c.index]
    coverage_bars(c, labels, "coverage_by_region_2026-08.png",
                  "Who is behind the missing 13.7%? Registered patients by practice status, August 2026",
                  "Share of registered patients at open, active practices. Almost every patient outside the data is at a practice\n"
                  "that agreed to take part but whose supplier data isn't published yet.",
                  SOURCE + " 42 practices with no list row count as zero patients.")


def coverage_by_deprivation():
    c = pd.read_csv(GOLD / f"coverage_by_deprivation_{MONTH}.csv", index_col=0)
    reg = pd.read_csv(GOLD / f"coverage_by_region_{MONTH}.csv", index_col=0)
    c = pd.concat([reg.loc[["ENGLAND"]], c.drop("No score").iloc[::-1]])  # England at the bottom, Q1 at the top
    labels = ["England"] + [f"{q}\nIMD score {r.replace(' to ', '–')}" for q, r in zip(c.index[1:], c.score_range[1:])]
    coverage_bars(c, labels, "coverage_by_deprivation_2026-08.png",
                  "The most deprived fifth of practices is the least covered, August 2026",
                  "Share of registered patients at open, active practices, by practice deprivation quintile (IMD 2025, equal numbers\n"
                  "of practices per quintile). Region doesn't explain the gap: given its regional mix, Q1 would be at about 86.9%.",
                  "Source: NHS England (CBT; registered patients, 1 Aug 2026); OHID Fingertips indicator 94240 (IMD 2025). "
                  "77 practices with no score (12,197 patients) not shown.")


def coverage_bars(c, labels, filename, title, subtitle, foot):
    included = c.patient_coverage
    agreed_not = c.patients_agreed_not_included / c.patients
    not_agreed = c.patients_not_agreed / c.patients

    fig, ax = plt.subplots(figsize=(10, 5.4))
    fig.subplots_adjust(left=0.22, right=0.83, top=0.76, bottom=0.14)
    y = np.arange(len(c), dtype=float)
    y[1:] += 0.6  # gap between England and the regions
    h = 0.55
    segs = [(included, SERIES[0], "Included in the data"),
            (agreed_not, SERIES[1], "Agreed to take part, no data published"),
            (not_agreed, SERIES[2], "Did not agree to take part")]
    left = np.zeros(len(c))
    for vals, colour, label in segs:
        ax.barh(y, vals, left=left, height=h, color=colour, edgecolor=SURFACE, linewidth=2, label=label)
        left += vals.values
    ax.set_xlim(0, 1)
    ax.set_yticks(y, labels)
    ax.get_yticklabels()[0].set_fontweight("semibold")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    quiet(ax, "x")
    for yi, (name, row) in zip(y, c.iterrows()):
        ax.text(0.015, yi, f"{row.patient_coverage:.1%}", va="center", ha="left", fontsize=9, color="#ffffff",
                fontweight="semibold")
        ax.text(1.015, yi, f"{row.patients_outside / 1e6:.2f}m", va="center", ha="left", fontsize=9, color=INK_2)
    ax.text(1.015, y[-1] + 0.75, "Patients\noutside", va="bottom", ha="left", fontsize=8, color=MUTED)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=3, frameon=False, fontsize=9, handlelength=1, handleheight=1)

    titles(fig, title, subtitle)
    footer(fig, foot)
    fig.savefig(OUT / filename, dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------- 3. monthly trend (small multiples)
def monthly_trend():
    t = pd.read_csv(GOLD / "monthly_trend.csv", parse_dates=["month"])
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True)
    fig.subplots_adjust(left=0.08, right=0.9, top=0.8, bottom=0.12, hspace=0.45)
    panels = [("patient_coverage", "Patient coverage: share of registered patients at included practices",
               lambda v: f"{v:.1%}", (0.7, 0.9)),
              ("calls_per_1000_patients_per_working_day", "Inbound calls per 1,000 patients at included practices, per working weekday",
               lambda v: f"{v:.1f}", (20, 30))]
    for ax, (col, label, fmt, lim) in zip(axes, panels):
        ax.plot(t.month, t[col], color=SERIES[0], linewidth=2, solid_capstyle="round", solid_joinstyle="round")
        ends = t.iloc[[0, -1]]
        ax.scatter(ends.month, ends[col], s=64, color=SERIES[0], edgecolor=SURFACE, linewidth=2, zorder=3)
        for _, r in ends.iterrows():
            ax.annotate(fmt(r[col]), (r.month, r[col]), xytext=(0, 10), textcoords="offset points",
                        ha="center", fontsize=9, color=INK)
        ax.set_ylim(*lim)
        ax.set_title(label, loc="left", fontsize=10, color=INK_2, pad=8)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(
            (lambda v, _: f"{v:.0%}") if col == "patient_coverage" else (lambda v, _: f"{v:.0f}")))
        quiet(ax, "y")
    low = t.loc[t.month >= "2026-07"]
    axes[1].annotate("July–August: lower demand per patient", (low.month.iloc[0], low[panels[1][0]].iloc[0]),
                     xytext=(-150, -28), textcoords="offset points", fontsize=9, color=INK_2,
                     arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=1))
    axes[1].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b\n%Y"))
    titles(fig, "Coverage rising, demand per patient flat until a summer dip: Oct 2025 to Aug 2026",
           "Raw call totals rise as practices join, so demand is shown per 1,000 patients and per working weekday.")
    footer(fig, SOURCE.split(";")[0] + ". Patient denominators from the August 2026 edition (earlier editions were revised). "
           "Nov 2025 calls later revised +0.1%.")
    fig.savefig(OUT / "monthly_trend.png", dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------- 4. outcomes by region
def outcomes_by_region():
    o = pd.read_csv(GOLD / f"outcomes_by_region_{MONTH}.csv", index_col=0)
    o = o.drop(index=[i for i in o.index if i.startswith("UNMAPPED")])
    eng = o.loc[["ENGLAND"]]
    reg = o.drop("ENGLAND").sort_values("neither_answered_nor_missed")
    o = pd.concat([eng, reg])
    segs = [("answered", "Answered by practice staff"), ("ended_in_ivr", "Ended in the automated menu (IVR)"),
            ("callback_requested", "Callback requested"), ("missed", "Missed (incl. voicemail)")]

    fig, ax = plt.subplots(figsize=(10, 5.4))
    fig.subplots_adjust(left=0.22, right=0.97, top=0.74, bottom=0.14)
    y = np.arange(len(o), dtype=float)
    y[1:] += 0.6
    left = np.zeros(len(o))
    for (col, label), colour in zip(segs, SERIES):
        ax.barh(y, o[col], left=left, height=0.55, color=colour, edgecolor=SURFACE, linewidth=2, label=label)
        for yi, l0, v in zip(y, left, o[col]):
            text = f"{v:.1%}"
            if fits(ax, text, v):
                light_fill = colour in (SERIES[2], SERIES[3])
                ax.text(l0 + v / 2, yi, text, ha="center", va="center", fontsize=9,
                        color=INK if light_fill else "#ffffff")
        left += o[col].values
    ax.set_xlim(0, 1.0)
    ax.set_yticks(y, [n.title().replace(" And ", " and ").replace("Of ", "of ") for n in o.index])
    ax.get_yticklabels()[0].set_fontweight("semibold")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    quiet(ax, "x")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=4, frameon=False, fontsize=9, handlelength=1, handleheight=1)
    titles(fig, "What happens to a call: outcomes of inbound calls by region, August 2026",
           "Share of inbound calls. Nearly a third are neither answered nor missed: they end in the automated menu\n"
           "or become a callback request. Regions sorted by that combined share (highest at top).")
    footer(fig, SOURCE.split(";")[0] + ". Includes shared-account calls whose region is known; "
           "outcomes may not sum exactly to inbound (+0.003% nationally).")
    fig.savefig(OUT / "outcomes_by_region_2026-08.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    week_heatmap()
    coverage_by_region()
    coverage_by_deprivation()
    monthly_trend()
    outcomes_by_region()
    for p in sorted(OUT.glob("*.png")):
        print(f"{p.relative_to(REPO)}  ({p.stat().st_size / 1e3:.0f} KB)")
