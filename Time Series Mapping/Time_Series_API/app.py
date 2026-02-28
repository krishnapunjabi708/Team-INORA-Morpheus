import os
import json
import logging
import warnings
import asyncio
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from io import BytesIO
import base64

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from scipy import stats

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Any
import uvicorn
import ee
from openai import OpenAI

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
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

ALL_BANDS = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]
DOT_C     = {"good": "#43A047", "low": "#FF9800", "high": "#E53935", "na": "#9E9E9E"}

# ─────────────────────────────────────────────────────────────────────────────
#  EARTH ENGINE INIT
# ─────────────────────────────────────────────────────────────────────────────
def initialize_ee():
    global ee_initialized
    try:
        credentials_base64 = os.getenv("GEE_SERVICE_ACCOUNT_KEY")
        if not credentials_base64:
            raise ValueError("GEE_SERVICE_ACCOUNT_KEY env var is missing.")
        credentials_json_str = base64.b64decode(credentials_base64).decode("utf-8")
        credentials_dict = json.loads(credentials_json_str)
        from ee import ServiceAccountCredentials
        credentials = ServiceAccountCredentials(
            credentials_dict["client_email"], key_data=credentials_json_str
        )
        ee.Initialize(credentials)
        ee_initialized = True
        logging.info("✅ Google Earth Engine initialized successfully.")
    except Exception as e:
        ee_initialized = False
        logging.error(f"❌ GEE initialization failed: {e}")
        raise

initialize_ee()

# ─────────────────────────────────────────────────────────────────────────────
#  SATELLITE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def get_all_visit_dates(region, start: date, end: date) -> list:
    try:
        coll = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
            .filterBounds(region)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
        )
        dates_ms = coll.aggregate_array("system:time_start").getInfo()
        if not dates_ms:
            return []
        return sorted({datetime.utcfromtimestamp(ms / 1000).date() for ms in dates_ms})
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
        logging.error(f"get_band_stats: {exc}")
        return {}


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
        logging.error(f"get_lst: {exc}")
        return None


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
                               {"B8": comp.select("B8"), "B4": comp.select("B4")}).rename("om")
        c_m  = clay.reduceRegion(ee.Reducer.mean(), region, 20, maxPixels=1e13).get("clay").getInfo()
        o_m  = om.reduceRegion(ee.Reducer.mean(),   region, 20, maxPixels=1e13).get("om").getInfo()
        if c_m is None or o_m is None: return None
        return 5.0+20.0*float(c_m)+15.0*float(o_m)
    except Exception as exc:
        logging.error(f"get_cec: {exc}")
        return None

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
#  FETCH SNAPSHOT
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


# ─────────────────────────────────────────────────────────────────────────────
#  SHARED: fetch snapshots → sorted DataFrame
#  (called by both endpoints to avoid code duplication)
# ─────────────────────────────────────────────────────────────────────────────
async def _build_dataframe(req_coordinates, req_start, req_end) -> tuple:
    """
    Returns (region, visit_dates, df) or raises HTTPException.
    """
    loop = asyncio.get_event_loop()
    try:
        start  = datetime.strptime(req_start, "%Y-%m-%d").date()
        end    = datetime.strptime(req_end,   "%Y-%m-%d").date()
        region = ee.Geometry.Polygon(req_coordinates)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}")

    visit_dates = await loop.run_in_executor(None, get_all_visit_dates, region, start, end)
    if not visit_dates:
        raise HTTPException(
            status_code=404,
            detail=(
                "No Sentinel-2 passes found for this region and date range. "
                "Try a wider date range or verify the coordinates."
            ),
        )

    records = []
    for day in visit_dates:
        snap = await loop.run_in_executor(None, fetch_snapshot, region, day)
        records.append({
            "date": day.strftime("%Y-%m-%d"),
            **(snap if snap else {p: None for p in IDEAL_RANGES}),
        })

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return region, visit_dates, df


# ─────────────────────────────────────────────────────────────────────────────
#  CHART RENDERERS  (return raw PNG bytes)
# ─────────────────────────────────────────────────────────────────────────────
def _fig_to_png(fig) -> bytes:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def render_health_score_chart(df: pd.DataFrame) -> bytes | None:
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
    return _fig_to_png(fig)


def render_param_chart(df: pd.DataFrame, param: str) -> bytes | None:
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
    arrow     = "↑" if pct > 1 else ("↓" if pct < -1 else "→")
    direction = "Increasing" if pct > 1 else ("Decreasing" if pct < -1 else "Stable")

    ax.set_title(f"{FULL_NAME.get(param, param)}", fontsize=11, fontweight="bold", pad=10)
    ax.set_xlabel(
        f"Trend: {arrow} {direction}  ({pct:+.1f}% over period)  ·  "
        f"Each point = one Sentinel-2 satellite pass",
        fontsize=8.5, labelpad=6, color="#555"
    )
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
    return _fig_to_png(fig)


# ─────────────────────────────────────────────────────────────────────────────
#  AI ADVISORY
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
    today      = date.today()
    month_name = today.strftime("%B %Y")
    mo         = today.month
    season     = ("Kharif — Monsoon Season (Jun–Oct)"  if 6 <= mo <= 10 else
                  "Rabi — Winter Season (Nov–Mar)"      if (mo >= 11 or mo <= 3) else
                  "Zaid — Summer Season (Mar–May)")

    if selected_param == "Soil Health Score":
        ts_rows = []
        for _, row in df.iterrows():
            snap = {p: row.get(p) for p in IDEAL_RANGES}
            sc   = health_score(snap)
            ts_rows.append({"date": row["date"], "value": sc})
        ts_df       = pd.DataFrame(ts_rows).dropna()
        param_label = "Overall Soil Health Score (%)"
        lo, hi      = 60.0, 100.0
        unit        = "%"
    else:
        if selected_param not in df.columns:
            return ""
        ts_df = df[["date", selected_param]].copy()
        ts_df = ts_df[ts_df[selected_param].apply(_is_valid)].rename(
            columns={selected_param: "value"}
        )
        param_label = FULL_NAME.get(selected_param, selected_param)
        lo, hi      = IDEAL_RANGES.get(selected_param, (None, None))
        unit        = UNIT_MAP.get(selected_param, "")

    if ts_df.empty:
        return ""

    vals      = [float(v) for v in ts_df["value"]]
    dates_str = [pd.Timestamp(d).strftime("%d %b %Y") for d in ts_df["date"]]
    time_series_str = "\n".join(
        f"  Pass {i+1} ({d}): {v:.3f}{unit}"
        for i, (d, v) in enumerate(zip(dates_str, vals))
    )

    first, last, avg = vals[0], vals[-1], sum(vals)/len(vals)
    peak   = max(vals); trough = min(vals)
    pct    = (last - first) / (abs(first) + 1e-9) * 100
    trend  = "RISING" if pct > 3 else ("FALLING" if pct < -3 else "STABLE")

    if selected_param != "Soil Health Score":
        current_status = param_status(selected_param, last)
        status_icon = {"good": "🟢 WITHIN RANGE", "low": "🟡 BELOW IDEAL",
                       "high": "🔴 ABOVE IDEAL", "na": "⚪ NO DATA"}[current_status]
    else:
        status_icon = ("🟢 GOOD" if last >= 60 else "🟡 FAIR" if last >= 40 else "🔴 POOR")

    ideal_str = (f"{lo}–{hi}{unit}" if (lo is not None and hi is not None) else
                 (f"≤{hi}{unit}" if lo is None else f"≥{lo}{unit}"))

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
GENERATE A FOCUSED ADVISORY IN EXACTLY THIS FORMAT:
📊 {param_label} — Satellite Time-Series Insight
🔍 What the Data Shows
• ...
• ...
---
⚠️ Current Status & Risk
Status: {status_icon}
- What this means for your crop: (one line)
- Why it may have changed: (one line)
- Risk if not addressed: (one line)
---
✅ Recommended Action
1. [Action] — [what, product, dose/acre, when]
2. ...
3. ...
---
📅 Watch Points
- Next check date: [specific date 15–20 days from now]
- Warning sign to watch for: [one observable field sign]
- Target value to reach: [specific number with unit]
---
Based on {n_passes} Sentinel-2 passes · ICAR standards · FarmMatrix
RULES:
- Focus ONLY on {selected_param}
- Use only locally available Indian inputs
- Doses per acre only
- Keep total length 200–280 words
"""


def call_groq(prompt: str) -> str | None:
    try:
        client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        resp   = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=800,
            temperature=0.30,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logging.error(f"Groq API: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  FASTAPI APP
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="FarmMatrix API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Shared request model ─────────────────────────────────────────────────────
class AnalyseRequest(BaseModel):
    """
    Used by BOTH /api/analyse  and  /api/chart — same body, different response.
    coordinates   : GeoJSON polygon ring — list of [longitude, latitude] pairs.
                    First and last point must be identical (closed ring).
                    Example: [[73.85,18.52],[73.86,18.52],[73.86,18.53],
                               [73.85,18.53],[73.85,18.52]]
    start_date    : "YYYY-MM-DD"
    end_date      : "YYYY-MM-DD"
    selected_param: One of:
                    "Soil Health Score" | "pH" | "Salinity" | "Organic Carbon" |
                    "CEC" | "LST" | "NDVI" | "EVI" | "FVC" | "NDWI" |
                    "Nitrogen" | "Phosphorus" | "Potassium" |
                    "Calcium" | "Magnesium" | "Sulphur"
    location      : Human-readable farm/location name (appears in AI advisory).
    """
    coordinates:    List[List[Any]]
    start_date:     str
    end_date:       str
    selected_param: str = "Soil Health Score"
    location:       str = "Unknown Location"


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "FarmMatrix", "version": "3.0.0"}


# ── Frontend ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read())


# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINT 1 — /api/analyse
#  Response: JSON  (meta + summary + time_series + ai_insight)
#  NO image in this response.
# ═════════════════════════════════════════════════════════════════════════════
@app.post("/api/analyse")
async def api_analyse(req: AnalyseRequest):
    """
    Runs the full satellite data pipeline and returns structured JSON:
    {
      "meta":        { location, period, n_passes, pass_dates, selected_param },
      "summary":     { health_score, rating, params: { <param>: {value, status, unit, label} } },
      "time_series": { records: [...], pass_scores: [{date, health_score}] },
      "ai_insight":  { text, param, model }
    }
    Does NOT include a chart image — call /api/chart for the PNG.
    Typical response time: 2–8 min.
    """
    loop = asyncio.get_event_loop()

    _, visit_dates, df = await _build_dataframe(
        req.coordinates, req.start_date, req.end_date
    )
    n_passes = len(visit_dates)
    period   = f"{req.start_date} to {req.end_date}"

    # Latest-pass summary
    last_row    = df.dropna(subset=list(IDEAL_RANGES.keys()), how="all").iloc[-1]
    snap_latest = {p: last_row.get(p) for p in IDEAL_RANGES}
    hs          = health_score(snap_latest)
    rating      = ("Excellent" if hs >= 80 else "Good" if hs >= 60 else "Fair" if hs >= 40 else "Poor")

    params_summary: dict = {}
    for p in IDEAL_RANGES:
        v = snap_latest.get(p)
        params_summary[p] = {
            "value":  round(float(v), 3) if _is_valid(v) else None,
            "status": param_status(p, v),
            "unit":   UNIT_MAP.get(p, ""),
            "label":  FULL_NAME.get(p, p),
        }

    # Per-pass health scores
    pass_scores = []
    for _, row in df.iterrows():
        s = {p: row.get(p) for p in IDEAL_RANGES}
        pass_scores.append({
            "date":         row["date"].strftime("%Y-%m-%d"),
            "health_score": round(health_score(s), 1),
        })

    # AI advisory
    prompt     = build_focused_prompt(df, req.location, period, n_passes, req.selected_param)
    ai_insight = None
    if prompt:
        ai_insight = await loop.run_in_executor(None, call_groq, prompt)

    # Serialise records (dates → strings)
    records_out = []
    for _, row in df.iterrows():
        r = {"date": row["date"].strftime("%Y-%m-%d")}
        for p in IDEAL_RANGES:
            v = row.get(p)
            r[p] = round(float(v), 4) if _is_valid(v) else None
        records_out.append(r)

    return {
        "meta": {
            "location":       req.location,
            "period":         period,
            "n_passes":       n_passes,
            "pass_dates":     [d.strftime("%Y-%m-%d") for d in visit_dates],
            "selected_param": req.selected_param,
        },
        "summary": {
            "health_score": round(hs, 1),
            "rating":       rating,
            "params":       params_summary,
        },
        "time_series": {
            "records":     records_out,
            "pass_scores": pass_scores,
        },
        "ai_insight": {
            "text":  ai_insight,
            "param": req.selected_param,
            "model": GROQ_MODEL,
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINT 2 — /api/chart
#  Response: raw PNG image (Content-Type: image/png)
#  NO JSON in this response.
# ═════════════════════════════════════════════════════════════════════════════
@app.post("/api/chart")
async def api_chart(req: AnalyseRequest):
    """
    Runs the same satellite data pipeline, then renders and returns a PNG chart
    directly as the response body (Content-Type: image/png).
    • In Postman: go to the response area → click "Visualize" tab to see the image,
      or save it via "Save Response → Save to a file".
    • In a browser / frontend: use as <img src="..."> after fetching.
    selected_param = "Soil Health Score"  → overall health-score-over-time chart
    selected_param = any other param      → that parameter's time-series chart
    Typical response time: 2–8 min.
    """
    loop = asyncio.get_event_loop()

    _, visit_dates, df = await _build_dataframe(
        req.coordinates, req.start_date, req.end_date
    )

    # Render PNG
    if req.selected_param == "Soil Health Score":
        png_bytes = await loop.run_in_executor(None, render_health_score_chart, df)
    else:
        png_bytes = await loop.run_in_executor(None, render_param_chart, df, req.selected_param)

    if not png_bytes:
        raise HTTPException(
            status_code=404,
            detail=f"No chart data available for parameter '{req.selected_param}'."
        )

    filename = f"farmmatrix_{req.selected_param.replace(' ', '_')}.png"
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            # inline → Postman Visualize tab shows it; attachment → triggers download
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-FarmMatrix-Param":  req.selected_param,
            "X-FarmMatrix-Passes": str(len(visit_dates)),
            "X-FarmMatrix-Period": f"{req.start_date} to {req.end_date}",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)