import logging
import os
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import pandas as pd
from folium.plugins import Draw
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfgen import canvas
from io import BytesIO
from openai import OpenAI

# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
GROQ_API_KEY = "grok-api"
GROQ_MODEL   = "llama-3.3-70b-versatile"
LOGO_PATH    = os.path.abspath("LOGO.jpg")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ─────────────────────────────────────────────
#  Google Earth Engine init
# ─────────────────────────────────────────────
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# ─────────────────────────────────────────────
#  Constants & Lookups
# ─────────────────────────────────────────────
SOIL_TEXTURE_IMG = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0')
TEXTURE_CLASSES = {
    1: "Clay", 2: "Silty Clay", 3: "Sandy Clay",
    4: "Clay Loam", 5: "Silty Clay Loam", 6: "Sandy Clay Loam",
    7: "Loam", 8: "Silty Loam", 9: "Sandy Loam",
    10: "Silt", 11: "Loamy Sand", 12: "Sand"
}

# ── ICAR / Indian Soil Health Card Standard Ranges ───────────────────────────
IDEAL_RANGES = {
    "pH":             (6.5, 7.5),
    "Soil Texture":   7,
    "Salinity":       (None, 1.0),
    "Organic Carbon": (0.75, 1.50),
    "CEC":            (10, 30),
    "LST":            (15, 35),
    "NDVI":           (0.2, 0.8),
    "EVI":            (0.2, 0.8),
    "FVC":            (0.3, 0.8),
    "NDWI":           (-0.3, 0.2),
    "Nitrogen":       (280, 560),
    "Phosphorus":     (11, 22),
    "Potassium":      (108, 280),
    # ── New parameters ──────────────────────────────────────────────────────
    # Calcium (Ca): ICAR range 400–800 kg/ha exchangeable Ca
    "Calcium":        (400, 800),
    # Magnesium (Mg): ICAR range 50–200 kg/ha exchangeable Mg
    "Magnesium":      (50, 200),
    # Sulphur (S): ICAR range 10–40 kg/ha available SO4-S
    "Sulphur":        (10, 40),
}

IDEAL_DISPLAY = {
    "pH": "6.5–7.5", "Salinity": "<=1.0 mS/cm",
    "Organic Carbon": "0.75–1.50 %", "CEC": "10–30 cmol/kg",
    "Soil Texture": "Loam", "LST": "15–35 C",
    "NDWI": "-0.3–0.2", "NDVI": "0.2–0.8",
    "EVI": "0.2–0.8",   "FVC": "0.3–0.8",
    "Nitrogen": "280–560 kg/ha", "Phosphorus": "11–22 kg/ha",
    "Potassium": "108–280 kg/ha",
    "Calcium":   "400–800 kg/ha",
    "Magnesium": "50–200 kg/ha",
    "Sulphur":   "10–40 kg/ha",
}

UNIT_MAP = {
    "pH": "", "Salinity": " mS/cm", "Organic Carbon": " %",
    "CEC": " cmol/kg", "Soil Texture": "", "LST": " C",
    "NDWI": "", "NDVI": "", "EVI": "", "FVC": "",
    "Nitrogen": " kg/ha", "Phosphorus": " kg/ha", "Potassium": " kg/ha",
    "Calcium": " kg/ha", "Magnesium": " kg/ha", "Sulphur": " kg/ha",
}

# ── Farmer-friendly parameter suggestions (ICAR-based) ───────────────────────
SUGGESTIONS = {
    "pH": {
        "good": "Apply lime once every 2–3 years to maintain pH. Avoid excess urea.",
        "low":  "Apply agricultural lime 2–4 bags/acre. Avoid acidifying fertilisers.",
        "high": "Add gypsum or sulphur 5–10 kg/acre. Use ammonium sulphate fertiliser.",
    },
    "Salinity": {
        "good": "Continue drip irrigation and avoid waterlogging to keep EC low.",
        "high": "Flush field with extra irrigation. Apply gypsum 200 kg/acre. Grow barley or salt-tolerant crops.",
    },
    "Organic Carbon": {
        "good": "Add 2 tonnes FYM/compost per acre yearly to maintain OC.",
        "low":  "Apply FYM 4–5 tonnes/acre. Do green manuring with dhaincha or sunhemp.",
        "high": "Balance with good tillage. If waterlogged, improve drainage.",
    },
    "CEC": {
        "good": "Maintain OC and avoid over-tilling to keep CEC stable.",
        "low":  "Add compost or clay amendments to improve nutrient holding.",
        "high": "Keep pH in range so nutrients stay plant-available.",
    },
    "LST": {
        "good": "Use mulching to keep soil temperature stable.",
        "low":  "Use black polythene mulch to warm soil. Delay sowing.",
        "high": "Apply straw mulch to cool soil. Increase irrigation frequency.",
    },
    "NDVI": {
        "good": "Maintain crop density and fertilisation schedule.",
        "low":  "Check for pest or disease. Apply balanced NPK as per soil test.",
        "high": "Monitor for lodging risk. Ensure good drainage.",
    },
    "EVI": {
        "good": "Continue current crop management.",
        "low":  "Apply foliar micronutrient spray: zinc sulphate + boron.",
        "high": "Ensure good aeration. Watch for fungal disease.",
    },
    "FVC": {
        "good": "Maintain ground cover to reduce erosion and moisture loss.",
        "low":  "Increase plant population or use intercropping. Control weeds.",
        "high": "Monitor water use — dense cover may mask moisture stress.",
    },
    "NDWI": {
        "good": "Maintain current irrigation schedule.",
        "low":  "Irrigate immediately. Switch to drip or sprinkler if possible.",
        "high": "Reduce irrigation. Check drainage to avoid waterlogging.",
    },
    "Nitrogen": {
        "good": "Apply urea in split doses (basal + top-dress) to avoid losses.",
        "low":  "Apply urea 25–30 kg/acre or DAP. Consider green manure crop.",
        "high": "Skip nitrogen this season. Use neem-coated urea next time.",
    },
    "Phosphorus": {
        "good": "Apply SSP or DAP at low maintenance dose during sowing.",
        "low":  "Apply DAP 12 kg/acre or SSP 50 kg/acre at sowing.",
        "high": "Skip phosphorus this season. Apply zinc sulphate 5 kg/acre.",
    },
    "Potassium": {
        "good": "Apply MOP at low maintenance dose every 2nd season.",
        "low":  "Apply MOP 8–10 kg/acre. Add wood ash as organic source.",
        "high": "Skip potassium this season. Watch for Mg deficiency symptoms.",
    },
    # ── New suggestions ──────────────────────────────────────────────────────
    "Calcium": {
        "good": "Maintain pH 6.5–7.5 to keep Ca available. Apply lime every 2–3 years.",
        "low":  "Apply agricultural lime (CaCO3) 200–400 kg/acre. Check soil pH and raise if acidic.",
        "high": "Avoid additional lime. Excess Ca may lock out Mg and K — monitor those levels.",
    },
    "Magnesium": {
        "good": "Apply dolomite lime (contains Mg) during routine pH correction.",
        "low":  "Apply dolomite limestone 50–100 kg/acre or magnesium sulphate (Kieserite) 10 kg/acre.",
        "high": "Excess Mg competes with Ca and K. Improve drainage. Avoid Mg-containing fertilisers.",
    },
    "Sulphur": {
        "good": "Use SSP fertiliser (contains S) at sowing to maintain levels.",
        "low":  "Apply gypsum (CaSO4) 50 kg/acre or elemental sulphur 5–10 kg/acre. Good for oilseeds and pulses.",
        "high": "Reduce sulphate-containing fertilisers. Check EC — high S may indicate salt accumulation.",
    },
}

ALL_BANDS = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]

# ─────────────────────────────────────────────
#  Utility helpers
# ─────────────────────────────────────────────
def safe_get_info(computed_obj, name="value"):
    if computed_obj is None:
        return None
    try:
        info = computed_obj.getInfo()
        return float(info) if info is not None else None
    except Exception as e:
        logging.warning(f"Failed to fetch {name}: {e}")
        return None


def sentinel_composite(region, start, end, bands):
    start_str = start.strftime("%Y-%m-%d")
    end_str   = end.strftime("%Y-%m-%d")
    try:
        coll = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(start_str, end_str)
            .filterBounds(region)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
            .select(bands)
        )
        if coll.size().getInfo() > 0:
            return coll.median().multiply(0.0001)
        for days in range(5, 31, 5):
            sd = (start - timedelta(days=days)).strftime("%Y-%m-%d")
            ed = (end   + timedelta(days=days)).strftime("%Y-%m-%d")
            coll = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterDate(sd, ed)
                .filterBounds(region)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
                .select(bands)
            )
            if coll.size().getInfo() > 0:
                logging.info(f"Sentinel window expanded to {sd} to {ed}")
                return coll.median().multiply(0.0001)
        logging.warning("No Sentinel-2 data available.")
        return None
    except Exception as e:
        logging.error(f"Error in sentinel_composite: {e}")
        return None


def get_band_stats(comp, region, scale=10):
    try:
        stats = comp.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region,
            scale=scale, maxPixels=1e13
        ).getInfo()
        return {k: (float(v) if v is not None else 0.0) for k, v in stats.items()}
    except Exception as e:
        logging.error(f"Error in get_band_stats: {e}")
        return {}


# ─────────────────────────────────────────────
#  LST
# ─────────────────────────────────────────────
def get_lst(region, start, end):
    end_dt   = end
    start_dt = end_dt - relativedelta(months=1)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str   = end_dt.strftime("%Y-%m-%d")
    try:
        coll = (
            ee.ImageCollection("MODIS/061/MOD11A2")
            .filterBounds(region.buffer(5000))
            .filterDate(start_str, end_str)
            .select("LST_Day_1km")
        )
        if coll.size().getInfo() == 0:
            return None
        img   = coll.median().multiply(0.02).subtract(273.15).rename("lst").clip(region.buffer(5000))
        stats = img.reduceRegion(reducer=ee.Reducer.mean(), geometry=region, scale=1000, maxPixels=1e13).getInfo()
        val   = stats.get("lst")
        return float(val) if val is not None else None
    except Exception as e:
        logging.error(f"Error in get_lst: {e}")
        return None


# ─────────────────────────────────────────────
#  Soil Texture
# ─────────────────────────────────────────────
def get_soil_texture(region):
    try:
        mode = SOIL_TEXTURE_IMG.clip(region.buffer(500)).reduceRegion(
            ee.Reducer.mode(), geometry=region, scale=250, maxPixels=1e13
        ).get("b0")
        val = safe_get_info(mode, "texture")
        return int(val) if val is not None else None
    except Exception as e:
        logging.error(f"Error in get_soil_texture: {e}")
        return None


# ─────────────────────────────────────────────
#  pH
# ─────────────────────────────────────────────
def get_ph_new(bs):
    try:
        b2  = bs.get("B2",  0.0)
        b3  = bs.get("B3",  0.0)
        b4  = bs.get("B4",  0.0)
        b5  = bs.get("B5",  0.0)
        b8  = bs.get("B8",  0.0)
        b11 = bs.get("B11", 0.0)

        ndvi_re_avg = ((b8 - b5) / (b8 + b5 + 1e-6) + (b8 - b4) / (b8 + b4 + 1e-6)) / 2.0
        swir_ratio  = b11 / (b8 + 1e-6)
        nir_ratio   = b8  / (b4 + 1e-6)
        brightness  = (b2 + b3 + b4) / 3.0

        pH_est = (6.5 + 1.2 * ndvi_re_avg + 0.8 * swir_ratio
                  - 0.5 * nir_ratio + 0.15 * (1.0 - brightness))
        return max(4.0, min(9.0, pH_est))
    except Exception as e:
        logging.error(f"Error in get_ph_new: {e}")
        return None


# ─────────────────────────────────────────────
#  Organic Carbon
# ─────────────────────────────────────────────
def get_organic_carbon_pct(bs):
    try:
        b2  = bs.get("B2",  0.0)
        b3  = bs.get("B3",  0.0)
        b4  = bs.get("B4",  0.0)
        b5  = bs.get("B5",  0.0)
        b8  = bs.get("B8",  0.0)
        b11 = bs.get("B11", 0.0)
        b12 = bs.get("B12", 0.0)

        ndvi_re_avg = ((b8 - b5) / (b8 + b5 + 1e-6) + (b8 - b4) / (b8 + b4 + 1e-6)) / 2.0
        L    = 0.5
        savi = ((b8 - b4) / (b8 + b4 + L + 1e-6)) * (1 + L)
        evi  = 2.5 * (b8 - b4) / (b8 + 6 * b4 - 7.5 * b2 + 1 + 1e-6)
        swir_avg = (b11 + b12) / 2.0

        oc_pct = 1.2 + 3.5 * ndvi_re_avg + 2.2 * savi - 1.5 * swir_avg + 0.4 * evi
        return max(0.1, min(5.0, oc_pct))
    except Exception as e:
        logging.error(f"Error in get_organic_carbon_pct: {e}")
        return None


# ─────────────────────────────────────────────
#  Salinity
# ─────────────────────────────────────────────
def get_salinity_ec(bs):
    try:
        b2  = bs.get("B2",  0.0)
        b3  = bs.get("B3",  0.0)
        b4  = bs.get("B4",  0.0)
        b8  = bs.get("B8",  0.0)
        b11 = bs.get("B11", 0.0)
        b12 = bs.get("B12", 0.0)

        ndvi              = (b8 - b4) / (b8 + b4 + 1e-6)
        brightness        = (b2 + b3 + b4) / 3.0
        si1               = (b3 * b4) ** 0.5
        si2               = (b3 ** 2 + b4 ** 2) ** 0.5 if (b3 ** 2 + b4 ** 2) > 0 else 0.0
        si_combined       = (si1 + si2) / 2.0
        vegetation_stress = 1.0 - max(0.0, min(1.0, ndvi))

        ec = 0.5 + abs(si_combined) * 4.0 + vegetation_stress * 2.0 + 0.3 * (1.0 - brightness)
        return max(0.0, min(16.0, ec))
    except Exception as e:
        logging.error(f"Error in get_salinity_ec: {e}")
        return None


# ─────────────────────────────────────────────
#  CEC
# ─────────────────────────────────────────────
def estimate_cec(comp, region, intercept, slope_clay, slope_om):
    if comp is None:
        return None
    try:
        clay = comp.expression("(B11-B8)/(B11+B8+1e-6)",
                               {"B11": comp.select("B11"), "B8": comp.select("B8")}).rename("clay")
        om   = comp.expression("(B8-B4)/(B8+B4+1e-6)",
                               {"B8": comp.select("B8"), "B4": comp.select("B4")}).rename("om")
        c_m = safe_get_info(clay.reduceRegion(ee.Reducer.mean(), geometry=region, scale=20, maxPixels=1e13).get("clay"), "clay")
        o_m = safe_get_info(om.reduceRegion(ee.Reducer.mean(),   geometry=region, scale=20, maxPixels=1e13).get("om"),   "om")
        if c_m is None or o_m is None:
            return None
        return intercept + slope_clay * c_m + slope_om * o_m
    except Exception as e:
        logging.error(f"Error in estimate_cec: {e}")
        return None


# ─────────────────────────────────────────────
#  Vegetation indices
# ─────────────────────────────────────────────
def get_ndvi(bs):
    b8, b4 = bs.get("B8", 0.0), bs.get("B4", 0.0)
    return (b8 - b4) / (b8 + b4 + 1e-6)

def get_evi(bs):
    b8, b4, b2 = bs.get("B8", 0.0), bs.get("B4", 0.0), bs.get("B2", 0.0)
    return 2.5 * (b8 - b4) / (b8 + 6 * b4 - 7.5 * b2 + 1 + 1e-6)

def get_fvc(bs):
    ndvi = get_ndvi(bs)
    return max(0.0, min(1.0, ((ndvi - 0.2) / (0.8 - 0.2)) ** 2))

def get_ndwi(bs):
    b3, b8 = bs.get("B3", 0.0), bs.get("B8", 0.0)
    return (b3 - b8) / (b3 + b8 + 1e-6)


# ─────────────────────────────────────────────
#  NPK
# ─────────────────────────────────────────────
def get_npk_kgha(bs):
    try:
        b2  = bs.get("B2",  0.0)
        b3  = bs.get("B3",  0.0)
        b4  = bs.get("B4",  0.0)
        b5  = bs.get("B5",  0.0)
        b6  = bs.get("B6",  0.0)
        b7  = bs.get("B7",  0.0)
        b8  = bs.get("B8",  0.0)
        b8a = bs.get("B8A", 0.0)
        b11 = bs.get("B11", 0.0)
        b12 = bs.get("B12", 0.0)

        ndvi       = (b8  - b4)  / (b8  + b4  + 1e-6)
        evi        = 2.5 * (b8 - b4) / (b8 + 6 * b4 - 7.5 * b2 + 1 + 1e-6)
        brightness = (b2 + b3 + b4) / 3.0
        ndre       = (b8a - b5) / (b8a + b5 + 1e-6)
        ci_re      = (b7 / (b5 + 1e-6)) - 1.0
        mcari      = ((b5 - b4) - 0.2 * (b5 - b3)) * (b5 / (b4 + 1e-6))

        N_kgha = (280.0
                  + 300.0 * ndre
                  + 150.0 * evi
                  + 20.0  * (ci_re / 5.0)
                  - 80.0  * brightness
                  + 30.0  * mcari)
        N_kgha = max(50.0, min(600.0, N_kgha))

        si1    = (b3 * b4) ** 0.5
        si2    = (b3 ** 2 + b4 ** 2) ** 0.5 if (b3 ** 2 + b4 ** 2) > 0 else 0.0
        mndbsi = (si1 + si2) / 2.0

        P_kgha = (11.0
                  + 15.0 * (1.0 - brightness)
                  + 6.0  * ndvi
                  + 4.0  * abs(mndbsi)
                  + 2.0  * b3)
        P_kgha = max(2.0, min(60.0, P_kgha))

        potassium_index = b11 / (b5 + b6 + 1e-6)
        salinity_factor = (b11 - b12) / (b11 + b12 + 1e-6)

        K_kgha = (150.0
                  + 200.0 * potassium_index
                  + 80.0  * salinity_factor
                  + 60.0  * ndvi)
        K_kgha = max(40.0, min(600.0, K_kgha))

        return float(N_kgha), float(P_kgha), float(K_kgha)
    except Exception as e:
        logging.error(f"Error in get_npk_kgha: {e}")
        return None, None, None


# ─────────────────────────────────────────────
#  Calcium (Ca) — kg/ha exchangeable
#
#  Spectral basis (Lagacherie et al. 2008; Gomez et al. 2012):
#  - High Ca soils (calcareous) show elevated SWIR1 (B11) and SWIR2 (B12)
#    reflectance due to carbonate mineralogy absorption features at ~2.3 µm
#  - Calcareous soils also appear brighter in visible bands
#  - NDVI inverse: bare calcareous soil → low NDVI
#  - Clay index (B11-B8)/(B11+B8): negative in Ca-rich calcareous soils
#  Calibrated to ICAR range: 400–800 kg/ha exchangeable Ca
# ─────────────────────────────────────────────
def get_calcium_kgha(bs):
    try:
        b2  = bs.get("B2",  0.0)
        b3  = bs.get("B3",  0.0)
        b4  = bs.get("B4",  0.0)
        b8  = bs.get("B8",  0.0)
        b11 = bs.get("B11", 0.0)
        b12 = bs.get("B12", 0.0)

        # Carbonate index: SWIR2 elevated in calcareous/Ca-rich soils
        carbonate_idx = (b11 + b12) / (b4 + b3 + 1e-6)

        # Brightness: bare calcareous soils are bright
        brightness = (b2 + b3 + b4) / 3.0

        # NDVI: low vegetation → likely more exposed soil signal
        ndvi = (b8 - b4) / (b8 + b4 + 1e-6)

        # Clay index proxy (inverse — Ca inversely related to pure clay)
        clay_idx = (b11 - b8) / (b11 + b8 + 1e-6)

        # Empirical formula calibrated to ICAR range 400–800 kg/ha
        Ca_kgha = (550.0
                   + 250.0 * carbonate_idx
                   + 150.0 * brightness
                   - 100.0 * ndvi
                   - 80.0  * clay_idx)
        return max(100.0, min(1200.0, float(Ca_kgha)))
    except Exception as e:
        logging.error(f"Error in get_calcium_kgha: {e}")
        return None


# ─────────────────────────────────────────────
#  Magnesium (Mg) — kg/ha exchangeable
#
#  Spectral basis (Nawar et al. 2016; Casa et al. 2015):
#  - Mg is associated with chlorophyll and clay minerals (smectite, vermiculite)
#  - Red-edge bands (B5, B6, B7) sensitive to chlorophyll → Mg proxy via leaf
#  - SWIR2 (B12): Mg-OH absorption feature near 2.3 µm in smectite clays
#  - High Mg → higher red-edge reflectance and lower SWIR2
#  Calibrated to ICAR range: 50–200 kg/ha
# ─────────────────────────────────────────────
def get_magnesium_kgha(bs):
    try:
        b4  = bs.get("B4",  0.0)
        b5  = bs.get("B5",  0.0)   # Red-Edge 1
        b6  = bs.get("B6",  0.0)   # Red-Edge 2
        b7  = bs.get("B7",  0.0)   # Red-Edge 3
        b8  = bs.get("B8",  0.0)
        b8a = bs.get("B8A", 0.0)
        b11 = bs.get("B11", 0.0)
        b12 = bs.get("B12", 0.0)

        # Red-edge chlorophyll index — proxy for leaf Mg (part of chlorophyll)
        re_chl = (b7 / (b5 + 1e-6)) - 1.0

        # NDRE: sensitive to Mg-driven chlorophyll variation
        ndre = (b8a - b5) / (b8a + b5 + 1e-6)

        # Mg-OH clay absorption index: smectite/vermiculite Mg clays
        # Lower B12 relative to B11 indicates Mg-OH feature absorption
        mg_clay_idx = (b11 - b12) / (b11 + b12 + 1e-6)

        # Canopy chlorophyll: high Mg supports higher chlorophyll
        ndvi = (b8 - b4) / (b8 + b4 + 1e-6)

        # Empirical formula calibrated to ICAR range 50–200 kg/ha
        Mg_kgha = (110.0
                   + 60.0  * ndre
                   + 40.0  * re_chl
                   + 30.0  * mg_clay_idx
                   + 20.0  * ndvi)
        return max(10.0, min(400.0, float(Mg_kgha)))
    except Exception as e:
        logging.error(f"Error in get_magnesium_kgha: {e}")
        return None


# ─────────────────────────────────────────────
#  Sulphur (S) — kg/ha available SO4-S
#
#  Spectral basis (Farifteh et al. 2007; Metternicht & Zinck 2003):
#  - Sulphate-bearing soils (gypsiferous) have distinct SWIR signatures
#  - Gypsum absorption feature at ~1.77 µm (falls within B11 range)
#  - Saline soils with high sulphate → elevated EC and SWIR/visible ratio
#  - Vegetation stress (low NDVI, low red-edge) indicates possible S deficiency
#  - S deficiency → yellowing (reduced B5 relative to B4)
#  Note: LOW spectral reliability (like P) — flagged as estimate only
#  Calibrated to ICAR range: 10–40 kg/ha
# ─────────────────────────────────────────────
def get_sulphur_kgha(bs):
    try:
        b2  = bs.get("B2",  0.0)
        b3  = bs.get("B3",  0.0)
        b4  = bs.get("B4",  0.0)
        b5  = bs.get("B5",  0.0)
        b8  = bs.get("B8",  0.0)
        b11 = bs.get("B11", 0.0)
        b12 = bs.get("B12", 0.0)

        # Gypsum/sulphate index: elevated SWIR1 in gypsiferous soils
        gypsum_idx = b11 / (b3 + b4 + 1e-6)

        # Salinity index (SO4 is a major salt anion)
        si1 = (b3 * b4) ** 0.5
        si2 = (b3 ** 2 + b4 ** 2) ** 0.5 if (b3 ** 2 + b4 ** 2) > 0 else 0.0
        salinity_idx = (si1 + si2) / 2.0

        # S deficiency shows as yellowing — low red-edge relative to red
        # High ratio = adequate S (green canopy)
        re_red_ratio = b5 / (b4 + 1e-6)

        # SWIR2/SWIR1: gypsum has distinct ratio vs other salts
        swir_ratio = b12 / (b11 + 1e-6)

        ndvi = (b8 - b4) / (b8 + b4 + 1e-6)

        # Empirical formula calibrated to ICAR range 10–40 kg/ha
        S_kgha = (20.0
                  + 15.0 * gypsum_idx
                  + 10.0 * abs(salinity_idx)
                  + 5.0  * (re_red_ratio - 1.0)
                  - 8.0  * swir_ratio
                  + 5.0  * ndvi)
        return max(2.0, min(80.0, float(S_kgha)))
    except Exception as e:
        logging.error(f"Error in get_sulphur_kgha: {e}")
        return None


# ─────────────────────────────────────────────
#  Status helpers
# ─────────────────────────────────────────────
def get_param_status(param, value):
    if value is None:
        return "na"
    if param == "Soil Texture":
        return "good" if value == IDEAL_RANGES[param] else "low"
    min_val, max_val = IDEAL_RANGES.get(param, (None, None))
    if min_val is None and max_val is not None:
        return "good" if value <= max_val else "high"
    elif max_val is None and min_val is not None:
        return "good" if value >= min_val else "low"
    elif min_val is not None and max_val is not None:
        if value < min_val:
            return "low"
        elif value > max_val:
            return "high"
        return "good"
    return "good"


def calculate_soil_health_score(params):
    score = 0
    total = len([v for v in params.values() if v is not None])
    for param, value in params.items():
        if get_param_status(param, value) == "good":
            score += 1
    pct    = (score / total) * 100 if total > 0 else 0
    rating = ("Excellent" if pct >= 80 else "Good" if pct >= 60 else
              "Fair"      if pct >= 40 else "Poor")
    return pct, rating


def generate_interpretation(param, value):
    if value is None:
        return "Data unavailable."
    if param == "Soil Texture":
        return TEXTURE_CLASSES.get(value, "Unknown texture.")
    if param == "NDWI":
        if value >= -0.10:
            return "Good moisture; no irrigation needed."
        elif -0.30 <= value < -0.10:
            return "Mild stress; irrigate within 2 days."
        elif -0.40 <= value < -0.30:
            return "Moderate stress; irrigate tomorrow."
        else:
            return "Severe stress; irrigate immediately."
    if param == "Phosphorus":
        return "Low spectral reliability. Use as guide only."
    if param == "Sulphur":
        return "Low spectral reliability (gypsum index). Use as guide only."
    status = get_param_status(param, value)
    if status == "good":
        return f"Optimal ({IDEAL_DISPLAY.get(param, 'N/A')})."
    elif status == "low":
        min_v, _ = IDEAL_RANGES.get(param, (None, None))
        return f"Low (below {min_v})."
    elif status == "high":
        _, max_v = IDEAL_RANGES.get(param, (None, None))
        return f"High (above {max_v})."
    return "No interpretation."


def get_suggestion(param, value):
    if value is None or param not in SUGGESTIONS:
        return "—"
    status = get_param_status(param, value)
    s = SUGGESTIONS[param]
    if status == "good":
        return "OK: " + s.get("good", "Maintain current practice.")
    elif status == "low":
        return "FIX: " + s.get("low", s.get("high", "Consult agronomist."))
    elif status == "high":
        return "FIX: " + s.get("high", s.get("low", "Consult agronomist."))
    return "—"


def get_color_for_value(param, value):
    s = get_param_status(param, value)
    return 'green' if s == 'good' else ('orange' if s == 'low' else ('red' if s == 'high' else 'grey'))


# ─────────────────────────────────────────────
#  Charts
# ─────────────────────────────────────────────
def make_nutrient_chart(n_val, p_val, k_val, ca_val, mg_val, s_val):
    try:
        nutrients  = [
            "Nitrogen\n(kg/ha)", "Phosphorus\nP2O5 (kg/ha)", "Potassium\nK2O (kg/ha)",
            "Calcium\n(kg/ha)", "Magnesium\n(kg/ha)", "Sulphur\n(kg/ha)"
        ]
        param_keys = ["Nitrogen", "Phosphorus", "Potassium", "Calcium", "Magnesium", "Sulphur"]
        values     = [n_val or 0, p_val or 0, k_val or 0, ca_val or 0, mg_val or 0, s_val or 0]
        bar_colors = [get_color_for_value(p, v) for p, v in zip(param_keys, values)]

        fig, ax = plt.subplots(figsize=(10, 4))
        bars = ax.bar(nutrients, values, color=bar_colors, alpha=0.82)
        ax.set_title("Soil Nutrient Levels (kg/hectare) — ICAR Standard", fontsize=11)
        ax.set_ylabel("kg / hectare")
        ymax = max(values) * 1.35 if any(values) else 400
        ax.set_ylim(0, ymax)

        for bar, val, pk in zip(bars, values, param_keys):
            st2 = get_param_status(pk, val)
            lbl = "Good" if st2 == "good" else ("Low" if st2 == "low" else "High")
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + ymax * 0.02,
                    f"{val:.1f}\n{lbl}", ha='center', va='bottom', fontsize=7)

        plt.tight_layout()
        path = "nutrient_chart.png"
        plt.savefig(path, dpi=100, bbox_inches='tight')
        plt.close()
        return path
    except Exception as e:
        logging.error(f"Error in make_nutrient_chart: {e}")
        return None


def make_vegetation_chart(ndvi, ndwi):
    """Only NDVI and NDWI — EVI and FVC removed from report."""
    try:
        indices    = ["NDVI", "NDWI"]
        values     = [ndvi or 0, ndwi or 0]
        bar_colors = [get_color_for_value(i, v) for i, v in zip(indices, values)]

        fig, ax = plt.subplots(figsize=(5, 4))
        bars = ax.bar(indices, values, color=bar_colors, alpha=0.82)
        ax.set_title("Vegetation and Water Indices", fontsize=11)
        ax.set_ylabel("Index Value")
        ax.set_ylim(-1, 1)
        ax.axhline(0, color='black', linewidth=0.5, linestyle='--')

        for i, (bar, val) in enumerate(zip(bars, values)):
            st2 = get_param_status(indices[i], val)
            lbl = "Good" if st2 == "good" else ("Low" if st2 == "low" else "High")
            ypos = bar.get_height() + 0.03 if val >= 0 else bar.get_height() - 0.08
            ax.text(bar.get_x() + bar.get_width() / 2,
                    ypos, f"{val:.2f}\n{lbl}", ha='center', va='bottom', fontsize=9)

        plt.tight_layout()
        path = "vegetation_chart.png"
        plt.savefig(path, dpi=100, bbox_inches='tight')
        plt.close()
        return path
    except Exception as e:
        logging.error(f"Error in make_vegetation_chart: {e}")
        return None


def make_soil_properties_chart(ph, sal_ec, oc_pct, cec, lst):
    try:
        labels     = ["pH", "EC (mS/cm)", "OC (%)", "CEC (cmol/kg)", "LST (C)"]
        param_keys = ["pH", "Salinity", "Organic Carbon", "CEC", "LST"]
        values     = [ph or 0, sal_ec or 0, oc_pct or 0, cec or 0, lst or 0]
        bar_colors = [get_color_for_value(p, v) for p, v in zip(param_keys, values)]

        fig, ax = plt.subplots(figsize=(8, 4))
        bars = ax.bar(labels, values, color=bar_colors, alpha=0.82)
        ax.set_title("Soil Properties (ICAR Standard)", fontsize=11)
        ax.set_ylabel("Value")
        ymax = max(values) * 1.35 if any(values) else 50
        ax.set_ylim(0, ymax)

        for bar, val, pk in zip(bars, values, param_keys):
            st2 = get_param_status(pk, val)
            lbl = "Good" if st2 == "good" else ("Low" if st2 == "low" else "High")
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + ymax * 0.02,
                    f"{val:.2f}\n{lbl}", ha='center', va='bottom', fontsize=8)

        plt.tight_layout()
        path = "properties_chart.png"
        plt.savefig(path, dpi=100, bbox_inches='tight')
        plt.close()
        return path
    except Exception as e:
        logging.error(f"Error in make_soil_properties_chart: {e}")
        return None


# ─────────────────────────────────────────────
#  Groq API
# ─────────────────────────────────────────────
def call_groq(prompt: str) -> str:
    try:
        client   = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700,
            temperature=0.35,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Groq API error: {e}")
        return None


# ─────────────────────────────────────────────
#  PDF Report
#  NOTE: EVI and FVC are excluded from the PDF
# ─────────────────────────────────────────────
def generate_report(params, location, date_range):
    try:
        # Params for report EXCLUDING EVI and FVC
        REPORT_PARAMS = {k: v for k, v in params.items() if k not in ("EVI", "FVC")}

        score, rating   = calculate_soil_health_score(REPORT_PARAMS)
        interpretations = {p: generate_interpretation(p, v) for p, v in REPORT_PARAMS.items()}

        nutrient_chart   = make_nutrient_chart(
            params["Nitrogen"], params["Phosphorus"], params["Potassium"],
            params["Calcium"],  params["Magnesium"],  params["Sulphur"]
        )
        vegetation_chart = make_vegetation_chart(params["NDVI"], params["NDWI"])
        properties_chart = make_soil_properties_chart(
            params["pH"], params["Salinity"], params["Organic Carbon"],
            params["CEC"], params["LST"])

        def fmtv(param, v):
            if v is None:
                return "N/A"
            u = UNIT_MAP.get(param, "")
            return f"{v:.2f}{u}"

        tex_d = TEXTURE_CLASSES.get(params["Soil Texture"], "N/A") if params["Soil Texture"] else "N/A"

        exec_prompt = f"""Write a 3-5 bullet executive summary for a soil health report for an Indian farmer. Simple, clear, no technical jargon.
Location: {location}
Date: {date_range}
Soil Health Score: {score:.1f}% ({rating})
pH={fmtv('pH', params['pH'])}, EC={fmtv('Salinity', params['Salinity'])}, OC={fmtv('Organic Carbon', params['Organic Carbon'])}, CEC={fmtv('CEC', params['CEC'])}
Texture={tex_d}, N={fmtv('Nitrogen', params['Nitrogen'])}, P={fmtv('Phosphorus', params['Phosphorus'])} (low reliability), K={fmtv('Potassium', params['Potassium'])}
Ca={fmtv('Calcium', params['Calcium'])}, Mg={fmtv('Magnesium', params['Magnesium'])}, S={fmtv('Sulphur', params['Sulphur'])} (estimate)
Start each bullet with a dot. No bold text, no markdown."""

        rec_prompt = f"""Give 3-5 practical crop and soil treatment recommendations for an Indian farmer.
pH={fmtv('pH', params['pH'])}, EC={fmtv('Salinity', params['Salinity'])}, OC={fmtv('Organic Carbon', params['Organic Carbon'])}, CEC={fmtv('CEC', params['CEC'])}, Texture={tex_d}
N={fmtv('Nitrogen', params['Nitrogen'])}, P2O5={fmtv('Phosphorus', params['Phosphorus'])} (estimate), K2O={fmtv('Potassium', params['Potassium'])}
Ca={fmtv('Calcium', params['Calcium'])}, Mg={fmtv('Magnesium', params['Magnesium'])}, S={fmtv('Sulphur', params['Sulphur'])} (estimate)
NDVI={fmtv('NDVI', params['NDVI'])}, NDWI={fmtv('NDWI', params['NDWI'])}
Suggest suitable crops for Indian climate and simple fertiliser treatments in plain farmer language.
Start each bullet with a dot. No bold text, no markdown."""

        executive_summary = call_groq(exec_prompt) or ". Summary unavailable."
        recommendations   = call_groq(rec_prompt)  or ". Recommendations unavailable."

        # ── PDF Build ─────────────────────────────────
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=3*cm,  bottomMargin=2*cm)
        styles      = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Title'],    fontSize=18, spaceAfter=16, alignment=TA_CENTER)
        h2          = ParagraphStyle('H2',    parent=styles['Heading2'], fontSize=12, spaceAfter=8, textColor=colors.darkgreen)
        body        = ParagraphStyle('Body',  parent=styles['BodyText'], fontSize=9,  leading=12)
        small       = ParagraphStyle('Small', parent=styles['BodyText'], fontSize=8,  leading=11)
        center_body = ParagraphStyle('CenterBody', parent=styles['BodyText'], fontSize=10, leading=14, alignment=TA_CENTER)

        elements = []

        # ── Cover — big centered logo ──────────────────
        elements.append(Spacer(1, 2*cm))
        if os.path.exists(LOGO_PATH):
            logo_img = Image(LOGO_PATH, width=10*cm, height=10*cm)
            logo_img.hAlign = 'CENTER'
            elements.append(logo_img)
        elements.append(Spacer(1, 0.8*cm))
        elements.append(Paragraph("FarmMatrix Soil Health Report", title_style))
        elements.append(Spacer(1, 0.4*cm))
        elements.append(Paragraph(f"<b>Location:</b> {location}", center_body))
        elements.append(Paragraph(f"<b>Date Range:</b> {date_range}", center_body))
        elements.append(Paragraph(f"<b>Generated:</b> {datetime.now():%d %B %Y, %H:%M}", center_body))
        elements.append(PageBreak())

        # ── Sec 1: Executive Summary ───────────────────
        elements.append(Paragraph("1. Executive Summary", h2))
        for line in executive_summary.split('\n'):
            if line.strip():
                elements.append(Paragraph(line.strip(), body))
        elements.append(Spacer(1, 0.4*cm))

        # ── Sec 2: Soil Health Rating ──────────────────
        elements.append(Paragraph("2. Soil Health Rating", h2))
        good_count  = sum(1 for p, v in REPORT_PARAMS.items() if get_param_status(p, v) == "good")
        valid_count = len([v for v in REPORT_PARAMS.values() if v is not None])
        rating_data = [
            ["Overall Score", "Rating", "Parameters Optimal"],
            [f"{score:.1f}%", rating, f"{good_count} / {valid_count}"]
        ]
        rt = Table(rating_data, colWidths=[5*cm, 4*cm, 7*cm])
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1,  0), 'Helvetica-Bold'),
            ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE',   (0, 0), (-1, -1), 10),
            ('BOX',        (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(rt)
        elements.append(Spacer(1, 0.4*cm))
        elements.append(PageBreak())

        # ── Sec 3: Parameter Table (no EVI, no FVC) ────
        elements.append(Paragraph("3. Soil Parameter Analysis (ICAR Standard)", h2))
        table_data = [["Parameter", "Value", "ICAR Ideal Range", "Status", "Interpretation"]]
        for param, value in REPORT_PARAMS.items():
            unit = UNIT_MAP.get(param, "")
            if param == "Soil Texture":
                val_text = TEXTURE_CLASSES.get(value, "N/A") if value is not None else "N/A"
            else:
                val_text = f"{value:.2f}{unit}" if value is not None else "N/A"
            status   = get_param_status(param, value)
            st_label = ("Good" if status == "good" else
                        "Low"  if status == "low"  else
                        "High" if status == "high" else "N/A")
            table_data.append([
                param, val_text,
                IDEAL_DISPLAY.get(param, "N/A"),
                st_label,
                Paragraph(interpretations[param], small)
            ])

        tbl = Table(table_data, colWidths=[3*cm, 2.5*cm, 3*cm, 1.8*cm, 5.7*cm])
        tbl_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID',       (0, 0), (-1,-1), 0.5, colors.grey),
            ('VALIGN',     (0, 0), (-1,-1), 'TOP'),
            ('FONTSIZE',   (0, 0), (-1,-1), 9),
            ('BOX',        (0, 0), (-1,-1), 1, colors.black),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.Color(0.94,0.98,0.94)]),
        ]
        for i, (param, value) in enumerate(REPORT_PARAMS.items(), start=1):
            s = get_param_status(param, value)
            c = (colors.Color(0.1, 0.55, 0.1) if s == "good" else
                 colors.Color(0.85, 0.45, 0.0) if s == "low"  else
                 colors.red if s == "high" else colors.grey)
            tbl_style.append(('TEXTCOLOR', (3, i), (3, i), c))
            tbl_style.append(('FONTNAME',  (3, i), (3, i), 'Helvetica-Bold'))
        tbl.setStyle(TableStyle(tbl_style))
        elements.append(tbl)
        elements.append(PageBreak())

        # ── Sec 4: Charts ──────────────────────────────
        elements.append(Paragraph("4. Visualizations", h2))
        for lbl, path in [
            ("Nutrient Levels — N, P2O5, K2O, Ca, Mg, S (kg/hectare)", nutrient_chart),
            ("Vegetation and Water Indices (NDVI, NDWI)",               vegetation_chart),
            ("Soil Properties",                                          properties_chart),
        ]:
            if path:
                elements.append(Paragraph(lbl + ":", body))
                elements.append(Image(path, width=13*cm, height=6.5*cm))
                elements.append(Spacer(1, 0.3*cm))
        elements.append(PageBreak())

        # ── Sec 5: Crop Recommendations ───────────────
        elements.append(Paragraph("5. Crop Recommendations and Treatments", h2))
        for line in recommendations.split('\n'):
            if line.strip():
                elements.append(Paragraph(line.strip(), body))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(PageBreak())

        # ── Sec 6: Parameter-wise Suggestions (no EVI, no FVC) ────────────
        elements.append(Paragraph("6. Parameter-wise Suggestions", h2))
        elements.append(Paragraph(
            "For each parameter: what to do to maintain good levels, or fix problem levels.", small))
        elements.append(Spacer(1, 0.3*cm))

        SUGGESTION_PARAMS = [
            "pH", "Salinity", "Organic Carbon", "CEC",
            "Nitrogen", "Phosphorus", "Potassium",
            "Calcium", "Magnesium", "Sulphur",
            "NDVI", "NDWI", "LST"
        ]
        sug_data = [["Parameter", "Status", "Action Required"]]
        for param in SUGGESTION_PARAMS:
            value    = params.get(param)
            status   = get_param_status(param, value)
            st_label = ("Good" if status == "good" else
                        "Low"  if status == "low"  else
                        "High" if status == "high" else "N/A")
            sug_text = get_suggestion(param, value)
            sug_data.append([param, st_label, Paragraph(sug_text, small)])

        sug_tbl = Table(sug_data, colWidths=[3*cm, 2*cm, 11*cm])
        sug_style_list = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID',       (0, 0), (-1,-1), 0.5, colors.grey),
            ('VALIGN',     (0, 0), (-1,-1), 'TOP'),
            ('FONTSIZE',   (0, 0), (-1,-1), 9),
            ('BOX',        (0, 0), (-1,-1), 1, colors.black),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.Color(0.94,0.98,0.94)]),
        ]
        for i, param in enumerate(SUGGESTION_PARAMS, start=1):
            value = params.get(param)
            s     = get_param_status(param, value)
            c     = (colors.Color(0.1, 0.55, 0.1) if s == "good" else
                     colors.Color(0.85, 0.45, 0.0) if s == "low"  else
                     colors.red if s == "high" else colors.grey)
            sug_style_list.append(('TEXTCOLOR', (1, i), (1, i), c))
            sug_style_list.append(('FONTNAME',  (1, i), (1, i), 'Helvetica-Bold'))
        sug_tbl.setStyle(TableStyle(sug_style_list))
        elements.append(sug_tbl)

        # ── Header / Footer ────────────────────────────
        def add_header(canv, doc):
            canv.saveState()
            if os.path.exists(LOGO_PATH):
                canv.drawImage(LOGO_PATH, 2*cm, A4[1] - 2.8*cm, width=1.8*cm, height=1.8*cm)
            canv.setFont("Helvetica-Bold", 11)
            canv.drawString(4.5*cm, A4[1] - 2.2*cm, "FarmMatrix Soil Health Report")
            canv.setFont("Helvetica", 8)
            canv.drawRightString(A4[0] - 2*cm, A4[1] - 2.2*cm,
                                 f"Generated: {datetime.now():%d %b %Y, %H:%M}")
            canv.setStrokeColor(colors.darkgreen)
            canv.setLineWidth(1)
            canv.line(2*cm, A4[1] - 3*cm, A4[0] - 2*cm, A4[1] - 3*cm)
            canv.restoreState()

        def add_footer(canv, doc):
            canv.saveState()
            canv.setStrokeColor(colors.darkgreen)
            canv.line(2*cm, 1.5*cm, A4[0] - 2*cm, 1.5*cm)
            canv.setFont("Helvetica", 8)
            canv.drawCentredString(A4[0] / 2, cm,
                                   f"Page {doc.page}  |  FarmMatrix Soil Health Report  |  ICAR Standard Units")
            canv.restoreState()

        doc.build(elements,
                  onFirstPage=add_header, onLaterPages=add_header,
                  canvasmaker=canvas.Canvas)
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()

    except Exception as e:
        logging.error(f"Error in generate_report: {e}")
        return None


# ═══════════════════════════════════════════════════════
#  Streamlit UI
# ═══════════════════════════════════════════════════════
st.set_page_config(layout='wide', page_title="Soil Health Dashboard")
st.title("FarmMatrix Soil Health Dashboard")
st.markdown("Satellite-based soil analysis — ICAR-aligned nutrient reporting in kg/hectare.")

# ── Sidebar ───────────────────────────────────
st.sidebar.header("Location")
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]
lat = st.sidebar.number_input("Latitude",  value=st.session_state.user_location[0], format="%.6f")
lon = st.sidebar.number_input("Longitude", value=st.session_state.user_location[1], format="%.6f")
st.session_state.user_location = [lat, lon]

st.sidebar.header("CEC Model Coefficients")
cec_intercept  = st.sidebar.number_input("Intercept",           value=5.0,  step=0.1)
cec_slope_clay = st.sidebar.number_input("Slope (Clay Index)",  value=20.0, step=0.1)
cec_slope_om   = st.sidebar.number_input("Slope (OM Index)",    value=15.0, step=0.1)

today      = date.today()
start_date = st.sidebar.date_input("Start Date", value=today - timedelta(days=16))
end_date   = st.sidebar.date_input("End Date",   value=today)
if start_date > end_date:
    st.sidebar.error("Start date must be before end date.")
    st.stop()

# ── Map ───────────────────────────────────────
m = folium.Map(location=[lat, lon], zoom_start=15)
Draw(export=True).add_to(m)
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google").add_to(m)
folium.Marker([lat, lon], popup="Centre").add_to(m)
map_data = st_folium(m, width=700, height=500)

# ── Region selection ──────────────────────────
region = None
if map_data and "last_active_drawing" in map_data:
    try:
        sel = map_data["last_active_drawing"]
        if sel and "geometry" in sel and "coordinates" in sel["geometry"]:
            region = ee.Geometry.Polygon(sel["geometry"]["coordinates"])
        else:
            st.error("Invalid region. Please draw a valid polygon.")
    except Exception as e:
        st.error(f"Error creating region: {e}")

# ── Analysis ──────────────────────────────────
if region:
    st.subheader(f"Analysis: {start_date} to {end_date}")
    progress_bar = st.progress(0)
    status_msg   = st.empty()

    status_msg.text("Fetching Sentinel-2 imagery...")
    comp = sentinel_composite(region, start_date, end_date, ALL_BANDS)
    progress_bar.progress(20)

    status_msg.text("Reading soil texture map...")
    texc = get_soil_texture(region)
    progress_bar.progress(35)

    status_msg.text("Fetching MODIS Land Surface Temperature...")
    lst = get_lst(region, start_date, end_date)
    progress_bar.progress(50)

    if comp is None:
        st.warning("No Sentinel-2 data found. Try expanding the date range.")
        ph = sal = oc = cec = ndwi = ndvi = evi = fvc = n_val = p_val = k_val = None
        ca_val = mg_val = s_val = None
    else:
        status_msg.text("Computing band statistics...")
        bs = get_band_stats(comp, region)

        status_msg.text("Computing soil parameters (ICAR standard)...")
        ph    = get_ph_new(bs)
        sal   = get_salinity_ec(bs)
        oc    = get_organic_carbon_pct(bs)
        cec   = estimate_cec(comp, region, cec_intercept, cec_slope_clay, cec_slope_om)
        ndwi  = get_ndwi(bs)
        ndvi  = get_ndvi(bs)
        evi   = get_evi(bs)
        fvc   = get_fvc(bs)
        n_val, p_val, k_val = get_npk_kgha(bs)
        ca_val = get_calcium_kgha(bs)
        mg_val = get_magnesium_kgha(bs)
        s_val  = get_sulphur_kgha(bs)
        progress_bar.progress(100)
        status_msg.text("Analysis complete.")

    params = {
        "pH":             ph,
        "Salinity":       sal,
        "Organic Carbon": oc,
        "CEC":            cec,
        "Soil Texture":   texc,
        "LST":            lst,
        "NDWI":           ndwi,
        "NDVI":           ndvi,
        "EVI":            evi,    # computed, shown in UI, excluded from PDF
        "FVC":            fvc,    # computed, shown in UI, excluded from PDF
        "Nitrogen":       n_val,
        "Phosphorus":     p_val,
        "Potassium":      k_val,
        "Calcium":        ca_val,
        "Magnesium":      mg_val,
        "Sulphur":        s_val,
    }

    # ── Metrics display ───────────────────────
    st.markdown("### Soil Parameters")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("pH",                   f"{ph:.2f}"   if ph   is not None else "N/A")
        st.metric("Salinity EC (mS/cm)",  f"{sal:.2f}"  if sal  is not None else "N/A")
        st.metric("Organic Carbon (%)",   f"{oc:.2f}"   if oc   is not None else "N/A")
        st.metric("CEC (cmol/kg)",        f"{cec:.2f}"  if cec  is not None else "N/A")
    with col2:
        st.metric("NDVI",  f"{ndvi:.3f}"  if ndvi  is not None else "N/A")
        st.metric("EVI",   f"{evi:.3f}"   if evi   is not None else "N/A")
        st.metric("FVC",   f"{fvc:.3f}"   if fvc   is not None else "N/A")
        st.metric("NDWI",  f"{ndwi:.3f}"  if ndwi  is not None else "N/A")
    with col3:
        st.metric("Nitrogen N (kg/ha)",       f"{n_val:.1f}" if n_val is not None else "N/A")
        st.metric("Phosphorus P2O5 (kg/ha)", f"{p_val:.1f}" if p_val is not None else "N/A")
        st.metric("Potassium K2O (kg/ha)",   f"{k_val:.1f}" if k_val is not None else "N/A")
        st.metric("LST (C)",                  f"{lst:.1f}"   if lst   is not None else "N/A")
    with col4:
        st.metric("Calcium Ca (kg/ha)",   f"{ca_val:.1f}" if ca_val is not None else "N/A")
        st.metric("Magnesium Mg (kg/ha)", f"{mg_val:.1f}" if mg_val is not None else "N/A")
        st.metric("Sulphur S (kg/ha)",    f"{s_val:.1f}"  if s_val  is not None else "N/A")

    score, rating = calculate_soil_health_score(params)
    icon = "🟢" if rating in ("Excellent", "Good") else ("🟡" if rating == "Fair" else "🔴")
    st.info(f"{icon} Soil Health Score: {score:.1f}% — {rating}  (ICAR Standard)")

    # ── Quick suggestions table in UI ─────────
    st.markdown("### Quick Suggestions")
    sug_rows = []
    for p in ["pH", "Salinity", "Organic Carbon", "Nitrogen", "Phosphorus", "Potassium",
              "Calcium", "Magnesium", "Sulphur"]:
        v  = params.get(p)
        s  = get_param_status(p, v)
        st_label = "Good" if s == "good" else ("Low" if s == "low" else ("High" if s == "high" else "N/A"))
        sug_rows.append({
            "Parameter": p,
            "Value": f"{v:.2f}{UNIT_MAP.get(p,'')}" if v is not None else "N/A",
            "Status": st_label,
            "Suggestion": get_suggestion(p, v).replace("OK: ", "").replace("FIX: ", ""),
        })
    st.dataframe(pd.DataFrame(sug_rows), use_container_width=True, hide_index=True)
    st.caption(
        "Note: Phosphorus (P) and Sulphur (S) have low spectral accuracy. "
        "Treat as estimates only. Ground-truth sampling recommended for all secondary nutrients."
    )

    if st.button("Generate Full PDF Report"):
        with st.spinner("Generating report with Groq AI insights..."):
            location   = f"Lat: {lat:.6f}, Lon: {lon:.6f}"
            date_range = f"{start_date} to {end_date}"
            pdf_data   = generate_report(params, location, date_range)
            if pdf_data:
                st.success("Report ready!")
                st.download_button(
                    label="Download PDF Report",
                    data=pdf_data,
                    file_name=f"soil_health_report_{date.today()}.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("Failed to generate report. Check logs.")
else:
    st.info("Draw a polygon on the map above to select your field or region.")