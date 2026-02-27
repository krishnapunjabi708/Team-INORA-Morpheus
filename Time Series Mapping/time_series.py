"""
FarmMatrix — Time Series Nutrient Mapping
Captures every actual Sentinel-2 satellite overpass between selected dates.
No fixed sampling interval — real visit dates only.
"""

import logging
import os
import warnings
import math
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from io import BytesIO

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from scipy import stats

import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import ee
from openai import OpenAI

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────
GROQ_API_KEY = "grok"
GROQ_MODEL   = "llama-3.3-70b-versatile"

IDEAL_RANGES = {
    "pH":             (6.5,  7.5),
    "Salinity":       (None, 1.0),
    "Organic Carbon": (0.75, 1.50),
    "CEC":            (10,   30),
    "LST":            (15,   35),
    "NDVI":           (0.2,  0.8),
    "EVI":            (0.2,  0.8),
    "FVC":            (0.3,  0.8),
    "NDWI":           (-0.3, 0.2),
    "Nitrogen":       (280,  560),
    "Phosphorus":     (11,   22),
    "Potassium":      (108,  280),
    "Calcium":        (400,  800),
    "Magnesium":      (50,   200),
    "Sulphur":        (10,   40),
}

UNIT_MAP = {
    "pH": "", "Salinity": " mS/cm", "Organic Carbon": " %",
    "CEC": " cmol/kg", "LST": " °C",
    "NDWI": "", "NDVI": "", "EVI": "", "FVC": "",
    "Nitrogen": " kg/ha", "Phosphorus": " kg/ha", "Potassium": " kg/ha",
    "Calcium": " kg/ha", "Magnesium": " kg/ha", "Sulphur": " kg/ha",
}

FULL_NAME = {
    "Soil Health Score": "Overall Soil Health Score (ICAR)",
    "pH":                "Soil pH",
    "Salinity":          "Salinity / EC (mS/cm)",
    "Organic Carbon":    "Organic Carbon (%)",
    "CEC":               "Cation Exchange Capacity (cmol/kg)",
    "LST":               "Land Surface Temperature (°C)",
    "NDVI":              "NDVI — Vegetation Density",
    "EVI":               "EVI — Enhanced Vegetation Index",
    "FVC":               "FVC — Fractional Vegetation Cover",
    "NDWI":              "NDWI — Soil Moisture Index",
    "Nitrogen":          "Nitrogen (kg/ha)",
    "Phosphorus":        "Phosphorus (kg/ha)",
    "Potassium":         "Potassium (kg/ha)",
    "Calcium":           "Calcium (kg/ha)",
    "Magnesium":         "Magnesium (kg/ha)",
    "Sulphur":           "Sulphur (kg/ha)",
}

COLOURS = {
    "Nitrogen": "#1E88E5", "Phosphorus": "#E53935", "Potassium": "#8E24AA",
    "Calcium":  "#FB8C00", "Magnesium":  "#43A047", "Sulphur":   "#F9A825",
    "pH":       "#00ACC1", "Organic Carbon": "#6D4C41", "Salinity": "#EF5350",
    "CEC":      "#546E7A", "LST":        "#FF7043",
    "NDVI":     "#2E7D32", "EVI":        "#388E3C", "FVC": "#81C784", "NDWI": "#1565C0",
}

ALL_PARAMS = ["Soil Health Score"] + list(IDEAL_RANGES.keys())
ALL_BANDS  = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]
DOT_C      = {"good": "#43A047", "low": "#FF9800", "high": "#E53935", "na": "#9E9E9E"}

# ─────────────────────────────────────────────────────────────────────────────
#  EARTH ENGINE INIT
# ─────────────────────────────────────────────────────────────────────────────
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# ─────────────────────────────────────────────────────────────────────────────
#  SATELLITE — get all actual overpass dates in range
# ─────────────────────────────────────────────────────────────────────────────
def get_all_visit_dates(region, start: date, end: date) -> list[date]:
    s = start.strftime("%Y-%m-%d")
    e = end.strftime("%Y-%m-%d")
    try:
        coll = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(s, e)
            .filterBounds(region)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
        )
        dates_ms = coll.aggregate_array("system:time_start").getInfo()
        if not dates_ms:
            return []
        unique_dates = sorted({
            datetime.utcfromtimestamp(ms / 1000).date()
            for ms in dates_ms
        })
        return unique_dates
    except Exception as exc:
        logging.error(f"get_all_visit_dates: {exc}")
        return []


def single_day_composite(region, day: date):
    s = day.strftime("%Y-%m-%d")
    e = (day + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        coll = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(s, e)
            .filterBounds(region)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60))
            .select(ALL_BANDS)
        )
        if coll.size().getInfo() == 0:
            return None
        return coll.median().multiply(0.0001)
    except Exception as exc:
        logging.error(f"single_day_composite {day}: {exc}")
        return None


def get_band_stats(comp, region):
    try:
        raw = comp.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region,
            scale=10, maxPixels=1e13
        ).getInfo()
        return {k: (float(v) if v is not None else 0.0) for k, v in raw.items()}
    except Exception as exc:
        logging.error(f"get_band_stats: {exc}"); return {}


def get_lst(region, day: date):
    s = (day - relativedelta(months=1)).strftime("%Y-%m-%d")
    e = day.strftime("%Y-%m-%d")
    try:
        coll = (
            ee.ImageCollection("MODIS/061/MOD11A2")
            .filterBounds(region.buffer(5000))
            .filterDate(s, e)
            .select("LST_Day_1km")
        )
        if coll.size().getInfo() == 0:
            return None
        img = coll.median().multiply(0.02).subtract(273.15).rename("lst").clip(region.buffer(5000))
        v   = img.reduceRegion(ee.Reducer.mean(), region, 1000, maxPixels=1e13).getInfo().get("lst")
        return float(v) if v is not None else None
    except Exception as exc:
        logging.error(f"get_lst: {exc}"); return None


# ─────────────────────────────────────────────────────────────────────────────
#  NUTRIENT FORMULAS
# ─────────────────────────────────────────────────────────────────────────────
def get_ph(bs):
    b2,b3,b4,b5,b8,b11 = (bs.get(k,0.0) for k in ["B2","B3","B4","B5","B8","B11"])
    ndvi_re = ((b8-b5)/(b8+b5+1e-6)+(b8-b4)/(b8+b4+1e-6))/2.0
    ph = 6.5+1.2*ndvi_re+0.8*b11/(b8+1e-6)-0.5*b8/(b4+1e-6)+0.15*(1.0-(b2+b3+b4)/3.0)
    return max(4.0, min(9.0, ph))

def get_organic_carbon(bs):
    b2,b3,b4,b5,b8,b11,b12 = (bs.get(k,0.0) for k in ["B2","B3","B4","B5","B8","B11","B12"])
    ndvi_re = ((b8-b5)/(b8+b5+1e-6)+(b8-b4)/(b8+b4+1e-6))/2.0
    L=0.5; savi=((b8-b4)/(b8+b4+L+1e-6))*(1+L)
    evi=2.5*(b8-b4)/(b8+6*b4-7.5*b2+1+1e-6)
    return max(0.1, min(5.0, 1.2+3.5*ndvi_re+2.2*savi-1.5*(b11+b12)/2.0+0.4*evi))

def get_salinity(bs):
    b2,b3,b4,b8 = (bs.get(k,0.0) for k in ["B2","B3","B4","B8"])
    ndvi=(b8-b4)/(b8+b4+1e-6)
    si=((b3*b4)**0.5+(b3**2+b4**2)**0.5)/2.0 if (b3**2+b4**2)>0 else 0.0
    return max(0.0, min(16.0, 0.5+abs(si)*4.0+(1.0-max(0,min(1,ndvi)))*2.0+0.3*(1.0-(b2+b3+b4)/3.0)))

def get_cec(comp, region):
    try:
        clay = comp.expression("(B11-B8)/(B11+B8+1e-6)",
                               {"B11": comp.select("B11"), "B8": comp.select("B8")}).rename("clay")
        om   = comp.expression("(B8-B4)/(B8+B4+1e-6)",
                               {"B8": comp.select("B8"),  "B4": comp.select("B4")}).rename("om")
        c_m  = clay.reduceRegion(ee.Reducer.mean(), region, 20, maxPixels=1e13).get("clay").getInfo()
        o_m  = om.reduceRegion(ee.Reducer.mean(),   region, 20, maxPixels=1e13).get("om").getInfo()
        if c_m is None or o_m is None: return None
        return 5.0+20.0*float(c_m)+15.0*float(o_m)
    except Exception as exc:
        logging.error(f"get_cec: {exc}"); return None

def get_ndvi(bs):
    b8,b4 = bs.get("B8",0), bs.get("B4",0)
    return (b8-b4)/(b8+b4+1e-6)

def get_evi(bs):
    b8,b4,b2 = bs.get("B8",0), bs.get("B4",0), bs.get("B2",0)
    return 2.5*(b8-b4)/(b8+6*b4-7.5*b2+1+1e-6)

def get_fvc(bs):
    return max(0.0, min(1.0, ((get_ndvi(bs)-0.2)/0.6)**2))

def get_ndwi(bs):
    b3,b8 = bs.get("B3",0), bs.get("B8",0)
    return (b3-b8)/(b3+b8+1e-6)

def get_npk(bs):
    b2,b3,b4,b5,b6,b7,b8,b8a,b11,b12 = (bs.get(k,0.0)
        for k in ["B2","B3","B4","B5","B6","B7","B8","B8A","B11","B12"])
    ndvi=(b8-b4)/(b8+b4+1e-6); evi=2.5*(b8-b4)/(b8+6*b4-7.5*b2+1+1e-6)
    br=(b2+b3+b4)/3.0; ndre=(b8a-b5)/(b8a+b5+1e-6)
    ci_re=(b7/(b5+1e-6))-1.0; mcari=((b5-b4)-0.2*(b5-b3))*(b5/(b4+1e-6))
    N=max(50, min(600, 280+300*ndre+150*evi+20*(ci_re/5)-80*br+30*mcari))
    si=((b3*b4)**0.5+(b3**2+b4**2)**0.5)/2.0 if (b3**2+b4**2)>0 else 0.0
    P=max(2,  min(60,  11+15*(1-br)+6*ndvi+4*abs(si)+2*b3))
    K=max(40, min(600, 150+200*b11/(b5+b6+1e-6)+80*(b11-b12)/(b11+b12+1e-6)+60*ndvi))
    return float(N), float(P), float(K)

def get_calcium(bs):
    b2,b3,b4,b8,b11,b12 = (bs.get(k,0.0) for k in ["B2","B3","B4","B8","B11","B12"])
    Ca=550+250*(b11+b12)/(b4+b3+1e-6)+150*(b2+b3+b4)/3-100*(b8-b4)/(b8+b4+1e-6)-80*(b11-b8)/(b11+b8+1e-6)
    return max(100.0, min(1200.0, float(Ca)))

def get_magnesium(bs):
    b4,b5,b7,b8,b8a,b11,b12 = (bs.get(k,0.0) for k in ["B4","B5","B7","B8","B8A","B11","B12"])
    Mg=110+60*(b8a-b5)/(b8a+b5+1e-6)+40*((b7/(b5+1e-6))-1)+30*(b11-b12)/(b11+b12+1e-6)+20*(b8-b4)/(b8+b4+1e-6)
    return max(10.0, min(400.0, float(Mg)))

def get_sulphur(bs):
    b2,b3,b4,b5,b8,b11,b12 = (bs.get(k,0.0) for k in ["B2","B3","B4","B5","B8","B11","B12"])
    si=((b3*b4)**0.5+(b3**2+b4**2)**0.5)/2.0 if (b3**2+b4**2)>0 else 0.0
    S=20+15*b11/(b3+b4+1e-6)+10*abs(si)+5*(b5/(b4+1e-6)-1)-8*b12/(b11+1e-6)+5*(b8-b4)/(b8+b4+1e-6)
    return max(2.0, min(80.0, float(S)))


# ─────────────────────────────────────────────────────────────────────────────
#  STATUS & HEALTH SCORE
# ─────────────────────────────────────────────────────────────────────────────
def _is_valid(value):
    if value is None: return False
    try:
        return not (pd.isna(value) or not pd.api.types.is_number(value))
    except Exception:
        return False

def param_status(param, value):
    if not _is_valid(value): return "na"
    value = float(value)
    lo, hi = IDEAL_RANGES.get(param, (None, None))
    if lo is None: return "good" if value <= hi else "high"
    if hi is None: return "good" if value >= lo else "low"
    return "low" if value < lo else ("high" if value > hi else "good")

def health_score(snap: dict) -> float:
    valid = [(p, v) for p, v in snap.items() if _is_valid(v)]
    if not valid: return 0.0
    good = sum(1 for p, v in valid if param_status(p, v) == "good")
    return (good / len(valid)) * 100.0


# ─────────────────────────────────────────────────────────────────────────────
#  FETCH — one snapshot per actual satellite visit date
# ─────────────────────────────────────────────────────────────────────────────
def fetch_snapshot(region, day: date) -> dict | None:
    comp = single_day_composite(region, day)
    if comp is None: return None
    bs = get_band_stats(comp, region)
    if not bs: return None
    N, P, K = get_npk(bs)
    return {
        "pH":             get_ph(bs),
        "Organic Carbon": get_organic_carbon(bs),
        "Salinity":       get_salinity(bs),
        "CEC":            get_cec(comp, region),
        "LST":            get_lst(region, day),
        "NDVI":           get_ndvi(bs),
        "EVI":            get_evi(bs),
        "FVC":            get_fvc(bs),
        "NDWI":           get_ndwi(bs),
        "Nitrogen":       N,
        "Phosphorus":     P,
        "Potassium":      K,
        "Calcium":        get_calcium(bs),
        "Magnesium":      get_magnesium(bs),
        "Sulphur":        get_sulphur(bs),
    }


def fetch_all_visits(region, visit_dates: list, pb, status_el) -> pd.DataFrame:
    records = []
    total   = len(visit_dates)
    for i, day in enumerate(visit_dates):
        status_el.markdown(
            f"⏳ **Pass {i+1}/{total}** — {day.strftime('%d %b %Y')}  "
            f"*(Sentinel-2 actual overpass)*"
        )
        snap = fetch_snapshot(region, day)
        row  = {
            "date": pd.Timestamp(day),
            **(snap if snap else {p: None for p in IDEAL_RANGES})
        }
        records.append(row)
        pb.progress((i + 1) / total)

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
#  CHARTS
# ─────────────────────────────────────────────────────────────────────────────
def chart_health_score(df: pd.DataFrame) -> BytesIO | None:
    clean = df[df["date"].notna()].copy()
    if clean.empty: return None

    scores, dates, dots = [], [], []
    for _, row in clean.iterrows():
        snap = {p: row.get(p) for p in IDEAL_RANGES}
        sc   = health_score(snap)
        scores.append(sc)
        dates.append(row["date"])
        dots.append(
            "#43A047" if sc >= 80 else
            "#8BC34A" if sc >= 60 else
            "#FF9800" if sc >= 40 else "#E53935"
        )

    fig, ax = plt.subplots(figsize=(12, 5))
    for lo, hi, label, bg in [
        (80, 100, "Excellent ≥80%", "#E8F5E9"),
        (60,  80, "Good  60–79%",   "#F1F8E9"),
        (40,  60, "Fair  40–59%",   "#FFF8E1"),
        (0,   40, "Poor  <40%",     "#FFEBEE"),
    ]:
        ax.axhspan(lo, hi, color=bg, alpha=0.70, zorder=0)
        ax.text(0.012, (lo+hi)/2, label, va="center", ha="left",
                transform=ax.get_yaxis_transform(),
                fontsize=8, color="#777", style="italic")

    ax.fill_between(dates, scores, alpha=0.10, color="#2E7D32", zorder=1)
    ax.plot(dates, scores, color="#2E7D32", lw=2.2, zorder=2)
    for dt, sc, co in zip(dates, scores, dots):
        ax.scatter(dt, sc, color=co, s=75, zorder=4, edgecolors="white", lw=1.0)
        ax.annotate(f"{sc:.0f}%", (dt, sc),
                    xytext=(0, 11), textcoords="offset points",
                    fontsize=8, ha="center", color="#333", fontweight="bold")

    if len(scores) >= 3:
        x = np.arange(len(scores), dtype=float)
        s_, i_, *_ = stats.linregress(x, scores)
        ax.plot(dates, s_*x+i_, color="#555", lw=1.2, ls="--", alpha=0.5, label="Trend")
        ax.legend(fontsize=8, loc="lower right", framealpha=0.6)

    ax.set_ylim(0, 115)
    ax.set_ylabel("Health Score (%)", fontsize=9)
    ax.set_title("Overall Soil Health Score — Every Sentinel-2 Pass (ICAR Standard)",
                 fontsize=11, fontweight="bold", pad=10)
    ax.tick_params(axis="x", labelrotation=35, labelsize=8)
    ax.spines[["top","right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.2, linestyle="--")
    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def chart_single_param(df: pd.DataFrame, param: str) -> BytesIO | None:
    if param not in df.columns: return None

    tmp = df[df["date"].notna()].copy()
    tmp = tmp[tmp[param].apply(_is_valid)].copy()
    if tmp.empty: return None

    tmp["_val"] = tmp[param].apply(float)
    tmp = tmp.sort_values("date").reset_index(drop=True)
    clean_dates = tmp["date"].values
    clean_vals  = tmp["_val"].values.astype(float)

    colour = COLOURS.get(param, "#1565C0")
    lo, hi = IDEAL_RANGES.get(param, (None, None))
    y_lo   = lo if lo is not None else float(clean_vals.min()) * 0.85
    y_hi   = hi if hi is not None else float(clean_vals.max()) * 1.15

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.axhspan(y_lo, y_hi, color="#E8F5E9", alpha=0.55, zorder=0, label="ICAR ideal range")
    ax.axhline(y_lo, color="#81C784", lw=0.9, ls="--", alpha=0.7, zorder=1)
    ax.axhline(y_hi, color="#81C784", lw=0.9, ls="--", alpha=0.7, zorder=1)

    ax.fill_between(clean_dates, clean_vals, alpha=0.08, color=colour, zorder=1)
    ax.plot(clean_dates, clean_vals, color=colour, lw=2.2, zorder=3)

    for dt, val in zip(clean_dates, clean_vals):
        ax.scatter(dt, val, color=DOT_C[param_status(param, val)],
                   s=65, zorder=5, edgecolors="white", lw=1.0)
        ax.annotate(f"{val:.2f}{UNIT_MAP.get(param,'')}",
                    (dt, val), xytext=(0, 11), textcoords="offset points",
                    fontsize=7.5, ha="center", color="#333")

    if len(clean_vals) >= 3:
        x = np.arange(len(clean_vals), dtype=float)
        s_, i_, *_ = stats.linregress(x, clean_vals)
        ax.plot(clean_dates, s_*x+i_, color="#555", lw=1.1, ls=":",
                alpha=0.6, zorder=2, label="Trend")

    pct = 0.0
    if len(clean_vals) >= 2:
        pct = (clean_vals[-1]-clean_vals[0]) / (abs(clean_vals[0])+1e-9) * 100
    arrow = "↑" if pct > 1 else ("↓" if pct < -1 else "→")
    direction = "Increasing" if pct > 1 else ("Decreasing" if pct < -1 else "Stable")

    ax.set_title(f"{FULL_NAME.get(param, param)}",
                 fontsize=11, fontweight="bold", pad=10)
    ax.set_xlabel(f"Trend: {arrow} {direction}  ({pct:+.1f}% over period)  ·  "
                  f"Each point = one Sentinel-2 satellite pass",
                  fontsize=8.5, labelpad=6, color="#555")
    ax.set_ylabel(f"Value{UNIT_MAP.get(param,'')}", fontsize=9)
    ax.tick_params(axis="x", labelrotation=35, labelsize=8)
    ax.spines[["top","right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.2, linestyle="--")

    ax.legend(
        handles=[
            Line2D([0],[0], color=colour, lw=2.2, label=param),
            Line2D([0],[0], color="#555", lw=1.1, ls=":", label="Trend"),
            mpatches.Patch(facecolor="#E8F5E9", label="ICAR ideal range"),
        ],
        fontsize=8, loc="upper left", framealpha=0.65
    )
    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────────────
#  AI — FOCUSED on selected parameter only
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are Dr. Arjun Patil, a Senior Soil Scientist and Precision Agriculture Specialist
with 30 years of field experience working with smallholder farmers across India
(Maharashtra, Punjab, Karnataka, Andhra Pradesh, Tamil Nadu).

You combine deep knowledge of:
• Soil chemistry and ICAR soil health standards
• Satellite remote sensing (Sentinel-2, MODIS) interpretation
• Indian crop calendars (Kharif / Rabi / Zaid seasons)
• Locally available, affordable fertilizer inputs
• Practical ground-level farming advice

Your communication style:
• Clear, simple language — no jargon
• Bullet points for easy reading
• Specific product names, doses per acre, timing
• Empathetic — you understand farmers' financial constraints
• Always prioritize soil long-term health, not just quick fixes

Format your response using EXACTLY the section structure given in the user prompt.
Use ✅ ⚠️ 🔴 🟡 🟢 emojis to make status instantly visible.
""".strip()


def build_focused_prompt(df: pd.DataFrame, location: str, period: str,
                         n_passes: int, selected_param: str) -> str:
    """Build a prompt focused ONLY on the selected parameter's time-series insights."""
    today      = date.today()
    month_name = today.strftime("%B %Y")
    mo         = today.month
    season     = ("Kharif — Monsoon Season (Jun–Oct)"   if 6 <= mo <= 10 else
                  "Rabi — Winter Season (Nov–Mar)"       if (mo >= 11 or mo <= 3) else
                  "Zaid — Summer Season (Mar–May)")

    # ── Build time-series data for selected param ──
    if selected_param == "Soil Health Score":
        # Compute health scores per date
        ts_rows = []
        for _, row in df.iterrows():
            snap = {p: row.get(p) for p in IDEAL_RANGES}
            sc   = health_score(snap)
            ts_rows.append({"date": row["date"], "value": sc})
        ts_df  = pd.DataFrame(ts_rows).dropna()
        param_label = "Overall Soil Health Score (%)"
        lo, hi = 60.0, 100.0
        unit   = "%"
    else:
        if selected_param not in df.columns:
            return ""
        ts_df = df[["date", selected_param]].copy()
        ts_df = ts_df[ts_df[selected_param].apply(_is_valid)].rename(columns={selected_param: "value"})
        param_label = FULL_NAME.get(selected_param, selected_param)
        lo, hi = IDEAL_RANGES.get(selected_param, (None, None))
        unit   = UNIT_MAP.get(selected_param, "")

    if ts_df.empty:
        return ""

    vals = [float(v) for v in ts_df["value"]]
    dates_str = [pd.Timestamp(d).strftime("%d %b %Y") for d in ts_df["date"]]

    time_series_str = "\n".join(
        f"  Pass {i+1} ({d}): {v:.3f}{unit}"
        for i, (d, v) in enumerate(zip(dates_str, vals))
    )

    first, last, avg = vals[0], vals[-1], sum(vals)/len(vals)
    peak  = max(vals); trough = min(vals)
    pct   = (last - first) / (abs(first) + 1e-9) * 100
    trend = "RISING" if pct > 3 else ("FALLING" if pct < -3 else "STABLE")

    if selected_param != "Soil Health Score":
        current_status = param_status(selected_param, last)
        status_icon = {"good": "🟢 WITHIN RANGE", "low": "🟡 BELOW IDEAL",
                       "high": "🔴 ABOVE IDEAL", "na": "⚪ NO DATA"}[current_status]
    else:
        status_icon = ("🟢 GOOD" if last >= 60 else "🟡 FAIR" if last >= 40 else "🔴 POOR")

    ideal_str = (f"{lo}–{hi}{unit}" if (lo is not None and hi is not None) else
                 (f"≤{hi}{unit}"    if lo is None else f"≥{lo}{unit}"))

    return f"""
SATELLITE TIME-SERIES ADVISORY REQUEST
════════════════════════════════════════════════════════
Location       : {location}
Period         : {period}
Satellite      : Sentinel-2 (ESA Copernicus) + MODIS (NASA)
Total passes   : {n_passes} actual satellite overpasses
Current date   : {month_name}
Season         : {season}
════════════════════════════════════════════════════════

SELECTED PARAMETER FOR ANALYSIS
  Parameter    : {param_label}
  ICAR ideal   : {ideal_str}
  Current value: {last:.3f}{unit}  →  {status_icon}
  Period avg   : {avg:.3f}{unit}
  Peak value   : {peak:.3f}{unit}
  Lowest value : {trough:.3f}{unit}
  Change       : {pct:+.1f}%  →  {trend}

TIME-SERIES DATA (one row per satellite pass)
──────────────────────────────────────────────────────────────────────
{time_series_str}
──────────────────────────────────────────────────────────────────────

════════════════════════════════════════════════════════
GENERATE A FOCUSED ADVISORY FOR THIS PARAMETER IN EXACTLY THIS FORMAT:
════════════════════════════════════════════════════════

## 📊 {param_label} — Satellite Time-Series Insight

### 🔍 What the Data Shows
(2–3 bullets describing the trend pattern across the satellite passes — plain language)
• ...
• ...

---

### ⚠️ Current Status & Risk
**Status: {status_icon}**
- **What this means for your crop:** (one line — direct impact)
- **Why it may have changed:** (one line — likely cause based on trend)
- **Risk if not addressed:** (one line)

---

### ✅ Recommended Action
(Exactly 3 specific, affordable steps — product name, dose per acre, timing)
1. **[Action]** — [what, product, dose/acre, when]
2. ...
3. ...

---

### 📅 Watch Points
- **Next check date:** [specific date 15–20 days from now]
- **Warning sign to watch for:** [one observable field sign]
- **Target value to reach:** [specific number with unit]

---
*Based on {n_passes} Sentinel-2 passes · ICAR standards · FarmMatrix*

RULES:
- Focus ONLY on {selected_param} — do not discuss other parameters
- Explain trends across the time-series (not just the latest value)
- Use only locally available Indian inputs
- Doses per acre only
- Keep total length 200–280 words
- No jargon — write for a farmer with 8th grade education
"""


# ─────────────────────────────────────────────────────────────────────────────
#  GROQ CALL
# ─────────────────────────────────────────────────────────────────────────────
def call_groq(prompt: str) -> str | None:
    try:
        client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        resp   = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system",  "content": SYSTEM_PROMPT},
                {"role": "user",    "content": prompt},
            ],
            max_tokens=800,
            temperature=0.30,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logging.error(f"Groq API: {exc}"); return None


# ═══════════════════════════════════════════════════════════════════════════════
#  STREAMLIT APP
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="FarmMatrix · Time Series", layout="wide", page_icon="🌾")

st.markdown(
    "<h1 style='margin-bottom:4px'>🌾 FarmMatrix — Satellite Nutrient Tracking</h1>"
    "<p style='color:#888;margin-top:0'>"
    "Every Sentinel-2 overpass captured · ICAR-aligned · AI soil scientist advisory"
    "</p>",
    unsafe_allow_html=True
)
st.markdown("---")

# ── Dynamic defaults: end = today, start = 1 month ago ───────────────────────
today         = date.today()
default_end   = today
default_start = today - relativedelta(months=1)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📍 Field Location")
    if "loc" not in st.session_state:
        st.session_state.loc = [18.4575, 73.8503]
    lat = st.number_input("Latitude",  value=st.session_state.loc[0], format="%.6f")
    lon = st.number_input("Longitude", value=st.session_state.loc[1], format="%.6f")
    st.session_state.loc = [lat, lon]

    st.markdown("---")
    st.header("📅 Date Range")
    st.caption(
        f"Default: last 30 days  "
        f"({default_start.strftime('%d %b')} → {default_end.strftime('%d %b %Y')})"
    )

    start_date = st.date_input("Start Date", value=default_start,
                               max_value=today - timedelta(days=1))
    end_date   = st.date_input("End Date",   value=default_end,
                               max_value=today)

    if start_date >= end_date:
        st.error("Start date must be before End date.")
        st.stop()

    st.markdown("---")
    st.header("🗺️ Display Parameter")
    st.caption("Default: Soil Health Score — overall ICAR rating")

    selected_param = st.selectbox(
        "Select what to plot",
        ALL_PARAMS,
        index=0,
        format_func=lambda x: FULL_NAME.get(x, x),
    )


# ── Map ───────────────────────────────────────────────────────────────────────
st.subheader("1️⃣  Draw Your Field on the Map")
st.caption(
    "Use the **polygon** or **rectangle** tool (left toolbar).  "
    "Draw around your field — analysis will start automatically."
)

m = folium.Map(location=[lat, lon], zoom_start=15)
Draw(export=True).add_to(m)
folium.TileLayer(
    "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    attr="Google Satellite"
).add_to(m)
folium.Marker([lat, lon], popup="Centre", tooltip="Centre").add_to(m)
map_data = st_folium(m, width=None, height=460,
                     returned_objects=["last_active_drawing"])

region = None
if map_data and map_data.get("last_active_drawing"):
    try:
        coords = map_data["last_active_drawing"]["geometry"]["coordinates"]
        region = ee.Geometry.Polygon(coords)
        st.success("✅ Field polygon detected — running satellite analysis automatically...")
    except Exception as exc:
        st.error(f"Polygon error: {exc}")

# ── Auto-run when polygon detected ───────────────────────────────────────────
if region is not None:
    # Only re-fetch if polygon/dates changed (use a hash as cache key)
    cache_key = f"{str(map_data.get('last_active_drawing'))}_{start_date}_{end_date}"

    if st.session_state.get("_cache_key") != cache_key:
        st.session_state["_cache_key"] = cache_key

        with st.spinner("🛰️ Scanning for Sentinel-2 satellite passes over your field..."):
            visit_dates = get_all_visit_dates(region, start_date, end_date)

        if not visit_dates:
            st.error(
                "No Sentinel-2 data found for this region and date range. "
                "Try extending the date range or choosing a different area."
            )
            st.stop()

        st.info(
            f"🛰️ Found **{len(visit_dates)} satellite passes** "
            f"between {start_date.strftime('%d %b')} and {end_date.strftime('%d %b %Y')}  —  "
            f"fetching nutrients for each pass..."
        )

        pb     = st.progress(0)
        status = st.empty()
        df     = fetch_all_visits(region, visit_dates, pb, status)
        status.empty()

        st.session_state["df"]          = df
        st.session_state["location"]    = f"Lat {lat:.5f}, Lon {lon:.5f}"
        st.session_state["period"]      = (f"{start_date.strftime('%d %b %Y')} "
                                           f"to {end_date.strftime('%d %b %Y')}")
        st.session_state["n_passes"]    = len(visit_dates)
        st.session_state["visit_dates"] = [d.strftime("%d %b %Y") for d in visit_dates]


# ── Results ───────────────────────────────────────────────────────────────────
if "df" in st.session_state:
    df        = st.session_state["df"]
    loc       = st.session_state["location"]
    per       = st.session_state["period"]
    n_passes  = st.session_state["n_passes"]
    vdates    = st.session_state["visit_dates"]

    st.markdown("---")

    # ── Pass summary strip ─────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("🛰️ Satellite Passes", n_passes)
    with col_b:
        st.metric("📅 Period", per)
    with col_c:
        latest_score = None
        if not df.empty:
            last_row = df.dropna(subset=list(IDEAL_RANGES.keys()), how="all").iloc[-1] if not df.empty else None
            if last_row is not None:
                snap = {p: last_row.get(p) for p in IDEAL_RANGES}
                latest_score = health_score(snap)
        if latest_score is not None:
            rating = ("Excellent" if latest_score >= 80 else
                      "Good"      if latest_score >= 60 else
                      "Fair"      if latest_score >= 40 else "Poor")
            st.metric("🌱 Latest Health Score", f"{latest_score:.0f}% — {rating}")

    with st.expander(f"📋 Show all {n_passes} satellite pass dates"):
        st.write("  ·  ".join(vdates))

    st.markdown("---")

    # ── Chart ─────────────────────────────────────────────────────────────────
    st.markdown(f"### 📊 {FULL_NAME.get(selected_param, selected_param)}")

    if selected_param == "Soil Health Score":
        buf = chart_health_score(df)
    else:
        buf = chart_single_param(df, selected_param)

    if buf:
        st.image(buf, use_container_width=True)
    else:
        st.info(f"No usable data for **{selected_param}** in this period and region.")

    st.caption(
        "🟢 Green dot = Within ICAR ideal range  ·  "
        "🟡 Orange dot = Below ideal  ·  "
        "🔴 Red dot = Above ideal  ·  "
        "🟩 Green band = ICAR ideal range  ·  "
        "Each dot = one actual satellite overpass"
    )

    # ── AI Advisory — focused on selected parameter ────────────────────────────
    st.markdown("---")
    st.markdown(f"### 🤖 AI Insight — {FULL_NAME.get(selected_param, selected_param)}")
    st.caption(
        "Dr. Arjun Patil · Senior Soil Scientist · 30 years field experience  |  "
        "Powered by Groq LLaMA 3.3-70B · ICAR-calibrated · For guidance only"
    )

    with st.spinner(f"📝 Analysing {selected_param} trends across {n_passes} satellite passes..."):
        prompt  = build_focused_prompt(df, loc, per, n_passes, selected_param)
        insight = call_groq(prompt) if prompt else None

    if insight:
        st.markdown(insight)
    else:
        st.warning(
            "⚠️ AI report could not be generated.  "
            "Check your Groq API key or internet connection."
        )

st.markdown("---")
st.caption(
    "FarmMatrix · Sentinel-2 (ESA Copernicus) + MODIS (NASA) · "
    "ICAR Soil Health Card Standards"
)