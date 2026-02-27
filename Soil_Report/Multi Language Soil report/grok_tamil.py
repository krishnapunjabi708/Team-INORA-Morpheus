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
    Image as RLImage, Table, TableStyle
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from io import BytesIO
from openai import OpenAI

# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
GROQ_API_KEY = "grok-api"
GROQ_MODEL   = "llama-3.3-70b-versatile"
LOGO_PATH    = os.path.abspath("LOGO.jpg")

# ── Tamil Font (PIL uses FreeType → proper Tamil shaping) ─────────────────────
TAMIL_FONT_PATH = "FreeSerif.ttf"
if not os.path.exists(TAMIL_FONT_PATH):
    TAMIL_FONT_PATH = "FreeSerif.ttf"

# Pre-load PIL fonts at various sizes
_PIL_FONTS = {}
def pil_font(size):
    if size not in _PIL_FONTS:
        try:
            _PIL_FONTS[size] = ImageFont.truetype(TAMIL_FONT_PATH, size)
        except Exception:
            _PIL_FONTS[size] = ImageFont.load_default()
    return _PIL_FONTS[size]

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
#  Constants
# ─────────────────────────────────────────────
SOIL_TEXTURE_IMG = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0')

TEXTURE_CLASSES = {
    1: "களிமண் (Clay)", 2: "மணல் களிமண் (Silty Clay)", 3: "மணல் களிமண் (Sandy Clay)",
    4: "களிமண் கலவை (Clay Loam)", 5: "மணல் களிமண் கலவை (Silty Clay Loam)",
    6: "மணல் களிமண் கலவை (Sandy Clay Loam)",
    7: "கலவை மண் (Loam)", 8: "மணல் கலவை மண் (Silty Loam)", 9: "மணல் கலவை (Sandy Loam)",
    10: "மணல் (Silt)", 11: "மணல் கலவை (Loamy Sand)", 12: "மணல் (Sand)"
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
    "pH": "6.5-7.5", "Salinity": "<=1.0 mS/cm",
    "Organic Carbon": "0.75-1.50 %", "CEC": "10-30 cmol/kg",
    "Soil Texture": "கலவை மண் (Loam)", "LST": "15-35 C",
    "NDWI": "-0.3 to 0.2", "NDVI": "0.2-0.8",
    "EVI": "0.2-0.8", "FVC": "0.3-0.8",
    "Nitrogen": "280-560 kg/ha", "Phosphorus": "11-22 kg/ha",
    "Potassium": "108-280 kg/ha",
    "Calcium":   "400-800 kg/ha",
    "Magnesium": "50-200 kg/ha",
    "Sulphur":   "10-40 kg/ha",
}

UNIT_MAP = {
    "pH": "", "Salinity": " mS/cm", "Organic Carbon": " %",
    "CEC": " cmol/kg", "Soil Texture": "", "LST": " C",
    "NDWI": "", "NDVI": "", "EVI": "", "FVC": "",
    "Nitrogen": " kg/ha", "Phosphorus": " kg/ha", "Potassium": " kg/ha",
    "Calcium": " kg/ha", "Magnesium": " kg/ha", "Sulphur": " kg/ha",
}

TAMIL_PARAM_NAMES = {
    "pH":             "pH அமிலத்தன்மை",
    "Salinity":       "உப்புத்தன்மை (EC)",
    "Organic Carbon": "கரிம கார்பன்",
    "CEC":            "கேஷன் பரிமாற்ற திறன்",
    "Soil Texture":   "மண் அமைப்பு",
    "LST":            "நில வெப்பநிலை",
    "NDVI":           "தாவர குறியீடு (NDVI)",
    "EVI":            "மேம்படுத்தப்பட்ட தாவர குறியீடு",
    "FVC":            "தாவர மூடுதல் குறியீடு",
    "NDWI":           "நீர் குறியீடு (NDWI)",
    "Nitrogen":       "நைட்ரஜன் (N)",
    "Phosphorus":     "பாஸ்பரஸ் (P)",
    "Potassium":      "பொட்டாசியம் (K)",
    "Calcium":        "கால்சியம் (Ca)",
    "Magnesium":      "மெக்னீசியம் (Mg)",
    "Sulphur":        "கந்தகம் (S)",
}

TAMIL_STATUS = {"good": "சிறந்தது", "low": "குறைவு", "high": "அதிகம்", "na": "N/A"}

SUGGESTIONS = {
    "pH": {
        "good": "ஒவ்வொரு 2-3 ஆண்டுகளுக்கு ஒருமுறை சுண்ணாம்பு இட்டு pH பராமரிக்கவும். அதிக யூரியா தவிர்க்கவும்.",
        "low":  "வேளாண் சுண்ணாம்பு 2-4 பை/ஏக்கர் இடவும். அமிலமயமாக்கும் உரங்களை தவிர்க்கவும்.",
        "high": "ஜிப்சம் அல்லது கந்தகம் 5-10 கிலோ/ஏக்கர் சேர்க்கவும். அமோனியம் சல்பேட் பயன்படுத்தவும்.",
    },
    "Salinity": {
        "good": "சொட்டு நீர்ப்பாசனம் தொடரவும். நீர்தேக்கம் தவிர்க்கவும்.",
        "high": "கூடுதல் நீர்ப்பாசனத்தால் வயலை கழுவவும். ஜிப்சம் 200 கிலோ/ஏக்கர் இடவும்.",
    },
    "Organic Carbon": {
        "good": "ஆண்டுதோறும் 2 டன் FYM/உரம் ஏக்கருக்கு சேர்க்கவும்.",
        "low":  "FYM 4-5 டன்/ஏக்கர் இடவும். பசுந்தாள் உரமிடல் செய்யவும்.",
        "high": "நல்ல உழவு மூலம் சமன்படுத்தவும். வடிகால் மேம்படுத்தவும்.",
    },
    "CEC": {
        "good": "கரிம கார்பன் பராமரித்து அதிக உழவை தவிர்க்கவும்.",
        "low":  "கம்போஸ்ட் அல்லது களிமண் திருத்தங்களை சேர்க்கவும்.",
        "high": "ஊட்டச்சத்துகள் கிடைக்க pH சரியான அளவில் வைக்கவும்.",
    },
    "LST": {
        "good": "மண் வெப்பநிலை நிலையாக வைக்க மல்ச் பயன்படுத்தவும்.",
        "low":  "கருப்பு பிளாஸ்டிக் மல்ச் பயன்படுத்தி மண்ணை சூடாக்கவும்.",
        "high": "வைக்கோல் மல்ச் இட்டு மண்ணை குளிர்விக்கவும். நீர்ப்பாசனம் அதிகரிக்கவும்.",
    },
    "NDVI": {
        "good": "தற்போதைய பயிர் அடர்த்தி மற்றும் உரமிடல் அட்டவணையை பராமரிக்கவும்.",
        "low":  "பூச்சி அல்லது நோய் இருக்கிறதா என சரிபார்க்கவும். NPK சமச்சீர் உரம் இடவும்.",
        "high": "வாய்ப்புக்கு சாய்வதை கவனிக்கவும். நல்ல வடிகால் உறுதி செய்யவும்.",
    },
    "EVI": {
        "good": "தற்போதைய பயிர் மேலாண்மையை தொடரவும்.",
        "low":  "இலை வழி நுண்ணூட்ட தெளிப்பு: ஜிங்க் சல்பேட் + போரான் இடவும்.",
        "high": "நல்ல காற்றோட்டம் உறுதி செய்யவும். பூஞ்சை நோயை கவனிக்கவும்.",
    },
    "FVC": {
        "good": "தரை மூடுதலை பராமரிக்கவும்.",
        "low":  "தாவர எண்ணிக்கை அதிகரிக்கவும். களை கட்டுப்படுத்தவும்.",
        "high": "அடர்த்தியான மூடுதல் ஈரப்பத அழுத்தத்தை மறைக்கலாம்.",
    },
    "NDWI": {
        "good": "தற்போதைய நீர்ப்பாசன அட்டவணையை தொடரவும்.",
        "low":  "உடனே நீர்ப்பாசனம் செய்யவும். சொட்டு நீர்ப்பாசனம் பரிந்துரைக்கப்படுகிறது.",
        "high": "நீர்ப்பாசனம் குறைக்கவும். நீர்தேக்கம் தவிர்க்க வடிகால் சரிபார்க்கவும்.",
    },
    "Nitrogen": {
        "good": "இழப்பை தவிர்க்க யூரியாவை பிரித்து இடவும் (அடிபரவல் + மேலுரம்).",
        "low":  "யூரியா 25-30 கிலோ/ஏக்கர் அல்லது DAP இடவும்.",
        "high": "இந்த சீசனில் நைட்ரஜன் தவிர்க்கவும். வேப்பம்பூசிய யூரியா பயன்படுத்தவும்.",
    },
    "Phosphorus": {
        "good": "விதைப்பின்போது குறைந்த அளவு SSP அல்லது DAP இடவும்.",
        "low":  "DAP 12 கிலோ/ஏக்கர் அல்லது SSP 50 கிலோ/ஏக்கர் விதைப்பின்போது இடவும்.",
        "high": "இந்த சீசனில் பாஸ்பரஸ் தவிர்க்கவும். ஜிங்க் சல்பேட் 5 கிலோ/ஏக்கர் இடவும்.",
    },
    "Potassium": {
        "good": "ஒவ்வொரு 2வது சீசனில் MOP குறைந்த அளவு இடவும்.",
        "low":  "MOP 8-10 கிலோ/ஏக்கர் இடவும். மரக்கரி கரிம மூலமாக சேர்க்கவும்.",
        "high": "இந்த சீசனில் பொட்டாசியம் தவிர்க்கவும். மெக்னீசியம் குறைபாட்டை கவனிக்கவும்.",
    },
    "Calcium": {
        "good": "கால்சியம் கிடைக்க pH 6.5-7.5 பராமரிக்கவும். ஒவ்வொரு 2-3 ஆண்டுகளுக்கு சுண்ணாம்பு இடவும்.",
        "low":  "வேளாண் சுண்ணாம்பு 200-400 கிலோ/ஏக்கர் இடவும். pH சரிபார்க்கவும்.",
        "high": "கூடுதல் சுண்ணாம்பு தவிர்க்கவும். Mg மற்றும் K அளவுகளை கவனிக்கவும்.",
    },
    "Magnesium": {
        "good": "வழக்கமான pH சரிசெய்யும்போது டோலோமைட் சுண்ணாம்பு இடவும்.",
        "low":  "டோலோமைட் 50-100 கிலோ/ஏக்கர் அல்லது கீசரைட் 10 கிலோ/ஏக்கர் இடவும்.",
        "high": "Ca மற்றும் K போட்டியை கவனிக்கவும். வடிகால் மேம்படுத்தவும்.",
    },
    "Sulphur": {
        "good": "விதைப்பின்போது SSP உரம் பயன்படுத்தி அளவை பராமரிக்கவும்.",
        "low":  "ஜிப்சம் 50 கிலோ/ஏக்கர் அல்லது தனிமக் கந்தகம் 5-10 கிலோ/ஏக்கர் இடவும்.",
        "high": "சல்பேட் கொண்ட உரங்களை குறைக்கவும். EC சரிபார்க்கவும்.",
    },
}

ALL_BANDS = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]

# ── Tamil chart font (matplotlib) ─────────────────────────────────────────────
TAMIL_FP = FontProperties(fname=TAMIL_FONT_PATH) if os.path.exists(TAMIL_FONT_PATH) else None


# ═══════════════════════════════════════════════════════
#  PIL Tamil Text Rendering — THE CORE FIX
# ═══════════════════════════════════════════════════════

PAGE_W_PX = 1240   # ~A4 width at 150 DPI
CONTENT_W  = 1100  # content area width in pixels
DPI        = 150

def _measure_text(text, font):
    tmp = Image.new('RGB', (1, 1))
    d   = ImageDraw.Draw(tmp)
    bb  = d.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]

def wrap_text(text, font, max_w):
    """Word-wrap Tamil/mixed text to fit max_w pixels."""
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
    return lines if lines else [text]

def render_text_image(text, font_size=18, color=(0,0,0), bg=(255,255,255),
                       max_w=CONTENT_W, bold=False, align='left'):
    """
    Render Tamil text to a PIL Image using FreeSerif (proper FreeType shaping).
    Returns PIL Image.
    """
    font = pil_font(font_size)
    lines = wrap_text(text, font, max_w - 10)
    _, lh = _measure_text('அ', font)
    line_h = lh + 6
    total_h = line_h * len(lines) + 10

    img  = Image.new('RGB', (max_w, max(total_h, line_h + 10)), bg)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        lw, _ = _measure_text(line, font)
        if align == 'center':
            x = (max_w - lw) // 2
        elif align == 'right':
            x = max_w - lw - 5
        else:
            x = 5
        draw.text((x, 5 + i * line_h), line, font=font, fill=color)
    return img

def pil_img_to_rl(pil_img, width_cm=None, height_cm=None):
    """Convert PIL image to ReportLab Image object via BytesIO."""
    buf = BytesIO()
    pil_img.save(buf, format='PNG')
    buf.seek(0)
    w_pt = width_cm  * cm if width_cm  else (pil_img.width  / DPI * 2.54 * cm)
    h_pt = height_cm * cm if height_cm else (pil_img.height / DPI * 2.54 * cm)
    ri = RLImage(buf, width=w_pt, height=h_pt)
    return ri

def t_heading(text, level=2, page_width_cm=17.0):
    """Render a Tamil section heading as ReportLab Image."""
    fs   = {1: 28, 2: 22, 3: 18}.get(level, 18)
    col  = (20, 100, 20)  # dark green
    pimg = render_text_image(text, font_size=fs, color=col,
                              bg=(255, 255, 255), max_w=int(page_width_cm * DPI / 2.54))
    return pil_img_to_rl(pimg, width_cm=page_width_cm,
                          height_cm=pimg.height / DPI * 2.54)

def t_para(text, font_size=16, color=(0,0,0), page_width_cm=17.0, align='left'):
    """Render a Tamil paragraph as ReportLab Image."""
    max_px = int(page_width_cm * DPI / 2.54)
    pimg   = render_text_image(text, font_size=font_size, color=color,
                                max_w=max_px, align=align)
    return pil_img_to_rl(pimg, width_cm=page_width_cm,
                          height_cm=pimg.height / DPI * 2.54)

def t_small(text, font_size=14, color=(0,0,0), page_width_cm=17.0):
    return t_para(text, font_size=font_size, color=color, page_width_cm=page_width_cm)

def t_title(text, page_width_cm=17.0):
    return t_para(text, font_size=30, color=(20,100,20),
                   page_width_cm=page_width_cm, align='center')


# ═══════════════════════════════════════════════════════
#  Tamil Table Builder (PIL-rendered cells)
# ═══════════════════════════════════════════════════════

def build_tamil_table_image(headers, rows, col_widths_px, font_size=15,
                             header_bg=(20,100,20), row_bg1=(255,255,255),
                             row_bg2=(240,250,240)):
    """
    Build a full table as a single PIL Image.
    headers: list of strings
    rows: list of lists of (text, color) tuples or plain strings
    col_widths_px: list of int pixel widths per column
    """
    font   = pil_font(font_size)
    hfont  = pil_font(font_size)
    _, ch  = _measure_text('அ', font)
    line_h = ch + 8
    pad    = 8

    total_w = sum(col_widths_px) + len(col_widths_px) + 1
    BORDER  = 1

    # --- Pre-measure all rows to get heights ---
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

    # --- Draw header ---
    x = BORDER
    draw.rectangle([0, 0, total_w - 1, header_h], fill=header_bg)
    for ci, (hdr, cw) in enumerate(zip(headers, col_widths_px)):
        draw.text((x + pad, pad), hdr, font=hfont, fill=(255, 255, 255))
        x += cw + BORDER

    # --- Draw rows ---
    y = header_h + BORDER
    for ri, (row, rh) in enumerate(zip(rows, row_heights)):
        bg = row_bg1 if ri % 2 == 0 else row_bg2
        draw.rectangle([0, y, total_w - 1, y + rh], fill=bg)
        x = BORDER
        for ci, (cell, cw) in enumerate(zip(row, col_widths_px)):
            txt    = cell[0] if isinstance(cell, tuple) else str(cell)
            tcol   = cell[1] if isinstance(cell, tuple) else (0, 0, 0)
            lns    = cell_lines(txt, cw)
            for li, ln in enumerate(lns):
                draw.text((x + pad, y + pad + li * line_h), ln, font=font, fill=tcol)
            x += cw + BORDER
        # row border
        draw.line([0, y + rh, total_w - 1, y + rh], fill=(180, 180, 180), width=1)
        y += rh + BORDER

    return img


# ═══════════════════════════════════════════════════════
#  Earth Engine helpers
# ═══════════════════════════════════════════════════════

def safe_get_info(obj, name="value"):
    if obj is None: return None
    try:
        v = obj.getInfo()
        return float(v) if v is not None else None
    except Exception as e:
        logging.warning(f"Failed {name}: {e}"); return None

def sentinel_composite(region, start, end, bands):
    ss, es = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    try:
        coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterDate(ss, es).filterBounds(region)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).select(bands))
        if coll.size().getInfo() > 0:
            return coll.median().multiply(0.0001)
        for days in range(5, 31, 5):
            sd = (start - timedelta(days=days)).strftime("%Y-%m-%d")
            ed = (end   + timedelta(days=days)).strftime("%Y-%m-%d")
            coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                    .filterDate(sd, ed).filterBounds(region)
                    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)).select(bands))
            if coll.size().getInfo() > 0:
                return coll.median().multiply(0.0001)
        return None
    except Exception as e:
        logging.error(f"sentinel_composite: {e}"); return None

def get_band_stats(comp, region, scale=10):
    try:
        s = comp.reduceRegion(reducer=ee.Reducer.mean(), geometry=region,
                              scale=scale, maxPixels=1e13).getInfo()
        return {k: (float(v) if v is not None else 0.0) for k, v in s.items()}
    except Exception as e:
        logging.error(f"get_band_stats: {e}"); return {}

def get_lst(region, start, end):
    try:
        sd = (end - relativedelta(months=1)).strftime("%Y-%m-%d")
        ed = end.strftime("%Y-%m-%d")
        coll = (ee.ImageCollection("MODIS/061/MOD11A2")
                .filterBounds(region.buffer(5000)).filterDate(sd, ed)
                .select("LST_Day_1km"))
        if coll.size().getInfo() == 0: return None
        img   = coll.median().multiply(0.02).subtract(273.15).rename("lst").clip(region.buffer(5000))
        stats = img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=1000, maxPixels=1e13).getInfo()
        v     = stats.get("lst")
        return float(v) if v is not None else None
    except Exception as e:
        logging.error(f"get_lst: {e}"); return None

def get_soil_texture(region):
    try:
        mode = SOIL_TEXTURE_IMG.clip(region.buffer(500)).reduceRegion(
            ee.Reducer.mode(), geometry=region, scale=250, maxPixels=1e13).get("b0")
        v = safe_get_info(mode, "texture")
        return int(v) if v is not None else None
    except Exception as e:
        logging.error(f"get_soil_texture: {e}"); return None

def get_ph_new(bs):
    b2,b3,b4,b5,b8,b11 = bs.get("B2",0),bs.get("B3",0),bs.get("B4",0),bs.get("B5",0),bs.get("B8",0),bs.get("B11",0)
    ndvi_re = ((b8-b5)/(b8+b5+1e-6)+(b8-b4)/(b8+b4+1e-6))/2
    ph = 6.5+1.2*ndvi_re+0.8*b11/(b8+1e-6)-0.5*b8/(b4+1e-6)+0.15*(1-(b2+b3+b4)/3)
    return max(4.0, min(9.0, ph))

def get_organic_carbon_pct(bs):
    b2,b3,b4,b5,b8,b11,b12 = bs.get("B2",0),bs.get("B3",0),bs.get("B4",0),bs.get("B5",0),bs.get("B8",0),bs.get("B11",0),bs.get("B12",0)
    ndvi_re = ((b8-b5)/(b8+b5+1e-6)+(b8-b4)/(b8+b4+1e-6))/2
    L=0.5; savi=((b8-b4)/(b8+b4+L+1e-6))*(1+L)
    evi=2.5*(b8-b4)/(b8+6*b4-7.5*b2+1+1e-6)
    oc=1.2+3.5*ndvi_re+2.2*savi-1.5*(b11+b12)/2+0.4*evi
    return max(0.1, min(5.0, oc))

def get_salinity_ec(bs):
    b2,b3,b4,b8 = bs.get("B2",0),bs.get("B3",0),bs.get("B4",0),bs.get("B8",0)
    ndvi=(b8-b4)/(b8+b4+1e-6); brightness=(b2+b3+b4)/3
    si1=(b3*b4)**0.5; si2=(b3**2+b4**2)**0.5 if (b3**2+b4**2)>0 else 0
    ec=0.5+abs((si1+si2)/2)*4+(1-max(0,min(1,ndvi)))*2+0.3*(1-brightness)
    return max(0.0, min(16.0, ec))

def estimate_cec(comp, region, intercept, slope_clay, slope_om):
    if comp is None: return None
    try:
        clay=comp.expression("(B11-B8)/(B11+B8+1e-6)",{"B11":comp.select("B11"),"B8":comp.select("B8")}).rename("clay")
        om=comp.expression("(B8-B4)/(B8+B4+1e-6)",{"B8":comp.select("B8"),"B4":comp.select("B4")}).rename("om")
        c_m=safe_get_info(clay.reduceRegion(ee.Reducer.mean(),geometry=region,scale=20,maxPixels=1e13).get("clay"))
        o_m=safe_get_info(om.reduceRegion(ee.Reducer.mean(),geometry=region,scale=20,maxPixels=1e13).get("om"))
        return (intercept+slope_clay*c_m+slope_om*o_m) if c_m and o_m else None
    except: return None

def get_ndvi(bs): b8,b4=bs.get("B8",0),bs.get("B4",0); return (b8-b4)/(b8+b4+1e-6)
def get_evi(bs):  b8,b4,b2=bs.get("B8",0),bs.get("B4",0),bs.get("B2",0); return 2.5*(b8-b4)/(b8+6*b4-7.5*b2+1+1e-6)
def get_fvc(bs):  return max(0,min(1,((get_ndvi(bs)-0.2)/(0.8-0.2))**2))
def get_ndwi(bs): b3,b8=bs.get("B3",0),bs.get("B8",0); return (b3-b8)/(b3+b8+1e-6)

def get_npk_kgha(bs):
    b2,b3,b4=bs.get("B2",0),bs.get("B3",0),bs.get("B4",0)
    b5,b6,b7=bs.get("B5",0),bs.get("B6",0),bs.get("B7",0)
    b8,b8a=bs.get("B8",0),bs.get("B8A",0)
    b11,b12=bs.get("B11",0),bs.get("B12",0)
    ndvi=((b8-b4)/(b8+b4+1e-6)); evi=2.5*(b8-b4)/(b8+6*b4-7.5*b2+1+1e-6)
    brightness=(b2+b3+b4)/3; ndre=(b8a-b5)/(b8a+b5+1e-6)
    ci_re=(b7/(b5+1e-6))-1; mcari=((b5-b4)-0.2*(b5-b3))*(b5/(b4+1e-6))
    N=max(50,min(600, 280+300*ndre+150*evi+20*(ci_re/5)-80*brightness+30*mcari))
    si1=(b3*b4)**0.5; si2=(b3**2+b4**2)**0.5 if (b3**2+b4**2)>0 else 0
    P=max(2,min(60, 11+15*(1-brightness)+6*ndvi+4*abs((si1+si2)/2)+2*b3))
    K=max(40,min(600, 150+200*b11/(b5+b6+1e-6)+80*(b11-b12)/(b11+b12+1e-6)+60*ndvi))
    return float(N),float(P),float(K)

def get_calcium_kgha(bs):
    b2,b3,b4,b8,b11,b12=bs.get("B2",0),bs.get("B3",0),bs.get("B4",0),bs.get("B8",0),bs.get("B11",0),bs.get("B12",0)
    Ca=550+250*(b11+b12)/(b4+b3+1e-6)+150*(b2+b3+b4)/3-100*(b8-b4)/(b8+b4+1e-6)-80*(b11-b8)/(b11+b8+1e-6)
    return max(100,min(1200,float(Ca)))

def get_magnesium_kgha(bs):
    b4,b5,b7,b8,b8a,b11,b12=bs.get("B4",0),bs.get("B5",0),bs.get("B7",0),bs.get("B8",0),bs.get("B8A",0),bs.get("B11",0),bs.get("B12",0)
    Mg=110+60*(b8a-b5)/(b8a+b5+1e-6)+40*((b7/(b5+1e-6))-1)+30*(b11-b12)/(b11+b12+1e-6)+20*(b8-b4)/(b8+b4+1e-6)
    return max(10,min(400,float(Mg)))

def get_sulphur_kgha(bs):
    b3,b4,b5,b8,b11,b12=bs.get("B3",0),bs.get("B4",0),bs.get("B5",0),bs.get("B8",0),bs.get("B11",0),bs.get("B12",0)
    si1=(b3*b4)**0.5; si2=(b3**2+b4**2)**0.5 if (b3**2+b4**2)>0 else 0
    S=20+15*b11/(b3+b4+1e-6)+10*abs((si1+si2)/2)+5*(b5/(b4+1e-6)-1)-8*b12/(b11+1e-6)+5*(b8-b4)/(b8+b4+1e-6)
    return max(2,min(80,float(S)))


# ═══════════════════════════════════════════════════════
#  Status & Scoring
# ═══════════════════════════════════════════════════════

def get_param_status(param, value):
    if value is None: return "na"
    if param == "Soil Texture": return "good" if value == IDEAL_RANGES[param] else "low"
    mn, mx = IDEAL_RANGES.get(param, (None, None))
    if mn is None and mx is not None: return "good" if value <= mx else "high"
    if mx is None and mn is not None: return "good" if value >= mn else "low"
    if mn is not None and mx is not None:
        if value < mn: return "low"
        if value > mx: return "high"
        return "good"
    return "good"

def calculate_soil_health_score(params):
    good  = sum(1 for p,v in params.items() if get_param_status(p,v)=="good")
    total = len([v for v in params.values() if v is not None])
    pct   = (good/total)*100 if total else 0
    rating = ("மிகச்சிறந்தது" if pct>=80 else "நல்லது" if pct>=60 else "சராசரி" if pct>=40 else "மோசமானது")
    return pct, rating, good, total

STATUS_COLOR_PIL = {
    "good": (20,150,20), "low": (200,100,0), "high": (200,0,0), "na": (120,120,120)
}

def get_suggestion(param, value):
    if value is None or param not in SUGGESTIONS: return "—"
    s = SUGGESTIONS[param]
    st = get_param_status(param, value)
    if st=="good": return "சரி: " + s.get("good","தற்போதைய நடைமுறையை தொடரவும்.")
    if st=="low":  return "சரிசெய்: " + s.get("low", s.get("high","வேளாண் நிபுணரை அணுகவும்."))
    if st=="high": return "சரிசெய்: " + s.get("high",s.get("low","வேளாண் நிபுணரை அணுகவும்."))
    return "—"

def generate_interpretation(param, value):
    if value is None: return "தகவல் இல்லை."
    if param=="Soil Texture": return TEXTURE_CLASSES.get(value,"தெரியாத மண் அமைப்பு.")
    if param=="NDWI":
        if value>=-0.10: return "நல்ல ஈரப்பதம்; நீர்ப்பாசனம் தேவையில்லை."
        if value>=-0.30: return "லேசான அழுத்தம்; 2 நாட்களில் நீர்ப்பாசனம் செய்யவும்."
        if value>=-0.40: return "மிதமான அழுத்தம்; நாளை நீர்ப்பாசனம் செய்யவும்."
        return "கடுமையான அழுத்தம்; உடனே நீர்ப்பாசனம் செய்யவும்."
    if param=="Phosphorus": return "குறைந்த ஒளியலை நம்பகத்தன்மை. வழிகாட்டியாக மட்டும்."
    if param=="Sulphur":    return "குறைந்த ஒளியலை நம்பகத்தன்மை. மதிப்பீடாக மட்டும்."
    st = get_param_status(param, value)
    ideal = IDEAL_DISPLAY.get(param,"N/A")
    if st=="good": return f"சிறந்த அளவு ({ideal})."
    if st=="low":  mn,_=IDEAL_RANGES.get(param,(None,None)); return f"குறைவான அளவு ({mn} கீழ்)."
    if st=="high": _,mx=IDEAL_RANGES.get(param,(None,None)); return f"அதிகமான அளவு ({mx} மேல்)."
    return "விளக்கம் இல்லை."


# ═══════════════════════════════════════════════════════
#  Charts (matplotlib with Tamil labels via TAMIL_FP)
# ═══════════════════════════════════════════════════════

def _bar_color(param, val):
    s = get_param_status(param, val)
    return {
        "good": (0.08,0.59,0.08), "low": (0.85,0.45,0.0),
        "high": (0.80,0.08,0.08), "na": (0.5,0.5,0.5)
    }.get(s,(0.5,0.5,0.5))

def _set_tamil_ticks(ax, labels, fp):
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontproperties=fp, fontsize=8)

def make_nutrient_chart(n,p,k,ca,mg,s):
    fp = TAMIL_FP
    pkeys = ["Nitrogen","Phosphorus","Potassium","Calcium","Magnesium","Sulphur"]
    vals  = [n or 0, p or 0, k or 0, ca or 0, mg or 0, s or 0]
    tlbls = ["நைட்ரஜன்\n(kg/ha)","பாஸ்பரஸ்\nP2O5 (kg/ha)","பொட்டாசியம்\nK2O (kg/ha)",
             "கால்சியம்\n(kg/ha)","மெக்னீசியம்\n(kg/ha)","கந்தகம்\n(kg/ha)"]
    bcs = [_bar_color(pk,v) for pk,v in zip(pkeys,vals)]
    fig,ax = plt.subplots(figsize=(11,4.5))
    bars = ax.bar(range(len(tlbls)), vals, color=bcs, alpha=0.85)
    ymax = max(vals)*1.4 if any(vals) else 400
    ax.set_ylim(0,ymax)
    if fp:
        ax.set_title("மண் ஊட்டச்சத்து அளவுகள் (கிலோ/ஹெக்டேர்) - ICAR தரநிலை", fontproperties=fp, fontsize=11)
        ax.set_ylabel("கிலோ / ஹெக்டேர்", fontproperties=fp, fontsize=9)
        _set_tamil_ticks(ax, tlbls, fp)
    tstatus = {pk:TAMIL_STATUS.get(get_param_status(pk,v),"N/A") for pk,v in zip(pkeys,vals)}
    for bar,val,pk in zip(bars,vals,pkeys):
        lbl = tstatus[pk]
        if fp:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+ymax*0.02,
                    f"{val:.1f}\n{lbl}", ha='center', va='bottom', fontproperties=fp, fontsize=7)
    plt.tight_layout()
    path = "nutrient_chart.png"; plt.savefig(path,dpi=120,bbox_inches='tight'); plt.close()
    return path

def make_vegetation_chart(ndvi, ndwi):
    fp = TAMIL_FP
    tlbls = ["தாவர குறியீடு\n(NDVI)","நீர் குறியீடு\n(NDWI)"]
    vals  = [ndvi or 0, ndwi or 0]
    bcs   = [_bar_color(p,v) for p,v in zip(["NDVI","NDWI"],vals)]
    fig,ax = plt.subplots(figsize=(5,4.5))
    bars = ax.bar(range(2), vals, color=bcs, alpha=0.85)
    ax.axhline(0,color='black',linewidth=0.5,linestyle='--'); ax.set_ylim(-1,1)
    if fp:
        ax.set_title("தாவர மற்றும் நீர் குறியீடுகள்", fontproperties=fp, fontsize=11)
        ax.set_ylabel("குறியீட்டு மதிப்பு", fontproperties=fp, fontsize=9)
        _set_tamil_ticks(ax, tlbls, fp)
    for i,(bar,val) in enumerate(zip(bars,vals)):
        lbl = TAMIL_STATUS.get(get_param_status(["NDVI","NDWI"][i],val),"N/A")
        yp = bar.get_height()+0.04 if val>=0 else bar.get_height()-0.12
        if fp:
            ax.text(bar.get_x()+bar.get_width()/2, yp, f"{val:.2f}\n{lbl}",
                    ha='center',va='bottom',fontproperties=fp,fontsize=9)
    plt.tight_layout()
    path = "vegetation_chart.png"; plt.savefig(path,dpi=120,bbox_inches='tight'); plt.close()
    return path

def make_soil_properties_chart(ph,sal,oc,cec,lst):
    fp = TAMIL_FP
    pkeys = ["pH","Salinity","Organic Carbon","CEC","LST"]
    tlbls = ["pH\nசார்பு அளவு","EC மின்கடத்தல்\n(mS/cm)","கரிம கார்பன்\n(%)","CEC\n(cmol/kg)","நில வெப்பம்\n(C)"]
    vals  = [ph or 0, sal or 0, oc or 0, cec or 0, lst or 0]
    bcs   = [_bar_color(pk,v) for pk,v in zip(pkeys,vals)]
    fig,ax = plt.subplots(figsize=(9,4.5))
    bars = ax.bar(range(len(tlbls)), vals, color=bcs, alpha=0.85)
    ymax = max(vals)*1.4 if any(vals) else 50; ax.set_ylim(0,ymax)
    if fp:
        ax.set_title("மண் பண்புகள் (ICAR தரநிலை)", fontproperties=fp, fontsize=11)
        ax.set_ylabel("மதிப்பு", fontproperties=fp, fontsize=9)
        _set_tamil_ticks(ax, tlbls, fp)
    for bar,val,pk in zip(bars,vals,pkeys):
        lbl = TAMIL_STATUS.get(get_param_status(pk,val),"N/A")
        if fp:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+ymax*0.02,
                    f"{val:.2f}\n{lbl}", ha='center',va='bottom',fontproperties=fp,fontsize=8)
    plt.tight_layout()
    path = "properties_chart.png"; plt.savefig(path,dpi=120,bbox_inches='tight'); plt.close()
    return path


# ═══════════════════════════════════════════════════════
#  Groq AI
# ═══════════════════════════════════════════════════════

def call_groq(prompt):
    try:
        client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        resp   = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"user","content":prompt}],
            max_tokens=900, temperature=0.35)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Groq: {e}"); return None


# ═══════════════════════════════════════════════════════
#  PDF REPORT — ALL TAMIL TEXT via PIL images
# ═══════════════════════════════════════════════════════

def generate_report(params, location, date_range):
    try:
        REPORT_PARAMS = {k:v for k,v in params.items() if k not in ("EVI","FVC")}
        score, rating, good_c, total_c = calculate_soil_health_score(REPORT_PARAMS)

        # Charts
        nc = make_nutrient_chart(params["Nitrogen"],params["Phosphorus"],params["Potassium"],
                                  params["Calcium"],params["Magnesium"],params["Sulphur"])
        vc = make_vegetation_chart(params["NDVI"], params["NDWI"])
        pc = make_soil_properties_chart(params["pH"],params["Salinity"],params["Organic Carbon"],
                                         params["CEC"],params["LST"])

        def fv(param, v):
            if v is None: return "N/A"
            return f"{v:.2f}{UNIT_MAP.get(param,'')}"

        tex_d = TEXTURE_CLASSES.get(params["Soil Texture"],"N/A") if params["Soil Texture"] else "N/A"

        exec_prompt = f"""நீங்கள் ஒரு இந்திய வேளாண் நிபுணர். கீழே உள்ள மண் தரவுகளை பார்த்து, ஒரு விவசாயிக்கு 4-5 புள்ளிகளில் தமிழில் மட்டுமே சுருக்கம் எழுதவும். எளிய மொழியில், Bold இல்லை, markdown இல்லை. ஒவ்வொரு புள்ளியும் . (புள்ளி) உடன் தொடங்கவும்.

மண் ஆரோக்கிய மதிப்பெண்: {score:.1f}% ({rating})
pH={fv('pH',params['pH'])}, EC={fv('Salinity',params['Salinity'])}, கரிம கார்பன்={fv('Organic Carbon',params['Organic Carbon'])}, CEC={fv('CEC',params['CEC'])}
மண் அமைப்பு={tex_d}
நைட்ரஜன்={fv('Nitrogen',params['Nitrogen'])}, பாஸ்பரஸ்={fv('Phosphorus',params['Phosphorus'])}, பொட்டாசியம்={fv('Potassium',params['Potassium'])}
கால்சியம்={fv('Calcium',params['Calcium'])}, மெக்னீசியம்={fv('Magnesium',params['Magnesium'])}, கந்தகம்={fv('Sulphur',params['Sulphur'])}"""

        rec_prompt = f"""நீங்கள் ஒரு இந்திய வேளாண் நிபுணர். கீழே உள்ள மண் தரவுகளை பார்த்து, 4-5 நடைமுறை சிபாரிசுகளை தமிழில் மட்டுமே கொடுக்கவும். எளிய விவசாயி மொழியில். Bold இல்லை, markdown இல்லை. ஒவ்வொரு புள்ளியும் . (புள்ளி) உடன் தொடங்கவும்.

pH={fv('pH',params['pH'])}, EC={fv('Salinity',params['Salinity'])}, மண்={tex_d}
நைட்ரஜன்={fv('Nitrogen',params['Nitrogen'])}, பாஸ்பரஸ்={fv('Phosphorus',params['Phosphorus'])} (மதிப்பீடு), பொட்டாசியம்={fv('Potassium',params['Potassium'])}
கால்சியம்={fv('Calcium',params['Calcium'])}, மெக்னீசியம்={fv('Magnesium',params['Magnesium'])}, கந்தகம்={fv('Sulphur',params['Sulphur'])} (மதிப்பீடு)
NDVI={fv('NDVI',params['NDVI'])}, NDWI={fv('NDWI',params['NDWI'])}
இந்திய காலநிலைக்கு ஏற்ற பயிர்களை பரிந்துரைக்கவும்."""

        exec_summary = call_groq(exec_prompt) or ". சுருக்கம் கிடைக்கவில்லை."
        recs         = call_groq(rec_prompt)  or ". சிபாரிசுகள் கிடைக்கவில்லை."

        # ── Build PDF ─────────────────────────────────────────────────────
        pdf_buf = BytesIO()
        doc = SimpleDocTemplate(pdf_buf, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=3*cm, bottomMargin=2*cm)
        PW_CM = 17.0  # usable page width in cm
        elems = []

        # ── COVER PAGE ────────────────────────────────────────────────────
        elems.append(Spacer(1, 1.5*cm))
        if os.path.exists(LOGO_PATH):
            li = RLImage(LOGO_PATH, width=9*cm, height=9*cm)
            li.hAlign = 'CENTER'; elems.append(li)
        elems.append(Spacer(1, 0.5*cm))
        elems.append(t_title("FarmMatrix மண் ஆரோக்கிய அறிக்கை", PW_CM))
        elems.append(Spacer(1, 0.3*cm))
        elems.append(t_para(f"இடம்: {location}", 16, (60,60,60), PW_CM, 'center'))
        elems.append(t_para(f"தேதி வரம்பு: {date_range}", 16, (60,60,60), PW_CM, 'center'))
        elems.append(t_para(f"உருவாக்கப்பட்ட தேதி: {datetime.now():%d %B %Y, %H:%M}", 14, (100,100,100), PW_CM, 'center'))
        elems.append(PageBreak())

        # ── SEC 1: EXECUTIVE SUMMARY ──────────────────────────────────────
        elems.append(t_heading("1. நிர்வாக சுருக்கம்", 2, PW_CM))
        elems.append(Spacer(1, 0.2*cm))
        for line in exec_summary.split('\n'):
            line = line.strip()
            if line:
                elems.append(t_para(line, 16, (30,30,30), PW_CM))
                elems.append(Spacer(1, 0.1*cm))
        elems.append(Spacer(1, 0.3*cm))

        # ── SEC 2: HEALTH SCORE ───────────────────────────────────────────
        elems.append(t_heading("2. மண் ஆரோக்கிய மதிப்பீடு", 2, PW_CM))
        elems.append(Spacer(1, 0.2*cm))

        score_color = (20,150,20) if score>=60 else ((200,150,0) if score>=40 else (200,50,50))
        score_tbl = build_tamil_table_image(
            headers=["மொத்த மதிப்பெண்", "மதிப்பீடு", "சிறந்த அளவுருக்கள்"],
            rows=[[
                (f"{score:.1f}%", score_color),
                (rating, score_color),
                (f"{good_c} / {total_c}", (30,30,30))
            ]],
            col_widths_px=[260, 260, 260],
            font_size=17
        )
        ri = pil_img_to_rl(score_tbl, width_cm=PW_CM)
        ri.hAlign = 'LEFT'; elems.append(ri)
        elems.append(Spacer(1, 0.3*cm))
        elems.append(PageBreak())

        # ── SEC 3: PARAMETER TABLE ────────────────────────────────────────
        elems.append(t_heading("3. மண் அளவுருக்கள் பகுப்பாய்வு (ICAR தரநிலை)", 2, PW_CM))
        elems.append(Spacer(1, 0.2*cm))

        headers3 = ["அளவுரு", "மதிப்பு", "ICAR சிறந்த வரம்பு", "நிலை", "விளக்கம்"]
        rows3 = []
        for param, value in REPORT_PARAMS.items():
            unit = UNIT_MAP.get(param,"")
            val_txt = (TEXTURE_CLASSES.get(value,"N/A") if param=="Soil Texture" and value
                       else (f"{value:.2f}{unit}" if value is not None else "N/A"))
            st     = get_param_status(param, value)
            st_lbl = TAMIL_STATUS.get(st,"N/A")
            st_col = STATUS_COLOR_PIL.get(st, (0,0,0))
            interp = generate_interpretation(param, value)
            rows3.append([
                (TAMIL_PARAM_NAMES.get(param, param), (30,30,30)),
                (val_txt, (30,30,30)),
                (IDEAL_DISPLAY.get(param,"N/A"), (30,30,30)),
                (st_lbl, st_col),
                (interp, (30,30,30))
            ])
        tbl3_img = build_tamil_table_image(
            headers=headers3, rows=rows3,
            col_widths_px=[200, 130, 160, 110, 300],
            font_size=14
        )
        ri3 = pil_img_to_rl(tbl3_img, width_cm=PW_CM)
        ri3.hAlign = 'LEFT'; elems.append(ri3)
        elems.append(PageBreak())

        # ── SEC 4: CHARTS ─────────────────────────────────────────────────
        elems.append(t_heading("4. காட்சிப்படுத்தல்கள்", 2, PW_CM))
        elems.append(Spacer(1, 0.2*cm))
        for lbl, cpath in [
            ("N, P2O5, K2O, Ca, Mg, S ஊட்டச்சத்து அளவுகள் (கிலோ/ஹெக்டேர்):", nc),
            ("தாவர மற்றும் நீர் குறியீடுகள் (NDVI, NDWI):", vc),
            ("மண் பண்புகள்:", pc),
        ]:
            elems.append(t_small(lbl, 15, (30,30,30), PW_CM))
            if cpath and os.path.exists(cpath):
                ci = RLImage(cpath, width=14*cm, height=7*cm)
                ci.hAlign = 'LEFT'; elems.append(ci)
            elems.append(Spacer(1, 0.3*cm))
        elems.append(PageBreak())

        # ── SEC 5: RECOMMENDATIONS ────────────────────────────────────────
        elems.append(t_heading("5. பயிர் சிபாரிசுகள் மற்றும் சிகிச்சைகள்", 2, PW_CM))
        elems.append(Spacer(1, 0.2*cm))
        for line in recs.split('\n'):
            line = line.strip()
            if line:
                elems.append(t_para(line, 16, (30,30,30), PW_CM))
                elems.append(Spacer(1, 0.1*cm))
        elems.append(Spacer(1, 0.3*cm))
        elems.append(PageBreak())

        # ── SEC 6: PARAMETER-WISE SUGGESTIONS ────────────────────────────
        elems.append(t_heading("6. அளவுரு வாரியான பரிந்துரைகள்", 2, PW_CM))
        elems.append(Spacer(1, 0.1*cm))
        elems.append(t_small("ஒவ்வொரு அளவுருவிற்கும்: நல்ல அளவை பராமரிக்க அல்லது சிக்கல்களை சரிசெய்ய என்ன செய்ய வேண்டும்.", 13, (80,80,80), PW_CM))
        elems.append(Spacer(1, 0.2*cm))

        SUG_PARAMS = ["pH","Salinity","Organic Carbon","CEC","Nitrogen","Phosphorus",
                      "Potassium","Calcium","Magnesium","Sulphur","NDVI","NDWI","LST"]
        headers6 = ["அளவுரு", "நிலை", "தேவையான நடவடிக்கை"]
        rows6 = []
        for param in SUG_PARAMS:
            value = params.get(param)
            st    = get_param_status(param, value)
            st_lbl = TAMIL_STATUS.get(st,"N/A")
            st_col = STATUS_COLOR_PIL.get(st,(0,0,0))
            sug_txt = get_suggestion(param, value)
            rows6.append([
                (TAMIL_PARAM_NAMES.get(param,param), (30,30,30)),
                (st_lbl, st_col),
                (sug_txt, (30,30,30))
            ])
        tbl6_img = build_tamil_table_image(
            headers=headers6, rows=rows6,
            col_widths_px=[200, 110, 590],
            font_size=14
        )
        ri6 = pil_img_to_rl(tbl6_img, width_cm=PW_CM)
        ri6.hAlign = 'LEFT'; elems.append(ri6)
        elems.append(Spacer(1, 0.4*cm))
        elems.append(t_small(
            "குறிப்பு: பாஸ்பரஸ் (P) மற்றும் கந்தகம் (S) ஆகியவற்றிற்கு ஒளியலை நம்பகத்தன்மை குறைவு. "
            "மதிப்பீடாக மட்டுமே கருதவும். களவாய்வு மாதிரி எடுப்பு பரிந்துரைக்கப்படுகிறது.",
            13, (120,60,0), PW_CM))

        # ── Header/Footer ──────────────────────────────────────────────────
        def add_header(canv, doc):
            canv.saveState()
            if os.path.exists(LOGO_PATH):
                canv.drawImage(LOGO_PATH, 2*cm, A4[1]-2.8*cm, width=1.8*cm, height=1.8*cm)
            canv.setFont("Helvetica-Bold", 11)
            canv.drawString(4.5*cm, A4[1]-2.2*cm, "FarmMatrix Soil Health Report (Tamil)")
            canv.setFont("Helvetica", 8)
            canv.drawRightString(A4[0]-2*cm, A4[1]-2.2*cm, f"Generated: {datetime.now():%d %b %Y, %H:%M}")
            canv.setStrokeColor(colors.darkgreen); canv.setLineWidth(1)
            canv.line(2*cm, A4[1]-3*cm, A4[0]-2*cm, A4[1]-3*cm)
            canv.restoreState()

        def add_footer(canv, doc):
            canv.saveState()
            canv.setStrokeColor(colors.darkgreen)
            canv.line(2*cm, 1.5*cm, A4[0]-2*cm, 1.5*cm)
            canv.setFont("Helvetica", 8)
            canv.drawCentredString(A4[0]/2, cm, f"Page {doc.page}  |  FarmMatrix  |  ICAR Standard")
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
#  Streamlit UI
# ═══════════════════════════════════════════════════════
st.set_page_config(layout='wide', page_title="FarmMatrix மண் ஆரோக்கிய டாஷ்போர்டு")
st.title("🌾 FarmMatrix மண் ஆரோக்கிய டாஷ்போர்டு")
st.markdown("செயற்கைக்கோள் தரவு அடிப்படையிலான மண் பகுப்பாய்வு — ICAR தரநிலை கிலோ/ஹெக்டேர் அலகுகளில்.")

# Sidebar
st.sidebar.header("📍 இடம் தேர்வு")
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]
lat = st.sidebar.number_input("அட்சாம்சம்",  value=st.session_state.user_location[0], format="%.6f")
lon = st.sidebar.number_input("தீர்க்காம்சம்", value=st.session_state.user_location[1], format="%.6f")
st.session_state.user_location = [lat, lon]

st.sidebar.header("CEC மாதிரி குணகங்கள்")
cec_intercept  = st.sidebar.number_input("Intercept",          value=5.0,  step=0.1)
cec_slope_clay = st.sidebar.number_input("Slope (Clay Index)", value=20.0, step=0.1)
cec_slope_om   = st.sidebar.number_input("Slope (OM Index)",   value=15.0, step=0.1)

today      = date.today()
start_date = st.sidebar.date_input("தொடக்க தேதி", value=today-timedelta(days=16))
end_date   = st.sidebar.date_input("முடிவு தேதி",   value=today)
if start_date > end_date:
    st.sidebar.error("தொடக்க தேதி முடிவு தேதிக்கு முன்பாக இருக்க வேண்டும்.")
    st.stop()

# Map
m = folium.Map(location=[lat, lon], zoom_start=15)
Draw(export=True).add_to(m)
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google").add_to(m)
folium.Marker([lat, lon], popup="மையம்").add_to(m)
map_data = st_folium(m, width=700, height=500)

region = None
if map_data and "last_active_drawing" in map_data:
    try:
        sel = map_data["last_active_drawing"]
        if sel and "geometry" in sel and "coordinates" in sel["geometry"]:
            region = ee.Geometry.Polygon(sel["geometry"]["coordinates"])
        else:
            st.error("தவறான பகுதி. சரியான பலகோணம் வரையவும்.")
    except Exception as e:
        st.error(f"பகுதி உருவாக்கத்தில் பிழை: {e}")

if region:
    st.subheader(f"பகுப்பாய்வு: {start_date} முதல் {end_date} வரை")
    pb = st.progress(0); sm = st.empty()

    sm.text("Sentinel-2 படங்களை பெறுகிறோம்...")
    comp = sentinel_composite(region, start_date, end_date, ALL_BANDS); pb.progress(20)
    sm.text("மண் அமைப்பு வரைபடம் படிக்கிறோம்...")
    texc = get_soil_texture(region); pb.progress(35)
    sm.text("MODIS நில வெப்பநிலை பெறுகிறோம்...")
    lst  = get_lst(region, start_date, end_date); pb.progress(50)

    if comp is None:
        st.warning("Sentinel-2 தரவு கிடைக்கவில்லை. தேதி வரம்பை விரிவுபடுத்தவும்.")
        ph=sal=oc=cec=ndwi=ndvi=evi=fvc=n_val=p_val=k_val=ca_val=mg_val=s_val=None
    else:
        sm.text("மண் அளவுருக்களை கணக்கிடுகிறோம்...")
        bs = get_band_stats(comp, region)
        ph   = get_ph_new(bs); sal  = get_salinity_ec(bs); oc  = get_organic_carbon_pct(bs)
        cec  = estimate_cec(comp, region, cec_intercept, cec_slope_clay, cec_slope_om)
        ndwi = get_ndwi(bs); ndvi = get_ndvi(bs); evi = get_evi(bs); fvc = get_fvc(bs)
        n_val,p_val,k_val = get_npk_kgha(bs)
        ca_val = get_calcium_kgha(bs); mg_val = get_magnesium_kgha(bs); s_val = get_sulphur_kgha(bs)
        pb.progress(100); sm.text("பகுப்பாய்வு முடிந்தது! ✅")

    params = {
        "pH":ph,"Salinity":sal,"Organic Carbon":oc,"CEC":cec,"Soil Texture":texc,
        "LST":lst,"NDWI":ndwi,"NDVI":ndvi,"EVI":evi,"FVC":fvc,
        "Nitrogen":n_val,"Phosphorus":p_val,"Potassium":k_val,
        "Calcium":ca_val,"Magnesium":mg_val,"Sulphur":s_val,
    }

    st.markdown("### 🧪 மண் அளவுருக்கள்")
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.metric("pH அமிலத்தன்மை",      f"{ph:.2f}"  if ph  else "N/A")
        st.metric("உப்புத்தன்மை (mS/cm)", f"{sal:.2f}" if sal else "N/A")
        st.metric("கரிம கார்பன் (%)",     f"{oc:.2f}"  if oc  else "N/A")
        st.metric("CEC (cmol/kg)",         f"{cec:.2f}" if cec else "N/A")
    with c2:
        st.metric("NDVI தாவர குறியீடு",  f"{ndvi:.3f}" if ndvi else "N/A")
        st.metric("EVI மேம்படுத்தப்பட்ட", f"{evi:.3f}"  if evi  else "N/A")
        st.metric("FVC மூடுதல் குறியீடு", f"{fvc:.3f}"  if fvc  else "N/A")
        st.metric("NDWI நீர் குறியீடு",   f"{ndwi:.3f}" if ndwi else "N/A")
    with c3:
        st.metric("நைட்ரஜன் N (kg/ha)",      f"{n_val:.1f}" if n_val else "N/A")
        st.metric("பாஸ்பரஸ் P2O5 (kg/ha)",  f"{p_val:.1f}" if p_val else "N/A")
        st.metric("பொட்டாசியம் K2O (kg/ha)", f"{k_val:.1f}" if k_val else "N/A")
        st.metric("நில வெப்பம் LST (C)",     f"{lst:.1f}"   if lst   else "N/A")
    with c4:
        st.metric("கால்சியம் Ca (kg/ha)",   f"{ca_val:.1f}" if ca_val else "N/A")
        st.metric("மெக்னீசியம் Mg (kg/ha)", f"{mg_val:.1f}" if mg_val else "N/A")
        st.metric("கந்தகம் S (kg/ha)",       f"{s_val:.1f}"  if s_val  else "N/A")

    score, rating, _, _ = calculate_soil_health_score(params)
    icon = "🟢" if "சிறந்த" in rating or "நல்ல" in rating else ("🟡" if "சராசரி" in rating else "🔴")
    st.info(f"{icon} மண் ஆரோக்கிய மதிப்பெண்: {score:.1f}% — {rating}  (ICAR தரநிலை)")

    st.markdown("### 💡 விரைவு பரிந்துரைகள்")
    sug_rows = []
    for p in ["pH","Salinity","Organic Carbon","Nitrogen","Phosphorus","Potassium","Calcium","Magnesium","Sulphur"]:
        v  = params.get(p)
        st2= get_param_status(p,v)
        sug_rows.append({
            "அளவுரு":  TAMIL_PARAM_NAMES.get(p,p),
            "மதிப்பு": f"{v:.2f}{UNIT_MAP.get(p,'')}" if v is not None else "N/A",
            "நிலை":    TAMIL_STATUS.get(st2,"N/A"),
            "பரிந்துரை": get_suggestion(p,v).replace("சரி: ","").replace("சரிசெய்: ",""),
        })
    st.dataframe(pd.DataFrame(sug_rows), use_container_width=True, hide_index=True)

    if st.button("📄 முழு PDF அறிக்கை உருவாக்கு (தமிழ்)"):
        with st.spinner("Groq AI மூலம் தமிழ் அறிக்கை உருவாக்குகிறோம்... (சில நிமிடங்கள் ஆகலாம்)"):
            loc_str  = f"அட்சாம்சம்: {lat:.6f}, தீர்க்காம்சம்: {lon:.6f}"
            date_str = f"{start_date} முதல் {end_date} வரை"
            pdf_data = generate_report(params, loc_str, date_str)
            if pdf_data:
                st.success("✅ தமிழ் அறிக்கை தயார்!")
                st.download_button(
                    label="📥 PDF அறிக்கை பதிவிறக்கம் செய்யவும்",
                    data=pdf_data,
                    file_name=f"maN_aarokkiya_arikkay_{date.today()}.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("அறிக்கை உருவாக்கம் தோல்வியடைந்தது. பதிவுகளை சரிபார்க்கவும்.")
else:
    st.info("🗺️ உங்கள் வயல் அல்லது பகுதியை தேர்வு செய்ய மேலே உள்ள வரைபடத்தில் ஒரு பலகோணம் வரையவும்.")