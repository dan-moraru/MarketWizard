import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os

# --- 1. Configuration & Paths ---
# Base directory for the data as requested
DATA_DIR = "/home/carter/Dev/Hacks/mchacks13/frontend/market-wizard/public/data"

# --- 2. NBC Branding Setup ---
NBC_RED = "#E31837"
NBC_BLACK = "#000000"
NBC_GREY = "#7F7F7F"
NBC_LIGHT_GREY = "#F2F2F2"
NBC_COLORS = [NBC_RED, NBC_BLACK, NBC_GREY, "#005670", "#8B0000"]

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.prop_cycle"] = plt.cycler(color=NBC_COLORS)


def setup_nbc_style(ax, title, xlabel, ylabel):
    """Applies National Bank of Canada styling to a matplotlib axis."""
    ax.set_title(
        title, fontsize=16, fontweight="bold", color=NBC_BLACK, loc="left", pad=15
    )
    ax.set_xlabel(xlabel, fontsize=12, fontweight="bold", color=NBC_GREY)
    ax.set_ylabel(ylabel, fontsize=12, fontweight="bold", color=NBC_GREY)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(NBC_GREY)
    ax.spines["bottom"].set_color(NBC_GREY)
    ax.tick_params(axis="both", colors=NBC_GREY)
    ax.grid(axis="y", linestyle="--", alpha=0.3, color=NBC_GREY)


# --- 3. Data Loading ---
pnl_files = {
    "Normal Market": "normal_market_pnl.csv",
    "Flash Crash": "flash_crash_pnl.csv",
    "Stressed Market": "stressed_market_pnl.csv",
    "Mini Flash Crash": "mini_flash_crash_pnl.csv",
    "HFT Dominated": "hft_dominated_pnl.csv",
}

trade_files = {
    "Normal Market": "received_trades_team_alpha_normal_market.csv",
    "Flash Crash": "received_trades_team_alpha_flash_crash.csv",
    "Stressed Market": "received_trades_team_alpha_stressed_market.csv",
    "Mini Flash Crash": "received_trades_team_alpha_mini_flash_crash.csv",
    "HFT Dominated": "received_trades_team_alpha_hft_dominated.csv",
}


def load_data(file_map):
    data = {}
    for name, filename in file_map.items():
        path = os.path.join(DATA_DIR, filename)
        try:
            data[name] = pd.read_csv(path)
            print(f"Loaded {name}")
        except FileNotFoundError:
            print(f"Warning: File not found at {path}")
        except Exception as e:
            print(f"Error loading {path}: {e}")
    return data


# Load Data
print("Loading PnL Data...")
pnl_data = load_data(pnl_files)
print("Loading Trade Data...")
trade_data = load_data(trade_files)

# --- 4. Visual Generation ---

# Visual A: All Scenarios PnL
fig1, ax1 = plt.subplots(figsize=(12, 6))
for name, df in pnl_data.items():
    # Dynamic styling for clarity
    if name == "Normal Market":
        style_kwargs = {
            "color": NBC_GREY,
            "alpha": 0.5,
            "linewidth": 2,
            "linestyle": "--",
            "zorder": 1,
        }
    elif name == "Flash Crash":
        style_kwargs = {
            "color": NBC_RED,
            "alpha": 1.0,
            "linewidth": 3,
            "linestyle": "-",
            "zorder": 5,
        }
    elif name == "Mini Flash Crash":
        style_kwargs = {
            "color": "#8B0000",
            "alpha": 0.8,
            "linewidth": 2,
            "linestyle": "-",
            "zorder": 4,
        }
    elif name == "Stressed Market":
        style_kwargs = {
            "color": NBC_BLACK,
            "alpha": 0.7,
            "linewidth": 1.5,
            "linestyle": "-",
            "zorder": 3,
        }
    else:
        style_kwargs = {
            "color": "#005670",
            "alpha": 0.6,
            "linewidth": 1.5,
            "linestyle": "-",
            "zorder": 2,
        }

    ax1.plot(df["step"], df["pnl"], label=name, **style_kwargs)

setup_nbc_style(
    ax1, "Fund Performance: Scenario Stress Testing", "Time Step", "Cumulative PnL ($)"
)
ax1.legend(frameon=False, loc="upper left", bbox_to_anchor=(1, 1))
plt.tight_layout()
plt.savefig("nbc_pnl_all_scenarios.png")
print("Saved nbc_pnl_all_scenarios.png")

# Visual B: Liquidity Comparison
fig2, ax2 = plt.subplots(figsize=(12, 5))
scenarios_to_plot = ["Normal Market", "Stressed Market", "Flash Crash"]
colors = [NBC_GREY, NBC_BLACK, NBC_RED]

for name, color in zip(scenarios_to_plot, colors):
    if name in trade_data:
        df = trade_data[name]
        # Rolling average for smoother lines
        rolling_spread = df["spread"].rolling(window=100).mean()
        ax2.plot(
            df["step"],
            rolling_spread,
            label=name,
            color=color,
            linewidth=1.5,
            alpha=0.9,
        )

setup_nbc_style(ax2, "Liquidity Crunch: Bid-Ask Spreads", "Time Step", "Spread ($)")
ax2.legend(frameon=False)
plt.tight_layout()
plt.savefig("nbc_liquidity_comparison.png")
print("Saved nbc_liquidity_comparison.png")

# Visual C: Price Impact (Flash Crash vs Mini)
fig3, ax3 = plt.subplots(figsize=(12, 5))
if "Flash Crash" in trade_data:
    df = trade_data["Flash Crash"]
    df = df[df["mid"] > 1]  # Filter valid
    start_p = df["mid"].iloc[0]
    ax3.plot(
        df["step"],
        df["mid"] / start_p * 100,
        color=NBC_RED,
        linewidth=2,
        label="Major Flash Crash",
    )

if "Mini Flash Crash" in trade_data:
    df = trade_data["Mini Flash Crash"]
    df = df[df["mid"] > 1]
    start_p = df["mid"].iloc[0]
    ax3.plot(
        df["step"],
        df["mid"] / start_p * 100,
        color=NBC_BLACK,
        linewidth=1.5,
        linestyle="--",
        label="Mini Flash Crash",
    )

setup_nbc_style(
    ax3, "Price Impact Analysis (Rebased to 100)", "Time Step", "Asset Price"
)
ax3.legend(frameon=False)
plt.tight_layout()
plt.savefig("nbc_price_impact.png")
print("Saved nbc_price_impact.png")

# Visual D: Summary Card
fig4, ax4 = plt.subplots(figsize=(12, 4))
ax4.axis("off")
# Header
ax4.add_patch(plt.Rectangle((0, 0.8), 1, 0.2, transform=ax4.transAxes, color=NBC_RED))
ax4.text(
    0.02,
    0.87,
    "FUND FACT SHEET: STRESS TEST METRICS",
    transform=ax4.transAxes,
    color="white",
    fontsize=18,
    fontweight="bold",
    va="center",
)

stats = []
if "Normal Market" in pnl_data:
    stats.append(
        ("Normal Return", f"${pnl_data['Normal Market']['pnl'].iloc[-1]:,.0f}")
    )
if "Flash Crash" in pnl_data:
    stats.append(("Flash Crash DD", f"${pnl_data['Flash Crash']['pnl'].min():,.0f}"))
if "Stressed Market" in trade_data:
    stats.append(
        ("Stress Spread", f"{trade_data['Stressed Market']['spread'].mean():.2f}")
    )
if "HFT Dominated" in pnl_data:
    stats.append(("HFT Volatility", f"{pnl_data['HFT Dominated']['pnl'].std():.1f}"))

for i, (label, val) in enumerate(stats):
    ax4.text(
        0.05 + i * 0.22,
        0.5,
        val,
        transform=ax4.transAxes,
        fontsize=24,
        fontweight="bold",
        color=NBC_BLACK,
    )
    ax4.text(
        0.05 + i * 0.22,
        0.35,
        label,
        transform=ax4.transAxes,
        fontsize=11,
        color=NBC_GREY,
    )

plt.tight_layout()
plt.savefig("nbc_full_summary.png")
print("Saved nbc_full_summary.png")

