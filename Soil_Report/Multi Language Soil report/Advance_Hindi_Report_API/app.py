import logging
import os
import json
import base64
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import ee
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from openai import OpenAI

# ─────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"
LOGO_PATH    = os.path.abspath("LOGO.jpeg")
HINDI_FONT   = os.path.abspath("NotoSerifDevanagari-Regular.ttf")

# Register Hindi/Devanagari font for ReportLab
if os.path.exists(HINDI_FONT):
    pdfmetrics.registerFont(TTFont("NotoDevanagari", HINDI_FONT))
    HINDI_FONT_REGISTERED = True
else:
    HINDI_FONT_REGISTERED = False
    logger.warning("NotoSerifDevanagari-Regular.ttf not found. Hindi text may not render.")

# Register font for Matplotlib
if os.path.exists(HINDI_FONT):
    fm.fontManager.addfont(HINDI_FONT)
    MATPLOTLIB_HINDI_FONT = fm.FontProperties(fname=HINDI_FONT)
else:
    MATPLOTLIB_HINDI_FONT = None

# ─────────────────────────────────────────────
#  FastAPI App
# ─────────────────────────────────────────────
app = FastAPI(
    title="FarmMatrix Hindi Soil Health API",
    description="Satellite-based soil analysis — ICAR-aligned Hindi PDF report",
    version="2.0.0",
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
# def initialize_ee():
#     try:
#         credentials_base64 = os.getenv("GEE_SERVICE_ACCOUNT_KEY")
#         if not credentials_base64:
#             raise ValueError("GEE_SERVICE_ACCOUNT_KEY env variable is missing.")
#         credentials_json_str = base64.b64decode(credentials_base64).decode("utf-8")
#         credentials_dict = json.loads(credentials_json_str)
#         from ee import ServiceAccountCredentials
#         credentials = ServiceAccountCredentials(
#             credentials_dict['client_email'], key_data=credentials_json_str
#         )
#         ee.Initialize(credentials)
#         logger.info("✅ Google Earth Engine initialized successfully.")
#     except Exception as e:
#         logger.error(f"❌ GEE initialization failed: {e}")
#         raise

# initialize_ee()


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

# ─────────────────────────────────────────────
#  Constants & Lookups
# ─────────────────────────────────────────────
SOIL_TEXTURE_IMG = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0')

TEXTURE_CLASSES = {
    1:  "चिकनी मिट्टी",
    2:  "गाद-चिकनी मिट्टी",
    3:  "बलुई-चिकनी मिट्टी",
    4:  "चिकनी दोमट",
    5:  "गाद-चिकनी दोमट",
    6:  "बलुई-चिकनी दोमट",
    7:  "दोमट",
    8:  "गाद दोमट",
    9:  "बलुई दोमट",
    10: "गाद",
    11: "दोमट बालू",
    12: "बालू",
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

PARAM_HINDI = {
    "pH":             "pH",
    "Salinity":       "लवणता",
    "Organic Carbon": "कार्बनिक कार्बन",
    "CEC":            "CEC",
    "Soil Texture":   "मिट्टी की बनावट",
    "LST":            "LST",
    "NDWI":           "NDWI",
    "NDVI":           "NDVI",
    "EVI":            "EVI",
    "FVC":            "FVC",
    "Nitrogen":       "नाइट्रोजन",
    "Phosphorus":     "फास्फोरस",
    "Potassium":      "पोटेशियम",
    "Calcium":        "कैल्शियम",
    "Magnesium":      "मैग्नीशियम",
    "Sulphur":        "सल्फर",
}

IDEAL_DISPLAY = {
    "pH":             "6.5-7.5",
    "Salinity":       "<=1.0 mS/cm",
    "Organic Carbon": "0.75-1.50 %",
    "CEC":            "10-30 cmol/kg",
    "Soil Texture":   "दोमट (Loam)",
    "LST":            "15-35 C",
    "NDWI":           "-0.3-0.2",
    "NDVI":           "0.2-0.8",
    "EVI":            "0.2-0.8",
    "FVC":            "0.3-0.8",
    "Nitrogen":       "280-560 kg/ha",
    "Phosphorus":     "11-22 kg/ha",
    "Potassium":      "108-280 kg/ha",
    "Calcium":        "400-800 kg/ha",
    "Magnesium":      "50-200 kg/ha",
    "Sulphur":        "10-40 kg/ha",
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
        "good": "हर 2-3 साल में चूना (lime) डालते रहें। यूरिया की अधिक मात्रा से बचें।",
        "low":  "खेत में 2-4 बोरी कृषि चूना (agricultural lime) प्रति एकड़ डालें। अम्लीय खाद से बचें।",
        "high": "जिप्सम या सल्फर 5-10 kg/एकड़ डालें। अमोनियम सल्फेट उर्वरक का प्रयोग करें।",
    },
    "Salinity": {
        "good": "ड्रिप सिंचाई जारी रखें और जलभराव से बचें ताकि EC कम रहे।",
        "high": "खेत में अतिरिक्त पानी से धुलाई करें। जिप्सम 200 kg/एकड़ डालें। जौ या नमक-सहिष्णु फसल उगाएं।",
    },
    "Organic Carbon": {
        "good": "प्रति एकड़ 2 टन गोबर खाद/कम्पोस्ट हर साल डालें।",
        "low":  "4-5 टन गोबर खाद प्रति एकड़ डालें। ढैंचा या सनई की हरी खाद करें।",
        "high": "अच्छी जुताई से संतुलन बनाएं। जलभराव हो तो जल निकासी सुधारें।",
    },
    "CEC": {
        "good": "कार्बनिक कार्बन बनाए रखें और अत्यधिक जुताई से बचें।",
        "low":  "कम्पोस्ट या मिट्टी-सुधारक मिलाएं जिससे पोषक तत्व धारण क्षमता बढ़े।",
        "high": "pH सही रेंज में रखें ताकि पोषक तत्व पौधों को मिलते रहें।",
    },
    "LST": {
        "good": "मिट्टी का तापमान स्थिर रखने के लिए पलवार (mulch) का उपयोग करें।",
        "low":  "काली पॉलीथिन पलवार से मिट्टी गर्म करें। बुवाई में देरी करें।",
        "high": "पुआल पलवार से मिट्टी ठंडी रखें। सिंचाई की आवृत्ति बढ़ाएं।",
    },
    "NDVI": {
        "good": "फसल घनत्व और उर्वरक कार्यक्रम बनाए रखें।",
        "low":  "कीट या रोग की जांच करें। मिट्टी परीक्षण के अनुसार NPK डालें।",
        "high": "फसल गिरने (lodging) का खतरा देखें। जल निकासी सुनिश्चित करें।",
    },
    "EVI": {
        "good": "वर्तमान फसल प्रबंधन जारी रखें।",
        "low":  "जिंक सल्फेट + बोरॉन का पत्तियों पर छिड़काव करें।",
        "high": "हवा का संचार सुनिश्चित करें। फफूंद रोग पर नजर रखें।",
    },
    "FVC": {
        "good": "जमीन ढकी रखें ताकि कटाव और नमी का नुकसान कम हो।",
        "low":  "पौध संख्या बढ़ाएं या मिश्रित फसल लगाएं। खरपतवार नियंत्रण करें।",
        "high": "पानी के उपयोग पर नजर रखें।",
    },
    "NDWI": {
        "good": "वर्तमान सिंचाई कार्यक्रम बनाए रखें।",
        "low":  "तुरंत सिंचाई करें। ड्रिप या स्प्रिंकलर सिंचाई पर जाएं।",
        "high": "सिंचाई कम करें। जलभराव से बचने के लिए जल निकासी जांचें।",
    },
    "Nitrogen": {
        "good": "यूरिया को विभाजित मात्रा में दें (बेसल + टॉप-ड्रेस) ताकि नुकसान कम हो।",
        "low":  "यूरिया 25-30 kg/एकड़ या DAP डालें। हरी खाद फसल उगाने पर विचार करें।",
        "high": "इस सीजन नाइट्रोजन न डालें। अगली बार नीम-लेपित यूरिया का उपयोग करें।",
    },
    "Phosphorus": {
        "good": "बुवाई के समय SSP या DAP कम रखरखाव मात्रा में डालें।",
        "low":  "DAP 12 kg/एकड़ या SSP 50 kg/एकड़ बुवाई के समय डालें।",
        "high": "इस सीजन फास्फोरस न डालें। जिंक सल्फेट 5 kg/एकड़ डालें।",
    },
    "Potassium": {
        "good": "MOP कम रखरखाव मात्रा में हर दूसरे सीजन में डालें।",
        "low":  "MOP 8-10 kg/एकड़ डालें। लकड़ी की राख जैविक स्रोत के रूप में उपयोग करें।",
        "high": "इस सीजन पोटेशियम न डालें। मैग्नीशियम की कमी के लक्षण देखें।",
    },
    "Calcium": {
        "good": "pH 6.5-7.5 बनाए रखें। हर 2-3 साल में चूना डालें।",
        "low":  "कृषि चूना (CaCO3) 200-400 kg/एकड़ डालें। pH जांचें और सुधारें।",
        "high": "अतिरिक्त चूना न डालें। अधिक Ca से Mg और K की कमी हो सकती है।",
    },
    "Magnesium": {
        "good": "pH सुधार के साथ डोलोमाइट चूना (Mg युक्त) डालें।",
        "low":  "डोलोमाइट 50-100 kg/एकड़ या मैग्नीशियम सल्फेट 10 kg/एकड़ डालें।",
        "high": "अधिक Mg से Ca और K की प्रतिस्पर्धा होती है। जल निकासी सुधारें।",
    },
    "Sulphur": {
        "good": "SSP उर्वरक (S युक्त) बुवाई के समय उपयोग करें।",
        "low":  "जिप्सम 50 kg/एकड़ या प्राथमिक सल्फर 5-10 kg/एकड़ डालें।",
        "high": "सल्फेट युक्त उर्वरक कम करें। EC जांचें।",
    },
}

ALL_BANDS = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]

# ─────────────────────────────────────────────
#  Request Model
# ─────────────────────────────────────────────
class ReportRequest(BaseModel):
    lat: float = Field(..., description="Latitude of field center", example=18.4575)
    lon: float = Field(..., description="Longitude of field center", example=73.8503)
    start_date: str = Field(..., description="Start date YYYY-MM-DD", example="2024-01-01")
    end_date: str   = Field(..., description="End date YYYY-MM-DD",   example="2024-01-16")
    buffer_meters: int = Field(default=200, description="Field buffer radius in meters")
    polygon_coords: Optional[List[List[float]]] = Field(
        default=None,
        description="List of [lon, lat] pairs forming a polygon. If null, buffer around lat/lon is used.",
        example=[
            [73.8483, 18.4555],
            [73.8523, 18.4555],
            [73.8523, 18.4595],
            [73.8483, 18.4595],
            [73.8483, 18.4555]
        ]
    )
    cec_intercept:  float = Field(default=5.0)
    cec_slope_clay: float = Field(default=20.0)
    cec_slope_om:   float = Field(default=15.0)

# ─────────────────────────────────────────────
#  GEE Helpers
# ─────────────────────────────────────────────
def build_region(req: ReportRequest) -> ee.Geometry:
    if req.polygon_coords and len(req.polygon_coords) >= 3:
        return ee.Geometry.Polygon(req.polygon_coords)
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


def sentinel_composite(region, start_str, end_str, bands):
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
                logger.info(f"Sentinel window expanded to {sd} to {ed}")
                return coll.median().multiply(0.0001)
        logger.warning("No Sentinel-2 data available.")
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
        mode = SOIL_TEXTURE_IMG.clip(region.buffer(500)).reduceRegion(
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
        pH_est = (6.5 + 1.2 * ndvi_re_avg + 0.8 * swir_ratio - 0.5 * nir_ratio + 0.15 * (1.0 - brightness))
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
        si1    = (b3 * b4) ** 0.5
        si2    = (b3 ** 2 + b4 ** 2) ** 0.5 if (b3 ** 2 + b4 ** 2) > 0 else 0.0
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
        re_chl      = (b7 / (b5 + 1e-6)) - 1.0
        ndre        = (b8a - b5) / (b8a + b5 + 1e-6)
        mg_clay_idx = (b11 - b12) / (b11 + b12 + 1e-6)
        ndvi        = (b8 - b4) / (b8 + b4 + 1e-6)
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
#  Status & Score Helpers
# ─────────────────────────────────────────────
def get_param_status(param, value):
    if value is None:
        return "na"
    if param == "Soil Texture":
        return "good" if value == 7 else "low"
    rng = IDEAL_RANGES.get(param)
    if rng is None:
        return "good"
    if isinstance(rng, tuple):
        min_val, max_val = rng
        if min_val is None and max_val is not None:
            return "good" if value <= max_val else "high"
        elif max_val is None and min_val is not None:
            return "good" if value >= min_val else "low"
        elif min_val is not None and max_val is not None:
            if value < min_val:   return "low"
            elif value > max_val: return "high"
            return "good"
    return "good"


def status_hindi(status):
    return {"good": "अच्छा", "low": "कम", "high": "अधिक", "na": "N/A"}.get(status, "N/A")


def calculate_soil_health_score(params):
    total = len([v for v in params.values() if v is not None])
    score = sum(1 for p, v in params.items() if get_param_status(p, v) == "good")
    pct   = (score / total) * 100 if total > 0 else 0
    rating = ("उत्कृष्ट" if pct >= 80 else "अच्छा" if pct >= 60 else
              "ठीक-ठाक"  if pct >= 40 else "खराब")
    return pct, rating


def generate_interpretation(param, value):
    if value is None:
        return "डेटा उपलब्ध नहीं।"
    if param == "Soil Texture":
        return TEXTURE_CLASSES.get(value, "अज्ञात मिट्टी।")
    if param == "NDWI":
        if value >= -0.10:    return "नमी पर्याप्त है; सिंचाई की जरूरत नहीं।"
        elif value >= -0.30:  return "हल्का तनाव; 2 दिन में सिंचाई करें।"
        elif value >= -0.40:  return "मध्यम तनाव; कल सिंचाई करें।"
        else:                 return "गंभीर तनाव; तुरंत सिंचाई करें।"
    if param == "Phosphorus":
        return "स्पेक्ट्रल विश्वसनीयता कम। केवल मार्गदर्शन के रूप में उपयोग करें।"
    if param == "Sulphur":
        return "स्पेक्ट्रल विश्वसनीयता कम (जिप्सम सूचकांक)। केवल अनुमान के रूप में उपयोग करें।"
    status = get_param_status(param, value)
    if status == "good":
        return f"उचित स्तर ({IDEAL_DISPLAY.get(param, 'N/A')})।"
    elif status == "low":
        rng   = IDEAL_RANGES.get(param, (None, None))
        min_v = rng[0] if isinstance(rng, tuple) else None
        return f"कम है (न्यूनतम {min_v} से नीचे)।"
    elif status == "high":
        rng   = IDEAL_RANGES.get(param, (None, None))
        max_v = rng[1] if isinstance(rng, tuple) else None
        return f"अधिक है (अधिकतम {max_v} से ऊपर)।"
    return "कोई व्याख्या नहीं।"


def get_suggestion(param, value):
    if value is None or param not in SUGGESTIONS:
        return "-"
    status = get_param_status(param, value)
    s = SUGGESTIONS[param]
    if status == "good":  return "ठीक है: " + s.get("good", "वर्तमान अभ्यास जारी रखें।")
    elif status == "low": return "सुधार करें: " + s.get("low", s.get("high", "कृषि विशेषज्ञ से परामर्श करें।"))
    elif status == "high":return "सुधार करें: " + s.get("high", s.get("low", "कृषि विशेषज्ञ से परामर्श करें।"))
    return "-"


def get_color_for_value(param, value):
    s = get_param_status(param, value)
    return 'green' if s == 'good' else ('orange' if s == 'low' else ('red' if s == 'high' else 'grey'))


# ─────────────────────────────────────────────
#  Charts (Hindi labels, BytesIO output)
# ─────────────────────────────────────────────
def hfont():
    if MATPLOTLIB_HINDI_FONT:
        return {"fontproperties": MATPLOTLIB_HINDI_FONT}
    return {}


def make_nutrient_chart(n, p, k, ca, mg, s):
    nutrients  = ["नाइट्रोजन\n(kg/ha)", "फास्फोरस\nP2O5 (kg/ha)", "पोटेशियम\nK2O (kg/ha)",
                  "कैल्शियम\n(kg/ha)", "मैग्नीशियम\n(kg/ha)", "सल्फर\n(kg/ha)"]
    param_keys = ["Nitrogen", "Phosphorus", "Potassium", "Calcium", "Magnesium", "Sulphur"]
    values     = [n or 0, p or 0, k or 0, ca or 0, mg or 0, s or 0]
    bar_colors = [get_color_for_value(pk, v) for pk, v in zip(param_keys, values)]
    fig, ax = plt.subplots(figsize=(10, 4))
    bars = ax.bar(range(len(nutrients)), values, color=bar_colors, alpha=0.82)
    if MATPLOTLIB_HINDI_FONT:
        ax.set_title("मिट्टी के पोषक तत्व (kg/हेक्टेयर) — ICAR मानक", fontsize=11, **hfont())
        ax.set_ylabel("kg / हेक्टेयर", **hfont())
        ax.set_xticks(range(len(nutrients)))
        ax.set_xticklabels(nutrients, fontproperties=MATPLOTLIB_HINDI_FONT, fontsize=8)
    else:
        ax.set_title("Soil Nutrients (kg/ha) — ICAR Standard", fontsize=11)
        ax.set_ylabel("kg / hectare")
        ax.set_xticks(range(len(nutrients)))
        ax.set_xticklabels(nutrients, fontsize=8)
    ymax = max(values) * 1.35 if any(values) else 400
    ax.set_ylim(0, ymax)
    status_labels = {"good": "अच्छा", "low": "कम", "high": "अधिक"}
    for bar, val, pk in zip(bars, values, param_keys):
        st2 = get_param_status(pk, val)
        lbl = status_labels.get(st2, "N/A")
        kw  = {"ha": "center", "va": "bottom", "fontsize": 7}
        if MATPLOTLIB_HINDI_FONT: kw["fontproperties"] = MATPLOTLIB_HINDI_FONT
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.02, f"{val:.1f}\n{lbl}", **kw)
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
    if MATPLOTLIB_HINDI_FONT:
        ax.set_title("वनस्पति और जल सूचकांक", fontsize=11, **hfont())
        ax.set_ylabel("सूचकांक मान", **hfont())
    else:
        ax.set_title("Vegetation and Water Indices", fontsize=11)
        ax.set_ylabel("Index Value")
    ax.set_ylim(-1, 1)
    ax.axhline(0, color='black', linewidth=0.5, linestyle='--')
    status_labels = {"good": "अच्छा", "low": "कम", "high": "अधिक"}
    for i, (bar, val) in enumerate(zip(bars, values)):
        st2  = get_param_status(indices[i], val)
        lbl  = status_labels.get(st2, "N/A")
        ypos = bar.get_height() + 0.03 if val >= 0 else bar.get_height() - 0.08
        kw   = {"ha": "center", "va": "bottom", "fontsize": 9}
        if MATPLOTLIB_HINDI_FONT: kw["fontproperties"] = MATPLOTLIB_HINDI_FONT
        ax.text(bar.get_x() + bar.get_width() / 2, ypos, f"{val:.2f}\n{lbl}", **kw)
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
    if MATPLOTLIB_HINDI_FONT:
        ax.set_title("मिट्टी के गुण (ICAR मानक)", fontsize=11, **hfont())
        ax.set_ylabel("मान", **hfont())
    else:
        ax.set_title("Soil Properties (ICAR Standard)", fontsize=11)
        ax.set_ylabel("Value")
    ymax = max(values) * 1.35 if any(values) else 50
    ax.set_ylim(0, ymax)
    status_labels = {"good": "अच्छा", "low": "कम", "high": "अधिक"}
    for bar, val, pk in zip(bars, values, param_keys):
        st2 = get_param_status(pk, val)
        lbl = status_labels.get(st2, "N/A")
        kw  = {"ha": "center", "va": "bottom", "fontsize": 8}
        if MATPLOTLIB_HINDI_FONT: kw["fontproperties"] = MATPLOTLIB_HINDI_FONT
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.02, f"{val:.2f}\n{lbl}", **kw)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────
#  Groq AI (Hindi)
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
#  Core Analysis
# ─────────────────────────────────────────────
def run_analysis(req: ReportRequest) -> dict:
    region = build_region(req)
    comp   = sentinel_composite(region, req.start_date, req.end_date, ALL_BANDS)
    texc   = get_soil_texture(region)
    lst    = get_lst(region, req.end_date)

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

    return {
        "pH": ph, "Salinity": sal, "Organic Carbon": oc, "CEC": cec,
        "Soil Texture": texc, "LST": lst, "NDWI": ndwi, "NDVI": ndvi,
        "EVI": evi, "FVC": fvc, "Nitrogen": n_val, "Phosphorus": p_val,
        "Potassium": k_val, "Calcium": ca_val, "Magnesium": mg_val, "Sulphur": s_val,
    }


# ─────────────────────────────────────────────
#  PDF Generator (Hindi)
# ─────────────────────────────────────────────
def generate_pdf(params: dict, location: str, date_range: str) -> bytes:
    REPORT_PARAMS   = {k: v for k, v in params.items() if k not in ("EVI", "FVC")}
    score, rating   = calculate_soil_health_score(REPORT_PARAMS)
    interpretations = {p: generate_interpretation(p, v) for p, v in REPORT_PARAMS.items()}

    nutrient_chart_buf   = make_nutrient_chart(
        params["Nitrogen"], params["Phosphorus"], params["Potassium"],
        params["Calcium"],  params["Magnesium"],  params["Sulphur"])
    vegetation_chart_buf = make_vegetation_chart(params["NDVI"], params["NDWI"])
    properties_chart_buf = make_soil_properties_chart(
        params["pH"], params["Salinity"], params["Organic Carbon"], params["CEC"], params["LST"])

    def fmtv(param, v):
        if v is None: return "N/A"
        return f"{v:.2f}{UNIT_MAP.get(param, '')}"

    tex_d = TEXTURE_CLASSES.get(params.get("Soil Texture"), "N/A") if params.get("Soil Texture") else "N/A"

    exec_prompt = f"""आप एक अनुभवी कृषि विशेषज्ञ हैं। नीचे दी गई मिट्टी की जांच रिपोर्ट के आधार पर 3-5 बिंदुओं में एक संक्षिप्त सारांश लिखें।
भाषा: सरल हिंदी, किसान के लिए समझने योग्य। कोई तकनीकी शब्दजाल नहीं।
स्थान: {location}
तिथि: {date_range}
मिट्टी स्वास्थ्य स्कोर: {score:.1f}% ({rating})
pH={fmtv('pH', params.get('pH'))}, EC={fmtv('Salinity', params.get('Salinity'))}, CEC={fmtv('CEC', params.get('CEC'))}
मिट्टी की बनावट={tex_d}, नाइट्रोजन={fmtv('Nitrogen', params.get('Nitrogen'))}, पोटेशियम={fmtv('Potassium', params.get('Potassium'))}
कैल्शियम={fmtv('Calcium', params.get('Calcium'))}, मैग्नीशियम={fmtv('Magnesium', params.get('Magnesium'))}, सल्फर={fmtv('Sulphur', params.get('Sulphur'))} (अनुमानित)
प्रत्येक बिंदु एक बुलेट से शुरू करें। कोई bold या markdown नहीं। केवल हिंदी में उत्तर दें।"""

    rec_prompt = f"""आप एक कृषि सलाहकार हैं। नीचे दी गई मिट्टी की जानकारी के आधार पर भारतीय किसान के लिए 3-5 व्यावहारिक सुझाव दें।
pH={fmtv('pH', params.get('pH'))}, EC={fmtv('Salinity', params.get('Salinity'))}, CEC={fmtv('CEC', params.get('CEC'))}, मिट्टी={tex_d}
नाइट्रोजन={fmtv('Nitrogen', params.get('Nitrogen'))}, पोटेशियम={fmtv('Potassium', params.get('Potassium'))}
NDVI={fmtv('NDVI', params.get('NDVI'))}, NDWI={fmtv('NDWI', params.get('NDWI'))}
भारतीय जलवायु के अनुसार उपयुक्त फसलें और सरल उर्वरक उपाय बताएं।
प्रत्येक बिंदु एक बुलेट से शुरू करें। कोई bold या markdown नहीं। केवल हिंदी में उत्तर दें।"""

    executive_summary = call_groq(exec_prompt) or "सारांश उपलब्ध नहीं।"
    recommendations   = call_groq(rec_prompt)  or "सुझाव उपलब्ध नहीं।"

    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=3*cm,  bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    HFONT  = "NotoDevanagari" if HINDI_FONT_REGISTERED else "Helvetica"

    title_style = ParagraphStyle('HTitle', parent=styles['Title'],    fontName=HFONT, fontSize=18, spaceAfter=16, alignment=TA_CENTER)
    h2          = ParagraphStyle('HH2',    parent=styles['Heading2'], fontName=HFONT, fontSize=12, spaceAfter=8,  textColor=colors.darkgreen)
    body        = ParagraphStyle('HBody',  parent=styles['BodyText'], fontName=HFONT, fontSize=9,  leading=14)
    small       = ParagraphStyle('HSmall', parent=styles['BodyText'], fontName=HFONT, fontSize=8,  leading=12)
    center_body = ParagraphStyle('HCtr',   parent=styles['BodyText'], fontName=HFONT, fontSize=10, leading=14, alignment=TA_CENTER)

    elements = []

    # Cover page
    elements.append(Spacer(1, 2*cm))
    if os.path.exists(LOGO_PATH):
        logo_img = Image(LOGO_PATH, width=10*cm, height=10*cm)
        logo_img.hAlign = 'CENTER'
        elements.append(logo_img)
    elements.append(Spacer(1, 0.8*cm))
    elements.append(Paragraph("FarmMatrix मिट्टी स्वास्थ्य रिपोर्ट", title_style))
    elements.append(Spacer(1, 0.4*cm))
    elements.append(Paragraph(f"<b>स्थान:</b> {location}", center_body))
    elements.append(Paragraph(f"<b>तिथि सीमा:</b> {date_range}", center_body))
    elements.append(Paragraph(f"<b>रिपोर्ट तैयार:</b> {datetime.now():%d %B %Y, %H:%M}", center_body))
    elements.append(PageBreak())

    # Section 1
    elements.append(Paragraph("1. संक्षिप्त सारांश", h2))
    for line in executive_summary.split('\n'):
        if line.strip(): elements.append(Paragraph(line.strip(), body))
    elements.append(Spacer(1, 0.4*cm))

    # Section 2
    elements.append(Paragraph("2. मिट्टी स्वास्थ्य रेटिंग", h2))
    good_count  = sum(1 for p, v in REPORT_PARAMS.items() if get_param_status(p, v) == "good")
    valid_count = len([v for v in REPORT_PARAMS.values() if v is not None])
    rt = Table(
        [["कुल स्कोर", "रेटिंग", "उचित स्तर पर पैरामीटर"],
         [f"{score:.1f}%", rating, f"{good_count} / {valid_count}"]],
        colWidths=[5*cm, 4*cm, 7*cm]
    )
    rt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,-1), HFONT),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE',   (0,0), (-1,-1), 10),
        ('BOX',        (0,0), (-1,-1), 1, colors.black),
    ]))
    elements.append(rt)
    elements.append(Spacer(1, 0.4*cm))
    elements.append(PageBreak())

    # Section 3
    elements.append(Paragraph("3. मिट्टी पैरामीटर विश्लेषण (ICAR मानक)", h2))
    table_data = [["पैरामीटर", "मान", "ICAR आदर्श सीमा", "स्थिति", "व्याख्या"]]
    for param, value in REPORT_PARAMS.items():
        unit     = UNIT_MAP.get(param, "")
        hindi_nm = PARAM_HINDI.get(param, param)
        if param == "Soil Texture":
            val_text = TEXTURE_CLASSES.get(value, "N/A") if value is not None else "N/A"
        else:
            val_text = f"{value:.2f}{unit}" if value is not None else "N/A"
        status   = get_param_status(param, value)
        st_label = status_hindi(status)
        table_data.append([
            Paragraph(hindi_nm, small), val_text,
            IDEAL_DISPLAY.get(param, "N/A"), st_label,
            Paragraph(interpretations[param], small)
        ])

    tbl = Table(table_data, colWidths=[3*cm, 2.5*cm, 3*cm, 1.8*cm, 5.7*cm])
    tbl_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,-1), HFONT),
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
        tbl_style.append(('FONTNAME',  (3,i), (3,i), HFONT))
    tbl.setStyle(TableStyle(tbl_style))
    elements.append(tbl)
    elements.append(PageBreak())

    # Section 4
    elements.append(Paragraph("4. चार्ट और ग्राफ", h2))
    for lbl, buf in [
        ("पोषक तत्व — नाइट्रोजन, फास्फोरस, पोटेशियम, कैल्शियम, मैग्नीशियम, सल्फर (kg/हेक्टेयर)", nutrient_chart_buf),
        ("वनस्पति और जल सूचकांक (NDVI, NDWI)", vegetation_chart_buf),
        ("मिट्टी के गुण", properties_chart_buf),
    ]:
        if buf:
            elements.append(Paragraph(lbl + ":", body))
            elements.append(Image(buf, width=13*cm, height=6.5*cm))
            elements.append(Spacer(1, 0.3*cm))
    elements.append(PageBreak())

    # Section 5
    elements.append(Paragraph("5. फसल सुझाव और उपचार", h2))
    for line in recommendations.split('\n'):
        if line.strip(): elements.append(Paragraph(line.strip(), body))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(PageBreak())

    # Section 6
    elements.append(Paragraph("6. पैरामीटर-वार सुझाव", h2))
    elements.append(Paragraph("प्रत्येक पैरामीटर के लिए: अच्छे स्तर को बनाए रखने या समस्या ठीक करने के उपाय।", small))
    elements.append(Spacer(1, 0.3*cm))

    SUGGESTION_PARAMS = ["pH", "Salinity", "Organic Carbon", "CEC",
                         "Nitrogen", "Phosphorus", "Potassium",
                         "Calcium", "Magnesium", "Sulphur", "NDVI", "NDWI", "LST"]
    sug_data = [["पैरामीटर", "स्थिति", "आवश्यक कार्रवाई"]]
    for param in SUGGESTION_PARAMS:
        value    = params.get(param)
        status   = get_param_status(param, value)
        st_label = status_hindi(status)
        hindi_nm = PARAM_HINDI.get(param, param)
        sug_data.append([
            Paragraph(hindi_nm, small),
            st_label,
            Paragraph(get_suggestion(param, value), small)
        ])

    sug_tbl = Table(sug_data, colWidths=[3*cm, 2*cm, 11*cm])
    sug_style_list = [
        ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,-1), HFONT),
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
        sug_style_list.append(('FONTNAME',  (1,i), (1,i), HFONT))
    sug_tbl.setStyle(TableStyle(sug_style_list))
    elements.append(sug_tbl)

    def add_header(canv, doc_obj):
        canv.saveState()
        if os.path.exists(LOGO_PATH):
            canv.drawImage(LOGO_PATH, 2*cm, A4[1]-2.8*cm, width=1.8*cm, height=1.8*cm)
        canv.setFont(HFONT if HINDI_FONT_REGISTERED else "Helvetica-Bold", 11)
        canv.drawString(4.5*cm, A4[1]-2.2*cm, "FarmMatrix मिट्टी स्वास्थ्य रिपोर्ट")
        canv.setFont("Helvetica", 8)
        canv.drawRightString(A4[0]-2*cm, A4[1]-2.2*cm, f"Report: {datetime.now():%d %b %Y, %H:%M}")
        canv.setStrokeColor(colors.darkgreen)
        canv.setLineWidth(1)
        canv.line(2*cm, A4[1]-3*cm, A4[0]-2*cm, A4[1]-3*cm)
        canv.restoreState()

    def add_footer(canv, doc_obj):
        canv.saveState()
        canv.setStrokeColor(colors.darkgreen)
        canv.line(2*cm, 1.5*cm, A4[0]-2*cm, 1.5*cm)
        canv.setFont(HFONT if HINDI_FONT_REGISTERED else "Helvetica", 8)
        canv.drawCentredString(A4[0]/2, cm, f"Page {doc_obj.page}  |  FarmMatrix मिट्टी स्वास्थ्य रिपोर्ट  |  ICAR मानक")
        canv.restoreState()

    doc.build(elements, onFirstPage=add_header, onLaterPages=add_header, canvasmaker=canvas.Canvas)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


# ─────────────────────────────────────────────
#  API Routes
# ─────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "FarmMatrix Hindi Soil Health API is running.", "version": "2.0.0"}


@app.post("/report", tags=["Report"])
async def generate_report_endpoint(req: ReportRequest):
    """
    Run full soil analysis and generate a complete Hindi PDF report.
    - Fetches Sentinel-2 satellite data for the given location and date range
    - Computes all ICAR soil parameters with Hindi labels
    - Generates AI-powered Hindi recommendations via Groq
    - Returns a downloadable PDF
    Use polygon_coords for a custom field shape, or leave null to use a buffer circle around lat/lon.
    """
    try:
        params     = run_analysis(req)
        location   = f"Lat: {req.lat:.6f}, Lon: {req.lon:.6f}"
        date_range = f"{req.start_date} to {req.end_date}"
        pdf_bytes  = generate_pdf(params, location, date_range)

        # ✅ ASCII-only filename to avoid latin-1 encoding error
        filename = f"soil_report_{date.today()}.pdf"

        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            }
        )
    except Exception as e:
        logger.error(f"/report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))