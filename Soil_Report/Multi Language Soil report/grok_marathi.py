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
#  Configuration
# ─────────────────────────────────────────────
GROQ_API_KEY  = "grok-api"
GROQ_MODEL    = "llama-3.3-70b-versatile"
LOGO_PATH     = os.path.abspath("LOGO.jpg")
MARATHI_FONT  = os.path.abspath("NotoSerifDevanagari-Regular.ttf")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ── Register Marathi/Devanagari font for ReportLab ────────────────────────────
if os.path.exists(MARATHI_FONT):
    pdfmetrics.registerFont(TTFont("NotoDevanagari", MARATHI_FONT))
    MARATHI_FONT_REGISTERED = True
else:
    MARATHI_FONT_REGISTERED = False
    logging.warning("NotoSerifDevanagari-Regular.ttf not found. Marathi text may not render.")

# ── Register font for Matplotlib ──────────────────────────────────────────────
if os.path.exists(MARATHI_FONT):
    fm.fontManager.addfont(MARATHI_FONT)
    MATPLOTLIB_MARATHI_FONT = fm.FontProperties(fname=MARATHI_FONT)
else:
    MATPLOTLIB_MARATHI_FONT = None

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
    1:  "चिकणमाती (Clay)",
    2:  "गाळ-चिकणमाती (Silty Clay)",
    3:  "वाळू-चिकणमाती (Sandy Clay)",
    4:  "चिकणमाती दुमट (Clay Loam)",
    5:  "गाळ-चिकणमाती दुमट (Silty Clay Loam)",
    6:  "वाळू-चिकणमाती दुमट (Sandy Clay Loam)",
    7:  "दुमट (Loam)",
    8:  "गाळ दुमट (Silty Loam)",
    9:  "वाळू दुमट (Sandy Loam)",
    10: "गाळ (Silt)",
    11: "दुमट वाळू (Loamy Sand)",
    12: "वाळू (Sand)",
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

# Internal English keys → Marathi display names
PARAM_MARATHI = {
    "pH":             "pH",
    "Salinity":       "क्षारता",
    "Organic Carbon": "सेंद्रिय कार्बन",
    "CEC":            "CEC",
    "Soil Texture":   "मातीचा पोत",
    "LST":            "LST",
    "NDWI":           "NDWI",
    "NDVI":           "NDVI",
    "EVI":            "EVI",
    "FVC":            "FVC",
    "Nitrogen":       "नत्र (नायट्रोजन)",
    "Phosphorus":     "स्फुरद (फॉस्फरस)",
    "Potassium":      "पालाश (पोटॅशियम)",
    "Calcium":        "कॅल्शियम",
    "Magnesium":      "मॅग्नेशियम",
    "Sulphur":        "गंधक (सल्फर)",
}

IDEAL_DISPLAY = {
    "pH":             "6.5–7.5",
    "Salinity":       "<=1.0 mS/cm",
    "Organic Carbon": "0.75–1.50 %",
    "CEC":            "10–30 cmol/kg",
    "Soil Texture":   "दुमट (Loam)",
    "LST":            "15–35 °C",
    "NDWI":           "-0.3–0.2",
    "NDVI":           "0.2–0.8",
    "EVI":            "0.2–0.8",
    "FVC":            "0.3–0.8",
    "Nitrogen":       "280–560 kg/ha",
    "Phosphorus":     "11–22 kg/ha",
    "Potassium":      "108–280 kg/ha",
    "Calcium":        "400–800 kg/ha",
    "Magnesium":      "50–200 kg/ha",
    "Sulphur":        "10–40 kg/ha",
}

UNIT_MAP = {
    "pH": "", "Salinity": " mS/cm", "Organic Carbon": " %",
    "CEC": " cmol/kg", "Soil Texture": "", "LST": " °C",
    "NDWI": "", "NDVI": "", "EVI": "", "FVC": "",
    "Nitrogen": " kg/ha", "Phosphorus": " kg/ha", "Potassium": " kg/ha",
    "Calcium": " kg/ha", "Magnesium": " kg/ha", "Sulphur": " kg/ha",
}

# ── Marathi suggestions ───────────────────────────────────────────────────────
SUGGESTIONS = {
    "pH": {
        "good": "दर 2–3 वर्षांनी चुना (lime) टाका. जास्त युरिया वापरणे टाळा.",
        "low":  "शेतात 2–4 पोती कृषी चुना प्रति एकर टाका. आम्लयुक्त खते टाळा.",
        "high": "जिप्सम किंवा गंधक 5–10 kg/एकर टाका. अमोनियम सल्फेट खत वापरा.",
    },
    "Salinity": {
        "good": "ठिबक सिंचन सुरू ठेवा आणि जमिनीत पाणी साचणे टाळा.",
        "high": "शेतात जास्तीचे पाणी सोडून धुवा. जिप्सम 200 kg/एकर टाका. सहनशील पिके घ्या.",
    },
    "Organic Carbon": {
        "good": "दरवर्षी 2 टन शेणखत/कंपोस्ट प्रति एकर टाका.",
        "low":  "4–5 टन शेणखत प्रति एकर टाका. ताग किंवा धैंचाचे हिरवे खत करा.",
        "high": "चांगल्या नांगरणीने संतुलन राखा. पाणी साचत असल्यास निचरा सुधारा.",
    },
    "CEC": {
        "good": "सेंद्रिय कार्बन टिकवा आणि अतिनांगरणी टाळा.",
        "low":  "कंपोस्ट किंवा माती सुधारक घाला जेणेकरून पोषकद्रव्ये टिकून राहतील.",
        "high": "pH योग्य श्रेणीत ठेवा म्हणजे पोषकद्रव्ये वनस्पतींना मिळतात.",
    },
    "LST": {
        "good": "जमिनीचे तापमान स्थिर ठेवण्यासाठी आच्छादन (mulch) वापरा.",
        "low":  "काळ्या पॉलिथिन आच्छादनाने जमीन उबदार करा. पेरणी उशिरा करा.",
        "high": "पेंढा आच्छादनाने जमीन थंड ठेवा. सिंचनाची वारंवारता वाढवा.",
    },
    "NDVI": {
        "good": "पिकाची घनता आणि खत वेळापत्रक टिकवा.",
        "low":  "कीड किंवा रोग तपासा. मातीचाचणीनुसार NPK टाका.",
        "high": "पीक लोळण्याचा धोका पाहा. चांगला निचरा सुनिश्चित करा.",
    },
    "EVI": {
        "good": "सध्याचे पीक व्यवस्थापन सुरू ठेवा.",
        "low":  "झिंक सल्फेट + बोरॉनची पानांवर फवारणी करा.",
        "high": "हवा खेळती ठेवा. बुरशीजन्य रोगावर लक्ष ठेवा.",
    },
    "FVC": {
        "good": "जमीन झाकलेली ठेवा म्हणजे धूप आणि ओलावा कमी होणार नाही.",
        "low":  "रोपांची संख्या वाढवा किंवा आंतरपीक घ्या. तण नियंत्रण करा.",
        "high": "पाण्याच्या वापरावर लक्ष ठेवा — दाट पीक ओलाव्याचा ताण लपवू शकते.",
    },
    "NDWI": {
        "good": "सध्याचे सिंचन वेळापत्रक सुरू ठेवा.",
        "low":  "ताबडतोब सिंचन करा. शक्य असल्यास ठिबक किंवा तुषार सिंचनावर जा.",
        "high": "सिंचन कमी करा. जलसाठा होऊ नये म्हणून निचरा तपासा.",
    },
    "Nitrogen": {
        "good": "युरिया विभागून द्या (मूळ + टॉप-ड्रेस) म्हणजे नुकसान कमी होईल.",
        "low":  "युरिया 25–30 kg/एकर किंवा DAP टाका. हिरवे खत पीक घेण्याचा विचार करा.",
        "high": "या हंगामात नत्र देऊ नका. पुढच्या वेळी निम-लेपित युरिया वापरा.",
    },
    "Phosphorus": {
        "good": "पेरणीच्या वेळी SSP किंवा DAP कमी देखभाल मात्रेत द्या.",
        "low":  "DAP 12 kg/एकर किंवा SSP 50 kg/एकर पेरणीच्या वेळी द्या.",
        "high": "या हंगामात स्फुरद देऊ नका. झिंक सल्फेट 5 kg/एकर टाका.",
    },
    "Potassium": {
        "good": "MOP कमी देखभाल मात्रेत दर दुसऱ्या हंगामात द्या.",
        "low":  "MOP 8–10 kg/एकर टाका. लाकडाची राख सेंद्रिय स्रोत म्हणून वापरा.",
        "high": "या हंगामात पालाश देऊ नका. मॅग्नेशियमच्या कमतरतेची लक्षणे पाहा.",
    },
    "Calcium": {
        "good": "pH 6.5–7.5 टिकवा. दर 2–3 वर्षांनी चुना टाका.",
        "low":  "कृषी चुना (CaCO3) 200–400 kg/एकर टाका. pH तपासा व सुधारा.",
        "high": "जास्तीचा चुना टाकू नका. जास्त Ca मुळे Mg व K ची कमतरता होऊ शकते.",
    },
    "Magnesium": {
        "good": "pH सुधारताना डोलोमाईट चुना (Mg युक्त) वापरा.",
        "low":  "डोलोमाईट 50–100 kg/एकर किंवा मॅग्नेशियम सल्फेट 10 kg/एकर टाका.",
        "high": "जास्त Mg मुळे Ca व K शी स्पर्धा होते. निचरा सुधारा.",
    },
    "Sulphur": {
        "good": "पेरणीच्या वेळी SSP खत (S युक्त) वापरा.",
        "low":  "जिप्सम 50 kg/एकर किंवा मूळ गंधक 5–10 kg/एकर टाका. तेलबिया व कडधान्यांसाठी उपयुक्त.",
        "high": "सल्फेट युक्त खते कमी करा. EC तपासा — जास्त S मीठ साठवण दर्शवू शकते.",
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
    end_dt    = end
    start_dt  = end_dt - relativedelta(months=1)
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
        N_kgha = (280.0 + 300.0 * ndre + 150.0 * evi + 20.0 * (ci_re / 5.0)
                  - 80.0 * brightness + 30.0 * mcari)
        N_kgha = max(50.0, min(600.0, N_kgha))
        si1    = (b3 * b4) ** 0.5
        si2    = (b3 ** 2 + b4 ** 2) ** 0.5 if (b3 ** 2 + b4 ** 2) > 0 else 0.0
        mndbsi = (si1 + si2) / 2.0
        P_kgha = (11.0 + 15.0 * (1.0 - brightness) + 6.0 * ndvi
                  + 4.0 * abs(mndbsi) + 2.0 * b3)
        P_kgha = max(2.0, min(60.0, P_kgha))
        potassium_index = b11 / (b5 + b6 + 1e-6)
        salinity_factor = (b11 - b12) / (b11 + b12 + 1e-6)
        K_kgha = (150.0 + 200.0 * potassium_index + 80.0 * salinity_factor + 60.0 * ndvi)
        K_kgha = max(40.0, min(600.0, K_kgha))
        return float(N_kgha), float(P_kgha), float(K_kgha)
    except Exception as e:
        logging.error(f"Error in get_npk_kgha: {e}")
        return None, None, None


def get_calcium_kgha(bs):
    try:
        b2  = bs.get("B2",  0.0)
        b3  = bs.get("B3",  0.0)
        b4  = bs.get("B4",  0.0)
        b8  = bs.get("B8",  0.0)
        b11 = bs.get("B11", 0.0)
        b12 = bs.get("B12", 0.0)
        carbonate_idx = (b11 + b12) / (b4 + b3 + 1e-6)
        brightness    = (b2 + b3 + b4) / 3.0
        ndvi          = (b8 - b4) / (b8 + b4 + 1e-6)
        clay_idx      = (b11 - b8) / (b11 + b8 + 1e-6)
        Ca_kgha = (550.0 + 250.0 * carbonate_idx + 150.0 * brightness
                   - 100.0 * ndvi - 80.0 * clay_idx)
        return max(100.0, min(1200.0, float(Ca_kgha)))
    except Exception as e:
        logging.error(f"Error in get_calcium_kgha: {e}")
        return None


def get_magnesium_kgha(bs):
    try:
        b4  = bs.get("B4",  0.0)
        b5  = bs.get("B5",  0.0)
        b6  = bs.get("B6",  0.0)
        b7  = bs.get("B7",  0.0)
        b8  = bs.get("B8",  0.0)
        b8a = bs.get("B8A", 0.0)
        b11 = bs.get("B11", 0.0)
        b12 = bs.get("B12", 0.0)
        re_chl      = (b7 / (b5 + 1e-6)) - 1.0
        ndre        = (b8a - b5) / (b8a + b5 + 1e-6)
        mg_clay_idx = (b11 - b12) / (b11 + b12 + 1e-6)
        ndvi        = (b8 - b4) / (b8 + b4 + 1e-6)
        Mg_kgha = (110.0 + 60.0 * ndre + 40.0 * re_chl + 30.0 * mg_clay_idx + 20.0 * ndvi)
        return max(10.0, min(400.0, float(Mg_kgha)))
    except Exception as e:
        logging.error(f"Error in get_magnesium_kgha: {e}")
        return None


def get_sulphur_kgha(bs):
    try:
        b2  = bs.get("B2",  0.0)
        b3  = bs.get("B3",  0.0)
        b4  = bs.get("B4",  0.0)
        b5  = bs.get("B5",  0.0)
        b8  = bs.get("B8",  0.0)
        b11 = bs.get("B11", 0.0)
        b12 = bs.get("B12", 0.0)
        gypsum_idx   = b11 / (b3 + b4 + 1e-6)
        si1          = (b3 * b4) ** 0.5
        si2          = (b3 ** 2 + b4 ** 2) ** 0.5 if (b3 ** 2 + b4 ** 2) > 0 else 0.0
        salinity_idx = (si1 + si2) / 2.0
        re_red_ratio = b5 / (b4 + 1e-6)
        swir_ratio   = b12 / (b11 + 1e-6)
        ndvi         = (b8 - b4) / (b8 + b4 + 1e-6)
        S_kgha = (20.0 + 15.0 * gypsum_idx + 10.0 * abs(salinity_idx)
                  + 5.0 * (re_red_ratio - 1.0) - 8.0 * swir_ratio + 5.0 * ndvi)
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
        return "good" if value == IDEAL_RANGES.get("Soil Texture", 7) else "low"
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


def status_marathi(status):
    return {"good": "चांगले", "low": "कमी", "high": "जास्त", "na": "N/A"}.get(status, "N/A")


def calculate_soil_health_score(params):
    score = 0
    total = len([v for v in params.values() if v is not None])
    for param, value in params.items():
        if get_param_status(param, value) == "good":
            score += 1
    pct    = (score / total) * 100 if total > 0 else 0
    rating = ("उत्कृष्ट" if pct >= 80 else "चांगले" if pct >= 60 else
              "ठीकठाक"   if pct >= 40 else "खराब")
    return pct, rating


def generate_interpretation(param, value):
    if value is None:
        return "माहिती उपलब्ध नाही."
    if param == "Soil Texture":
        return TEXTURE_CLASSES.get(value, "अज्ञात माती.")
    if param == "NDWI":
        if value >= -0.10:
            return "ओलावा पुरेसा आहे; सिंचनाची गरज नाही."
        elif -0.30 <= value < -0.10:
            return "सौम्य ताण; 2 दिवसांत सिंचन करा."
        elif -0.40 <= value < -0.30:
            return "मध्यम ताण; उद्या सिंचन करा."
        else:
            return "तीव्र ताण; ताबडतोब सिंचन करा."
    if param == "Phosphorus":
        return "स्पेक्ट्रल विश्वासार्हता कमी. फक्त मार्गदर्शन म्हणून वापरा."
    if param == "Sulphur":
        return "स्पेक्ट्रल विश्वासार्हता कमी (जिप्सम निर्देशांक). अंदाज म्हणून वापरा."
    status = get_param_status(param, value)
    if status == "good":
        return f"योग्य पातळी ({IDEAL_DISPLAY.get(param, 'N/A')})."
    elif status == "low":
        rng   = IDEAL_RANGES.get(param, (None, None))
        min_v = rng[0] if isinstance(rng, tuple) else None
        return f"कमी आहे (किमान {min_v} पेक्षा खाली)."
    elif status == "high":
        rng   = IDEAL_RANGES.get(param, (None, None))
        max_v = rng[1] if isinstance(rng, tuple) else None
        return f"जास्त आहे (कमाल {max_v} पेक्षा वर)."
    return "कोणतीही व्याख्या नाही."


def get_suggestion(param, value):
    if value is None or param not in SUGGESTIONS:
        return "—"
    status = get_param_status(param, value)
    s = SUGGESTIONS[param]
    if status == "good":
        return "ठीक आहे: " + s.get("good", "सध्याची पद्धत सुरू ठेवा.")
    elif status == "low":
        return "सुधारणा करा: " + s.get("low", s.get("high", "कृषी तज्ज्ञाचा सल्ला घ्या."))
    elif status == "high":
        return "सुधारणा करा: " + s.get("high", s.get("low", "कृषी तज्ज्ञाचा सल्ला घ्या."))
    return "—"


def get_color_for_value(param, value):
    s = get_param_status(param, value)
    return 'green' if s == 'good' else ('orange' if s == 'low' else ('red' if s == 'high' else 'grey'))


# ─────────────────────────────────────────────
#  Marathi font helper for matplotlib
# ─────────────────────────────────────────────
def mfont():
    if MATPLOTLIB_MARATHI_FONT:
        return {"fontproperties": MATPLOTLIB_MARATHI_FONT}
    return {}


# ─────────────────────────────────────────────
#  Charts — Marathi labels
# ─────────────────────────────────────────────
def make_nutrient_chart(n_val, p_val, k_val, ca_val, mg_val, s_val):
    try:
        nutrients  = [
            "नत्र\n(kg/ha)", "स्फुरद\nP2O5 (kg/ha)", "पालाश\nK2O (kg/ha)",
            "कॅल्शियम\n(kg/ha)", "मॅग्नेशियम\n(kg/ha)", "गंधक\n(kg/ha)"
        ]
        param_keys = ["Nitrogen", "Phosphorus", "Potassium", "Calcium", "Magnesium", "Sulphur"]
        values     = [n_val or 0, p_val or 0, k_val or 0, ca_val or 0, mg_val or 0, s_val or 0]
        bar_colors = [get_color_for_value(p, v) for p, v in zip(param_keys, values)]

        fig, ax = plt.subplots(figsize=(10, 4))
        bars = ax.bar(range(len(nutrients)), values, color=bar_colors, alpha=0.82)

        if MATPLOTLIB_MARATHI_FONT:
            ax.set_title("मातीतील पोषकद्रव्ये (kg/हेक्टर) — ICAR मानक",
                         fontsize=11, **mfont())
            ax.set_ylabel("kg / हेक्टर", **mfont())
            ax.set_xticks(range(len(nutrients)))
            ax.set_xticklabels(nutrients, fontproperties=MATPLOTLIB_MARATHI_FONT, fontsize=8)
        else:
            ax.set_title("Soil Nutrients (kg/ha) — ICAR Standard", fontsize=11)
            ax.set_ylabel("kg / hectare")
            ax.set_xticks(range(len(nutrients)))
            ax.set_xticklabels(nutrients, fontsize=8)

        ymax = max(values) * 1.35 if any(values) else 400
        ax.set_ylim(0, ymax)

        status_labels = {"good": "चांगले", "low": "कमी", "high": "जास्त"}
        for bar, val, pk in zip(bars, values, param_keys):
            st2 = get_param_status(pk, val)
            lbl = status_labels.get(st2, "N/A")
            kw  = {"ha": "center", "va": "bottom", "fontsize": 7}
            if MATPLOTLIB_MARATHI_FONT:
                kw["fontproperties"] = MATPLOTLIB_MARATHI_FONT
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + ymax * 0.02,
                    f"{val:.1f}\n{lbl}", **kw)

        plt.tight_layout()
        path = "nutrient_chart.png"
        plt.savefig(path, dpi=100, bbox_inches='tight')
        plt.close()
        return path
    except Exception as e:
        logging.error(f"Error in make_nutrient_chart: {e}")
        return None


def make_vegetation_chart(ndvi, ndwi):
    try:
        indices    = ["NDVI", "NDWI"]
        values     = [ndvi or 0, ndwi or 0]
        bar_colors = [get_color_for_value(i, v) for i, v in zip(indices, values)]

        fig, ax = plt.subplots(figsize=(5, 4))
        bars = ax.bar(indices, values, color=bar_colors, alpha=0.82)

        if MATPLOTLIB_MARATHI_FONT:
            ax.set_title("वनस्पती आणि पाणी निर्देशांक", fontsize=11, **mfont())
            ax.set_ylabel("निर्देशांक मूल्य", **mfont())
        else:
            ax.set_title("Vegetation and Water Indices", fontsize=11)
            ax.set_ylabel("Index Value")

        ax.set_ylim(-1, 1)
        ax.axhline(0, color='black', linewidth=0.5, linestyle='--')

        status_labels = {"good": "चांगले", "low": "कमी", "high": "जास्त"}
        for i, (bar, val) in enumerate(zip(bars, values)):
            st2  = get_param_status(indices[i], val)
            lbl  = status_labels.get(st2, "N/A")
            ypos = bar.get_height() + 0.03 if val >= 0 else bar.get_height() - 0.08
            kw   = {"ha": "center", "va": "bottom", "fontsize": 9}
            if MATPLOTLIB_MARATHI_FONT:
                kw["fontproperties"] = MATPLOTLIB_MARATHI_FONT
            ax.text(bar.get_x() + bar.get_width() / 2, ypos,
                    f"{val:.2f}\n{lbl}", **kw)

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
        labels     = ["pH", "EC (mS/cm)", "OC (%)", "CEC (cmol/kg)", "LST (°C)"]
        param_keys = ["pH", "Salinity", "Organic Carbon", "CEC", "LST"]
        values     = [ph or 0, sal_ec or 0, oc_pct or 0, cec or 0, lst or 0]
        bar_colors = [get_color_for_value(p, v) for p, v in zip(param_keys, values)]

        fig, ax = plt.subplots(figsize=(8, 4))
        bars = ax.bar(labels, values, color=bar_colors, alpha=0.82)

        if MATPLOTLIB_MARATHI_FONT:
            ax.set_title("मातीचे गुणधर्म (ICAR मानक)", fontsize=11, **mfont())
            ax.set_ylabel("मूल्य", **mfont())
        else:
            ax.set_title("Soil Properties (ICAR Standard)", fontsize=11)
            ax.set_ylabel("Value")

        ymax = max(values) * 1.35 if any(values) else 50
        ax.set_ylim(0, ymax)

        status_labels = {"good": "चांगले", "low": "कमी", "high": "जास्त"}
        for bar, val, pk in zip(bars, values, param_keys):
            st2 = get_param_status(pk, val)
            lbl = status_labels.get(st2, "N/A")
            kw  = {"ha": "center", "va": "bottom", "fontsize": 8}
            if MATPLOTLIB_MARATHI_FONT:
                kw["fontproperties"] = MATPLOTLIB_MARATHI_FONT
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + ymax * 0.02,
                    f"{val:.2f}\n{lbl}", **kw)

        plt.tight_layout()
        path = "properties_chart.png"
        plt.savefig(path, dpi=100, bbox_inches='tight')
        plt.close()
        return path
    except Exception as e:
        logging.error(f"Error in make_soil_properties_chart: {e}")
        return None


# ─────────────────────────────────────────────
#  Groq API — Marathi output
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
#  ReportLab Marathi style helper
# ─────────────────────────────────────────────
def mpara_style(base_style, font_size=9, leading=14, alignment=None):
    font = "NotoDevanagari" if MARATHI_FONT_REGISTERED else "Helvetica"
    kwargs = dict(parent=base_style, fontName=font, fontSize=font_size, leading=leading)
    if alignment is not None:
        kwargs["alignment"] = alignment
    return ParagraphStyle(f"Marathi_{font_size}_{id(base_style)}", **kwargs)


# ─────────────────────────────────────────────
#  PDF Report — Full Marathi
# ─────────────────────────────────────────────
def generate_report(params, location, date_range):
    try:
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

        # ── Groq prompts in Marathi ────────────────────────────────────────
        exec_prompt = f"""तुम्ही एक अनुभवी कृषी तज्ज्ञ आहात. खालील माती तपासणी अहवालावर आधारित 3-5 मुद्द्यांमध्ये थोडक्यात सारांश लिहा.
भाषा: सोपी मराठी, शेतकऱ्यांना समजेल अशी. कोणतेही तांत्रिक शब्द वापरू नका.
स्थान: {location}
तारीख: {date_range}
माती आरोग्य गुण: {score:.1f}% ({rating})
pH={fmtv('pH', params['pH'])}, EC={fmtv('Salinity', params['Salinity'])}, सेंद्रिय कार्बन={fmtv('Organic Carbon', params['Organic Carbon'])}, CEC={fmtv('CEC', params['CEC'])}
मातीचा पोत={tex_d}, नत्र={fmtv('Nitrogen', params['Nitrogen'])}, स्फुरद={fmtv('Phosphorus', params['Phosphorus'])} (कमी विश्वासार्ह), पालाश={fmtv('Potassium', params['Potassium'])}
कॅल्शियम={fmtv('Calcium', params['Calcium'])}, मॅग्नेशियम={fmtv('Magnesium', params['Magnesium'])}, गंधक={fmtv('Sulphur', params['Sulphur'])} (अंदाजित)
प्रत्येक मुद्दा बुलेट (•) ने सुरू करा. कोणतेही bold किंवा markdown नको. फक्त मराठीत उत्तर द्या."""

        rec_prompt = f"""तुम्ही एक कृषी सल्लागार आहात. खालील माती माहितीवर आधारित महाराष्ट्रातील शेतकऱ्यांसाठी 3-5 व्यावहारिक सुझाव द्या.
pH={fmtv('pH', params['pH'])}, EC={fmtv('Salinity', params['Salinity'])}, सेंद्रिय कार्बन={fmtv('Organic Carbon', params['Organic Carbon'])}, CEC={fmtv('CEC', params['CEC'])}, माती={tex_d}
नत्र={fmtv('Nitrogen', params['Nitrogen'])}, स्फुरद={fmtv('Phosphorus', params['Phosphorus'])} (अंदाजित), पालाश={fmtv('Potassium', params['Potassium'])}
कॅल्शियम={fmtv('Calcium', params['Calcium'])}, मॅग्नेशियम={fmtv('Magnesium', params['Magnesium'])}, गंधक={fmtv('Sulphur', params['Sulphur'])} (अंदाजित)
NDVI={fmtv('NDVI', params['NDVI'])}, NDWI={fmtv('NDWI', params['NDWI'])}
महाराष्ट्राच्या हवामानानुसार योग्य पिके आणि साधे खत उपाय सांगा.
प्रत्येक मुद्दा बुलेट (•) ने सुरू करा. कोणतेही bold किंवा markdown नको. फक्त मराठीत उत्तर द्या."""

        executive_summary = call_groq(exec_prompt) or "• सारांश उपलब्ध नाही."
        recommendations   = call_groq(rec_prompt)  or "• सुझाव उपलब्ध नाहीत."

        # ── PDF Build ──────────────────────────────────────────────────────
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=3*cm,  bottomMargin=2*cm)

        styles = getSampleStyleSheet()
        MFONT  = "NotoDevanagari" if MARATHI_FONT_REGISTERED else "Helvetica"

        title_style = ParagraphStyle('MTitle',
            parent=styles['Title'], fontName=MFONT, fontSize=18,
            spaceAfter=16, alignment=TA_CENTER)
        h2 = ParagraphStyle('MH2',
            parent=styles['Heading2'], fontName=MFONT, fontSize=12,
            spaceAfter=8, textColor=colors.darkgreen)
        body = ParagraphStyle('MBody',
            parent=styles['BodyText'], fontName=MFONT, fontSize=9, leading=14)
        small = ParagraphStyle('MSmall',
            parent=styles['BodyText'], fontName=MFONT, fontSize=8, leading=12)
        center_body = ParagraphStyle('MCenter',
            parent=styles['BodyText'], fontName=MFONT, fontSize=10,
            leading=14, alignment=TA_CENTER)

        elements = []

        # ── Cover page ──────────────────────────────────────────────────────
        elements.append(Spacer(1, 2*cm))
        if os.path.exists(LOGO_PATH):
            logo_img = Image(LOGO_PATH, width=10*cm, height=10*cm)
            logo_img.hAlign = 'CENTER'
            elements.append(logo_img)
        elements.append(Spacer(1, 0.8*cm))
        elements.append(Paragraph("FarmMatrix माती आरोग्य अहवाल", title_style))
        elements.append(Spacer(1, 0.4*cm))
        elements.append(Paragraph(f"<b>स्थान:</b> {location}", center_body))
        elements.append(Paragraph(f"<b>तारीख श्रेणी:</b> {date_range}", center_body))
        elements.append(Paragraph(f"<b>अहवाल तयार:</b> {datetime.now():%d %B %Y, %H:%M}", center_body))
        elements.append(PageBreak())

        # ── Section 1: Executive Summary ────────────────────────────────────
        elements.append(Paragraph("1. थोडक्यात सारांश", h2))
        for line in executive_summary.split('\n'):
            if line.strip():
                elements.append(Paragraph(line.strip(), body))
        elements.append(Spacer(1, 0.4*cm))

        # ── Section 2: Soil Health Score ────────────────────────────────────
        elements.append(Paragraph("2. माती आरोग्य रेटिंग", h2))
        good_count  = sum(1 for p, v in REPORT_PARAMS.items() if get_param_status(p, v) == "good")
        valid_count = len([v for v in REPORT_PARAMS.values() if v is not None])
        rating_data = [
            ["एकूण गुण", "रेटिंग", "योग्य पातळीवरील घटक"],
            [f"{score:.1f}%", rating, f"{good_count} / {valid_count}"]
        ]
        rt = Table(rating_data, colWidths=[5*cm, 4*cm, 7*cm])
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, -1), MFONT),
            ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE',   (0, 0), (-1, -1), 10),
            ('BOX',        (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(rt)
        elements.append(Spacer(1, 0.4*cm))
        elements.append(PageBreak())

        # ── Section 3: Parameter Table ───────────────────────────────────────
        elements.append(Paragraph("3. माती घटक विश्लेषण (ICAR मानक)", h2))
        table_data = [["घटक", "मूल्य", "ICAR आदर्श श्रेणी", "स्थिती", "स्पष्टीकरण"]]

        for param, value in REPORT_PARAMS.items():
            unit      = UNIT_MAP.get(param, "")
            marathi_nm = PARAM_MARATHI.get(param, param)
            if param == "Soil Texture":
                val_text = TEXTURE_CLASSES.get(value, "N/A") if value is not None else "N/A"
            else:
                val_text = f"{value:.2f}{unit}" if value is not None else "N/A"
            status   = get_param_status(param, value)
            st_label = status_marathi(status)
            table_data.append([
                Paragraph(marathi_nm, small),
                val_text,
                IDEAL_DISPLAY.get(param, "N/A"),
                st_label,
                Paragraph(interpretations[param], small)
            ])

        tbl = Table(table_data, colWidths=[3*cm, 2.5*cm, 3*cm, 1.8*cm, 5.7*cm])
        tbl_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, -1), MFONT),
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('BOX',        (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.94, 0.98, 0.94)]),
        ]
        for i, (param, value) in enumerate(REPORT_PARAMS.items(), start=1):
            s = get_param_status(param, value)
            c = (colors.Color(0.1, 0.55, 0.1) if s == "good" else
                 colors.Color(0.85, 0.45, 0.0) if s == "low"  else
                 colors.red if s == "high" else colors.grey)
            tbl_style.append(('TEXTCOLOR', (3, i), (3, i), c))
            tbl_style.append(('FONTNAME',  (3, i), (3, i), MFONT))
        tbl.setStyle(TableStyle(tbl_style))
        elements.append(tbl)
        elements.append(PageBreak())

        # ── Section 4: Charts ────────────────────────────────────────────────
        elements.append(Paragraph("4. आलेख आणि तक्ते", h2))
        for lbl, path in [
            ("पोषकद्रव्ये — नत्र, स्फुरद, पालाश, कॅल्शियम, मॅग्नेशियम, गंधक (kg/हेक्टर)", nutrient_chart),
            ("वनस्पती आणि पाणी निर्देशांक (NDVI, NDWI)",                                   vegetation_chart),
            ("मातीचे गुणधर्म",                                                               properties_chart),
        ]:
            if path:
                elements.append(Paragraph(lbl + ":", body))
                elements.append(Image(path, width=13*cm, height=6.5*cm))
                elements.append(Spacer(1, 0.3*cm))
        elements.append(PageBreak())

        # ── Section 5: Crop Recommendations ─────────────────────────────────
        elements.append(Paragraph("5. पीक सुझाव आणि उपचार", h2))
        for line in recommendations.split('\n'):
            if line.strip():
                elements.append(Paragraph(line.strip(), body))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(PageBreak())

        # ── Section 6: Parameter-wise Suggestions ───────────────────────────
        elements.append(Paragraph("6. घटकनिहाय सुझाव", h2))
        elements.append(Paragraph(
            "प्रत्येक घटकासाठी: चांगली पातळी टिकवण्यासाठी किंवा समस्या दुरुस्त करण्यासाठी काय करावे.", small))
        elements.append(Spacer(1, 0.3*cm))

        SUGGESTION_PARAMS = [
            "pH", "Salinity", "Organic Carbon", "CEC",
            "Nitrogen", "Phosphorus", "Potassium",
            "Calcium", "Magnesium", "Sulphur",
            "NDVI", "NDWI", "LST"
        ]
        sug_data = [["घटक", "स्थिती", "आवश्यक कृती"]]
        for param in SUGGESTION_PARAMS:
            value      = params.get(param)
            status     = get_param_status(param, value)
            st_label   = status_marathi(status)
            sug_text   = get_suggestion(param, value)
            marathi_nm = PARAM_MARATHI.get(param, param)
            sug_data.append([
                Paragraph(marathi_nm, small),
                st_label,
                Paragraph(sug_text, small)
            ])

        sug_tbl = Table(sug_data, colWidths=[3*cm, 2*cm, 11*cm])
        sug_style_list = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, -1), MFONT),
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('BOX',        (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.94, 0.98, 0.94)]),
        ]
        for i, param in enumerate(SUGGESTION_PARAMS, start=1):
            value = params.get(param)
            s     = get_param_status(param, value)
            c     = (colors.Color(0.1, 0.55, 0.1) if s == "good" else
                     colors.Color(0.85, 0.45, 0.0) if s == "low"  else
                     colors.red if s == "high" else colors.grey)
            sug_style_list.append(('TEXTCOLOR', (1, i), (1, i), c))
            sug_style_list.append(('FONTNAME',  (1, i), (1, i), MFONT))
        sug_tbl.setStyle(TableStyle(sug_style_list))
        elements.append(sug_tbl)

        # ── Header / Footer ──────────────────────────────────────────────────
        def add_header(canv, doc):
            canv.saveState()
            if os.path.exists(LOGO_PATH):
                canv.drawImage(LOGO_PATH, 2*cm, A4[1] - 2.8*cm, width=1.8*cm, height=1.8*cm)
            if MARATHI_FONT_REGISTERED:
                canv.setFont("NotoDevanagari", 11)
            else:
                canv.setFont("Helvetica-Bold", 11)
            canv.drawString(4.5*cm, A4[1] - 2.2*cm, "FarmMatrix माती आरोग्य अहवाल")
            canv.setFont("Helvetica", 8)
            canv.drawRightString(A4[0] - 2*cm, A4[1] - 2.2*cm,
                                 f"तयार: {datetime.now():%d %b %Y, %H:%M}")
            canv.setStrokeColor(colors.darkgreen)
            canv.setLineWidth(1)
            canv.line(2*cm, A4[1] - 3*cm, A4[0] - 2*cm, A4[1] - 3*cm)
            canv.restoreState()

        def add_footer(canv, doc):
            canv.saveState()
            canv.setStrokeColor(colors.darkgreen)
            canv.line(2*cm, 1.5*cm, A4[0] - 2*cm, 1.5*cm)
            if MARATHI_FONT_REGISTERED:
                canv.setFont("NotoDevanagari", 8)
            else:
                canv.setFont("Helvetica", 8)
            canv.drawCentredString(A4[0] / 2, cm,
                                   f"पृष्ठ {doc.page}  |  FarmMatrix माती आरोग्य अहवाल  |  ICAR मानक एकके")
            canv.restoreState()

        doc.build(elements,
                  onFirstPage=lambda c, d: (add_header(c, d), add_footer(c, d)),
                  onLaterPages=lambda c, d: (add_header(c, d), add_footer(c, d)),
                  canvasmaker=canvas.Canvas)
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()

    except Exception as e:
        logging.error(f"Error in generate_report: {e}")
        return None


# ═══════════════════════════════════════════════════════
#  Streamlit UI — Marathi
# ═══════════════════════════════════════════════════════
st.set_page_config(layout='wide', page_title="माती आरोग्य डॅशबोर्ड")
st.title("🌾 FarmMatrix माती आरोग्य डॅशबोर्ड")
st.markdown("उपग्रह-आधारित माती विश्लेषण — ICAR मानकानुसार पोषकद्रव्ये अहवाल (kg/हेक्टर).")

# ── Sidebar ───────────────────────────────────
st.sidebar.header("📍 स्थान निवडा")
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]
lat = st.sidebar.number_input("अक्षांश (Latitude)",  value=st.session_state.user_location[0], format="%.6f")
lon = st.sidebar.number_input("रेखांश (Longitude)", value=st.session_state.user_location[1], format="%.6f")
st.session_state.user_location = [lat, lon]

st.sidebar.header("⚙️ CEC मॉडेल गुणांक")
cec_intercept  = st.sidebar.number_input("अंतर्खंड (Intercept)",           value=5.0,  step=0.1)
cec_slope_clay = st.sidebar.number_input("उतार - माती निर्देशांक (Clay)",  value=20.0, step=0.1)
cec_slope_om   = st.sidebar.number_input("उतार - OM निर्देशांक",           value=15.0, step=0.1)

today      = date.today()
start_date = st.sidebar.date_input("सुरुवात तारीख", value=today - timedelta(days=16))
end_date   = st.sidebar.date_input("शेवट तारीख",    value=today)
if start_date > end_date:
    st.sidebar.error("सुरुवात तारीख शेवटच्या तारखेपेक्षा आधी असणे आवश्यक आहे.")
    st.stop()

# ── Map ───────────────────────────────────────
st.markdown("### 🗺️ आपले शेत निवडा — नकाशावर पॉलिगन काढा")
m = folium.Map(location=[lat, lon], zoom_start=15)
Draw(export=True).add_to(m)
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google Satellite").add_to(m)
folium.Marker([lat, lon], popup="मध्यबिंदू").add_to(m)
map_data = st_folium(m, width=700, height=500)

# ── Region selection ──────────────────────────
region = None
if map_data and "last_active_drawing" in map_data:
    try:
        sel = map_data["last_active_drawing"]
        if sel and "geometry" in sel and "coordinates" in sel["geometry"]:
            region = ee.Geometry.Polygon(sel["geometry"]["coordinates"])
        else:
            st.error("अवैध क्षेत्र. कृपया वैध पॉलिगन काढा.")
    except Exception as e:
        st.error(f"क्षेत्र तयार करण्यात त्रुटी: {e}")

# ── Analysis ──────────────────────────────────
if region:
    st.subheader(f"📊 विश्लेषण: {start_date} ते {end_date}")
    progress_bar = st.progress(0)
    status_msg   = st.empty()

    status_msg.text("Sentinel-2 उपग्रह प्रतिमा मिळवत आहे...")
    comp = sentinel_composite(region, start_date, end_date, ALL_BANDS)
    progress_bar.progress(20)

    status_msg.text("मातीच्या पोताचा नकाशा वाचत आहे...")
    texc = get_soil_texture(region)
    progress_bar.progress(35)

    status_msg.text("MODIS भूपृष्ठ तापमान (LST) मिळवत आहे...")
    lst = get_lst(region, start_date, end_date)
    progress_bar.progress(50)

    if comp is None:
        st.warning("Sentinel-2 डेटा सापडला नाही. कृपया तारीख श्रेणी वाढवा.")
        ph = sal = oc = cec = ndwi = ndvi = evi = fvc = n_val = p_val = k_val = None
        ca_val = mg_val = s_val = None
    else:
        status_msg.text("बँड आकडेवारी गणना होत आहे...")
        bs = get_band_stats(comp, region)

        status_msg.text("माती घटक गणना होत आहे (ICAR मानक)...")
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
        status_msg.text("✅ विश्लेषण पूर्ण झाले.")

    params = {
        "pH":             ph,
        "Salinity":       sal,
        "Organic Carbon": oc,
        "CEC":            cec,
        "Soil Texture":   texc,
        "LST":            lst,
        "NDWI":           ndwi,
        "NDVI":           ndvi,
        "EVI":            evi,
        "FVC":            fvc,
        "Nitrogen":       n_val,
        "Phosphorus":     p_val,
        "Potassium":      k_val,
        "Calcium":        ca_val,
        "Magnesium":      mg_val,
        "Sulphur":        s_val,
    }

    # ── Metrics display ───────────────────────
    st.markdown("### 🧪 मातीचे घटक")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("pH",                       f"{ph:.2f}"   if ph   is not None else "N/A")
        st.metric("क्षारता EC (mS/cm)",       f"{sal:.2f}"  if sal  is not None else "N/A")
        st.metric("सेंद्रिय कार्बन (%)",      f"{oc:.2f}"   if oc   is not None else "N/A")
        st.metric("CEC (cmol/kg)",             f"{cec:.2f}"  if cec  is not None else "N/A")
    with col2:
        st.metric("NDVI",  f"{ndvi:.3f}"  if ndvi  is not None else "N/A")
        st.metric("EVI",   f"{evi:.3f}"   if evi   is not None else "N/A")
        st.metric("FVC",   f"{fvc:.3f}"   if fvc   is not None else "N/A")
        st.metric("NDWI",  f"{ndwi:.3f}"  if ndwi  is not None else "N/A")
    with col3:
        st.metric("नत्र N (kg/ha)",            f"{n_val:.1f}" if n_val is not None else "N/A")
        st.metric("स्फुरद P2O5 (kg/ha)",      f"{p_val:.1f}" if p_val is not None else "N/A")
        st.metric("पालाश K2O (kg/ha)",        f"{k_val:.1f}" if k_val is not None else "N/A")
        st.metric("LST (°C)",                  f"{lst:.1f}"   if lst   is not None else "N/A")
    with col4:
        st.metric("कॅल्शियम Ca (kg/ha)",     f"{ca_val:.1f}" if ca_val is not None else "N/A")
        st.metric("मॅग्नेशियम Mg (kg/ha)",   f"{mg_val:.1f}" if mg_val is not None else "N/A")
        st.metric("गंधक S (kg/ha)",           f"{s_val:.1f}"  if s_val  is not None else "N/A")

    score, rating = calculate_soil_health_score(params)
    icon = "🟢" if rating in ("उत्कृष्ट", "चांगले") else ("🟡" if rating == "ठीकठाक" else "🔴")
    st.info(f"{icon} माती आरोग्य गुण: {score:.1f}% — {rating}  (ICAR मानक)")

    # ── Quick suggestions table ───────────────
    st.markdown("### 💡 त्वरित सुझाव")
    sug_rows = []
    for p in ["pH", "Salinity", "Organic Carbon", "Nitrogen", "Phosphorus", "Potassium",
              "Calcium", "Magnesium", "Sulphur"]:
        v        = params.get(p)
        s        = get_param_status(p, v)
        st_label = status_marathi(s)
        sug_rows.append({
            "घटक":      PARAM_MARATHI.get(p, p),
            "मूल्य":    f"{v:.2f}{UNIT_MAP.get(p,'')}" if v is not None else "N/A",
            "स्थिती":   st_label,
            "सुझाव":    get_suggestion(p, v).replace("ठीक आहे: ", "").replace("सुधारणा करा: ", ""),
        })
    st.dataframe(pd.DataFrame(sug_rows), use_container_width=True, hide_index=True)
    st.caption(
        "⚠️ टीप: स्फुरद (P) आणि गंधक (S) ची स्पेक्ट्रल अचूकता कमी आहे. "
        "हे फक्त अंदाज म्हणून घ्या. सर्व दुय्यम पोषकद्रव्यांसाठी माती नमुना चाचणी करवून घ्या."
    )

    if st.button("📄 संपूर्ण PDF अहवाल तयार करा"):
        with st.spinner("Groq AI कडून मराठी अहवाल तयार होत आहे..."):
            location   = f"अक्षांश: {lat:.6f}, रेखांश: {lon:.6f}"
            date_range = f"{start_date} ते {end_date}"
            pdf_data   = generate_report(params, location, date_range)
            if pdf_data:
                st.success("✅ अहवाल तयार आहे!")
                st.download_button(
                    label="📥 PDF अहवाल डाउनलोड करा",
                    data=pdf_data,
                    file_name=f"माती_आरोग्य_अहवाल_{date.today()}.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("❌ अहवाल तयार करण्यात अपयश. लॉग तपासा.")
else:
    st.info("👆 वरील नकाशावर आपल्या शेताचे पॉलिगन काढा.")