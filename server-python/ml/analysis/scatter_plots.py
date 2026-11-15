"""Scatter plots of weather against later pest levels, as the 2026-10 panel
asked: "convert the datasets into scatter plots to explore relationships
between variables, identify trends, and examine how weather conditions and
pest indicators relate to one another."

Each point is one (municipality, 14-day window): the x-axis is a weather
summary over that window, the y-axis is the pest value FORECAST_HORIZON_DAYS
after it ends. That is the same lag the BiLSTM forecasts at, so the plots
show the relationship the model is actually asked to learn, not a same-day
correlation it never uses. Points are coloured by the growth stage on the
window's last day, because SHAP ranks growth stage as the strongest driver
for both pests and colouring by it shows whether a weather trend survives
once stage is accounted for.

RSB uses the stage-matched indicator, as the model does: dead hearts while
vegetative, white ears while reproductive.

Each panel is annotated with Spearman's rho (rank correlation, since the pest
targets are heavily right-skewed). A table of all rho values, overall and
within each growth stage, is written alongside the figures.

Needs matplotlib, which is not a server dependency. Run it with any Python
that has pandas, scipy and matplotlib, from server-python/:
    PYTHONPATH=. python -m ml.analysis.scatter_plots

Output: ml/analysis/figures/*.png and ml/analysis/figures/correlations.csv
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from ml.config import CLEAN_DAILY_CSV, FORECAST_HORIZON_DAYS, GROWTH_STAGE_BUCKETS, PEST_PARAMS

OUT_DIR = Path(__file__).resolve().parent / "figures"
WINDOW = PEST_PARAMS["BPH"].crf_window_days

STAGE_ORDER = ["Seedling", "Tillering", "Elongation", "Panicle", "Flowering", "Ripening"]
STAGE_COLOURS = {
    "Seedling": "#9ccc65",
    "Tillering": "#2e7d32",
    "Elongation": "#00838f",
    "Panicle": "#5e35b1",
    "Flowering": "#f9a825",
    "Ripening": "#c62828",
}

WEATHER = [
    ("tmax_mean", "Max temperature, 14-day mean (°C)"),
    ("tmin_mean", "Min temperature, 14-day mean (°C)"),
    ("rh_mean", "Relative humidity, 14-day mean (%)"),
    ("rain_sum", "Rainfall, 14-day total (mm)"),
]


def build_windows() -> pd.DataFrame:
    df = pd.read_csv(CLEAN_DAILY_CSV, parse_dates=["Date"]).sort_values(["Municipality", "Date"])
    rows = []
    for municipality, g in df.groupby("Municipality"):
        g = g.reset_index(drop=True)
        roll = pd.DataFrame(
            {
                "tmax_mean": g["Tmax"].rolling(WINDOW).mean(),
                "tmin_mean": g["Tmin"].rolling(WINDOW).mean(),
                "rh_mean": g["Relative_Humidity"].rolling(WINDOW).mean(),
                "rain_sum": g["Rainfall"].rolling(WINDOW).sum(),
            }
        )
        stage = g["Rice_Growth_Stage"]
        bucket = stage.map(GROWTH_STAGE_BUCKETS)
        ahead = g.shift(-FORECAST_HORIZON_DAYS)
        rsb = np.where(bucket == "Reproductive", ahead["RSB_White_Ears_Pct"], ahead["RSB_Dead_Hearts_Pct"])
        rows.append(
            roll.assign(
                municipality=municipality,
                stage=stage,
                bph_ahead=ahead["BPH_Hoppers_per_Hill"],
                rsb_ahead=rsb,
            )
        )
    return pd.concat(rows).dropna().reset_index(drop=True)


def scatter_grid(windows: pd.DataFrame, target: str, ylabel: str, title: str, path: Path) -> None:
    fig, axes = plt.subplots(1, len(WEATHER), figsize=(5 * len(WEATHER), 4.6), sharey=True)
    for ax, (col, xlabel) in zip(axes, WEATHER):
        for stage in STAGE_ORDER:
            sub = windows[windows["stage"] == stage]
            ax.scatter(sub[col], sub[target], s=5, alpha=0.35, color=STAGE_COLOURS[stage], label=stage, linewidths=0)
        rho, p = spearmanr(windows[col], windows[target])
        ax.set_title(f"Spearman ρ = {rho:+.2f}" + ("" if p < 0.001 else f"  (p={p:.3f})"), fontsize=10)
        ax.set_xlabel(xlabel, fontsize=9)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel(ylabel, fontsize=9)
    handles = [plt.Line2D([], [], marker="o", ls="", color=STAGE_COLOURS[s], label=s) for s in STAGE_ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=len(STAGE_ORDER), frameon=False, fontsize=9, title="Growth stage at window end")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0.1, 1, 0.94))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def stage_box(windows: pd.DataFrame, path: Path) -> None:
    """Pest level 14 days ahead by growth stage: the relationship SHAP says
    dominates, shown directly."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for ax, (target, label) in zip(axes, [("bph_ahead", "BPH, hoppers per hill"), ("rsb_ahead", "RSB, % damage (stage-matched)")]):
        data = [windows.loc[windows["stage"] == s, target] for s in STAGE_ORDER]
        box = ax.boxplot(data, tick_labels=STAGE_ORDER, showfliers=False, patch_artist=True)
        for patch, s in zip(box["boxes"], STAGE_ORDER):
            patch.set_facecolor(STAGE_COLOURS[s])
            patch.set_alpha(0.55)
        ax.set_title(label, fontsize=10)
        ax.set_ylabel(f"Value {FORECAST_HORIZON_DAYS} days after window", fontsize=9)
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(alpha=0.25, axis="y")
    fig.suptitle("Pest level by growth stage at window end", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def correlation_table(windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for target in ["bph_ahead", "rsb_ahead"]:
        for col, _ in WEATHER:
            for stage in ["All"] + STAGE_ORDER:
                sub = windows if stage == "All" else windows[windows["stage"] == stage]
                rho, p = spearmanr(sub[col], sub[target])
                rows.append(
                    {"pest": target.split("_")[0].upper(), "weather": col, "stage": stage, "n": len(sub), "spearman_rho": round(rho, 3), "p_value": p}
                )
    return pd.DataFrame(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    windows = build_windows()
    print(f"{len(windows)} windows across {windows['municipality'].nunique()} municipalities")

    scatter_grid(
        windows,
        "bph_ahead",
        f"BPH hoppers per hill, {FORECAST_HORIZON_DAYS} days later",
        f"Brown planthopper: 14-day weather vs. population {FORECAST_HORIZON_DAYS} days later",
        OUT_DIR / "bph_weather_scatter.png",
    )
    scatter_grid(
        windows,
        "rsb_ahead",
        f"RSB % damage, {FORECAST_HORIZON_DAYS} days later",
        f"Rice stem borer: 14-day weather vs. damage {FORECAST_HORIZON_DAYS} days later",
        OUT_DIR / "rsb_weather_scatter.png",
    )
    stage_box(windows, OUT_DIR / "pest_by_growth_stage.png")

    table = correlation_table(windows)
    table.to_csv(OUT_DIR / "correlations.csv", index=False)
    overall = table[table["stage"] == "All"].pivot(index="weather", columns="pest", values="spearman_rho")
    print("\nSpearman rho, all windows:\n" + overall.to_string())
    print(f"\nSaved figures and correlations.csv to {OUT_DIR}")


if __name__ == "__main__":
    main()
