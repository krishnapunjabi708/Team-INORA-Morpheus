import logging
import os
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import ee
import matplotlib
matplotlib.use("Agg")
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
import json
import base64

# ─────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Configuration (from environment variables)
# ─────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"
LOGO_PATH    = os.path.abspath("LOGO.jpeg")

# ─────────────────────────────────────────────
#  FastAPI App
# ─────────────────────────────────────────────
app = FastAPI(
    title="FarmMatrix Soil Health API",
    description="Satellite-based soil analysis API using Google Earth Engine — ICAR-aligned nutrient reporting",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
#  GEE Initialization
# ─────────────────────────────────────────────
# def initialize_gee():
#     """Initialize Google Earth Engine using service account credentials from env."""
#     try:
#         gee_sa_key = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")
#         gee_email  = os.environ.get("GEE_SERVICE_ACCOUNT_EMAIL", "")

#         if gee_sa_key and gee_email:
#             # Service account auth (recommended for production)
#             key_data = json.loads(gee_sa_key)
#             credentials = ee.ServiceAccountCredentials(gee_email, key_data=json.dumps(key_data))
#             ee.Initialize(credentials)
#             logger.info("GEE initialized with service account.")
#         else:
#             # Fallback: try default credentials or existing token
#             ee.Initialize()
#             logger.info("GEE initialized with default credentials.")
#     except Exception as e:
#         logger.error(f"GEE initialization failed: {e}")
#         raise RuntimeError(f"GEE initialization failed: {e}")


def initialize_ee():
    global ee_initialized
    try:
        credentials_base64 = os.getenv("GEE_SERVICE_ACCOUNT_KEY")
        if not credentials_base64:
            raise ValueError("❌ Google Earth Engine credentials are missing.")
        credentials_json_str = base64.b64decode(credentials_base64).decode("utf-8")
        credentials_dict = json.loads(credentials_json_str)
        from ee import ServiceAccountCredentials
        credentials = ServiceAccountCredentials(credentials_dict['client_email'], key_data=credentials_json_str)
        ee.Initialize(credentials)
        ee_initialized = True
        logging.info("✅ Google Earth Engine initialized successfully.")
    except Exception as e:
        ee_initialized = False
        logging.error(f"❌ Google Earth Engine initialization failed: {e}")
        raise

initialize_ee()

# Initialize GEE on startup
# @app.on_event("startup")
# async def startup_event():
#     initialize_gee()

# ─────────────────────────────────────────────
#  Constants & Lookups
# ─────────────────────────────────────────────
SOIL_TEXTURE_IMG = None  # Lazy-loaded after GEE init

def get_soil_texture_img():
    global SOIL_TEXTURE_IMG
    if SOIL_TEXTURE_IMG is None:
        SOIL_TEXTURE_IMG = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0')
    return SOIL_TEXTURE_IMG

TEXTURE_CLASSES = {
    1: "Clay", 2: "Silty Clay", 3: "Sandy Clay",
    4: "Clay Loam", 5: "Silty Clay Loam", 6: "Sandy Clay Loam",
    7: "Loam", 8: "Silty Loam", 9: "Sandy Loam",
    10: "Silt", 11: "Loamy Sand", 12: "Sand"
}

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
    "Calcium":        (400, 800),
    "Magnesium":      (50, 200),
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
#  Pydantic Request Models
# ─────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    lat: float = Field(..., description="Latitude of field center", example=18.4575)
    lon: float = Field(..., description="Longitude of field center", example=73.8503)
    start_date: str = Field(..., description="Start date YYYY-MM-DD", example="2024-01-01")
    end_date: str   = Field(..., description="End date YYYY-MM-DD",   example="2024-01-16")
    buffer_meters: int = Field(default=200, description="Field buffer radius in meters (used when no polygon)")
    polygon_coords: Optional[list] = Field(
        default=None,
        description="List of [lon, lat] coordinate pairs forming a polygon. If omitted, a square buffer around lat/lon is used."
    )
    cec_intercept:  float = Field(default=5.0,  description="CEC model intercept")
    cec_slope_clay: float = Field(default=20.0, description="CEC model clay slope")
    cec_slope_om:   float = Field(default=15.0, description="CEC model OM slope")

class ReportRequest(AnalyzeRequest):
    """Same as AnalyzeRequest — PDF report is generated from same inputs."""
    pass

# ─────────────────────────────────────────────
#  GEE Helpers
# ─────────────────────────────────────────────
def build_region(req: AnalyzeRequest) -> ee.Geometry:
    """Build EE geometry from polygon coords or buffer around lat/lon."""
    if req.polygon_coords and len(req.polygon_coords) >= 3:
        return ee.Geometry.Polygon(req.polygon_coords)
    # Default: square-ish buffer (circle)
    point = ee.Geometry.Point([req.lon, req.lat])
    return point.buffer(req.buffer_meters)


def safe_get_info(computed_obj, name="value"):
    if computed_obj is None:
        return None
    try:
        info = computed_obj.getInfo()
        return float(info) if info is not None else None
    except Exception as e:
        logger.warning(f"Failed to fetch {name}: {e}")
        return None


def sentinel_composite(region, start, end, bands):
    start_str = start if isinstance(start, str) else start.strftime("%Y-%m-%d")
    end_str   = end   if isinstance(end, str)   else end.strftime("%Y-%m-%d")
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
        start_dt = datetime.strptime(start_str, "%Y-%m-%d")
        end_dt   = datetime.strptime(end_str,   "%Y-%m-%d")
        for days in range(5, 31, 5):
            sd = (start_dt - timedelta(days=days)).strftime("%Y-%m-%d")
            ed = (end_dt   + timedelta(days=days)).strftime("%Y-%m-%d")
            coll = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterDate(sd, ed)
                .filterBounds(region)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
                .select(bands)
            )
            if coll.size().getInfo() > 0:
                logger.info(f"Sentinel window expanded to {sd} – {ed}")
                return coll.median().multiply(0.0001)
        logger.warning("No Sentinel-2 data found.")
        return None
    except Exception as e:
        logger.error(f"sentinel_composite error: {e}")
        return None


def get_band_stats(comp, region, scale=10):
    try:
        stats = comp.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region,
            scale=scale, maxPixels=1e13
        ).getInfo()
        return {k: (float(v) if v is not None else 0.0) for k, v in stats.items()}
    except Exception as e:
        logger.error(f"get_band_stats error: {e}")
        return {}


def get_lst(region, end_str):
    try:
        end_dt   = datetime.strptime(end_str, "%Y-%m-%d")
        start_dt = end_dt - relativedelta(months=1)
        coll = (
            ee.ImageCollection("MODIS/061/MOD11A2")
            .filterBounds(region.buffer(5000))
            .filterDate(start_dt.strftime("%Y-%m-%d"), end_str)
            .select("LST_Day_1km")
        )
        if coll.size().getInfo() == 0:
            return None
        img   = coll.median().multiply(0.02).subtract(273.15).rename("lst").clip(region.buffer(5000))
        stats = img.reduceRegion(reducer=ee.Reducer.mean(), geometry=region, scale=1000, maxPixels=1e13).getInfo()
        val   = stats.get("lst")
        return float(val) if val is not None else None
    except Exception as e:
        logger.error(f"get_lst error: {e}")
        return None


def get_soil_texture(region):
    try:
        img  = get_soil_texture_img()
        mode = img.clip(region.buffer(500)).reduceRegion(
            ee.Reducer.mode(), geometry=region, scale=250, maxPixels=1e13
        ).get("b0")
        val = safe_get_info(mode, "texture")
        return int(val) if val is not None else None
    except Exception as e:
        logger.error(f"get_soil_texture error: {e}")
        return None


# ─────────────────────────────────────────────
#  Derived Parameters
# ─────────────────────────────────────────────
def get_ph_new(bs):
    try:
        b2, b3, b4 = bs.get("B2", 0.0), bs.get("B3", 0.0), bs.get("B4", 0.0)
        b5, b8, b11 = bs.get("B5", 0.0), bs.get("B8", 0.0), bs.get("B11", 0.0)
        ndvi_re_avg = ((b8 - b5) / (b8 + b5 + 1e-6) + (b8 - b4) / (b8 + b4 + 1e-6)) / 2.0
        swir_ratio  = b11 / (b8 + 1e-6)
        nir_ratio   = b8  / (b4 + 1e-6)
        brightness  = (b2 + b3 + b4) / 3.0
        pH_est = (6.5 + 1.2 * ndvi_re_avg + 0.8 * swir_ratio
                  - 0.5 * nir_ratio + 0.15 * (1.0 - brightness))
        return max(4.0, min(9.0, pH_est))
    except Exception as e:
        logger.error(f"get_ph_new error: {e}"); return None


def get_organic_carbon_pct(bs):
    try:
        b2, b4, b5 = bs.get("B2", 0.0), bs.get("B4", 0.0), bs.get("B5", 0.0)
        b8, b11, b12 = bs.get("B8", 0.0), bs.get("B11", 0.0), bs.get("B12", 0.0)
        ndvi_re_avg = ((b8 - b5) / (b8 + b5 + 1e-6) + (b8 - b4) / (b8 + b4 + 1e-6)) / 2.0
        L    = 0.5
        savi = ((b8 - b4) / (b8 + b4 + L + 1e-6)) * (1 + L)
        evi  = 2.5 * (b8 - b4) / (b8 + 6 * b4 - 7.5 * b2 + 1 + 1e-6)
        swir_avg = (b11 + b12) / 2.0
        oc_pct = 1.2 + 3.5 * ndvi_re_avg + 2.2 * savi - 1.5 * swir_avg + 0.4 * evi
        return max(0.1, min(5.0, oc_pct))
    except Exception as e:
        logger.error(f"get_organic_carbon_pct error: {e}"); return None


def get_salinity_ec(bs):
    try:
        b2, b3, b4, b8 = bs.get("B2", 0.0), bs.get("B3", 0.0), bs.get("B4", 0.0), bs.get("B8", 0.0)
        ndvi        = (b8 - b4) / (b8 + b4 + 1e-6)
        brightness  = (b2 + b3 + b4) / 3.0
        si1         = (b3 * b4) ** 0.5
        si2         = (b3 ** 2 + b4 ** 2) ** 0.5 if (b3 ** 2 + b4 ** 2) > 0 else 0.0
        si_combined = (si1 + si2) / 2.0
        veg_stress  = 1.0 - max(0.0, min(1.0, ndvi))
        ec = 0.5 + abs(si_combined) * 4.0 + veg_stress * 2.0 + 0.3 * (1.0 - brightness)
        return max(0.0, min(16.0, ec))
    except Exception as e:
        logger.error(f"get_salinity_ec error: {e}"); return None


def estimate_cec(comp, region, intercept, slope_clay, slope_om):
    if comp is None:
        return None
    try:
        clay = comp.expression("(B11-B8)/(B11+B8+1e-6)", {"B11": comp.select("B11"), "B8": comp.select("B8")}).rename("clay")
        om   = comp.expression("(B8-B4)/(B8+B4+1e-6)",   {"B8":  comp.select("B8"),  "B4": comp.select("B4")}).rename("om")
        c_m  = safe_get_info(clay.reduceRegion(ee.Reducer.mean(), geometry=region, scale=20, maxPixels=1e13).get("clay"), "clay")
        o_m  = safe_get_info(om.reduceRegion(ee.Reducer.mean(),   geometry=region, scale=20, maxPixels=1e13).get("om"),   "om")
        if c_m is None or o_m is None:
            return None
        return intercept + slope_clay * c_m + slope_om * o_m
    except Exception as e:
        logger.error(f"estimate_cec error: {e}"); return None


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


def get_npk_kgha(bs):
    try:
        b2, b3, b4, b5 = bs.get("B2", 0.0), bs.get("B3", 0.0), bs.get("B4", 0.0), bs.get("B5", 0.0)
        b6, b7, b8, b8a = bs.get("B6", 0.0), bs.get("B7", 0.0), bs.get("B8", 0.0), bs.get("B8A", 0.0)
        b11, b12 = bs.get("B11", 0.0), bs.get("B12", 0.0)
        ndvi       = (b8 - b4) / (b8 + b4 + 1e-6)
        evi        = 2.5 * (b8 - b4) / (b8 + 6 * b4 - 7.5 * b2 + 1 + 1e-6)
        brightness = (b2 + b3 + b4) / 3.0
        ndre       = (b8a - b5) / (b8a + b5 + 1e-6)
        ci_re      = (b7 / (b5 + 1e-6)) - 1.0
        mcari      = ((b5 - b4) - 0.2 * (b5 - b3)) * (b5 / (b4 + 1e-6))
        N = max(50.0, min(600.0, 280.0 + 300.0 * ndre + 150.0 * evi + 20.0 * (ci_re / 5.0) - 80.0 * brightness + 30.0 * mcari))
        si1 = (b3 * b4) ** 0.5
        si2 = (b3 ** 2 + b4 ** 2) ** 0.5 if (b3 ** 2 + b4 ** 2) > 0 else 0.0
        mndbsi = (si1 + si2) / 2.0
        P = max(2.0, min(60.0, 11.0 + 15.0 * (1.0 - brightness) + 6.0 * ndvi + 4.0 * abs(mndbsi) + 2.0 * b3))
        potassium_index = b11 / (b5 + b6 + 1e-6)
        salinity_factor = (b11 - b12) / (b11 + b12 + 1e-6)
        K = max(40.0, min(600.0, 150.0 + 200.0 * potassium_index + 80.0 * salinity_factor + 60.0 * ndvi))
        return float(N), float(P), float(K)
    except Exception as e:
        logger.error(f"get_npk_kgha error: {e}"); return None, None, None


def get_calcium_kgha(bs):
    try:
        b2, b3, b4, b8 = bs.get("B2", 0.0), bs.get("B3", 0.0), bs.get("B4", 0.0), bs.get("B8", 0.0)
        b11, b12 = bs.get("B11", 0.0), bs.get("B12", 0.0)
        carbonate_idx = (b11 + b12) / (b4 + b3 + 1e-6)
        brightness    = (b2 + b3 + b4) / 3.0
        ndvi          = (b8 - b4) / (b8 + b4 + 1e-6)
        clay_idx      = (b11 - b8) / (b11 + b8 + 1e-6)
        Ca = 550.0 + 250.0 * carbonate_idx + 150.0 * brightness - 100.0 * ndvi - 80.0 * clay_idx
        return max(100.0, min(1200.0, float(Ca)))
    except Exception as e:
        logger.error(f"get_calcium_kgha error: {e}"); return None


def get_magnesium_kgha(bs):
    try:
        b4, b5, b7, b8, b8a = bs.get("B4", 0.0), bs.get("B5", 0.0), bs.get("B7", 0.0), bs.get("B8", 0.0), bs.get("B8A", 0.0)
        b11, b12 = bs.get("B11", 0.0), bs.get("B12", 0.0)
        re_chl     = (b7 / (b5 + 1e-6)) - 1.0
        ndre       = (b8a - b5) / (b8a + b5 + 1e-6)
        mg_clay_idx = (b11 - b12) / (b11 + b12 + 1e-6)
        ndvi       = (b8 - b4) / (b8 + b4 + 1e-6)
        Mg = 110.0 + 60.0 * ndre + 40.0 * re_chl + 30.0 * mg_clay_idx + 20.0 * ndvi
        return max(10.0, min(400.0, float(Mg)))
    except Exception as e:
        logger.error(f"get_magnesium_kgha error: {e}"); return None


def get_sulphur_kgha(bs):
    try:
        b3, b4, b5, b8 = bs.get("B3", 0.0), bs.get("B4", 0.0), bs.get("B5", 0.0), bs.get("B8", 0.0)
        b11, b12 = bs.get("B11", 0.0), bs.get("B12", 0.0)
        gypsum_idx   = b11 / (b3 + b4 + 1e-6)
        si1          = (b3 * b4) ** 0.5
        si2          = (b3 ** 2 + b4 ** 2) ** 0.5 if (b3 ** 2 + b4 ** 2) > 0 else 0.0
        salinity_idx = (si1 + si2) / 2.0
        re_red_ratio = b5 / (b4 + 1e-6)
        swir_ratio   = b12 / (b11 + 1e-6)
        ndvi         = (b8 - b4) / (b8 + b4 + 1e-6)
        S = 20.0 + 15.0 * gypsum_idx + 10.0 * abs(salinity_idx) + 5.0 * (re_red_ratio - 1.0) - 8.0 * swir_ratio + 5.0 * ndvi
        return max(2.0, min(80.0, float(S)))
    except Exception as e:
        logger.error(f"get_sulphur_kgha error: {e}"); return None


# ─────────────────────────────────────────────
#  Status & Score helpers
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
        if value < min_val:   return "low"
        elif value > max_val: return "high"
        return "good"
    return "good"


def calculate_soil_health_score(params):
    total = len([v for v in params.values() if v is not None])
    score = sum(1 for p, v in params.items() if get_param_status(p, v) == "good")
    pct   = (score / total) * 100 if total > 0 else 0
    rating = ("Excellent" if pct >= 80 else "Good" if pct >= 60 else
              "Fair"      if pct >= 40 else "Poor")
    return pct, rating


def generate_interpretation(param, value):
    if value is None:
        return "Data unavailable."
    if param == "Soil Texture":
        return TEXTURE_CLASSES.get(value, "Unknown texture.")
    if param == "NDWI":
        if value >= -0.10:    return "Good moisture; no irrigation needed."
        elif value >= -0.30:  return "Mild stress; irrigate within 2 days."
        elif value >= -0.40:  return "Moderate stress; irrigate tomorrow."
        else:                 return "Severe stress; irrigate immediately."
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
    if status == "good":  return "OK: " + s.get("good", "Maintain current practice.")
    elif status == "low": return "FIX: " + s.get("low", s.get("high", "Consult agronomist."))
    elif status == "high":return "FIX: " + s.get("high", s.get("low", "Consult agronomist."))
    return "—"


def get_color_for_value(param, value):
    s = get_param_status(param, value)
    return 'green' if s == 'good' else ('orange' if s == 'low' else ('red' if s == 'high' else 'grey'))


# ─────────────────────────────────────────────
#  Core Analysis Runner
# ─────────────────────────────────────────────
def run_analysis(req: AnalyzeRequest) -> dict:
    region = build_region(req)

    comp = sentinel_composite(region, req.start_date, req.end_date, ALL_BANDS)
    texc = get_soil_texture(region)
    lst  = get_lst(region, req.end_date)

    if comp is None:
        ph = sal = oc = cec = ndwi = ndvi = evi = fvc = n_val = p_val = k_val = None
        ca_val = mg_val = s_val = None
    else:
        bs    = get_band_stats(comp, region)
        ph    = get_ph_new(bs)
        sal   = get_salinity_ec(bs)
        oc    = get_organic_carbon_pct(bs)
        cec   = estimate_cec(comp, region, req.cec_intercept, req.cec_slope_clay, req.cec_slope_om)
        ndwi  = get_ndwi(bs)
        ndvi  = get_ndvi(bs)
        evi   = get_evi(bs)
        fvc   = get_fvc(bs)
        n_val, p_val, k_val = get_npk_kgha(bs)
        ca_val = get_calcium_kgha(bs)
        mg_val = get_magnesium_kgha(bs)
        s_val  = get_sulphur_kgha(bs)

    params = {
        "pH": ph, "Salinity": sal, "Organic Carbon": oc, "CEC": cec,
        "Soil Texture": texc, "LST": lst, "NDWI": ndwi, "NDVI": ndvi,
        "EVI": evi, "FVC": fvc, "Nitrogen": n_val, "Phosphorus": p_val,
        "Potassium": k_val, "Calcium": ca_val, "Magnesium": mg_val, "Sulphur": s_val,
    }

    score, rating = calculate_soil_health_score(params)

    # Build response
    parameters = []
    for param, value in params.items():
        unit = UNIT_MAP.get(param, "")
        if param == "Soil Texture":
            display_value = TEXTURE_CLASSES.get(value, "N/A") if value is not None else "N/A"
        else:
            display_value = f"{value:.4f}{unit}" if value is not None else "N/A"
        parameters.append({
            "name":            param,
            "value":           value,
            "display_value":   display_value,
            "unit":            unit,
            "status":          get_param_status(param, value),
            "ideal_range":     IDEAL_DISPLAY.get(param, "N/A"),
            "interpretation":  generate_interpretation(param, value),
            "suggestion":      get_suggestion(param, value),
        })

    # Quick suggestions for key nutrients
    suggestions = []
    for p in ["pH", "Salinity", "Organic Carbon", "Nitrogen", "Phosphorus", "Potassium",
              "Calcium", "Magnesium", "Sulphur"]:
        v = params.get(p)
        suggestions.append({
            "parameter": p,
            "value":     v,
            "unit":      UNIT_MAP.get(p, ""),
            "status":    get_param_status(p, v),
            "suggestion": get_suggestion(p, v),
        })

    return {
        "soil_health_score": round(score, 2),
        "soil_health_rating": rating,
        "sentinel_data_available": comp is not None,
        "analysis_period": {"start": req.start_date, "end": req.end_date},
        "location": {"lat": req.lat, "lon": req.lon},
        "parameters": parameters,
        "suggestions": suggestions,
    }


# ─────────────────────────────────────────────
#  Charts (for PDF)
# ─────────────────────────────────────────────
def make_nutrient_chart(n, p, k, ca, mg, s):
    nutrients  = ["Nitrogen\n(kg/ha)", "Phosphorus\nP2O5 (kg/ha)", "Potassium\nK2O (kg/ha)",
                  "Calcium\n(kg/ha)", "Magnesium\n(kg/ha)", "Sulphur\n(kg/ha)"]
    param_keys = ["Nitrogen", "Phosphorus", "Potassium", "Calcium", "Magnesium", "Sulphur"]
    values     = [n or 0, p or 0, k or 0, ca or 0, mg or 0, s or 0]
    bar_colors = [get_color_for_value(pk, v) for pk, v in zip(param_keys, values)]
    fig, ax = plt.subplots(figsize=(10, 4))
    bars = ax.bar(nutrients, values, color=bar_colors, alpha=0.82)
    ax.set_title("Soil Nutrient Levels (kg/hectare) — ICAR Standard", fontsize=11)
    ax.set_ylabel("kg / hectare")
    ymax = max(values) * 1.35 if any(values) else 400
    ax.set_ylim(0, ymax)
    for bar, val, pk in zip(bars, values, param_keys):
        st2 = get_param_status(pk, val)
        lbl = "Good" if st2 == "good" else ("Low" if st2 == "low" else "High")
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.02,
                f"{val:.1f}\n{lbl}", ha='center', va='bottom', fontsize=7)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf


def make_vegetation_chart(ndvi, ndwi):
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
        st2  = get_param_status(indices[i], val)
        lbl  = "Good" if st2 == "good" else ("Low" if st2 == "low" else "High")
        ypos = bar.get_height() + 0.03 if val >= 0 else bar.get_height() - 0.08
        ax.text(bar.get_x() + bar.get_width() / 2, ypos, f"{val:.2f}\n{lbl}", ha='center', va='bottom', fontsize=9)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf


def make_soil_properties_chart(ph, sal, oc, cec, lst):
    labels     = ["pH", "EC (mS/cm)", "OC (%)", "CEC (cmol/kg)", "LST (C)"]
    param_keys = ["pH", "Salinity", "Organic Carbon", "CEC", "LST"]
    values     = [ph or 0, sal or 0, oc or 0, cec or 0, lst or 0]
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
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.02,
                f"{val:.2f}\n{lbl}", ha='center', va='bottom', fontsize=8)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────
#  Groq AI
# ─────────────────────────────────────────────
def call_groq(prompt: str) -> str:
    try:
        client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        resp   = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700,
            temperature=0.35,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return None


# ─────────────────────────────────────────────
#  PDF Generator
# ─────────────────────────────────────────────
def generate_pdf(params: dict, location: str, date_range: str) -> bytes:
    REPORT_PARAMS = {k: v for k, v in params.items() if k not in ("EVI", "FVC")}
    score, rating = calculate_soil_health_score(REPORT_PARAMS)
    interpretations = {p: generate_interpretation(p, v) for p, v in REPORT_PARAMS.items()}

    nutrient_chart_buf   = make_nutrient_chart(
        params["Nitrogen"], params["Phosphorus"], params["Potassium"],
        params["Calcium"],  params["Magnesium"],  params["Sulphur"])
    vegetation_chart_buf = make_vegetation_chart(params["NDVI"], params["NDWI"])
    properties_chart_buf = make_soil_properties_chart(
        params["pH"], params["Salinity"], params["Organic Carbon"], params["CEC"], params["LST"])

    def fmtv(param, v):
        if v is None: return "N/A"
        u = UNIT_MAP.get(param, "")
        return f"{v:.2f}{u}"

    tex_d = TEXTURE_CLASSES.get(params.get("Soil Texture"), "N/A") if params.get("Soil Texture") else "N/A"

    exec_prompt = f"""Write a 3-5 bullet executive summary for a soil health report for an Indian farmer. Simple, clear, no technical jargon.
Location: {location}
Date: {date_range}
Soil Health Score: {score:.1f}% ({rating})
pH={fmtv('pH', params.get('pH'))}, EC={fmtv('Salinity', params.get('Salinity'))}, OC={fmtv('Organic Carbon', params.get('Organic Carbon'))}, CEC={fmtv('CEC', params.get('CEC'))}
Texture={tex_d}, N={fmtv('Nitrogen', params.get('Nitrogen'))}, P={fmtv('Phosphorus', params.get('Phosphorus'))} (low reliability), K={fmtv('Potassium', params.get('Potassium'))}
Ca={fmtv('Calcium', params.get('Calcium'))}, Mg={fmtv('Magnesium', params.get('Magnesium'))}, S={fmtv('Sulphur', params.get('Sulphur'))} (estimate)
Start each bullet with a dot. No bold text, no markdown."""

    rec_prompt = f"""Give 3-5 practical crop and soil treatment recommendations for an Indian farmer.
pH={fmtv('pH', params.get('pH'))}, EC={fmtv('Salinity', params.get('Salinity'))}, OC={fmtv('Organic Carbon', params.get('Organic Carbon'))}, CEC={fmtv('CEC', params.get('CEC'))}, Texture={tex_d}
N={fmtv('Nitrogen', params.get('Nitrogen'))}, P2O5={fmtv('Phosphorus', params.get('Phosphorus'))} (estimate), K2O={fmtv('Potassium', params.get('Potassium'))}
Ca={fmtv('Calcium', params.get('Calcium'))}, Mg={fmtv('Magnesium', params.get('Magnesium'))}, S={fmtv('Sulphur', params.get('Sulphur'))} (estimate)
NDVI={fmtv('NDVI', params.get('NDVI'))}, NDWI={fmtv('NDWI', params.get('NDWI'))}
Suggest suitable crops for Indian climate and simple fertiliser treatments in plain farmer language.
Start each bullet with a dot. No bold text, no markdown."""

    executive_summary = call_groq(exec_prompt) or ". Summary unavailable."
    recommendations   = call_groq(rec_prompt)  or ". Recommendations unavailable."

    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=3*cm,  bottomMargin=2*cm)
    styles      = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'],    fontSize=18, spaceAfter=16, alignment=TA_CENTER)
    h2          = ParagraphStyle('H2',    parent=styles['Heading2'], fontSize=12, spaceAfter=8,  textColor=colors.darkgreen)
    body        = ParagraphStyle('Body',  parent=styles['BodyText'], fontSize=9,  leading=12)
    small       = ParagraphStyle('Small', parent=styles['BodyText'], fontSize=8,  leading=11)
    center_body = ParagraphStyle('CenterBody', parent=styles['BodyText'], fontSize=10, leading=14, alignment=TA_CENTER)

    elements = []
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

    elements.append(Paragraph("1. Executive Summary", h2))
    for line in executive_summary.split('\n'):
        if line.strip(): elements.append(Paragraph(line.strip(), body))
    elements.append(Spacer(1, 0.4*cm))

    elements.append(Paragraph("2. Soil Health Rating", h2))
    good_count  = sum(1 for p, v in REPORT_PARAMS.items() if get_param_status(p, v) == "good")
    valid_count = len([v for v in REPORT_PARAMS.values() if v is not None])
    rt = Table(
        [["Overall Score", "Rating", "Parameters Optimal"],
         [f"{score:.1f}%", rating,   f"{good_count} / {valid_count}"]],
        colWidths=[5*cm, 4*cm, 7*cm]
    )
    rt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE',   (0,0), (-1,-1), 10),
        ('BOX',        (0,0), (-1,-1), 1, colors.black),
    ]))
    elements.append(rt)
    elements.append(Spacer(1, 0.4*cm))
    elements.append(PageBreak())

    elements.append(Paragraph("3. Soil Parameter Analysis (ICAR Standard)", h2))
    table_data = [["Parameter", "Value", "ICAR Ideal Range", "Status", "Interpretation"]]
    for param, value in REPORT_PARAMS.items():
        unit = UNIT_MAP.get(param, "")
        if param == "Soil Texture":
            val_text = TEXTURE_CLASSES.get(value, "N/A") if value is not None else "N/A"
        else:
            val_text = f"{value:.2f}{unit}" if value is not None else "N/A"
        status   = get_param_status(param, value)
        st_label = "Good" if status == "good" else "Low" if status == "low" else "High" if status == "high" else "N/A"
        table_data.append([param, val_text, IDEAL_DISPLAY.get(param, "N/A"), st_label,
                           Paragraph(interpretations[param], small)])

    tbl = Table(table_data, colWidths=[3*cm, 2.5*cm, 3*cm, 1.8*cm, 5.7*cm])
    tbl_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN',     (0,0), (-1,-1), 'TOP'),
        ('FONTSIZE',   (0,0), (-1,-1), 9),
        ('BOX',        (0,0), (-1,-1), 1, colors.black),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.Color(0.94,0.98,0.94)]),
    ]
    for i, (param, value) in enumerate(REPORT_PARAMS.items(), start=1):
        s = get_param_status(param, value)
        c = (colors.Color(0.1,0.55,0.1) if s == "good" else
             colors.Color(0.85,0.45,0.0) if s == "low"  else
             colors.red if s == "high"   else colors.grey)
        tbl_style.append(('TEXTCOLOR', (3,i), (3,i), c))
        tbl_style.append(('FONTNAME',  (3,i), (3,i), 'Helvetica-Bold'))
    tbl.setStyle(TableStyle(tbl_style))
    elements.append(tbl)
    elements.append(PageBreak())

    elements.append(Paragraph("4. Visualizations", h2))
    for lbl, buf in [
        ("Nutrient Levels — N, P2O5, K2O, Ca, Mg, S (kg/hectare)", nutrient_chart_buf),
        ("Vegetation and Water Indices (NDVI, NDWI)",               vegetation_chart_buf),
        ("Soil Properties",                                          properties_chart_buf),
    ]:
        if buf:
            elements.append(Paragraph(lbl + ":", body))
            elements.append(Image(buf, width=13*cm, height=6.5*cm))
            elements.append(Spacer(1, 0.3*cm))
    elements.append(PageBreak())

    elements.append(Paragraph("5. Crop Recommendations and Treatments", h2))
    for line in recommendations.split('\n'):
        if line.strip(): elements.append(Paragraph(line.strip(), body))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(PageBreak())

    elements.append(Paragraph("6. Parameter-wise Suggestions", h2))
    elements.append(Paragraph("For each parameter: what to do to maintain good levels, or fix problem levels.", small))
    elements.append(Spacer(1, 0.3*cm))

    SUGGESTION_PARAMS = ["pH", "Salinity", "Organic Carbon", "CEC",
                         "Nitrogen", "Phosphorus", "Potassium",
                         "Calcium", "Magnesium", "Sulphur", "NDVI", "NDWI", "LST"]
    sug_data = [["Parameter", "Status", "Action Required"]]
    for param in SUGGESTION_PARAMS:
        value    = params.get(param)
        status   = get_param_status(param, value)
        st_label = "Good" if status == "good" else "Low" if status == "low" else "High" if status == "high" else "N/A"
        sug_data.append([param, st_label, Paragraph(get_suggestion(param, value), small)])

    sug_tbl = Table(sug_data, colWidths=[3*cm, 2*cm, 11*cm])
    sug_style_list = [
        ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN',     (0,0), (-1,-1), 'TOP'),
        ('FONTSIZE',   (0,0), (-1,-1), 9),
        ('BOX',        (0,0), (-1,-1), 1, colors.black),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.Color(0.94,0.98,0.94)]),
    ]
    for i, param in enumerate(SUGGESTION_PARAMS, start=1):
        value = params.get(param)
        s     = get_param_status(param, value)
        c     = (colors.Color(0.1,0.55,0.1) if s == "good" else
                 colors.Color(0.85,0.45,0.0) if s == "low"  else
                 colors.red if s == "high"   else colors.grey)
        sug_style_list.append(('TEXTCOLOR', (1,i), (1,i), c))
        sug_style_list.append(('FONTNAME',  (1,i), (1,i), 'Helvetica-Bold'))
    sug_tbl.setStyle(TableStyle(sug_style_list))
    elements.append(sug_tbl)

    def add_header(canv, doc_obj):
        canv.saveState()
        if os.path.exists(LOGO_PATH):
            canv.drawImage(LOGO_PATH, 2*cm, A4[1]-2.8*cm, width=1.8*cm, height=1.8*cm)
        canv.setFont("Helvetica-Bold", 11)
        canv.drawString(4.5*cm, A4[1]-2.2*cm, "FarmMatrix Soil Health Report")
        canv.setFont("Helvetica", 8)
        canv.drawRightString(A4[0]-2*cm, A4[1]-2.2*cm, f"Generated: {datetime.now():%d %b %Y, %H:%M}")
        canv.setStrokeColor(colors.darkgreen)
        canv.setLineWidth(1)
        canv.line(2*cm, A4[1]-3*cm, A4[0]-2*cm, A4[1]-3*cm)
        canv.restoreState()

    def add_footer(canv, doc_obj):
        canv.saveState()
        canv.setStrokeColor(colors.darkgreen)
        canv.line(2*cm, 1.5*cm, A4[0]-2*cm, 1.5*cm)
        canv.setFont("Helvetica", 8)
        canv.drawCentredString(A4[0]/2, cm, f"Page {doc_obj.page}  |  FarmMatrix Soil Health Report  |  ICAR Standard Units")
        canv.restoreState()

    doc.build(elements, onFirstPage=add_header, onLaterPages=add_header, canvasmaker=canvas.Canvas)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


# ─────────────────────────────────────────────
#  API Routes
# ─────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "FarmMatrix Soil Health API is running.", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/analyze", tags=["Analysis"])
async def analyze(req: AnalyzeRequest):
    """
    Run full soil health analysis for a field.
    Returns all soil parameters, status, suggestions, and health score.
    """
    try:
        result = run_analysis(req)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"/analyze error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/report", tags=["Report"])
async def generate_report_endpoint(req: ReportRequest):
    """
    Generate a full PDF soil health report.
    Returns the PDF as a file download (application/pdf).
    """
    try:
        # First run analysis to get params
        result = run_analysis(req)

        # Reconstruct flat params dict for PDF generator
        params = {p["name"]: p["value"] for p in result["parameters"]}

        location   = f"Lat: {req.lat:.6f}, Lon: {req.lon:.6f}"
        date_range = f"{req.start_date} to {req.end_date}"
        pdf_bytes  = generate_pdf(params, location, date_range)

        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="soil_report_{date.today()}.pdf"',
                "Content-Length": str(len(pdf_bytes)),
            }
        )
    except Exception as e:
        logger.error(f"/report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/report/base64", tags=["Report"])
async def generate_report_base64(req: ReportRequest):
    """
    Generate a PDF soil health report and return it base64-encoded.
    Useful for mobile apps that prefer JSON responses.
    """
    try:
        result = run_analysis(req)
        params = {p["name"]: p["value"] for p in result["parameters"]}
        location   = f"Lat: {req.lat:.6f}, Lon: {req.lon:.6f}"
        date_range = f"{req.start_date} to {req.end_date}"
        pdf_bytes  = generate_pdf(params, location, date_range)
        encoded    = base64.b64encode(pdf_bytes).decode("utf-8")
        return JSONResponse(content={
            "filename": f"soil_report_{date.today()}.pdf",
            "mime_type": "application/pdf",
            "data_base64": encoded,
            "size_bytes": len(pdf_bytes),
        })
    except Exception as e:
        logger.error(f"/report/base64 error: {e}")
        raise HTTPException(status_code=500, detail=str(e))