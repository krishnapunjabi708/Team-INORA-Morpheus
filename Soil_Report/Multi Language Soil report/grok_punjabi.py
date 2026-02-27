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
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Spacer, PageBreak,
    Image as RLImage,
)
from reportlab.pdfgen import canvas
from io import BytesIO
from openai import OpenAI

# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
GROQ_API_KEY = "grok-api"
GROQ_MODEL   = "llama-3.3-70b-versatile"
LOGO_PATH    = os.path.abspath("LOGO.jpg")

# ── Punjabi / Gurmukhi Font ───────────────────────────────────────────────────
# unifont.otf is the ONLY reliable font on this system that renders Gurmukhi
# correctly. It lives at the path below.
PUNJABI_FONT_PATH = "unifont.otf"

# Pre-load PIL fonts at various sizes
_PIL_FONTS: dict = {}

def pil_font(size: int):
    if size not in _PIL_FONTS:
        try:
            _PIL_FONTS[size] = ImageFont.truetype(PUNJABI_FONT_PATH, size)
        except Exception as e:
            logging.error(f"Font load failed: {e}")
            _PIL_FONTS[size] = ImageFont.load_default()
    return _PIL_FONTS[size]

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ─────────────────────────────────────────────
#  Google Earth Engine init
# ─────────────────────────────────────────────
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────
SOIL_TEXTURE_IMG = (ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02")
                    .select('b0'))

TEXTURE_CLASSES = {
    1:  "ਚੀਕਣੀ ਮਿੱਟੀ (Clay)",
    2:  "ਗਾਰੀ ਚੀਕਣੀ ਮਿੱਟੀ (Silty Clay)",
    3:  "ਰੇਤਲੀ ਚੀਕਣੀ ਮਿੱਟੀ (Sandy Clay)",
    4:  "ਮਿੱਟੀ ਦੋਮਟ (Clay Loam)",
    5:  "ਗਾਰੀ ਮਿੱਟੀ ਦੋਮਟ (Silty Clay Loam)",
    6:  "ਰੇਤਲੀ ਮਿੱਟੀ ਦੋਮਟ (Sandy Clay Loam)",
    7:  "ਦੋਮਟ ਮਿੱਟੀ (Loam)",
    8:  "ਗਾਰੀ ਦੋਮਟ (Silty Loam)",
    9:  "ਰੇਤਲੀ ਦੋਮਟ (Sandy Loam)",
    10: "ਗਾਰ (Silt)",
    11: "ਦੋਮਟ ਰੇਤ (Loamy Sand)",
    12: "ਰੇਤ (Sand)",
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
    "pH":             "6.5-7.5",
    "Salinity":       "<=1.0 mS/cm",
    "Organic Carbon": "0.75-1.50 %",
    "CEC":            "10-30 cmol/kg",
    "Soil Texture":   "ਦੋਮਟ ਮਿੱਟੀ (Loam)",
    "LST":            "15-35 C",
    "NDWI":           "-0.3 ਤੋਂ 0.2",
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

PUNJABI_PARAM_NAMES = {
    "pH":             "pH ਤੇਜ਼ਾਬੀਪਣ",
    "Salinity":       "ਲੂਣਾਪਣ (EC)",
    "Organic Carbon": "ਜੈਵਿਕ ਕਾਰਬਨ",
    "CEC":            "ਕੈਸ਼ਨ ਵਟਾਂਦਰਾ ਸਮਰੱਥਾ",
    "Soil Texture":   "ਮਿੱਟੀ ਦੀ ਬਣਤਰ",
    "LST":            "ਭੂਮੀ ਤਾਪਮਾਨ",
    "NDVI":           "ਬਨਸਪਤੀ ਸੂਚਕ (NDVI)",
    "EVI":            "ਵਧੀਆ ਬਨਸਪਤੀ ਸੂਚਕ (EVI)",
    "FVC":            "ਬਨਸਪਤੀ ਢੱਕਣ ਸੂਚਕ (FVC)",
    "NDWI":           "ਪਾਣੀ ਸੂਚਕ (NDWI)",
    "Nitrogen":       "ਨਾਈਟ੍ਰੋਜਨ (N)",
    "Phosphorus":     "ਫਾਸਫੋਰਸ (P)",
    "Potassium":      "ਪੋਟਾਸ਼ੀਅਮ (K)",
    "Calcium":        "ਕੈਲਸ਼ੀਅਮ (Ca)",
    "Magnesium":      "ਮੈਗਨੀਸ਼ੀਅਮ (Mg)",
    "Sulphur":        "ਗੰਧਕ (S)",
}

PUNJABI_STATUS = {
    "good": "ਵਧੀਆ",
    "low":  "ਘੱਟ",
    "high": "ਵੱਧ",
    "na":   "N/A",
}

SUGGESTIONS = {
    "pH": {
        "good": "ਹਰ 2-3 ਸਾਲਾਂ ਵਿੱਚ ਇੱਕ ਵਾਰ ਚੂਨਾ ਪਾ ਕੇ pH ਬਣਾਈ ਰੱਖੋ। ਜ਼ਿਆਦਾ ਯੂਰੀਆ ਤੋਂ ਬਚੋ।",
        "low":  "ਖੇਤੀਬਾੜੀ ਚੂਨਾ 2-4 ਬੋਰੀਆਂ ਪ੍ਰਤੀ ਏਕੜ ਪਾਓ। ਤੇਜ਼ਾਬੀਕਰਨ ਵਾਲੀਆਂ ਖਾਦਾਂ ਤੋਂ ਬਚੋ।",
        "high": "ਜਿਪਸਮ ਜਾਂ ਗੰਧਕ 5-10 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਮਿਲਾਓ। ਅਮੋਨੀਅਮ ਸਲਫੇਟ ਵਰਤੋ।",
    },
    "Salinity": {
        "good": "ਤੁਪਕਾ ਸਿੰਚਾਈ ਜਾਰੀ ਰੱਖੋ। ਪਾਣੀ ਖੜ੍ਹਾ ਨਾ ਹੋਣ ਦਿਓ।",
        "high": "ਵਾਧੂ ਸਿੰਚਾਈ ਨਾਲ ਖੇਤ ਧੋਵੋ। ਜਿਪਸਮ 200 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਪਾਓ।",
    },
    "Organic Carbon": {
        "good": "ਹਰ ਸਾਲ 2 ਟਨ ਰੂੜੀ ਖਾਦ ਜਾਂ ਕੰਪੋਸਟ ਪ੍ਰਤੀ ਏਕੜ ਮਿਲਾਓ।",
        "low":  "ਰੂੜੀ ਖਾਦ 4-5 ਟਨ ਪ੍ਰਤੀ ਏਕੜ ਪਾਓ। ਹਰੀ ਖਾਦ ਬੀਜੋ।",
        "high": "ਚੰਗੀ ਵਾਹੀ ਨਾਲ ਬਰਾਬਰ ਕਰੋ। ਨਿਕਾਸੀ ਸੁਧਾਰੋ।",
    },
    "CEC": {
        "good": "ਜੈਵਿਕ ਕਾਰਬਨ ਬਣਾਈ ਰੱਖੋ ਅਤੇ ਵੱਧ ਵਾਹੀ ਤੋਂ ਬਚੋ।",
        "low":  "ਕੰਪੋਸਟ ਜਾਂ ਮਿੱਟੀ ਸੁਧਾਰ ਮਿਲਾਓ।",
        "high": "ਪੋਸ਼ਕ ਤੱਤਾਂ ਦੀ ਉਪਲਬਧਤਾ ਲਈ pH ਸਹੀ ਪੱਧਰ ਤੇ ਰੱਖੋ।",
    },
    "LST": {
        "good": "ਮਿੱਟੀ ਦਾ ਤਾਪਮਾਨ ਸਥਿਰ ਰੱਖਣ ਲਈ ਮਲਚ ਵਰਤੋ।",
        "low":  "ਕਾਲੀ ਪਲਾਸਟਿਕ ਮਲਚ ਵਰਤ ਕੇ ਮਿੱਟੀ ਗਰਮ ਕਰੋ।",
        "high": "ਪਰਾਲੀ ਮਲਚ ਪਾ ਕੇ ਮਿੱਟੀ ਠੰਢੀ ਕਰੋ। ਸਿੰਚਾਈ ਵਧਾਓ।",
    },
    "NDVI": {
        "good": "ਮੌਜੂਦਾ ਫਸਲ ਘਣਤਾ ਅਤੇ ਖਾਦ ਸਮਾਂ-ਸਾਰਣੀ ਬਣਾਈ ਰੱਖੋ।",
        "low":  "ਕੀੜੇ ਜਾਂ ਬਿਮਾਰੀ ਦੀ ਜਾਂਚ ਕਰੋ। NPK ਸੰਤੁਲਿਤ ਖਾਦ ਪਾਓ।",
        "high": "ਡਿੱਗਣ ਦੀ ਸੰਭਾਵਨਾ ਵੱਲ ਧਿਆਨ ਦਿਓ। ਚੰਗੀ ਨਿਕਾਸੀ ਯਕੀਨੀ ਕਰੋ।",
    },
    "EVI": {
        "good": "ਮੌਜੂਦਾ ਫਸਲ ਪ੍ਰਬੰਧਨ ਜਾਰੀ ਰੱਖੋ।",
        "low":  "ਪੱਤਾ-ਛਿੜਕਾਅ ਸੂਖਮ ਤੱਤ: ਜ਼ਿੰਕ ਸਲਫੇਟ ਅਤੇ ਬੋਰਾਨ ਪਾਓ।",
        "high": "ਚੰਗਾ ਹਵਾ ਸੰਚਾਰ ਯਕੀਨੀ ਕਰੋ। ਉੱਲੀ ਰੋਗ ਵੱਲ ਧਿਆਨ ਦਿਓ।",
    },
    "FVC": {
        "good": "ਜ਼ਮੀਨੀ ਢੱਕਣ ਬਣਾਈ ਰੱਖੋ।",
        "low":  "ਪੌਦਿਆਂ ਦੀ ਗਿਣਤੀ ਵਧਾਓ। ਨਦੀਨ ਕਾਬੂ ਕਰੋ।",
        "high": "ਘਣੇ ਢੱਕਣ ਕਾਰਨ ਨਮੀ ਦਾ ਤਣਾਅ ਲੁਕਿਆ ਹੋ ਸਕਦਾ ਹੈ।",
    },
    "NDWI": {
        "good": "ਮੌਜੂਦਾ ਸਿੰਚਾਈ ਸਮਾਂ-ਸਾਰਣੀ ਜਾਰੀ ਰੱਖੋ।",
        "low":  "ਤੁਰੰਤ ਸਿੰਚਾਈ ਕਰੋ। ਤੁਪਕਾ ਸਿੰਚਾਈ ਦੀ ਸਿਫਾਰਸ਼ ਕੀਤੀ ਜਾਂਦੀ ਹੈ।",
        "high": "ਸਿੰਚਾਈ ਘਟਾਓ। ਪਾਣੀ ਖੜ੍ਹਾ ਨਾ ਹੋਵੇ ਇਸ ਲਈ ਨਿਕਾਸੀ ਜਾਂਚੋ।",
    },
    "Nitrogen": {
        "good": "ਨੁਕਸਾਨ ਘਟਾਉਣ ਲਈ ਯੂਰੀਆ ਨੂੰ ਹਿੱਸਿਆਂ ਵਿੱਚ ਪਾਓ (ਬੇਸਲ + ਉੱਪਰੀ ਖੁਰਾਕ)।",
        "low":  "ਯੂਰੀਆ 25-30 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਜਾਂ DAP ਪਾਓ।",
        "high": "ਇਸ ਸੀਜ਼ਨ ਵਿੱਚ ਨਾਈਟ੍ਰੋਜਨ ਘਟਾਓ। ਨਿੰਮ ਲੇਪਿਤ ਯੂਰੀਆ ਵਰਤੋ।",
    },
    "Phosphorus": {
        "good": "ਬਿਜਾਈ ਸਮੇਂ ਘੱਟ ਮਾਤਰਾ ਵਿੱਚ SSP ਜਾਂ DAP ਪਾਓ।",
        "low":  "DAP 12 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਜਾਂ SSP 50 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਬਿਜਾਈ ਸਮੇਂ ਪਾਓ।",
        "high": "ਇਸ ਸੀਜ਼ਨ ਵਿੱਚ ਫਾਸਫੋਰਸ ਘਟਾਓ। ਜ਼ਿੰਕ ਸਲਫੇਟ 5 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਪਾਓ।",
    },
    "Potassium": {
        "good": "ਹਰ 2ਵੇਂ ਸੀਜ਼ਨ ਵਿੱਚ MOP ਘੱਟ ਮਾਤਰਾ ਵਿੱਚ ਪਾਓ।",
        "low":  "MOP 8-10 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਪਾਓ। ਰੁੱਖਾਂ ਦੀ ਸੁਆਹ ਜੈਵਿਕ ਸਰੋਤ ਵਜੋਂ ਮਿਲਾਓ।",
        "high": "ਇਸ ਸੀਜ਼ਨ ਵਿੱਚ ਪੋਟਾਸ਼ੀਅਮ ਘਟਾਓ। ਮੈਗਨੀਸ਼ੀਅਮ ਦੀ ਕਮੀ ਵੱਲ ਧਿਆਨ ਦਿਓ।",
    },
    "Calcium": {
        "good": "ਕੈਲਸ਼ੀਅਮ ਦੀ ਉਪਲਬਧਤਾ ਲਈ pH 6.5-7.5 ਬਣਾਈ ਰੱਖੋ। ਹਰ 2-3 ਸਾਲਾਂ ਵਿੱਚ ਚੂਨਾ ਪਾਓ।",
        "low":  "ਖੇਤੀਬਾੜੀ ਚੂਨਾ 200-400 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਪਾਓ। pH ਜਾਂਚੋ।",
        "high": "ਵਾਧੂ ਚੂਨਾ ਪਾਉਣ ਤੋਂ ਬਚੋ। Mg ਅਤੇ K ਪੱਧਰਾਂ ਵੱਲ ਧਿਆਨ ਦਿਓ।",
    },
    "Magnesium": {
        "good": "pH ਸੁਧਾਰ ਸਮੇਂ ਡੋਲੋਮਾਈਟ ਚੂਨਾ ਪਾਓ।",
        "low":  "ਡੋਲੋਮਾਈਟ 50-100 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਜਾਂ ਕੀਜ਼ਰਾਈਟ 10 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਪਾਓ।",
        "high": "Ca ਅਤੇ K ਦੇ ਮੁਕਾਬਲੇ ਵੱਲ ਧਿਆਨ ਦਿਓ। ਨਿਕਾਸੀ ਸੁਧਾਰੋ।",
    },
    "Sulphur": {
        "good": "ਬਿਜਾਈ ਸਮੇਂ SSP ਖਾਦ ਵਰਤ ਕੇ ਪੱਧਰ ਬਣਾਈ ਰੱਖੋ।",
        "low":  "ਜਿਪਸਮ 50 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਜਾਂ ਮੂਲ ਗੰਧਕ 5-10 ਕਿਲੋ ਪ੍ਰਤੀ ਏਕੜ ਪਾਓ।",
        "high": "ਸਲਫੇਟ ਵਾਲੀਆਂ ਖਾਦਾਂ ਘਟਾਓ। EC ਜਾਂਚੋ।",
    },
}

ALL_BANDS = ["B2","B3","B4","B5","B6","B7","B8","B8A","B11","B12"]

# Matplotlib font for Gurmukhi axis labels
PUNJABI_FP = FontProperties(fname=PUNJABI_FONT_PATH) if os.path.exists(PUNJABI_FONT_PATH) else None


# ═══════════════════════════════════════════════════════
#  PIL Punjabi (Gurmukhi) Text Rendering
# ═══════════════════════════════════════════════════════

PAGE_W_PX = 1240
CONTENT_W = 1100
DPI       = 150


def _measure_text(text: str, font):
    tmp  = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(tmp)
    bb   = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


def wrap_text(text: str, font, max_w: int):
    words = text.split(' ')
    lines, cur = [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        tw, _ = _measure_text(test, font)
        if tw <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text]


def render_text_image(text: str, font_size: int = 18,
                      color=(0, 0, 0), bg=(255, 255, 255),
                      max_w: int = CONTENT_W, align: str = 'left'):
    font   = pil_font(font_size)
    lines  = wrap_text(text, font, max_w - 10)
    _, lh  = _measure_text('ਅ', font)
    line_h = lh + 8
    total_h = line_h * len(lines) + 12

    img  = Image.new('RGB', (max_w, max(total_h, line_h + 12)), bg)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        lw, _ = _measure_text(line, font)
        if align == 'center':
            x = max(0, (max_w - lw) // 2)
        elif align == 'right':
            x = max(0, max_w - lw - 5)
        else:
            x = 5
        draw.text((x, 6 + i * line_h), line, font=font, fill=color)
    return img


def pil_img_to_rl(pil_img, width_cm=None, height_cm=None):
    buf = BytesIO()
    pil_img.save(buf, format='PNG')
    buf.seek(0)
    w_pt = width_cm  * cm if width_cm  else (pil_img.width  / DPI * 2.54 * cm)
    h_pt = height_cm * cm if height_cm else (pil_img.height / DPI * 2.54 * cm)
    return RLImage(buf, width=w_pt, height=h_pt)


def t_heading(text: str, level: int = 2, pw: float = 17.0):
    fs  = {1: 26, 2: 20, 3: 17}.get(level, 17)
    col = (20, 100, 20)
    px  = int(pw * DPI / 2.54)
    img = render_text_image(text, font_size=fs, color=col, bg=(255, 255, 255), max_w=px)
    return pil_img_to_rl(img, width_cm=pw, height_cm=img.height / DPI * 2.54)


def t_para(text: str, font_size: int = 16, color=(0, 0, 0),
           pw: float = 17.0, align: str = 'left'):
    px  = int(pw * DPI / 2.54)
    img = render_text_image(text, font_size=font_size, color=color, max_w=px, align=align)
    return pil_img_to_rl(img, width_cm=pw, height_cm=img.height / DPI * 2.54)


def t_small(text: str, font_size: int = 13, color=(0, 0, 0), pw: float = 17.0):
    return t_para(text, font_size=font_size, color=color, pw=pw)


def t_title(text: str, pw: float = 17.0):
    return t_para(text, font_size=26, color=(20, 100, 20), pw=pw, align='center')


# ═══════════════════════════════════════════════════════
#  Table Builder (PIL-rendered cells)
# ═══════════════════════════════════════════════════════

def build_table_image(headers, rows, col_widths_px, font_size=14,
                      header_bg=(20, 100, 20), row_bg1=(255, 255, 255),
                      row_bg2=(240, 250, 240)):
    font   = pil_font(font_size)
    _, ch  = _measure_text('ਅ', font)
    line_h = ch + 8
    pad    = 8
    BORDER = 1

    total_w = sum(col_widths_px) + len(col_widths_px) + 1

    def cell_lines(text, col_w):
        return wrap_text(str(text), font, col_w - pad * 2)

    row_heights = []
    for row in rows:
        max_lines = 1
        for ci, cell in enumerate(row):
            txt = cell[0] if isinstance(cell, tuple) else str(cell)
            lns = cell_lines(txt, col_widths_px[ci])
            max_lines = max(max_lines, len(lns))
        row_heights.append(max_lines * line_h + pad * 2)

    header_h = line_h + pad * 2
    total_h  = header_h + sum(row_heights) + len(rows) + 2

    img  = Image.new('RGB', (total_w, total_h), (180, 180, 180))
    draw = ImageDraw.Draw(img)

    # Header
    x = BORDER
    draw.rectangle([0, 0, total_w - 1, header_h], fill=header_bg)
    for hdr, cw in zip(headers, col_widths_px):
        draw.text((x + pad, pad), hdr, font=font, fill=(255, 255, 255))
        x += cw + BORDER

    # Data rows
    y = header_h + BORDER
    for ri, (row, rh) in enumerate(zip(rows, row_heights)):
        bg = row_bg1 if ri % 2 == 0 else row_bg2
        draw.rectangle([0, y, total_w - 1, y + rh], fill=bg)
        x = BORDER
        for ci, (cell, cw) in enumerate(zip(row, col_widths_px)):
            txt  = cell[0] if isinstance(cell, tuple) else str(cell)
            tcol = cell[1] if isinstance(cell, tuple) else (0, 0, 0)
            lns  = cell_lines(txt, cw)
            for li, ln in enumerate(lns):
                draw.text((x + pad, y + pad + li * line_h), ln, font=font, fill=tcol)
            x += cw + BORDER
        draw.line([0, y + rh, total_w - 1, y + rh], fill=(180, 180, 180), width=1)
        y += rh + BORDER

    return img


# ═══════════════════════════════════════════════════════
#  Earth Engine helpers
# ═══════════════════════════════════════════════════════

def safe_get_info(obj, name="value"):
    if obj is None:
        return None
    try:
        v = obj.getInfo()
        return float(v) if v is not None else None
    except Exception as e:
        logging.warning(f"Failed {name}: {e}")
        return None


def sentinel_composite(region, start, end, bands):
    ss, es = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    try:
        coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterDate(ss, es).filterBounds(region)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
                .select(bands))
        if coll.size().getInfo() > 0:
            return coll.median().multiply(0.0001)
        for days in range(5, 31, 5):
            sd = (start - timedelta(days=days)).strftime("%Y-%m-%d")
            ed = (end   + timedelta(days=days)).strftime("%Y-%m-%d")
            coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                    .filterDate(sd, ed).filterBounds(region)
                    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
                    .select(bands))
            if coll.size().getInfo() > 0:
                return coll.median().multiply(0.0001)
        return None
    except Exception as e:
        logging.error(f"sentinel_composite: {e}")
        return None


def get_band_stats(comp, region, scale=10):
    try:
        s = comp.reduceRegion(reducer=ee.Reducer.mean(), geometry=region,
                              scale=scale, maxPixels=1e13).getInfo()
        return {k: (float(v) if v is not None else 0.0) for k, v in s.items()}
    except Exception as e:
        logging.error(f"get_band_stats: {e}")
        return {}


def get_lst(region, start, end):
    try:
        sd = (end - relativedelta(months=1)).strftime("%Y-%m-%d")
        ed = end.strftime("%Y-%m-%d")
        coll = (ee.ImageCollection("MODIS/061/MOD11A2")
                .filterBounds(region.buffer(5000)).filterDate(sd, ed)
                .select("LST_Day_1km"))
        if coll.size().getInfo() == 0:
            return None
        img   = (coll.median().multiply(0.02).subtract(273.15)
                 .rename("lst").clip(region.buffer(5000)))
        stats = img.reduceRegion(ee.Reducer.mean(), geometry=region,
                                 scale=1000, maxPixels=1e13).getInfo()
        v = stats.get("lst")
        return float(v) if v is not None else None
    except Exception as e:
        logging.error(f"get_lst: {e}")
        return None


def get_soil_texture(region):
    try:
        mode = SOIL_TEXTURE_IMG.clip(region.buffer(500)).reduceRegion(
            ee.Reducer.mode(), geometry=region, scale=250,
            maxPixels=1e13).get("b0")
        v = safe_get_info(mode, "texture")
        return int(v) if v is not None else None
    except Exception as e:
        logging.error(f"get_soil_texture: {e}")
        return None


def get_ph_new(bs):
    b2,b3,b4,b5,b8,b11 = (bs.get(k,0) for k in ["B2","B3","B4","B5","B8","B11"])
    ndvi_re = ((b8-b5)/(b8+b5+1e-6) + (b8-b4)/(b8+b4+1e-6)) / 2
    ph = 6.5 + 1.2*ndvi_re + 0.8*b11/(b8+1e-6) - 0.5*b8/(b4+1e-6) + 0.15*(1-(b2+b3+b4)/3)
    return max(4.0, min(9.0, ph))


def get_organic_carbon_pct(bs):
    b2,b3,b4,b5,b8,b11,b12 = (bs.get(k,0) for k in ["B2","B3","B4","B5","B8","B11","B12"])
    ndvi_re = ((b8-b5)/(b8+b5+1e-6) + (b8-b4)/(b8+b4+1e-6)) / 2
    L = 0.5
    savi = ((b8-b4)/(b8+b4+L+1e-6)) * (1+L)
    evi  = 2.5*(b8-b4)/(b8+6*b4-7.5*b2+1+1e-6)
    oc   = 1.2 + 3.5*ndvi_re + 2.2*savi - 1.5*(b11+b12)/2 + 0.4*evi
    return max(0.1, min(5.0, oc))


def get_salinity_ec(bs):
    b2,b3,b4,b8 = (bs.get(k,0) for k in ["B2","B3","B4","B8"])
    ndvi       = (b8-b4)/(b8+b4+1e-6)
    brightness = (b2+b3+b4)/3
    si1 = (b3*b4)**0.5
    si2 = (b3**2+b4**2)**0.5 if (b3**2+b4**2) > 0 else 0
    ec  = 0.5 + abs((si1+si2)/2)*4 + (1-max(0,min(1,ndvi)))*2 + 0.3*(1-brightness)
    return max(0.0, min(16.0, ec))


def estimate_cec(comp, region, intercept, slope_clay, slope_om):
    if comp is None:
        return None
    try:
        clay = comp.expression("(B11-B8)/(B11+B8+1e-6)",
                               {"B11":comp.select("B11"),"B8":comp.select("B8")}).rename("clay")
        om   = comp.expression("(B8-B4)/(B8+B4+1e-6)",
                               {"B8":comp.select("B8"),"B4":comp.select("B4")}).rename("om")
        c_m  = safe_get_info(clay.reduceRegion(ee.Reducer.mean(),geometry=region,scale=20,maxPixels=1e13).get("clay"))
        o_m  = safe_get_info(om.reduceRegion(ee.Reducer.mean(),geometry=region,scale=20,maxPixels=1e13).get("om"))
        return (intercept + slope_clay*c_m + slope_om*o_m) if (c_m and o_m) else None
    except Exception:
        return None


def get_ndvi(bs):
    b8,b4 = bs.get("B8",0), bs.get("B4",0)
    return (b8-b4)/(b8+b4+1e-6)

def get_evi(bs):
    b8,b4,b2 = bs.get("B8",0), bs.get("B4",0), bs.get("B2",0)
    return 2.5*(b8-b4)/(b8+6*b4-7.5*b2+1+1e-6)

def get_fvc(bs):
    return max(0, min(1, ((get_ndvi(bs)-0.2)/(0.8-0.2))**2))

def get_ndwi(bs):
    b3,b8 = bs.get("B3",0), bs.get("B8",0)
    return (b3-b8)/(b3+b8+1e-6)


def get_npk_kgha(bs):
    b2,b3,b4 = bs.get("B2",0),bs.get("B3",0),bs.get("B4",0)
    b5,b6,b7 = bs.get("B5",0),bs.get("B6",0),bs.get("B7",0)
    b8,b8a   = bs.get("B8",0),bs.get("B8A",0)
    b11,b12  = bs.get("B11",0),bs.get("B12",0)
    ndvi = (b8-b4)/(b8+b4+1e-6)
    evi  = 2.5*(b8-b4)/(b8+6*b4-7.5*b2+1+1e-6)
    brightness = (b2+b3+b4)/3
    ndre  = (b8a-b5)/(b8a+b5+1e-6)
    ci_re = (b7/(b5+1e-6)) - 1
    mcari = ((b5-b4) - 0.2*(b5-b3)) * (b5/(b4+1e-6))
    N = max(50,  min(600, 280+300*ndre+150*evi+20*(ci_re/5)-80*brightness+30*mcari))
    si1 = (b3*b4)**0.5
    si2 = (b3**2+b4**2)**0.5 if (b3**2+b4**2) > 0 else 0
    P = max(2,   min(60,  11+15*(1-brightness)+6*ndvi+4*abs((si1+si2)/2)+2*b3))
    K = max(40,  min(600, 150+200*b11/(b5+b6+1e-6)+80*(b11-b12)/(b11+b12+1e-6)+60*ndvi))
    return float(N), float(P), float(K)


def get_calcium_kgha(bs):
    b2,b3,b4,b8,b11,b12 = (bs.get(k,0) for k in ["B2","B3","B4","B8","B11","B12"])
    Ca = 550 + 250*(b11+b12)/(b4+b3+1e-6) + 150*(b2+b3+b4)/3 \
         - 100*(b8-b4)/(b8+b4+1e-6) - 80*(b11-b8)/(b11+b8+1e-6)
    return max(100, min(1200, float(Ca)))


def get_magnesium_kgha(bs):
    b4,b5,b7,b8,b8a,b11,b12 = (bs.get(k,0) for k in ["B4","B5","B7","B8","B8A","B11","B12"])
    Mg = 110 + 60*(b8a-b5)/(b8a+b5+1e-6) + 40*((b7/(b5+1e-6))-1) \
         + 30*(b11-b12)/(b11+b12+1e-6) + 20*(b8-b4)/(b8+b4+1e-6)
    return max(10, min(400, float(Mg)))


def get_sulphur_kgha(bs):
    b3,b4,b5,b8,b11,b12 = (bs.get(k,0) for k in ["B3","B4","B5","B8","B11","B12"])
    si1 = (b3*b4)**0.5
    si2 = (b3**2+b4**2)**0.5 if (b3**2+b4**2) > 0 else 0
    S   = 20 + 15*b11/(b3+b4+1e-6) + 10*abs((si1+si2)/2) \
          + 5*(b5/(b4+1e-6)-1) - 8*b12/(b11+1e-6) + 5*(b8-b4)/(b8+b4+1e-6)
    return max(2, min(80, float(S)))


# ═══════════════════════════════════════════════════════
#  Status & Scoring
# ═══════════════════════════════════════════════════════

def get_param_status(param, value):
    if value is None:
        return "na"
    if param == "Soil Texture":
        return "good" if value == IDEAL_RANGES[param] else "low"
    mn, mx = IDEAL_RANGES.get(param, (None, None))
    if mn is None and mx is not None:
        return "good" if value <= mx else "high"
    if mx is None and mn is not None:
        return "good" if value >= mn else "low"
    if mn is not None and mx is not None:
        if value < mn: return "low"
        if value > mx: return "high"
        return "good"
    return "good"


def calculate_soil_health_score(params):
    good  = sum(1 for p, v in params.items() if get_param_status(p, v) == "good")
    total = len([v for v in params.values() if v is not None])
    pct   = (good / total) * 100 if total else 0
    rating = ("ਸ਼੍ਰੇਸ਼ਠ" if pct >= 80 else
              "ਚੰਗਾ"     if pct >= 60 else
              "ਔਸਤ"      if pct >= 40 else
              "ਮਾੜਾ")
    return pct, rating, good, total


STATUS_COLOR_PIL = {
    "good": (20,  150,  20),
    "low":  (200, 100,   0),
    "high": (200,   0,   0),
    "na":   (120, 120, 120),
}


def get_suggestion(param, value):
    if value is None or param not in SUGGESTIONS:
        return "—"
    s  = SUGGESTIONS[param]
    st = get_param_status(param, value)
    if st == "good":
        return "ਠੀਕ: " + s.get("good", "ਮੌਜੂਦਾ ਅਭਿਆਸ ਜਾਰੀ ਰੱਖੋ।")
    if st == "low":
        return "ਸੁਧਾਰੋ: " + s.get("low", s.get("high", "ਖੇਤੀਬਾੜੀ ਮਾਹਿਰ ਨਾਲ ਸੰਪਰਕ ਕਰੋ।"))
    if st == "high":
        return "ਸੁਧਾਰੋ: " + s.get("high", s.get("low", "ਖੇਤੀਬਾੜੀ ਮਾਹਿਰ ਨਾਲ ਸੰਪਰਕ ਕਰੋ।"))
    return "—"


def generate_interpretation(param, value):
    if value is None:
        return "ਜਾਣਕਾਰੀ ਨਹੀਂ।"
    if param == "Soil Texture":
        return TEXTURE_CLASSES.get(value, "ਅਣਜਾਣ ਮਿੱਟੀ ਦੀ ਬਣਤਰ।")
    if param == "NDWI":
        if value >= -0.10: return "ਚੰਗੀ ਨਮੀ; ਸਿੰਚਾਈ ਦੀ ਲੋੜ ਨਹੀਂ।"
        if value >= -0.30: return "ਹਲਕਾ ਤਣਾਅ; 2 ਦਿਨਾਂ ਵਿੱਚ ਸਿੰਚਾਈ ਕਰੋ।"
        if value >= -0.40: return "ਦਰਮਿਆਨਾ ਤਣਾਅ; ਕੱਲ੍ਹ ਸਿੰਚਾਈ ਕਰੋ।"
        return "ਗੰਭੀਰ ਤਣਾਅ; ਤੁਰੰਤ ਸਿੰਚਾਈ ਕਰੋ।"
    if param == "Phosphorus":
        return "ਘੱਟ ਸਪੈਕਟ੍ਰਲ ਭਰੋਸੇਯੋਗਤਾ। ਸਿਰਫ਼ ਮਾਰਗਦਰਸ਼ਨ ਵਜੋਂ।"
    if param == "Sulphur":
        return "ਘੱਟ ਸਪੈਕਟ੍ਰਲ ਭਰੋਸੇਯੋਗਤਾ। ਸਿਰਫ਼ ਅਨੁਮਾਨ ਵਜੋਂ।"
    st    = get_param_status(param, value)
    ideal = IDEAL_DISPLAY.get(param, "N/A")
    if st == "good":
        return f"ਵਧੀਆ ਪੱਧਰ ({ideal})।"
    if st == "low":
        mn, _ = IDEAL_RANGES.get(param, (None, None))
        return f"ਘੱਟ ਪੱਧਰ ({mn} ਤੋਂ ਘੱਟ)।"
    if st == "high":
        _, mx = IDEAL_RANGES.get(param, (None, None))
        return f"ਵੱਧ ਪੱਧਰ ({mx} ਤੋਂ ਵੱਧ)।"
    return "ਕੋਈ ਵਿਆਖਿਆ ਨਹੀਂ।"


# ═══════════════════════════════════════════════════════
#  Charts
# ═══════════════════════════════════════════════════════

def _bar_color(param, val):
    s = get_param_status(param, val)
    return {"good":(0.08,0.59,0.08),"low":(0.85,0.45,0.00),
            "high":(0.80,0.08,0.08),"na":(0.50,0.50,0.50)}.get(s,(0.5,0.5,0.5))


def _set_punjabi_ticks(ax, labels, fp):
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontproperties=fp, fontsize=8)


def make_nutrient_chart(n, p, k, ca, mg, s):
    fp    = PUNJABI_FP
    pkeys = ["Nitrogen","Phosphorus","Potassium","Calcium","Magnesium","Sulphur"]
    vals  = [n or 0, p or 0, k or 0, ca or 0, mg or 0, s or 0]
    tlbls = ["ਨਾਈਟ੍ਰੋਜਨ\n(kg/ha)","ਫਾਸਫੋਰਸ\nP2O5 (kg/ha)",
             "ਪੋਟਾਸ਼ੀਅਮ\nK2O (kg/ha)","ਕੈਲਸ਼ੀਅਮ\n(kg/ha)",
             "ਮੈਗਨੀਸ਼ੀਅਮ\n(kg/ha)","ਗੰਧਕ\n(kg/ha)"]
    bcs = [_bar_color(pk, v) for pk, v in zip(pkeys, vals)]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    bars = ax.bar(range(len(tlbls)), vals, color=bcs, alpha=0.85)
    ymax = max(vals)*1.4 if any(vals) else 400
    ax.set_ylim(0, ymax)
    if fp:
        ax.set_title("ਮਿੱਟੀ ਪੋਸ਼ਕ ਤੱਤ (ਕਿਲੋ/ਹੈਕਟੇਅਰ) - ICAR ਮਿਆਰ", fontproperties=fp, fontsize=11)
        ax.set_ylabel("ਕਿਲੋ / ਹੈਕਟੇਅਰ", fontproperties=fp, fontsize=9)
        _set_punjabi_ticks(ax, tlbls, fp)
    tstatus = {pk: PUNJABI_STATUS.get(get_param_status(pk, v), "N/A") for pk, v in zip(pkeys, vals)}
    for bar, val, pk in zip(bars, vals, pkeys):
        lbl = tstatus[pk]
        if fp:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+ymax*0.02,
                    f"{val:.1f}\n{lbl}", ha='center', va='bottom', fontproperties=fp, fontsize=7)
    plt.tight_layout()
    path = "nutrient_chart.png"
    plt.savefig(path, dpi=120, bbox_inches='tight')
    plt.close()
    return path


def make_vegetation_chart(ndvi, ndwi):
    fp    = PUNJABI_FP
    tlbls = ["ਬਨਸਪਤੀ ਸੂਚਕ\n(NDVI)", "ਪਾਣੀ ਸੂਚਕ\n(NDWI)"]
    vals  = [ndvi or 0, ndwi or 0]
    bcs   = [_bar_color(p, v) for p, v in zip(["NDVI","NDWI"], vals)]
    fig, ax = plt.subplots(figsize=(5, 4.5))
    bars = ax.bar(range(2), vals, color=bcs, alpha=0.85)
    ax.axhline(0, color='black', linewidth=0.5, linestyle='--')
    ax.set_ylim(-1, 1)
    if fp:
        ax.set_title("ਬਨਸਪਤੀ ਅਤੇ ਪਾਣੀ ਸੂਚਕ", fontproperties=fp, fontsize=11)
        ax.set_ylabel("ਸੂਚਕ ਮੁੱਲ", fontproperties=fp, fontsize=9)
        _set_punjabi_ticks(ax, tlbls, fp)
    for i, (bar, val) in enumerate(zip(bars, vals)):
        lbl = PUNJABI_STATUS.get(get_param_status(["NDVI","NDWI"][i], val), "N/A")
        yp  = bar.get_height()+0.04 if val >= 0 else bar.get_height()-0.12
        if fp:
            ax.text(bar.get_x()+bar.get_width()/2, yp, f"{val:.2f}\n{lbl}",
                    ha='center', va='bottom', fontproperties=fp, fontsize=9)
    plt.tight_layout()
    path = "vegetation_chart.png"
    plt.savefig(path, dpi=120, bbox_inches='tight')
    plt.close()
    return path


def make_soil_properties_chart(ph, sal, oc, cec, lst):
    fp    = PUNJABI_FP
    pkeys = ["pH","Salinity","Organic Carbon","CEC","LST"]
    tlbls = ["pH\nਪੱਧਰ","EC ਬਿਜਲਈ\n(mS/cm)","ਜੈਵਿਕ\nਕਾਰਬਨ (%)","CEC\n(cmol/kg)","ਭੂਮੀ ਤਾਪ\n(C)"]
    vals  = [ph or 0, sal or 0, oc or 0, cec or 0, lst or 0]
    bcs   = [_bar_color(pk, v) for pk, v in zip(pkeys, vals)]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(range(len(tlbls)), vals, color=bcs, alpha=0.85)
    ymax = max(vals)*1.4 if any(vals) else 50
    ax.set_ylim(0, ymax)
    if fp:
        ax.set_title("ਮਿੱਟੀ ਦੇ ਗੁਣ (ICAR ਮਿਆਰ)", fontproperties=fp, fontsize=11)
        ax.set_ylabel("ਮੁੱਲ", fontproperties=fp, fontsize=9)
        _set_punjabi_ticks(ax, tlbls, fp)
    for bar, val, pk in zip(bars, vals, pkeys):
        lbl = PUNJABI_STATUS.get(get_param_status(pk, val), "N/A")
        if fp:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+ymax*0.02,
                    f"{val:.2f}\n{lbl}", ha='center', va='bottom', fontproperties=fp, fontsize=8)
    plt.tight_layout()
    path = "properties_chart.png"
    plt.savefig(path, dpi=120, bbox_inches='tight')
    plt.close()
    return path


# ═══════════════════════════════════════════════════════
#  Groq AI
# ═══════════════════════════════════════════════════════

def call_groq(prompt: str):
    try:
        client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        resp   = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900, temperature=0.35)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Groq: {e}")
        return None


# ═══════════════════════════════════════════════════════
#  PDF REPORT — ALL PUNJABI TEXT via PIL images
# ═══════════════════════════════════════════════════════

def generate_report(params, location, date_range):
    try:
        REPORT_PARAMS = {k: v for k, v in params.items() if k not in ("EVI", "FVC")}
        score, rating, good_c, total_c = calculate_soil_health_score(REPORT_PARAMS)

        # Charts
        nc = make_nutrient_chart(params["Nitrogen"], params["Phosphorus"], params["Potassium"],
                                  params["Calcium"], params["Magnesium"], params["Sulphur"])
        vc = make_vegetation_chart(params["NDVI"], params["NDWI"])
        pc = make_soil_properties_chart(params["pH"], params["Salinity"],
                                         params["Organic Carbon"], params["CEC"], params["LST"])

        def fv(param, v):
            if v is None: return "N/A"
            return f"{v:.2f}{UNIT_MAP.get(param,'')}"

        tex_d = TEXTURE_CLASSES.get(params["Soil Texture"], "N/A") if params["Soil Texture"] else "N/A"

        exec_prompt = (
            f"ਤੁਸੀਂ ਇੱਕ ਭਾਰਤੀ ਖੇਤੀਬਾੜੀ ਮਾਹਿਰ ਹੋ। ਹੇਠਾਂ ਦਿੱਤੇ ਮਿੱਟੀ ਡੇਟਾ ਨੂੰ ਦੇਖ ਕੇ, ਕਿਸਾਨ ਲਈ "
            f"4-5 ਬਿੰਦੂਆਂ ਵਿੱਚ ਸਿਰਫ਼ ਪੰਜਾਬੀ ਵਿੱਚ ਸੰਖੇਪ ਲਿਖੋ। "
            f"ਸਰਲ ਭਾਸ਼ਾ ਵਿੱਚ, Bold ਨਹੀਂ, markdown ਨਹੀਂ। "
            f"ਹਰ ਬਿੰਦੂ . (ਪੂਰਨ ਵਿਰਾਮ) ਨਾਲ ਸ਼ੁਰੂ ਕਰੋ।\n\n"
            f"ਮਿੱਟੀ ਸਿਹਤ ਸਕੋਰ: {score:.1f}% ({rating})\n"
            f"pH={fv('pH',params['pH'])}, EC={fv('Salinity',params['Salinity'])}, "
            f"ਜੈਵਿਕ ਕਾਰਬਨ={fv('Organic Carbon',params['Organic Carbon'])}, CEC={fv('CEC',params['CEC'])}\n"
            f"ਮਿੱਟੀ ਦੀ ਬਣਤਰ={tex_d}\n"
            f"ਨਾਈਟ੍ਰੋਜਨ={fv('Nitrogen',params['Nitrogen'])}, "
            f"ਫਾਸਫੋਰਸ={fv('Phosphorus',params['Phosphorus'])}, "
            f"ਪੋਟਾਸ਼ੀਅਮ={fv('Potassium',params['Potassium'])}\n"
            f"ਕੈਲਸ਼ੀਅਮ={fv('Calcium',params['Calcium'])}, "
            f"ਮੈਗਨੀਸ਼ੀਅਮ={fv('Magnesium',params['Magnesium'])}, "
            f"ਗੰਧਕ={fv('Sulphur',params['Sulphur'])}"
        )

        rec_prompt = (
            f"ਤੁਸੀਂ ਇੱਕ ਭਾਰਤੀ ਖੇਤੀਬਾੜੀ ਮਾਹਿਰ ਹੋ। ਹੇਠਾਂ ਦਿੱਤੇ ਮਿੱਟੀ ਡੇਟਾ ਨੂੰ ਦੇਖ ਕੇ, 4-5 ਅਮਲੀ ਸਿਫਾਰਸ਼ਾਂ "
            f"ਸਿਰਫ਼ ਪੰਜਾਬੀ ਵਿੱਚ ਦਿਓ। ਸਰਲ ਕਿਸਾਨ ਭਾਸ਼ਾ ਵਿੱਚ। Bold ਨਹੀਂ, markdown ਨਹੀਂ। "
            f"ਹਰ ਬਿੰਦੂ . (ਪੂਰਨ ਵਿਰਾਮ) ਨਾਲ ਸ਼ੁਰੂ ਕਰੋ।\n\n"
            f"pH={fv('pH',params['pH'])}, EC={fv('Salinity',params['Salinity'])}, ਮਿੱਟੀ={tex_d}\n"
            f"ਨਾਈਟ੍ਰੋਜਨ={fv('Nitrogen',params['Nitrogen'])}, "
            f"ਫਾਸਫੋਰਸ={fv('Phosphorus',params['Phosphorus'])} (ਅਨੁਮਾਨ), "
            f"ਪੋਟਾਸ਼ੀਅਮ={fv('Potassium',params['Potassium'])}\n"
            f"ਕੈਲਸ਼ੀਅਮ={fv('Calcium',params['Calcium'])}, "
            f"ਮੈਗਨੀਸ਼ੀਅਮ={fv('Magnesium',params['Magnesium'])}, "
            f"ਗੰਧਕ={fv('Sulphur',params['Sulphur'])} (ਅਨੁਮਾਨ)\n"
            f"NDVI={fv('NDVI',params['NDVI'])}, NDWI={fv('NDWI',params['NDWI'])}\n"
            f"ਭਾਰਤੀ ਮੌਸਮ ਲਈ ਢੁਕਵੀਆਂ ਫਸਲਾਂ ਦੀ ਸਿਫਾਰਸ਼ ਕਰੋ।"
        )

        exec_summary = call_groq(exec_prompt) or ". ਸੰਖੇਪ ਉਪਲਬਧ ਨਹੀਂ।"
        recs         = call_groq(rec_prompt)  or ". ਸਿਫਾਰਸ਼ਾਂ ਉਪਲਬਧ ਨਹੀਂ।"

        # ─── Build PDF ────────────────────────────────────────────────────
        pdf_buf = BytesIO()
        doc = SimpleDocTemplate(pdf_buf, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=3*cm, bottomMargin=2*cm)
        PW = 17.0  # usable width in cm
        elems = []

        # ── COVER PAGE ────────────────────────────────────────────────────
        elems.append(Spacer(1, 1.5*cm))
        if os.path.exists(LOGO_PATH):
            li = RLImage(LOGO_PATH, width=9*cm, height=9*cm)
            li.hAlign = 'CENTER'
            elems.append(li)
        elems.append(Spacer(1, 0.5*cm))
        elems.append(t_title("FarmMatrix ਮਿੱਟੀ ਸਿਹਤ ਰਿਪੋਰਟ", PW))
        elems.append(Spacer(1, 0.4*cm))
        elems.append(t_para(f"ਸਥਾਨ: {location}", 16, (60,60,60), PW, 'center'))
        elems.append(t_para(f"ਤਾਰੀਖ਼ ਸੀਮਾ: {date_range}", 16, (60,60,60), PW, 'center'))
        elems.append(t_para(f"ਤਿਆਰ ਕੀਤੀ ਤਾਰੀਖ਼: {datetime.now():%d %B %Y, %H:%M}",
                            14, (100,100,100), PW, 'center'))
        elems.append(PageBreak())

        # ── SEC 1: EXECUTIVE SUMMARY ──────────────────────────────────────
        elems.append(t_heading("1. ਕਾਰਜਕਾਰੀ ਸੰਖੇਪ", 2, PW))
        elems.append(Spacer(1, 0.2*cm))
        for line in exec_summary.split('\n'):
            line = line.strip()
            if line:
                elems.append(t_para(line, 15, (30,30,30), PW))
                elems.append(Spacer(1, 0.1*cm))
        elems.append(Spacer(1, 0.3*cm))

        # ── SEC 2: HEALTH SCORE ───────────────────────────────────────────
        elems.append(t_heading("2. ਮਿੱਟੀ ਸਿਹਤ ਮੁਲਾਂਕਣ", 2, PW))
        elems.append(Spacer(1, 0.2*cm))
        score_color = (20,150,20) if score>=60 else ((200,150,0) if score>=40 else (200,50,50))
        score_tbl = build_table_image(
            headers=["ਕੁੱਲ ਸਕੋਰ", "ਮੁਲਾਂਕਣ", "ਵਧੀਆ ਪੈਰਾਮੀਟਰ"],
            rows=[[
                (f"{score:.1f}%", score_color),
                (rating,          score_color),
                (f"{good_c} / {total_c}", (30,30,30))
            ]],
            col_widths_px=[260, 260, 260], font_size=17)
        ri = pil_img_to_rl(score_tbl, width_cm=PW)
        ri.hAlign = 'LEFT'
        elems.append(ri)
        elems.append(Spacer(1, 0.3*cm))
        elems.append(PageBreak())

        # ── SEC 3: PARAMETER TABLE ────────────────────────────────────────
        elems.append(t_heading("3. ਮਿੱਟੀ ਪੈਰਾਮੀਟਰ ਵਿਸ਼ਲੇਸ਼ਣ (ICAR ਮਿਆਰ)", 2, PW))
        elems.append(Spacer(1, 0.2*cm))
        headers3 = ["ਪੈਰਾਮੀਟਰ", "ਮੁੱਲ", "ICAR ਵਧੀਆ ਸੀਮਾ", "ਸਥਿਤੀ", "ਵਿਆਖਿਆ"]
        rows3 = []
        for param, value in REPORT_PARAMS.items():
            unit    = UNIT_MAP.get(param, "")
            val_txt = (TEXTURE_CLASSES.get(value, "N/A")
                       if param == "Soil Texture" and value
                       else (f"{value:.2f}{unit}" if value is not None else "N/A"))
            st      = get_param_status(param, value)
            st_lbl  = PUNJABI_STATUS.get(st, "N/A")
            st_col  = STATUS_COLOR_PIL.get(st, (0,0,0))
            interp  = generate_interpretation(param, value)
            rows3.append([
                (PUNJABI_PARAM_NAMES.get(param, param), (30,30,30)),
                (val_txt, (30,30,30)),
                (IDEAL_DISPLAY.get(param, "N/A"), (30,30,30)),
                (st_lbl, st_col),
                (interp, (30,30,30)),
            ])
        tbl3 = build_table_image(headers=headers3, rows=rows3,
                                  col_widths_px=[200, 130, 160, 100, 310], font_size=13)
        ri3 = pil_img_to_rl(tbl3, width_cm=PW)
        ri3.hAlign = 'LEFT'
        elems.append(ri3)
        elems.append(PageBreak())

        # ── SEC 4: CHARTS ─────────────────────────────────────────────────
        elems.append(t_heading("4. ਦ੍ਰਿਸ਼ਟੀਕੋਣ", 2, PW))
        elems.append(Spacer(1, 0.2*cm))
        for lbl, cpath in [
            ("N, P2O5, K2O, Ca, Mg, S ਪੋਸ਼ਕ ਤੱਤ (ਕਿਲੋ/ਹੈਕਟੇਅਰ):", nc),
            ("ਬਨਸਪਤੀ ਅਤੇ ਪਾਣੀ ਸੂਚਕ (NDVI, NDWI):", vc),
            ("ਮਿੱਟੀ ਦੇ ਗੁਣ:", pc),
        ]:
            elems.append(t_small(lbl, 14, (30,30,30), PW))
            if cpath and os.path.exists(cpath):
                ci = RLImage(cpath, width=14*cm, height=7*cm)
                ci.hAlign = 'LEFT'
                elems.append(ci)
            elems.append(Spacer(1, 0.3*cm))
        elems.append(PageBreak())

        # ── SEC 5: RECOMMENDATIONS ────────────────────────────────────────
        elems.append(t_heading("5. ਫਸਲ ਸਿਫਾਰਸ਼ਾਂ ਅਤੇ ਇਲਾਜ", 2, PW))
        elems.append(Spacer(1, 0.2*cm))
        for line in recs.split('\n'):
            line = line.strip()
            if line:
                elems.append(t_para(line, 15, (30,30,30), PW))
                elems.append(Spacer(1, 0.1*cm))
        elems.append(Spacer(1, 0.3*cm))
        elems.append(PageBreak())

        # ── SEC 6: PARAMETER-WISE SUGGESTIONS ────────────────────────────
        elems.append(t_heading("6. ਪੈਰਾਮੀਟਰ ਅਨੁਸਾਰ ਸਿਫਾਰਸ਼ਾਂ", 2, PW))
        elems.append(Spacer(1, 0.1*cm))
        elems.append(t_small(
            "ਹਰ ਪੈਰਾਮੀਟਰ ਲਈ: ਵਧੀਆ ਪੱਧਰ ਬਣਾਈ ਰੱਖਣ ਜਾਂ ਸਮੱਸਿਆਵਾਂ ਠੀਕ ਕਰਨ ਲਈ ਕੀ ਕਰਨਾ ਹੈ।",
            13, (80,80,80), PW))
        elems.append(Spacer(1, 0.2*cm))

        SUG_PARAMS = ["pH","Salinity","Organic Carbon","CEC","Nitrogen","Phosphorus",
                      "Potassium","Calcium","Magnesium","Sulphur","NDVI","NDWI","LST"]
        headers6 = ["ਪੈਰਾਮੀਟਰ", "ਸਥਿਤੀ", "ਲੋੜੀਂਦੀ ਕਾਰਵਾਈ"]
        rows6 = []
        for param in SUG_PARAMS:
            value  = params.get(param)
            st     = get_param_status(param, value)
            st_lbl = PUNJABI_STATUS.get(st, "N/A")
            st_col = STATUS_COLOR_PIL.get(st, (0,0,0))
            sug    = get_suggestion(param, value)
            rows6.append([
                (PUNJABI_PARAM_NAMES.get(param, param), (30,30,30)),
                (st_lbl, st_col),
                (sug, (30,30,30)),
            ])
        tbl6 = build_table_image(headers=headers6, rows=rows6,
                                  col_widths_px=[200, 100, 600], font_size=13)
        ri6 = pil_img_to_rl(tbl6, width_cm=PW)
        ri6.hAlign = 'LEFT'
        elems.append(ri6)
        elems.append(Spacer(1, 0.4*cm))
        elems.append(t_small(
            "ਨੋਟ: ਫਾਸਫੋਰਸ (P) ਅਤੇ ਗੰਧਕ (S) ਦੀਆਂ ਕੀਮਤਾਂ ਲਈ ਸਪੈਕਟ੍ਰਲ ਭਰੋਸੇਯੋਗਤਾ ਘੱਟ ਹੈ। "
            "ਸਿਰਫ਼ ਅਨੁਮਾਨ ਵਜੋਂ ਮੰਨੋ। ਖੇਤ ਨਮੂਨਾ ਜਾਂਚ ਦੀ ਸਿਫਾਰਸ਼ ਕੀਤੀ ਜਾਂਦੀ ਹੈ।",
            12, (120,60,0), PW))

        # ─── Header / Footer ──────────────────────────────────────────────
        def add_header(canv, doc):
            canv.saveState()
            if os.path.exists(LOGO_PATH):
                canv.drawImage(LOGO_PATH, 2*cm, A4[1]-2.8*cm, width=1.8*cm, height=1.8*cm)
            canv.setFont("Helvetica-Bold", 11)
            canv.drawString(4.5*cm, A4[1]-2.2*cm, "FarmMatrix Soil Health Report (Punjabi)")
            canv.setFont("Helvetica", 8)
            canv.drawRightString(A4[0]-2*cm, A4[1]-2.2*cm,
                                 f"Generated: {datetime.now():%d %b %Y, %H:%M}")
            canv.setStrokeColor(colors.darkgreen)
            canv.setLineWidth(1)
            canv.line(2*cm, A4[1]-3*cm, A4[0]-2*cm, A4[1]-3*cm)
            canv.restoreState()

        def add_footer(canv, doc):
            canv.saveState()
            canv.setStrokeColor(colors.darkgreen)
            canv.line(2*cm, 1.5*cm, A4[0]-2*cm, 1.5*cm)
            canv.setFont("Helvetica", 8)
            canv.drawCentredString(A4[0]/2, cm,
                                   f"Page {doc.page}  |  FarmMatrix  |  ICAR Standard")
            canv.restoreState()

        doc.build(elems, onFirstPage=add_header, onLaterPages=add_header,
                  canvasmaker=canvas.Canvas)
        pdf_buf.seek(0)
        return pdf_buf.getvalue()

    except Exception as e:
        logging.error(f"generate_report error: {e}")
        import traceback; traceback.print_exc()
        return None


# ═══════════════════════════════════════════════════════
#  Streamlit UI — Punjabi
# ═══════════════════════════════════════════════════════

st.set_page_config(layout='wide', page_title="FarmMatrix ਮਿੱਟੀ ਸਿਹਤ ਡੈਸ਼ਬੋਰਡ")
st.title("🌾 FarmMatrix ਮਿੱਟੀ ਸਿਹਤ ਡੈਸ਼ਬੋਰਡ")
st.markdown("ਉਪਗ੍ਰਹਿ ਡੇਟਾ ਅਧਾਰਿਤ ਮਿੱਟੀ ਵਿਸ਼ਲੇਸ਼ਣ — ICAR ਮਿਆਰ ਕਿਲੋ/ਹੈਕਟੇਅਰ ਇਕਾਈਆਂ ਵਿੱਚ।")

# Sidebar
st.sidebar.header("📍 ਸਥਾਨ ਚੋਣ")
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]
lat = st.sidebar.number_input("ਅਕਸ਼ਾਂਸ਼",  value=st.session_state.user_location[0], format="%.6f")
lon = st.sidebar.number_input("ਦੇਸ਼ਾਂਤਰ",  value=st.session_state.user_location[1], format="%.6f")
st.session_state.user_location = [lat, lon]

st.sidebar.header("CEC ਨਮੂਨਾ ਗੁਣਾਂਕ")
cec_intercept  = st.sidebar.number_input("Intercept",          value=5.0,  step=0.1)
cec_slope_clay = st.sidebar.number_input("Slope (Clay Index)", value=20.0, step=0.1)
cec_slope_om   = st.sidebar.number_input("Slope (OM Index)",   value=15.0, step=0.1)

today      = date.today()
start_date = st.sidebar.date_input("ਸ਼ੁਰੂਆਤੀ ਤਾਰੀਖ਼", value=today - timedelta(days=16))
end_date   = st.sidebar.date_input("ਅੰਤਮ ਤਾਰੀਖ਼",      value=today)
if start_date > end_date:
    st.sidebar.error("ਸ਼ੁਰੂਆਤੀ ਤਾਰੀਖ਼ ਅੰਤਮ ਤਾਰੀਖ਼ ਤੋਂ ਪਹਿਲਾਂ ਹੋਣੀ ਚਾਹੀਦੀ ਹੈ।")
    st.stop()

# Map
m = folium.Map(location=[lat, lon], zoom_start=15)
Draw(export=True).add_to(m)
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google").add_to(m)
folium.Marker([lat, lon], popup="ਕੇਂਦਰ").add_to(m)
map_data = st_folium(m, width=700, height=500)

region = None
if map_data and "last_active_drawing" in map_data:
    try:
        sel = map_data["last_active_drawing"]
        if sel and "geometry" in sel and "coordinates" in sel["geometry"]:
            region = ee.Geometry.Polygon(sel["geometry"]["coordinates"])
        else:
            st.error("ਗਲਤ ਖੇਤਰ। ਸਹੀ ਬਹੁਭੁਜ ਬਣਾਓ।")
    except Exception as e:
        st.error(f"ਖੇਤਰ ਬਣਾਉਣ ਵਿੱਚ ਗਲਤੀ: {e}")

if region:
    st.subheader(f"ਵਿਸ਼ਲੇਸ਼ਣ: {start_date} ਤੋਂ {end_date} ਤੱਕ")
    pb = st.progress(0)
    sm = st.empty()

    sm.text("Sentinel-2 ਤਸਵੀਰਾਂ ਪ੍ਰਾਪਤ ਕਰ ਰਹੇ ਹਾਂ...")
    comp = sentinel_composite(region, start_date, end_date, ALL_BANDS)
    pb.progress(20)

    sm.text("ਮਿੱਟੀ ਬਣਤਰ ਨਕਸ਼ਾ ਪੜ੍ਹ ਰਹੇ ਹਾਂ...")
    texc = get_soil_texture(region)
    pb.progress(35)

    sm.text("MODIS ਭੂਮੀ ਤਾਪਮਾਨ ਪ੍ਰਾਪਤ ਕਰ ਰਹੇ ਹਾਂ...")
    lst = get_lst(region, start_date, end_date)
    pb.progress(50)

    if comp is None:
        st.warning("Sentinel-2 ਡੇਟਾ ਉਪਲਬਧ ਨਹੀਂ। ਤਾਰੀਖ਼ ਸੀਮਾ ਵਧਾਓ।")
        ph=sal=oc=cec=ndwi=ndvi=evi=fvc=n_val=p_val=k_val=ca_val=mg_val=s_val=None
    else:
        sm.text("ਮਿੱਟੀ ਪੈਰਾਮੀਟਰ ਗਣਨਾ ਕਰ ਰਹੇ ਹਾਂ...")
        bs   = get_band_stats(comp, region)
        ph   = get_ph_new(bs)
        sal  = get_salinity_ec(bs)
        oc   = get_organic_carbon_pct(bs)
        cec  = estimate_cec(comp, region, cec_intercept, cec_slope_clay, cec_slope_om)
        ndwi = get_ndwi(bs)
        ndvi = get_ndvi(bs)
        evi  = get_evi(bs)
        fvc  = get_fvc(bs)
        n_val, p_val, k_val = get_npk_kgha(bs)
        ca_val = get_calcium_kgha(bs)
        mg_val = get_magnesium_kgha(bs)
        s_val  = get_sulphur_kgha(bs)
        pb.progress(100)
        sm.text("ਵਿਸ਼ਲੇਸ਼ਣ ਮੁਕੰਮਲ! ✅")

    params = {
        "pH": ph, "Salinity": sal, "Organic Carbon": oc, "CEC": cec,
        "Soil Texture": texc, "LST": lst, "NDWI": ndwi, "NDVI": ndvi,
        "EVI": evi, "FVC": fvc, "Nitrogen": n_val, "Phosphorus": p_val,
        "Potassium": k_val, "Calcium": ca_val, "Magnesium": mg_val, "Sulphur": s_val,
    }

    st.markdown("### 🧪 ਮਿੱਟੀ ਪੈਰਾਮੀਟਰ")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("pH ਤੇਜ਼ਾਬੀਪਣ",           f"{ph:.2f}"  if ph  else "N/A")
        st.metric("ਲੂਣਾਪਣ (mS/cm)",           f"{sal:.2f}" if sal else "N/A")
        st.metric("ਜੈਵਿਕ ਕਾਰਬਨ (%)",          f"{oc:.2f}"  if oc  else "N/A")
        st.metric("CEC (cmol/kg)",              f"{cec:.2f}" if cec else "N/A")
    with c2:
        st.metric("NDVI ਬਨਸਪਤੀ ਸੂਚਕ",        f"{ndvi:.3f}" if ndvi else "N/A")
        st.metric("EVI ਵਧੀਆ ਬਨਸਪਤੀ ਸੂਚਕ",   f"{evi:.3f}"  if evi  else "N/A")
        st.metric("FVC ਢੱਕਣ ਸੂਚਕ",            f"{fvc:.3f}"  if fvc  else "N/A")
        st.metric("NDWI ਪਾਣੀ ਸੂਚਕ",           f"{ndwi:.3f}" if ndwi else "N/A")
    with c3:
        st.metric("ਨਾਈਟ੍ਰੋਜਨ N (kg/ha)",      f"{n_val:.1f}" if n_val else "N/A")
        st.metric("ਫਾਸਫੋਰਸ P2O5 (kg/ha)",     f"{p_val:.1f}" if p_val else "N/A")
        st.metric("ਪੋਟਾਸ਼ੀਅਮ K2O (kg/ha)",    f"{k_val:.1f}" if k_val else "N/A")
        st.metric("ਭੂਮੀ ਤਾਪਮਾਨ LST (C)",       f"{lst:.1f}"   if lst   else "N/A")
    with c4:
        st.metric("ਕੈਲਸ਼ੀਅਮ Ca (kg/ha)",      f"{ca_val:.1f}" if ca_val else "N/A")
        st.metric("ਮੈਗਨੀਸ਼ੀਅਮ Mg (kg/ha)",    f"{mg_val:.1f}" if mg_val else "N/A")
        st.metric("ਗੰਧਕ S (kg/ha)",            f"{s_val:.1f}"  if s_val  else "N/A")

    score, rating, _, _ = calculate_soil_health_score(params)
    icon = ("🟢" if "ਸ਼੍ਰੇਸ਼ਠ" in rating or "ਚੰਗਾ" in rating
            else "🟡" if "ਔਸਤ" in rating else "🔴")
    st.info(f"{icon} ਮਿੱਟੀ ਸਿਹਤ ਸਕੋਰ: {score:.1f}% — {rating}  (ICAR ਮਿਆਰ)")

    st.markdown("### 💡 ਤੇਜ਼ ਸਿਫਾਰਸ਼ਾਂ")
    sug_rows = []
    for p in ["pH","Salinity","Organic Carbon","Nitrogen","Phosphorus",
              "Potassium","Calcium","Magnesium","Sulphur"]:
        v   = params.get(p)
        st2 = get_param_status(p, v)
        sug_rows.append({
            "ਪੈਰਾਮੀਟਰ": PUNJABI_PARAM_NAMES.get(p, p),
            "ਮੁੱਲ":      f"{v:.2f}{UNIT_MAP.get(p,'')}" if v is not None else "N/A",
            "ਸਥਿਤੀ":    PUNJABI_STATUS.get(st2, "N/A"),
            "ਸਿਫਾਰਸ਼":  get_suggestion(p, v).replace("ਠੀਕ: ","").replace("ਸੁਧਾਰੋ: ",""),
        })
    st.dataframe(pd.DataFrame(sug_rows), use_container_width=True, hide_index=True)

    if st.button("📄 ਪੂਰੀ PDF ਰਿਪੋਰਟ ਬਣਾਓ (ਪੰਜਾਬੀ)"):
        with st.spinner("Groq AI ਰਾਹੀਂ ਪੰਜਾਬੀ ਰਿਪੋਰਟ ਬਣਾ ਰਹੇ ਹਾਂ... (ਕੁਝ ਮਿੰਟ ਲੱਗ ਸਕਦੇ ਹਨ)"):
            loc_str  = f"ਅਕਸ਼ਾਂਸ਼: {lat:.6f}, ਦੇਸ਼ਾਂਤਰ: {lon:.6f}"
            date_str = f"{start_date} ਤੋਂ {end_date} ਤੱਕ"
            pdf_data = generate_report(params, loc_str, date_str)
            if pdf_data:
                st.success("✅ ਪੰਜਾਬੀ ਰਿਪੋਰਟ ਤਿਆਰ ਹੈ!")
                st.download_button(
                    label="📥 PDF ਰਿਪੋਰਟ ਡਾਊਨਲੋਡ ਕਰੋ",
                    data=pdf_data,
                    file_name=f"mitti_sihat_report_{date.today()}.pdf",
                    mime="application/pdf",
                )
            else:
                st.error("ਰਿਪੋਰਟ ਬਣਾਉਣ ਵਿੱਚ ਅਸਫਲਤਾ। ਲੌਗ ਜਾਂਚੋ।")
else:
    st.info("🗺️ ਆਪਣੇ ਖੇਤ ਜਾਂ ਖੇਤਰ ਦੀ ਚੋਣ ਕਰਨ ਲਈ ਉੱਪਰਲੇ ਨਕਸ਼ੇ ਵਿੱਚ ਬਹੁਭੁਜ ਬਣਾਓ।")