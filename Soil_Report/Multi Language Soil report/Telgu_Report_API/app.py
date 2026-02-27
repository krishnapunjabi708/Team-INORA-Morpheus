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
from matplotlib.font_manager import FontProperties
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Spacer, PageBreak,
    Image as RLImage
)
from reportlab.pdfgen import canvas
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
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL       = "llama-3.3-70b-versatile"
LOGO_PATH        = os.path.abspath("LOGO.jpeg")
TELUGU_FONT_PATH = os.path.abspath("unifont.otf")

# Pre-load PIL fonts
_PIL_FONTS = {}
def pil_font(size):
    if size not in _PIL_FONTS:
        try:
            _PIL_FONTS[size] = ImageFont.truetype(TELUGU_FONT_PATH, size)
        except Exception:
            _PIL_FONTS[size] = ImageFont.load_default()
    return _PIL_FONTS[size]

# Matplotlib font
TELUGU_FP = FontProperties(fname=TELUGU_FONT_PATH) if os.path.exists(TELUGU_FONT_PATH) else None

# ─────────────────────────────────────────────
#  FastAPI App
# ─────────────────────────────────────────────
app = FastAPI(
    title="FarmMatrix Telugu Soil Health API",
    description="Satellite-based soil analysis — ICAR-aligned Telugu PDF report",
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
def initialize_ee():
    try:
        credentials_base64 = os.getenv("GEE_SERVICE_ACCOUNT_KEY")
        if not credentials_base64:
            raise ValueError("GEE_SERVICE_ACCOUNT_KEY env variable is missing.")
        credentials_json_str = base64.b64decode(credentials_base64).decode("utf-8")
        credentials_dict = json.loads(credentials_json_str)
        from ee import ServiceAccountCredentials
        credentials = ServiceAccountCredentials(
            credentials_dict['client_email'], key_data=credentials_json_str
        )
        ee.Initialize(credentials)
        logger.info("GEE initialized successfully.")
    except Exception as e:
        logger.error(f"GEE initialization failed: {e}")
        raise

initialize_ee()

# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────
SOIL_TEXTURE_IMG = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0')

TEXTURE_CLASSES = {
    1:  "బంకమట్టి (Clay)",
    2:  "పూడిక బంకమట్టి (Silty Clay)",
    3:  "ఇసుక బంకమట్టి (Sandy Clay)",
    4:  "బంకమట్టి మిశ్రమం (Clay Loam)",
    5:  "పూడిక బంకమట్టి మిశ్రమం (Silty Clay Loam)",
    6:  "ఇసుక బంకమట్టి మిశ్రమం (Sandy Clay Loam)",
    7:  "మిశ్రమ నేల (Loam)",
    8:  "పూడిక మిశ్రమ నేల (Silty Loam)",
    9:  "ఇసుక మిశ్రమ నేల (Sandy Loam)",
    10: "పూడిక (Silt)",
    11: "ఇసుక మిశ్రమం (Loamy Sand)",
    12: "ఇసుక (Sand)",
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
    "Soil Texture":   "మిశ్రమ నేల (Loam)",
    "LST":            "15-35 C",
    "NDWI":           "-0.3 to 0.2",
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

TELUGU_PARAM_NAMES = {
    "pH":             "pH ఆమ్లత్వం",
    "Salinity":       "లవణీయత (EC)",
    "Organic Carbon": "సేంద్రీయ కార్బన్",
    "CEC":            "కాటయాన్ మార్పిడి సామర్థ్యం",
    "Soil Texture":   "నేల నిర్మాణం",
    "LST":            "భూ ఉష్ణోగ్రత",
    "NDVI":           "వృక్ష సూచిక (NDVI)",
    "EVI":            "మెరుగైన వృక్ష సూచిక (EVI)",
    "FVC":            "వృక్ష ఆచ్ఛాదన సూచిక (FVC)",
    "NDWI":           "నీటి సూచిక (NDWI)",
    "Nitrogen":       "నైట్రోజన్ (N)",
    "Phosphorus":     "భాస్వరం (P)",
    "Potassium":      "పొటాషియం (K)",
    "Calcium":        "కాల్షియం (Ca)",
    "Magnesium":      "మెగ్నీషియం (Mg)",
    "Sulphur":        "గంధకం (S)",
}

TELUGU_STATUS = {
    "good": "మంచిది",
    "low":  "తక్కువ",
    "high": "ఎక్కువ",
    "na":   "N/A",
}

STATUS_COLOR_PIL = {
    "good": (20, 150, 20),
    "low":  (200, 100, 0),
    "high": (200, 0, 0),
    "na":   (120, 120, 120),
}

SUGGESTIONS = {
    "pH": {
        "good": "ప్రతి 2-3 సంవత్సరాలకు ఒకసారి సున్నపురాయి వేసి pH నిర్వహించండి. అధిక యూరియా వాడకం తగ్గించండి.",
        "low":  "వ్యవసాయ సున్నపురాయి 2-4 బస్తాలు/ఎకరం వేయండి. ఆమ్లీకరణ చేసే ఎరువులు వాడకండి.",
        "high": "జిప్సమ్ లేదా గంధకం 5-10 కిలోలు/ఎకరం కలపండి. అమోనియం సల్ఫేట్ ఉపయోగించండి.",
    },
    "Salinity": {
        "good": "చుక్కల నీటిపారుదల కొనసాగించండి. నీటి నిల్వ తగ్గించండి.",
        "high": "అదనపు నీటిపారుదలతో పొలాన్ని కడగండి. జిప్సమ్ 200 కిలోలు/ఎకరం వేయండి.",
    },
    "Organic Carbon": {
        "good": "సంవత్సరంతోపాటు 2 టన్నుల పశువుల ఎరువు/కంపోస్ట్ ఎకరానికి కలపండి.",
        "low":  "పశువుల ఎరువు 4-5 టన్నులు/ఎకరం వేయండి. పచ్చిరొట్ట ఎరువు వేయండి.",
        "high": "మంచి దుక్కితో సమం చేయండి. నీటి పారుదల మెరుగుపరచండి.",
    },
    "CEC": {
        "good": "సేంద్రీయ కార్బన్ నిర్వహించి అధిక దుక్కి తగ్గించండి.",
        "low":  "కంపోస్ట్ లేదా బంకమట్టి సవరణలు కలపండి.",
        "high": "పోషకాలు అందుబాటులో ఉండేలా pH సరైన స్థాయిలో ఉంచండి.",
    },
    "LST": {
        "good": "నేల ఉష్ణోగ్రత స్థిరంగా ఉంచేందుకు మల్చ్ ఉపయోగించండి.",
        "low":  "నల్ల ప్లాస్టిక్ మల్చ్ ఉపయోగించి నేలను వేడి చేయండి.",
        "high": "గడ్డి మల్చ్ వేసి నేలను చల్లబరచండి. నీటిపారుదల పెంచండి.",
    },
    "NDVI": {
        "good": "ప్రస్తుత పంట సాంద్రత మరియు ఎరువుల షెడ్యూల్ నిర్వహించండి.",
        "low":  "తెగుళ్ళు లేదా వ్యాధులు ఉన్నాయా అని తనిఖీ చేయండి. NPK సమతుల్య ఎరువు వేయండి.",
        "high": "నేలకు ఒరిగే అవకాశం గమనించండి. మంచి నీటి పారుదల నిర్ధారించండి.",
    },
    "EVI": {
        "good": "ప్రస్తుత పంట నిర్వహణ కొనసాగించండి.",
        "low":  "ఆకు ద్వారా సూక్ష్మపోషక స్ప్రే: జింక్ సల్ఫేట్ + బోరాన్ వేయండి.",
        "high": "మంచి గాలి ప్రసరణ నిర్ధారించండి. శిలీంద్ర వ్యాధులు గమనించండి.",
    },
    "FVC": {
        "good": "నేల ఆచ్ఛాదన నిర్వహించండి.",
        "low":  "మొక్కల సంఖ్య పెంచండి. కలుపు నియంత్రించండి.",
        "high": "దట్టమైన ఆచ్ఛాదన తేమ ఒత్తిడిని దాచవచ్చు.",
    },
    "NDWI": {
        "good": "ప్రస్తుత నీటిపారుదల షెడ్యూల్ కొనసాగించండి.",
        "low":  "వెంటనే నీటిపారుదల చేయండి. చుక్కల నీటిపారుదల సిఫార్సు చేయబడింది.",
        "high": "నీటిపారుదల తగ్గించండి. నీటి నిల్వ నివారించేందుకు పారుదల తనిఖీ చేయండి.",
    },
    "Nitrogen": {
        "good": "నష్టం తగ్గించేందుకు యూరియాను విభజించి వేయండి (బేసల్ + టాప్ డ్రెస్సింగ్).",
        "low":  "యూరియా 25-30 కిలోలు/ఎకరం లేదా DAP వేయండి.",
        "high": "ఈ సీజన్లో నైట్రోజన్ తగ్గించండి. వేప పూసిన యూరియా ఉపయోగించండి.",
    },
    "Phosphorus": {
        "good": "విత్తన సమయంలో తక్కువ SSP లేదా DAP వేయండి.",
        "low":  "DAP 12 కిలోలు/ఎకరం లేదా SSP 50 కిలోలు/ఎకరం విత్తన సమయంలో వేయండి.",
        "high": "ఈ సీజన్లో భాస్వరం తగ్గించండి. జింక్ సల్ఫేట్ 5 కిలోలు/ఎకరం వేయండి.",
    },
    "Potassium": {
        "good": "ప్రతి 2వ సీజన్లో MOP తక్కువ మోతాదులో వేయండి.",
        "low":  "MOP 8-10 కిలోలు/ఎకరం వేయండి. చెట్ల బూడిద సేంద్రీయ మూలంగా కలపండి.",
        "high": "ఈ సీజన్లో పొటాషియం తగ్గించండి. మెగ్నీషియం లోపాన్ని గమనించండి.",
    },
    "Calcium": {
        "good": "కాల్షియం అందుబాటుకు pH 6.5-7.5 నిర్వహించండి. ప్రతి 2-3 సంవత్సరాలకు సున్నపురాయి వేయండి.",
        "low":  "వ్యవసాయ సున్నపురాయి 200-400 కిలోలు/ఎకరం వేయండి. pH తనిఖీ చేయండి.",
        "high": "అదనపు సున్నపురాయి వాడకం తగ్గించండి. Mg మరియు K స్థాయిలు గమనించండి.",
    },
    "Magnesium": {
        "good": "pH సవరణ సమయంలో డోలోమైట్ సున్నపురాయి వేయండి.",
        "low":  "డోలోమైట్ 50-100 కిలోలు/ఎకరం లేదా కీసరైట్ 10 కిలోలు/ఎకరం వేయండి.",
        "high": "Ca మరియు K పోటీని గమనించండి. నీటి పారుదల మెరుగుపరచండి.",
    },
    "Sulphur": {
        "good": "విత్తన సమయంలో SSP ఎరువు ఉపయోగించి స్థాయి నిర్వహించండి.",
        "low":  "జిప్సమ్ 50 కిలోలు/ఎకరం లేదా మూల గంధకం 5-10 కిలోలు/ఎకరం వేయండి.",
        "high": "సల్ఫేట్ కలిగిన ఎరువులు తగ్గించండి. EC తనిఖీ చేయండి.",
    },
}

ALL_BANDS = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]

# PIL image constants
PAGE_W_PX = 1240
CONTENT_W  = 1100
DPI        = 150

# ─────────────────────────────────────────────
#  Request Model
# ─────────────────────────────────────────────
class ReportRequest(BaseModel):
    lat: float = Field(..., example=18.4575)
    lon: float = Field(..., example=73.8503)
    start_date: str = Field(..., example="2024-01-01")
    end_date: str   = Field(..., example="2024-01-16")
    buffer_meters: int = Field(default=200)
    polygon_coords: Optional[List[List[float]]] = Field(
        default=None,
        example=[
            [75.004513, 21.198307],
            [75.003476, 21.198545],
            [75.003612, 21.198904],
            [75.004640, 21.198642],
            [75.004513, 21.198307]
        ]
    )
    cec_intercept:  float = Field(default=5.0)
    cec_slope_clay: float = Field(default=20.0)
    cec_slope_om:   float = Field(default=15.0)

# ─────────────────────────────────────────────
#  PIL Telugu Text Helpers
# ─────────────────────────────────────────────
def _measure_text(text, font):
    tmp = Image.new('RGB', (1, 1))
    d   = ImageDraw.Draw(tmp)
    bb  = d.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


def wrap_text(text, font, max_w):
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


def render_text_image(text, font_size=18, color=(0, 0, 0), bg=(255, 255, 255),
                      max_w=CONTENT_W, align='left'):
    font  = pil_font(font_size)
    lines = wrap_text(text, font, max_w - 10)
    _, lh = _measure_text('అ', font)
    line_h  = lh + 6
    total_h = line_h * len(lines) + 10
    img  = Image.new('RGB', (max_w, max(total_h, line_h + 10)), bg)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        lw, _ = _measure_text(line, font)
        x = (max_w - lw) // 2 if align == 'center' else (max_w - lw - 5 if align == 'right' else 5)
        draw.text((x, 5 + i * line_h), line, font=font, fill=color)
    return img


def pil_img_to_rl(pil_img, width_cm=None, height_cm=None):
    buf = BytesIO()
    pil_img.save(buf, format='PNG')
    buf.seek(0)
    w_pt = width_cm  * cm if width_cm  else (pil_img.width  / DPI * 2.54 * cm)
    h_pt = height_cm * cm if height_cm else (pil_img.height / DPI * 2.54 * cm)
    return RLImage(buf, width=w_pt, height=h_pt)


def t_title(text, pw_cm=17.0):
    max_px = int(pw_cm * DPI / 2.54)
    pimg   = render_text_image(text, font_size=30, color=(20, 100, 20), max_w=max_px, align='center')
    return pil_img_to_rl(pimg, width_cm=pw_cm, height_cm=pimg.height / DPI * 2.54)


def t_heading(text, pw_cm=17.0):
    max_px = int(pw_cm * DPI / 2.54)
    pimg   = render_text_image(text, font_size=22, color=(20, 100, 20), max_w=max_px)
    return pil_img_to_rl(pimg, width_cm=pw_cm, height_cm=pimg.height / DPI * 2.54)


def t_para(text, font_size=16, color=(0, 0, 0), pw_cm=17.0, align='left'):
    max_px = int(pw_cm * DPI / 2.54)
    pimg   = render_text_image(text, font_size=font_size, color=color, max_w=max_px, align=align)
    return pil_img_to_rl(pimg, width_cm=pw_cm, height_cm=pimg.height / DPI * 2.54)


def t_small(text, font_size=14, color=(0, 0, 0), pw_cm=17.0):
    return t_para(text, font_size=font_size, color=color, pw_cm=pw_cm)


# ─────────────────────────────────────────────
#  Telugu Table Builder
# ─────────────────────────────────────────────
def build_telugu_table_image(headers, rows, col_widths_px, font_size=15,
                              header_bg=(20, 100, 20), row_bg1=(255, 255, 255),
                              row_bg2=(240, 250, 240)):
    font   = pil_font(font_size)
    _, ch  = _measure_text('అ', font)
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

    x = BORDER
    draw.rectangle([0, 0, total_w - 1, header_h], fill=header_bg)
    for hdr, cw in zip(headers, col_widths_px):
        draw.text((x + pad, pad), hdr, font=font, fill=(255, 255, 255))
        x += cw + BORDER

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


# ─────────────────────────────────────────────
#  GEE Helpers
# ─────────────────────────────────────────────
def build_region(req: ReportRequest) -> ee.Geometry:
    if req.polygon_coords and len(req.polygon_coords) >= 3:
        return ee.Geometry.Polygon(req.polygon_coords)
    return ee.Geometry.Point([req.lon, req.lat]).buffer(req.buffer_meters)


def safe_get_info(obj, name="value"):
    if obj is None: return None
    try:
        v = obj.getInfo()
        return float(v) if v is not None else None
    except Exception as e:
        logger.warning(f"Failed {name}: {e}"); return None


def sentinel_composite(region, start_str, end_str, bands):
    try:
        coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterDate(start_str, end_str).filterBounds(region)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).select(bands))
        if coll.size().getInfo() > 0:
            return coll.median().multiply(0.0001)
        start_dt = datetime.strptime(start_str, "%Y-%m-%d")
        end_dt   = datetime.strptime(end_str,   "%Y-%m-%d")
        for days in range(5, 31, 5):
            sd = (start_dt - timedelta(days=days)).strftime("%Y-%m-%d")
            ed = (end_dt   + timedelta(days=days)).strftime("%Y-%m-%d")
            coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                    .filterDate(sd, ed).filterBounds(region)
                    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)).select(bands))
            if coll.size().getInfo() > 0:
                logger.info(f"Sentinel expanded to {sd} - {ed}")
                return coll.median().multiply(0.0001)
        return None
    except Exception as e:
        logger.error(f"sentinel_composite: {e}"); return None


def get_band_stats(comp, region, scale=10):
    try:
        s = comp.reduceRegion(reducer=ee.Reducer.mean(), geometry=region,
                              scale=scale, maxPixels=1e13).getInfo()
        return {k: (float(v) if v is not None else 0.0) for k, v in s.items()}
    except Exception as e:
        logger.error(f"get_band_stats: {e}"); return {}


def get_lst(region, end_str):
    try:
        end_dt   = datetime.strptime(end_str, "%Y-%m-%d")
        start_dt = end_dt - relativedelta(months=1)
        coll = (ee.ImageCollection("MODIS/061/MOD11A2")
                .filterBounds(region.buffer(5000))
                .filterDate(start_dt.strftime("%Y-%m-%d"), end_str)
                .select("LST_Day_1km"))
        if coll.size().getInfo() == 0: return None
        img   = coll.median().multiply(0.02).subtract(273.15).rename("lst").clip(region.buffer(5000))
        stats = img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=1000, maxPixels=1e13).getInfo()
        v     = stats.get("lst")
        return float(v) if v is not None else None
    except Exception as e:
        logger.error(f"get_lst: {e}"); return None


def get_soil_texture(region):
    try:
        mode = SOIL_TEXTURE_IMG.clip(region.buffer(500)).reduceRegion(
            ee.Reducer.mode(), geometry=region, scale=250, maxPixels=1e13).get("b0")
        v = safe_get_info(mode, "texture")
        return int(v) if v is not None else None
    except Exception as e:
        logger.error(f"get_soil_texture: {e}"); return None


# ─────────────────────────────────────────────
#  Derived Parameters
# ─────────────────────────────────────────────
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
    b8,b8a=bs.get("B8",0),bs.get("B8A",0); b11,b12=bs.get("B11",0),bs.get("B12",0)
    ndvi=(b8-b4)/(b8+b4+1e-6); evi=2.5*(b8-b4)/(b8+6*b4-7.5*b2+1+1e-6)
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


# ─────────────────────────────────────────────
#  Status & Score
# ─────────────────────────────────────────────
def get_param_status(param, value):
    if value is None: return "na"
    if param == "Soil Texture": return "good" if value == 7 else "low"
    rng = IDEAL_RANGES.get(param, (None, None))
    if isinstance(rng, tuple):
        mn, mx = rng
        if mn is None and mx is not None: return "good" if value <= mx else "high"
        if mx is None and mn is not None: return "good" if value >= mn else "low"
        if mn is not None and mx is not None:
            if value < mn: return "low"
            if value > mx: return "high"
            return "good"
    return "good"


def calculate_soil_health_score(params):
    good  = sum(1 for p, v in params.items() if get_param_status(p, v) == "good")
    total = len([v for v in params.values() if v is not None])
    pct   = (good / total) * 100 if total else 0
    rating = ("అత్యుత్తమం" if pct >= 80 else "మంచిది" if pct >= 60 else "సగటు" if pct >= 40 else "పేలవంగా ఉంది")
    return pct, rating, good, total


def get_suggestion(param, value):
    if value is None or param not in SUGGESTIONS: return "-"
    s  = SUGGESTIONS[param]
    st = get_param_status(param, value)
    if st == "good": return "సరైనది: " + s.get("good", "ప్రస్తుత పద్ధతి కొనసాగించండి.")
    if st == "low":  return "సరిచేయండి: " + s.get("low",  s.get("high", "వ్యవసాయ నిపుణుడిని సంప్రదించండి."))
    if st == "high": return "సరిచేయండి: " + s.get("high", s.get("low",  "వ్యవసాయ నిపుణుడిని సంప్రదించండి."))
    return "-"


def generate_interpretation(param, value):
    if value is None: return "సమాచారం లేదు."
    if param == "Soil Texture": return TEXTURE_CLASSES.get(value, "తెలియని నేల నిర్మాణం.")
    if param == "NDWI":
        if value >= -0.10: return "మంచి తేమ; నీటిపారుదల అవసరం లేదు."
        if value >= -0.30: return "తేలికపాటి ఒత్తిడి; 2 రోజుల్లో నీటిపారుదల చేయండి."
        if value >= -0.40: return "మధ్యస్థ ఒత్తిడి; రేపు నీటిపారుదల చేయండి."
        return "తీవ్రమైన ఒత్తిడి; వెంటనే నీటిపారుదల చేయండి."
    if param == "Phosphorus": return "తక్కువ స్పెక్ట్రల్ విశ్వసనీయత. మార్గదర్శకంగా మాత్రమే."
    if param == "Sulphur":    return "తక్కువ స్పెక్ట్రల్ విశ్వసనీయత. అంచనాగా మాత్రమే."
    st    = get_param_status(param, value)
    ideal = IDEAL_DISPLAY.get(param, "N/A")
    if st == "good": return f"అత్యుత్తమ స్థాయి ({ideal})."
    if st == "low":
        mn, _ = IDEAL_RANGES.get(param, (None, None))
        return f"తక్కువ స్థాయి ({mn} కంటే తక్కువ)."
    if st == "high":
        _, mx = IDEAL_RANGES.get(param, (None, None))
        return f"అధిక స్థాయి ({mx} కంటే ఎక్కువ)."
    return "వివరణ లేదు."


# ─────────────────────────────────────────────
#  Charts (matplotlib, BytesIO output)
# ─────────────────────────────────────────────
def _bar_color(param, val):
    s = get_param_status(param, val)
    return {"good":(0.08,0.59,0.08),"low":(0.85,0.45,0.0),"high":(0.80,0.08,0.08),"na":(0.5,0.5,0.5)}.get(s,(0.5,0.5,0.5))

def _set_telugu_ticks(ax, labels):
    ax.set_xticks(range(len(labels)))
    if TELUGU_FP:
        ax.set_xticklabels(labels, fontproperties=TELUGU_FP, fontsize=8)
    else:
        ax.set_xticklabels(labels, fontsize=8)


def make_nutrient_chart(n, p, k, ca, mg, s):
    pkeys = ["Nitrogen","Phosphorus","Potassium","Calcium","Magnesium","Sulphur"]
    vals  = [n or 0, p or 0, k or 0, ca or 0, mg or 0, s or 0]
    tlbls = ["నైట్రోజన్\n(kg/ha)","భాస్వరం\nP2O5 (kg/ha)","పొటాషియం\nK2O (kg/ha)",
             "కాల్షియం\n(kg/ha)","మెగ్నీషియం\n(kg/ha)","గంధకం\n(kg/ha)"]
    bcs = [_bar_color(pk, v) for pk, v in zip(pkeys, vals)]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    bars = ax.bar(range(len(tlbls)), vals, color=bcs, alpha=0.85)
    ymax = max(vals) * 1.4 if any(vals) else 400
    ax.set_ylim(0, ymax)
    if TELUGU_FP:
        ax.set_title("నేల పోషక స్థాయిలు (కిలో/హెక్టారు) - ICAR ప్రమాణం", fontproperties=TELUGU_FP, fontsize=11)
        ax.set_ylabel("కిలో / హెక్టారు", fontproperties=TELUGU_FP, fontsize=9)
    _set_telugu_ticks(ax, tlbls)
    for bar, val, pk in zip(bars, vals, pkeys):
        lbl = TELUGU_STATUS.get(get_param_status(pk, val), "N/A")
        kw  = {"ha":"center","va":"bottom","fontsize":7}
        if TELUGU_FP: kw["fontproperties"] = TELUGU_FP
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+ymax*0.02, f"{val:.1f}\n{lbl}", **kw)
    plt.tight_layout()
    buf = BytesIO(); plt.savefig(buf, format='png', dpi=120, bbox_inches='tight'); plt.close(); buf.seek(0)
    return buf


def make_vegetation_chart(ndvi, ndwi):
    tlbls = ["వృక్ష సూచిక\n(NDVI)", "నీటి సూచిక\n(NDWI)"]
    vals  = [ndvi or 0, ndwi or 0]
    bcs   = [_bar_color(p, v) for p, v in zip(["NDVI","NDWI"], vals)]
    fig, ax = plt.subplots(figsize=(5, 4.5))
    bars = ax.bar(range(2), vals, color=bcs, alpha=0.85)
    ax.axhline(0, color='black', linewidth=0.5, linestyle='--'); ax.set_ylim(-1, 1)
    if TELUGU_FP:
        ax.set_title("వృక్ష మరియు నీటి సూచికలు", fontproperties=TELUGU_FP, fontsize=11)
        ax.set_ylabel("సూచిక విలువ", fontproperties=TELUGU_FP, fontsize=9)
    _set_telugu_ticks(ax, tlbls)
    for i, (bar, val) in enumerate(zip(bars, vals)):
        lbl = TELUGU_STATUS.get(get_param_status(["NDVI","NDWI"][i], val), "N/A")
        yp  = bar.get_height()+0.04 if val >= 0 else bar.get_height()-0.12
        kw  = {"ha":"center","va":"bottom","fontsize":9}
        if TELUGU_FP: kw["fontproperties"] = TELUGU_FP
        ax.text(bar.get_x()+bar.get_width()/2, yp, f"{val:.2f}\n{lbl}", **kw)
    plt.tight_layout()
    buf = BytesIO(); plt.savefig(buf, format='png', dpi=120, bbox_inches='tight'); plt.close(); buf.seek(0)
    return buf


def make_soil_properties_chart(ph, sal, oc, cec, lst):
    pkeys = ["pH","Salinity","Organic Carbon","CEC","LST"]
    tlbls = ["pH\nస్థాయి","EC విద్యుత్\n(mS/cm)","సేంద్రీయ\nకార్బన్ (%)","CEC\n(cmol/kg)","భూ వేడి\n(C)"]
    vals  = [ph or 0, sal or 0, oc or 0, cec or 0, lst or 0]
    bcs   = [_bar_color(pk, v) for pk, v in zip(pkeys, vals)]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(range(len(tlbls)), vals, color=bcs, alpha=0.85)
    ymax = max(vals) * 1.4 if any(vals) else 50; ax.set_ylim(0, ymax)
    if TELUGU_FP:
        ax.set_title("నేల లక్షణాలు (ICAR ప్రమాణం)", fontproperties=TELUGU_FP, fontsize=11)
        ax.set_ylabel("విలువ", fontproperties=TELUGU_FP, fontsize=9)
    _set_telugu_ticks(ax, tlbls)
    for bar, val, pk in zip(bars, vals, pkeys):
        lbl = TELUGU_STATUS.get(get_param_status(pk, val), "N/A")
        kw  = {"ha":"center","va":"bottom","fontsize":8}
        if TELUGU_FP: kw["fontproperties"] = TELUGU_FP
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+ymax*0.02, f"{val:.2f}\n{lbl}", **kw)
    plt.tight_layout()
    buf = BytesIO(); plt.savefig(buf, format='png', dpi=120, bbox_inches='tight'); plt.close(); buf.seek(0)
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
            max_tokens=900, temperature=0.35)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq: {e}"); return None


# ─────────────────────────────────────────────
#  Core Analysis
# ─────────────────────────────────────────────
def run_analysis(req: ReportRequest) -> dict:
    region = build_region(req)
    comp   = sentinel_composite(region, req.start_date, req.end_date, ALL_BANDS)
    texc   = get_soil_texture(region)
    lst    = get_lst(region, req.end_date)

    if comp is None:
        ph=sal=oc=cec=ndwi=ndvi=evi=fvc=n_val=p_val=k_val=ca_val=mg_val=s_val=None
    else:
        bs    = get_band_stats(comp, region)
        ph    = get_ph_new(bs);          sal  = get_salinity_ec(bs)
        oc    = get_organic_carbon_pct(bs)
        cec   = estimate_cec(comp, region, req.cec_intercept, req.cec_slope_clay, req.cec_slope_om)
        ndwi  = get_ndwi(bs);            ndvi = get_ndvi(bs)
        evi   = get_evi(bs);             fvc  = get_fvc(bs)
        n_val, p_val, k_val = get_npk_kgha(bs)
        ca_val = get_calcium_kgha(bs);   mg_val = get_magnesium_kgha(bs)
        s_val  = get_sulphur_kgha(bs)

    return {
        "pH":ph,"Salinity":sal,"Organic Carbon":oc,"CEC":cec,
        "Soil Texture":texc,"LST":lst,"NDWI":ndwi,"NDVI":ndvi,
        "EVI":evi,"FVC":fvc,"Nitrogen":n_val,"Phosphorus":p_val,
        "Potassium":k_val,"Calcium":ca_val,"Magnesium":mg_val,"Sulphur":s_val,
    }


# ─────────────────────────────────────────────
#  PDF Generator (Telugu via PIL)
# ─────────────────────────────────────────────
def generate_pdf(params: dict, location: str, date_range: str) -> bytes:
    REPORT_PARAMS = {k: v for k, v in params.items() if k not in ("EVI", "FVC")}
    score, rating, good_c, total_c = calculate_soil_health_score(REPORT_PARAMS)

    # Charts → BytesIO
    nc_buf = make_nutrient_chart(params["Nitrogen"], params["Phosphorus"], params["Potassium"],
                                  params["Calcium"],  params["Magnesium"],  params["Sulphur"])
    vc_buf = make_vegetation_chart(params["NDVI"], params["NDWI"])
    pc_buf = make_soil_properties_chart(params["pH"], params["Salinity"],
                                         params["Organic Carbon"], params["CEC"], params["LST"])

    def fv(p, v): return "N/A" if v is None else f"{v:.2f}{UNIT_MAP.get(p,'')}"

    tex_d = TEXTURE_CLASSES.get(params.get("Soil Texture"), "N/A") if params.get("Soil Texture") else "N/A"

    exec_prompt = f"""మీరు ఒక భారతీయ వ్యవసాయ నిపుణుడు. క్రింది నేల డేటాను పరిశీలించి, ఒక రైతుకు 4-5 అంశాలలో తెలుగులో మాత్రమే సారాంశం రాయండి. సరళమైన భాషలో, Bold వద్దు, markdown వద్దు. ప్రతి అంశం . (పూర్ణవిరామం) తో మొదలుపెట్టండి.
నేల ఆరోగ్య స్కోర్: {score:.1f}% ({rating})
pH={fv('pH',params['pH'])}, EC={fv('Salinity',params['Salinity'])}, నేల={tex_d}
నైట్రోజన్={fv('Nitrogen',params['Nitrogen'])}, పొటాషియం={fv('Potassium',params['Potassium'])}
కాల్షియం={fv('Calcium',params['Calcium'])}, మెగ్నీషియం={fv('Magnesium',params['Magnesium'])}, గంధకం={fv('Sulphur',params['Sulphur'])}"""

    rec_prompt = f"""మీరు ఒక భారతీయ వ్యవసాయ నిపుణుడు. క్రింది నేల డేటాను పరిశీలించి, 4-5 ఆచరణీయ సిఫార్సులను తెలుగులో మాత్రమే ఇవ్వండి. Bold వద్దు, markdown వద్దు. ప్రతి అంశం . తో మొదలుపెట్టండి.
pH={fv('pH',params['pH'])}, EC={fv('Salinity',params['Salinity'])}, నేల={tex_d}
నైట్రోజన్={fv('Nitrogen',params['Nitrogen'])}, పొటాషియం={fv('Potassium',params['Potassium'])}
NDVI={fv('NDVI',params['NDVI'])}, NDWI={fv('NDWI',params['NDWI'])}
భారతీయ వాతావరణానికి అనువైన పంటలు సూచించండి."""

    exec_summary = call_groq(exec_prompt) or ". సారాంశం అందుబాటులో లేదు."
    recs         = call_groq(rec_prompt)  or ". సిఫార్సులు అందుబాటులో లేవు."

    pdf_buf = BytesIO()
    doc = SimpleDocTemplate(pdf_buf, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=3*cm, bottomMargin=2*cm)
    PW_CM = 17.0
    elems = []

    # Cover page
    elems.append(Spacer(1, 1.5*cm))
    if os.path.exists(LOGO_PATH):
        li = RLImage(LOGO_PATH, width=9*cm, height=9*cm)
        li.hAlign = 'CENTER'; elems.append(li)
    elems.append(Spacer(1, 0.5*cm))
    elems.append(t_title("FarmMatrix నేల ఆరోగ్య నివేదిక", PW_CM))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(t_para(f"స్థలం: {location}", 16, (60,60,60), PW_CM, 'center'))
    elems.append(t_para(f"తేదీ పరిధి: {date_range}", 16, (60,60,60), PW_CM, 'center'))
    elems.append(t_para(f"రూపొందించిన తేదీ: {datetime.now():%d %B %Y, %H:%M}", 14, (100,100,100), PW_CM, 'center'))
    elems.append(PageBreak())

    # Section 1: Summary
    elems.append(t_heading("1. కార్యనిర్వాహక సారాంశం", PW_CM))
    elems.append(Spacer(1, 0.2*cm))
    for line in exec_summary.split('\n'):
        line = line.strip()
        if line:
            elems.append(t_para(line, 16, (30,30,30), PW_CM))
            elems.append(Spacer(1, 0.1*cm))
    elems.append(Spacer(1, 0.3*cm))

    # Section 2: Health Score
    elems.append(t_heading("2. నేల ఆరోగ్య అంచనా", PW_CM))
    elems.append(Spacer(1, 0.2*cm))
    score_color = (20,150,20) if score >= 60 else ((200,150,0) if score >= 40 else (200,50,50))
    score_tbl = build_telugu_table_image(
        headers=["మొత్తం స్కోర్", "అంచనా", "అత్యుత్తమ పారామీటర్లు"],
        rows=[[
            (f"{score:.1f}%", score_color),
            (rating, score_color),
            (f"{good_c} / {total_c}", (30,30,30))
        ]],
        col_widths_px=[260, 260, 260], font_size=17
    )
    ri = pil_img_to_rl(score_tbl, width_cm=PW_CM); ri.hAlign = 'LEFT'; elems.append(ri)
    elems.append(Spacer(1, 0.3*cm))
    elems.append(PageBreak())

    # Section 3: Parameter Table
    elems.append(t_heading("3. నేల పారామీటర్ల విశ్లేషణ (ICAR ప్రమాణం)", PW_CM))
    elems.append(Spacer(1, 0.2*cm))
    headers3 = ["పారామీటర్", "విలువ", "ICAR అత్యుత్తమ పరిధి", "స్థితి", "వివరణ"]
    rows3 = []
    for param, value in REPORT_PARAMS.items():
        unit    = UNIT_MAP.get(param, "")
        val_txt = (TEXTURE_CLASSES.get(value,"N/A") if param=="Soil Texture" and value
                   else (f"{value:.2f}{unit}" if value is not None else "N/A"))
        st      = get_param_status(param, value)
        rows3.append([
            (TELUGU_PARAM_NAMES.get(param, param), (30,30,30)),
            (val_txt, (30,30,30)),
            (IDEAL_DISPLAY.get(param,"N/A"), (30,30,30)),
            (TELUGU_STATUS.get(st,"N/A"), STATUS_COLOR_PIL.get(st,(0,0,0))),
            (generate_interpretation(param, value), (30,30,30))
        ])
    tbl3_img = build_telugu_table_image(headers=headers3, rows=rows3,
                                         col_widths_px=[200,130,160,110,300], font_size=14)
    ri3 = pil_img_to_rl(tbl3_img, width_cm=PW_CM); ri3.hAlign = 'LEFT'; elems.append(ri3)
    elems.append(PageBreak())

    # Section 4: Charts
    elems.append(t_heading("4. దృశ్యమాన చిత్రీకరణలు", PW_CM))
    elems.append(Spacer(1, 0.2*cm))
    for lbl, buf in [
        ("N, P2O5, K2O, Ca, Mg, S పోషక స్థాయిలు (కిలో/హెక్టారు):", nc_buf),
        ("వృక్ష మరియు నీటి సూచికలు (NDVI, NDWI):", vc_buf),
        ("నేల లక్షణాలు:", pc_buf),
    ]:
        elems.append(t_small(lbl, 15, (30,30,30), PW_CM))
        if buf:
            buf.seek(0)
            ci = RLImage(buf, width=14*cm, height=7*cm)
            ci.hAlign = 'LEFT'; elems.append(ci)
        elems.append(Spacer(1, 0.3*cm))
    elems.append(PageBreak())

    # Section 5: Recommendations
    elems.append(t_heading("5. పంట సిఫార్సులు మరియు చికిత్సలు", PW_CM))
    elems.append(Spacer(1, 0.2*cm))
    for line in recs.split('\n'):
        line = line.strip()
        if line:
            elems.append(t_para(line, 16, (30,30,30), PW_CM))
            elems.append(Spacer(1, 0.1*cm))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(PageBreak())

    # Section 6: Parameter Suggestions
    elems.append(t_heading("6. పారామీటర్ వారీ సిఫార్సులు", PW_CM))
    elems.append(Spacer(1, 0.1*cm))
    elems.append(t_small("ప్రతి పారామీటర్కు: మంచి స్థాయి నిర్వహించేందుకు లేదా సమస్యలు సరిచేసేందుకు ఏమి చేయాలో తెలుసుకోండి.", 13, (80,80,80), PW_CM))
    elems.append(Spacer(1, 0.2*cm))

    SUG_PARAMS = ["pH","Salinity","Organic Carbon","CEC","Nitrogen","Phosphorus",
                  "Potassium","Calcium","Magnesium","Sulphur","NDVI","NDWI","LST"]
    rows6 = []
    for param in SUG_PARAMS:
        value = params.get(param)
        st    = get_param_status(param, value)
        rows6.append([
            (TELUGU_PARAM_NAMES.get(param, param), (30,30,30)),
            (TELUGU_STATUS.get(st, "N/A"), STATUS_COLOR_PIL.get(st, (0,0,0))),
            (get_suggestion(param, value), (30,30,30))
        ])
    tbl6_img = build_telugu_table_image(
        headers=["పారామీటర్", "స్థితి", "అవసరమైన చర్య"],
        rows=rows6, col_widths_px=[200,110,590], font_size=14
    )
    ri6 = pil_img_to_rl(tbl6_img, width_cm=PW_CM); ri6.hAlign = 'LEFT'; elems.append(ri6)
    elems.append(Spacer(1, 0.4*cm))
    elems.append(t_small(
        "గమనిక: భాస్వరం (P) మరియు గంధకం (S) విలువలకు స్పెక్ట్రల్ విశ్వసనీయత తక్కువ. అంచనాగా మాత్రమే పరిగణించండి.",
        13, (120,60,0), PW_CM))

    def add_header(canv, doc_obj):
        canv.saveState()
        if os.path.exists(LOGO_PATH):
            canv.drawImage(LOGO_PATH, 2*cm, A4[1]-2.8*cm, width=1.8*cm, height=1.8*cm)
        canv.setFont("Helvetica-Bold", 11)
        canv.drawString(4.5*cm, A4[1]-2.2*cm, "FarmMatrix Soil Health Report (Telugu)")
        canv.setFont("Helvetica", 8)
        canv.drawRightString(A4[0]-2*cm, A4[1]-2.2*cm, f"Generated: {datetime.now():%d %b %Y, %H:%M}")
        canv.setStrokeColor(colors.darkgreen); canv.setLineWidth(1)
        canv.line(2*cm, A4[1]-3*cm, A4[0]-2*cm, A4[1]-3*cm)
        canv.restoreState()

    def add_footer(canv, doc_obj):
        canv.saveState()
        canv.setStrokeColor(colors.darkgreen)
        canv.line(2*cm, 1.5*cm, A4[0]-2*cm, 1.5*cm)
        canv.setFont("Helvetica", 8)
        canv.drawCentredString(A4[0]/2, cm, f"Page {doc_obj.page}  |  FarmMatrix  |  ICAR Standard")
        canv.restoreState()

    doc.build(elems, onFirstPage=add_header, onLaterPages=add_header, canvasmaker=canvas.Canvas)
    pdf_buf.seek(0)
    return pdf_buf.getvalue()


# ─────────────────────────────────────────────
#  API Routes
# ─────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "FarmMatrix Telugu Soil Health API is running.", "version": "2.0.0"}


@app.post("/report", tags=["Report"])
async def generate_report_endpoint(req: ReportRequest):
    """
    Run full soil analysis and generate a complete Telugu PDF report.
    Accepts polygon_coords as List[List[float]] e.g. [[lon,lat],[lon,lat],...].
    If polygon_coords is null, uses a circular buffer around lat/lon.
    Returns a downloadable PDF with all text rendered in Telugu via PIL.
    """
    try:
        params     = run_analysis(req)
        location   = f"Lat: {req.lat:.6f}, Lon: {req.lon:.6f}"
        date_range = f"{req.start_date} to {req.end_date}"
        pdf_bytes  = generate_pdf(params, location, date_range)

        # ASCII-only filename — avoids latin-1 encoding error in HTTP headers
        filename = f"soil_report_telugu_{date.today()}.pdf"

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