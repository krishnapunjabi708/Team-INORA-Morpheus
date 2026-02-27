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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import sys
import matplotlib.font_manager as fm
sys.path.append(r'C:\Users\pavan\AppData\Roaming\Python\Python313\site-packages')
import google.generativeai as genai

# Register Hindi font for PDF
pdfmetrics.registerFont(TTFont('NotoSerifDevanagari', 'NotoSerifDevanagari-Regular.ttf'))

# Set up font for Matplotlib
font_path = 'NotoSerifDevanagari-Regular.ttf'  # Adjust path if needed
fm.fontManager.addfont(font_path)
prop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = prop.get_name()

# Configuration
API_KEY = "AIzaSyAWA9Kqh2FRtBmxRZmNlZ7pcfasG5RJmR8"
MODEL = "models/gemini-1.5-flash"
LOGO_PATH = os.path.abspath("LOGO.jpg")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Initialize Google Earth Engine
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# Constants & Lookups
SOIL_TEXTURE_IMG = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0')
TEXTURE_CLASSES = {
    1: "मिट्टी", 2: "गाद मिट्टी", 3: "बलुई मिट्टी",
    4: "मिट्टी दोमट", 5: "गाद मिट्टी दोमट", 6: "बलुई मिट्टी दोमट",
    7: "दोमट", 8: "गाद दोमट", 9: "बलुई दोमट",
    10: "गाद", 11: "दोमट रेत", 12: "रेत"
}
IDEAL_RANGES = {
    "पीएच":           (6.0, 7.5),
    "मिट्टी की बनावट": 7,
    "लवणता":     (None, 0.2),
    "कार्बनिक कार्बन": (0.02, 0.05),
    "सीईसी":            (10, 30),
    "एलएसटी":            (10, 30),
    "एनडीवीआई":           (0.2, 0.8),
    "ईवीआई":            (0.2, 0.8),
    "एफवीसी":            (0.3, 0.8),
    "एनडीडब्ल्यूआई":           (-0.5, 0.5),
    "नाइट्रोजन":       (280, 450),
    "फास्फोरस":     (20, 50),
    "पोटैशियम":      (150, 300)
}

# Utility Functions
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
    end_str = end.strftime("%Y-%m-%d")
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
            ed = (end + timedelta(days=days)).strftime("%Y-%m-%d")
            coll = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterDate(sd, ed)
                .filterBounds(region)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
                .select(bands)
            )
            if coll.size().getInfo() > 0:
                logging.info(f"Sentinel window expanded to {sd}–{ed}")
                return coll.median().multiply(0.0001)
        logging.warning("No Sentinel-2 data available.")
        return None
    except Exception as e:
        logging.error(f"Error in sentinel_composite: {e}")
        return None

def get_lst(region, start, end):
    end_dt = end
    start_dt = end_dt - relativedelta(months=1)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")
    logging.info(f"Fetching MODIS LST from {start_str} to {end_str}")
    try:
        coll = (
            ee.ImageCollection("MODIS/061/MOD11A2")
            .filterBounds(region.buffer(5000))
            .filterDate(start_str, end_str)
            .select("LST_Day_1km")
        )
        cnt = coll.size().getInfo()
        if cnt == 0:
            logging.warning("No LST images in the specified range.")
            return None
        img = coll.median().multiply(0.02).subtract(273.15).rename("lst").clip(region.buffer(5000))
        stats = img.reduceRegion(reducer=ee.Reducer.mean(), geometry=region, scale=1000, maxPixels=1e13).getInfo()
        lst_value = stats.get("lst")
        return float(lst_value) if lst_value is not None else None
    except Exception as e:
        logging.error(f"Error in get_lst: {e}")
        return None

def get_ph(comp, region):
    if comp is None:
        return None
    try:
        br = comp.expression("(B2+B3+B4)/3", {"B2": comp.select("B2"), "B3": comp.select("B3"), "B4": comp.select("B4")})
        sa = comp.expression("(B11-B8)/(B11+B8+1e-6)", {"B11": comp.select("B11"), "B8": comp.select("B8")})
        img = comp.expression("7.1 + 0.15*B2 - 0.32*B11 + 1.2*br - 0.7*sa", {"B2": comp.select("B2"), "B11": comp.select("B11"), "br": br, "sa": sa}).rename("ph")
        return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ph"), "पीएच")
    except Exception as e:
        logging.error(f"Error in get_ph: {e}")
        return None

def get_salinity(comp, region):
    if comp is None:
        return None
    try:
        img = comp.expression("(B11-B3)/(B11+B3+1e-6)", {"B11": comp.select("B11"), "B3": comp.select("B3")}).rename("ndsi")
        return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndsi"), "लवणता")
    except Exception as e:
        logging.error(f"Error in get_salinity: {e}")
        return None

def get_organic_carbon(comp, region):
    if comp is None:
        return None
    try:
        ndvi = comp.normalizedDifference(["B8", "B4"])
        img = ndvi.multiply(0.05).rename("oc")
        return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("oc"), "कार्बनिक कार्बन")
    except Exception as e:
        logging.error(f"Error in get_organic_carbon: {e}")
        return None

def estimate_cec(comp, region, intercept, slope_clay, slope_om):
    if comp is None:
        return None
    try:
        clay = comp.expression("(B11-B8)/(B11+B8+1e-6)", {"B11": comp.select("B11"), "B8": comp.select("B8")}).rename("clay")
        om = comp.expression("(B8-B4)/(B8+B4+1e-6)", {"B8": comp.select("B8"), "B4": comp.select("B4")}).rename("om")
        c_m = safe_get_info(clay.reduceRegion(ee.Reducer.mean(), geometry=region, scale=20, maxPixels=1e13).get("clay"), "clay")
        o_m = safe_get_info(om.reduceRegion(ee.Reducer.mean(), geometry=region, scale=20, maxPixels=1e13).get("om"), "om")
        if c_m is None or o_m is None:
            return None
        return intercept + slope_clay * c_m + slope_om * o_m
    except Exception as e:
        logging.error(f"Error in estimate_cec: {e}")
        return None

def get_soil_texture(region):
    try:
        mode = SOIL_TEXTURE_IMG.clip(region.buffer(500)).reduceRegion(ee.Reducer.mode(), geometry=region, scale=250, maxPixels=1e13).get("b0")
        val = safe_get_info(mode, "बनावट")
        return int(val) if val is not None else None
    except Exception as e:
        logging.error(f"Error in get_soil_texture: {e}")
        return None

def get_ndwi(comp, region):
    if comp is None:
        return None
    try:
        img = comp.expression("(B3-B8)/(B3+B8+1e-6)", {"B3": comp.select("B3"), "B8": comp.select("B8")}).rename("ndwi")
        return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndwi"), "एनडीडब्ल्यूआई")
    except Exception as e:
        logging.error(f"Error in get_ndwi: {e}")
        return None

def get_ndvi(comp, region):
    if comp is None:
        return None
    try:
        ndvi = comp.normalizedDifference(["B8", "B4"]).rename("ndvi")
        return safe_get_info(ndvi.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndvi"), "एनडीवीआई")
    except Exception as e:
        logging.error(f"Error in get_ndvi: {e}")
        return None

def get_evi(comp, region):
    if comp is None:
        return None
    try:
        evi = comp.expression(
            "2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)",
            {"NIR": comp.select("B8"), "RED": comp.select("B4"), "BLUE": comp.select("B2")}
        ).rename("evi")
        return safe_get_info(evi.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("evi"), "ईवीआई")
    except Exception as e:
        logging.error(f"Error in get_evi: {e}")
        return None

def get_fvc(comp, region):
    if comp is None:
        return None
    try:
        ndvi = comp.normalizedDifference(["B8", "B4"])
        ndvi_min = 0.2
        ndvi_max = 0.8
        fvc = ndvi.subtract(ndvi_min).divide(ndvi_max - ndvi_min).pow(2).clamp(0, 1).rename("fvc")
        return safe_get_info(fvc.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("fvc"), "एफवीसी")
    except Exception as e:
        logging.error(f"Error in get_fvc: {e}")
        return None

def get_npk_for_region(comp, region):
    if comp is None:
        return None, None, None
    try:
        brightness = comp.expression('(B2 + B3 + B4) / 3', {'B2': comp.select('B2'), 'B3': comp.select('B3'), 'B4': comp.select('B4')})
        salinity2 = comp.expression('(B11 - B8) / (B11 + B8 + 1e-6)', {'B11': comp.select('B11'), 'B8': comp.select('B8')})
        N_est = comp.expression("5 + 100*(3 - (B2 + B3 + B4))", {'B2': comp.select('B2'), 'B3': comp.select('B3'), 'B4': comp.select('B4')}).rename('N').clamp(0, 1000)
        P_est = comp.expression("3 + 50*(1 - B8) + 20*(1 - B11)", {'B8': comp.select('B8'), 'B11': comp.select('B11')}).rename('P').clamp(0, 500)
        K_est = comp.expression("5 + 150*(1 - brightness) + 50*(1 - B3) + 30*salinity2", {'brightness': brightness, 'B3': comp.select('B3'), 'salinity2': salinity2}).rename('K').clamp(0, 1000)
        npk_image = N_est.addBands(P_est).addBands(K_est)
        stats = npk_image.reduceRegion(reducer=ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e9).getInfo()
        n = stats.get('N', None)
        p = stats.get('P', None)
        k = stats.get('K', None)
        if n is not None and (n < 0 or n > 1000):
            logging.warning(f"Unrealistic Nitrogen value: {n}")
            n = None
        if p is not None and (p < 0 or p > 500):
            logging.warning(f"Unrealistic Phosphorus value: {p}")
            p = None
        if k is not None and (k < 0 or k > 1000):
            logging.warning(f"Unrealistic Potassium value: {k}")
            k = None
        return float(n) if n is not None else None, float(p) if p is not None else None, float(k) if k is not None else None
    except Exception as e:
        logging.error(f"Error in get_npk_for_region: {e}")
        return None, None, None

def calculate_soil_health_score(params):
    score = 0
    total_params = len(params)
    for param, value in params.items():
        if value is None:
            total_params -= 1
            continue
        if param == "मिट्टी की बनावट":
            if value == IDEAL_RANGES[param]:
                score += 1
        else:
            min_val, max_val = IDEAL_RANGES.get(param, (None, None))
            if min_val is None and max_val is not None:
                if value <= max_val:
                    score += 1
            elif max_val is None and min_val is not None:
                if value >= min_val:
                    score += 1
            elif min_val is not None and max_val is not None:
                if min_val <= value <= max_val:
                    score += 1
    percentage = (score / total_params) * 100 if total_params > 0 else 0
    rating = "उत्कृष्ट" if percentage >= 80 else "अच्छा" if percentage >= 60 else "सामान्य" if percentage >= 40 else "खराब"
    return percentage, rating

def generate_interpretation(param, value):
    if value is None:
        return "डेटा उपलब्ध नहीं है।"
    if param == "मिट्टी की बनावट":
        return TEXTURE_CLASSES.get(value, "अज्ञात बनावट।")
    if param == "एनडीडब्ल्यूआई":
        if value >= -0.10:
            return "अच्छी नमी; सिंचाई की आवश्यकता नहीं।"
        elif -0.30 <= value < -0.15:
            return "हल्का तनाव; जल्द ही हल्की सिंचाई करें।"
        elif -0.40 <= value < -0.30:
            return "मध्यम तनाव; 1-2 दिनों में सिंचाई करें।"
        else:
            return "गंभीर तनाव; तुरंत सिंचाई करें।"
    min_val, max_val = IDEAL_RANGES.get(param, (None, None))
    if min_val is None and max_val is not None:
        return f"इष्टतम (≤{max_val})।" if value <= max_val else f"उच्च (>{max_val})।"
    elif max_val is None and min_val is not None:
        return f"इष्टतम (≥{min_val})।" if value >= min_val else f"निम्न (<{min_val})।"
    else:
        range_text = f"{min_val}-{max_val}" if min_val and max_val else "N/A"
        if min_val is not None and max_val is not None and min_val <= value <= max_val:
            return f"इष्टतम ({range_text})।"
        elif min_val is not None and value < min_val:
            return f"निम्न (<{min_val})।"
        elif max_val is not None and value > max_val:
            return f"उच्च (>{max_val})।"
        return f"{param} के लिए कोई व्याख्या नहीं।"

def get_color_for_value(param, value):
    if value is None:
        return 'grey'
    if param == "मिट्टी की बनावट":
        return 'green' if value == IDEAL_RANGES[param] else 'red'
    min_val, max_val = IDEAL_RANGES.get(param, (None, None))
    if min_val is None and max_val is not None:
        if value <= max_val:
            return 'green'
        elif value <= max_val * 1.2:
            return 'yellow'
        else:
            return 'red'
    elif max_val is None and min_val is not None:
        if value >= min_val:
            return 'green'
        elif value >= min_val * 0.8:
            return 'yellow'
        else:
            return 'red'
    elif min_val is not None and max_val is not None:
        if min_val <= value <= max_val:
            return 'green'
        elif value < min_val:
            if value >= min_val * 0.8:
                return 'yellow'
            else:
                return 'red'
        elif value > max_val:
            if param in ["फास्फोरस", "पोटैशियम"] and value <= max_val * 1.5:
                return 'yellow'
            elif value <= max_val * 1.2:
                return 'yellow'
            else:
                return 'red'
    return 'blue'

def make_nutrient_chart(n_val, p_val, k_val):
    try:
        nutrients = ["नाइट्रोजन", "फास्फोरस", "पोटैशियम"]
        values = [n_val or 0, p_val or 0, k_val or 0]
        colors = [get_color_for_value(nutrient, value) for nutrient, value in zip(nutrients, values)]
        plt.figure(figsize=(6, 4))
        bars = plt.bar(nutrients, values, color=colors, alpha=0.7)
        plt.title("मिट्टी पोषक तत्व स्तर (मिलीग्राम/किलोग्राम)", fontsize=12)
        plt.ylabel("सांद्रता (मिलीग्राम/किलोग्राम)")
        plt.ylim(0, max(values) * 1.2 if any(values) else 500)
        for bar, value in zip(bars, values):
            yval = bar.get_height()
            status = 'अच्छा' if colors[bars.index(bar)] == 'green' else 'उच्च' if value > IDEAL_RANGES[nutrients[bars.index(bar)]][1] else 'निम्न'
            plt.text(bar.get_x() + bar.get_width()/2, yval + 5, f"{yval:.1f}\n{status}", ha='center', va='bottom')
        plt.tight_layout()
        chart_path = "nutrient_chart.png"
        plt.savefig(chart_path, dpi=100, bbox_inches='tight')
        plt.close()
        return chart_path
    except Exception as e:
        logging.error(f"Error in make_nutrient_chart: {e}")
        return None

def make_vegetation_chart(ndvi, evi, fvc, ndwi):
    try:
        indices = ["एनडीवीआई", "ईवीआई", "एफवीसी", "एनडीडब्ल्यूआई"]
        values = [ndvi or 0, evi or 0, fvc or 0, ndwi or 0]
        colors = [get_color_for_value(idx, val) for idx, val in zip(indices, values)]
        plt.figure(figsize=(8, 4))
        bars = plt.bar(indices, values, color=colors, alpha=0.7)
        plt.title("वनस्पति और नमी सूचकांक", fontsize=12)
        plt.ylabel("मान")
        plt.ylim(-1, 1)
        for bar, value, idx in zip(bars, values, indices):
            yval = bar.get_height()
            if idx == "एनडीडब्ल्यूआई":
                status = 'अच्छा' if value >= -0.10 else 'निम्न'
            else:
                min_val, max_val = IDEAL_RANGES.get(idx, (0, 1))
                if value >= min_val:
                    status = 'अच्छा'
                else:
                    status = 'निम्न'
            plt.text(bar.get_x() + bar.get_width()/2, yval + 0.05, f"{yval:.2f}\n{status}", ha='center', va='bottom')
        plt.tight_layout()
        chart_path = "vegetation_chart.png"
        plt.savefig(chart_path, dpi=100, bbox_inches='tight')
        plt.close()
        return chart_path
    except Exception as e:
        logging.error(f"Error in make_vegetation_chart: {e}")
        return None

def make_soil_properties_chart(ph, sal, oc, cec, lst):
    try:
        properties = ["पीएच", "लवणता", "कार्बनिक कार्बन (%)", "सीईसी", "एलएसटी"]
        values = [ph or 0, sal or 0, (oc * 100 if oc else 0), cec or 0, lst or 0]
        colors = [get_color_for_value(prop, value) for prop, value in zip(["पीएच", "लवणता", "कार्बनिक कार्बन", "सीईसी", "एलएसटी"], values)]
        plt.figure(figsize=(8, 4))
        bars = plt.bar(properties, values, color=colors, alpha=0.7)
        plt.title("मिट्टी के गुण", fontsize=12)
        plt.ylabel("मान")
        plt.ylim(0, max(values) * 1.2 if any(values) else 50)
        for bar, value, prop in zip(bars, values, ["पीएच", "लवणता", "कार्बनिक कार्बन", "सीईसी", "एलएसटी"]):
            yval = bar.get_height()
            status = 'अच्छा' if colors[bars.index(bar)] == 'green' else 'उच्च' if (prop == "लवणता" and value > IDEAL_RANGES[prop][1]) or (prop != "लवणता" and value > IDEAL_RANGES[prop][1]) else 'निम्न'
            plt.text(bar.get_x() + bar.get_width()/2, yval + max(values) * 0.05, f"{yval:.2f}\n{status}", ha='center', va='bottom')
        plt.tight_layout()
        chart_path = "properties_chart.png"
        plt.savefig(chart_path, dpi=100, bbox_inches='tight')
        plt.close()
        return chart_path
    except Exception as e:
        logging.error(f"Error in make_soil_properties_chart: {e}")
        return None

def generate_report(params, location, date_range):
    try:
        score, rating = calculate_soil_health_score(params)
        interpretations = {param: generate_interpretation(param, value) for param, value in params.items()}
        
        nutrient_chart = make_nutrient_chart(params["नाइट्रोजन"], params["फास्फोरस"], params["पोटैशियम"])
        vegetation_chart = make_vegetation_chart(params["एनडीवीआई"], params["ईवीआई"], params["एफवीसी"], params["एनडीडब्ल्यूआई"])
        properties_chart = make_soil_properties_chart(params["पीएच"], params["लवणता"], params["कार्बनिक कार्बन"], params["सीईसी"], params["एलएसटी"])

        genai_configured = False
        try:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel(MODEL)
            response = model.generate_content("परीक्षण: एक वाक्य का सारांश उत्पन्न करें।")
            if response and response.text:
                genai_configured = True
                logging.info("जेमिनी एपीआई सफलतापूर्वक कॉन्फ़िगर किया गया।")
        except Exception as e:
            logging.error(f"जेमिनी एपीआई कॉन्फ़िगर करने में विफल: {e}")

        if genai_configured:
            try:
                prompt = f"""
                किसानों के लिए मिट्टी स्वास्थ्य रिपोर्ट का एक सरल कार्यकारी सारांश बुलेट-पॉइंट सूची (3-5 छोटे बिंदु) में उत्पन्न करें, जिसमें शामिल हैं:
                - स्थान: {location}
                - तिथि सीमा: {date_range}
                - मिट्टी स्वास्थ्य स्कोर: {score:.1f}% ({rating})
                - पैरामीटर: पीएच={params['पीएच'] or 'N/A'}, लवणता={params['लवणता'] or 'N/A'}, कार्बनिक कार्बन={params['कार्बनिक कार्बन']*100 if params['कार्बनिक कार्बन'] else 'N/A'}%, सीईसी={params['सीईसी'] or 'N/A'}, मिट्टी की बनावट={TEXTURE_CLASSES.get(params['मिट्टी की बनावट'], 'N/A')}, N={params['नाइट्रोजन'] or 'N/A'}, P={params['फास्फोरस'] or 'N/A'}, K={params['पोटैशियम'] or 'N/A'}
                मुख्य निष्कर्षों और तत्काल मुद्दों पर ध्यान केंद्रित करें, सरल और किसान-अनुकूल भाषा में।
                "•" से शुरू होने वाले बुलेट पॉइंट्स का उपयोग करें और ** या * जैसे मार्कडाउन फॉर्मेटिंग से बचें।
                """
                response = model.generate_content(prompt)
                executive_summary = response.text if response and response.text else "• सारांश उपलब्ध नहीं है।"

                prompt_recommendations = f"""
                किसानों के लिए फसल और मिट्टी उपचार की सिफारिशें एक बुलेट-पॉइंट सूची (3-5 छोटे बिंदु) में प्रदान करें, जो निम्नलिखित पर आधारित हैं:
                - पीएच: {params['पीएच'] or 'N/A'}
                - लवणता: {params['लवणता'] or 'N/A'}
                - कार्बनिक कार्बन: {params['कार्बनिक कार्बन']*100 if params['कार्बनिक कार्बन'] else 'N/A'}%
                - सीईसी: {params['सीईसी'] or 'N/A'}
                - मिट्टी की बनावट: {TEXTURE_CLASSES.get(params['मिट्टी की बनावट'], 'N/A')}
                - नाइट्रोजन: {params['नाइट्रोजन'] or 'N/A'} मिलीग्राम/किलोग्राम
                - फास्फोरस: {params['फास्फोरस'] or 'N/A'} मिलीग्राम/किलोग्राम
                - पोटैशियम: {params['पोटैशियम'] or 'N/A'} मिलीग्राम/किलोग्राम
                - एनडीवीआई: {params['एनडीवीआई'] or 'N/A'}
                - ईवीआई: {params['ईवीआई'] or 'N/A'}
                - एफवीसी: {params['एफवीसी'] or 'N/A'}
                उपयुक्त फसलों और सरल मिट्टी उपचारों का सुझाव दें, सरल और किसान-अनुकूल भाषा में।
                "•" से शुरू होने वाले बुलेट पॉइंट्स का उपयोग करें और ** या * जैसे मार्कडाउन फॉर्मेटिंग से बचें।
                """
                response = model.generate_content(prompt_recommendations)
                recommendations = response.text if response and response.text else "• सिफारिशें उपलब्ध नहीं हैं।"
            except Exception as e:
                logging.error(f"जेमिनी एपीआई त्रुटि: {e}")
                executive_summary = "• सारांश उपलब्ध नहीं है (एपीआई त्रुटि के कारण)।"
                recommendations = "• सिफारिशें उपलब्ध नहीं हैं (एपीआई त्रुटि के कारण)।"
        else:
            executive_summary = "• सारांश उपलब्ध नहीं है; जेमिनी एपीआई कॉन्फ़िगर नहीं है।"
            recommendations = "• सिफारिशें उपलब्ध नहीं हैं; जेमिनी एपीआई कॉन्फ़िगर नहीं है।"

        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=3*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, spaceAfter=12, alignment=TA_CENTER, fontName='NotoSerifDevanagari')
        h2 = ParagraphStyle('Heading2', parent=styles['Heading2'], fontSize=12, spaceAfter=10, fontName='NotoSerifDevanagari')
        body = ParagraphStyle('Body', parent=styles['BodyText'], fontSize=10, leading=12, fontName='NotoSerifDevanagari')

        elements = []
        if os.path.exists(LOGO_PATH):
            elements.append(Image(LOGO_PATH, width=6*cm, height=6*cm))
        elements.append(Paragraph("फार्ममैट्रिक्स मिट्टी स्वास्थ्य रिपोर्ट", title_style))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph(f"<b>स्थान:</b> {location}", body))
        elements.append(Paragraph(f"<b>तिथि सीमा:</b> {date_range}", body))
        elements.append(Paragraph(f"<b>उत्पन्न किया गया:</b> {datetime.now():%d %B %Y %H:%M}", body))
        elements.append(PageBreak())

        elements.append(Paragraph("1. कार्यकारी सारांश", h2))
        for line in executive_summary.split('\n'):
            elements.append(Paragraph(line.strip(), body))
        elements.append(Spacer(1, 0.5*cm))

        elements.append(Paragraph("2. मिट्टी पैरामीटर विश्लेषण", h2))
        table_data = [["पैरामीटर", "मान", "आदर्श सीमा", "व्याख्या"]]
        for param, value in params.items():
            if param == "मिट्टी की बनावट":
                value_text = TEXTURE_CLASSES.get(value, 'N/A')
                ideal = "दोमट" if value == 7 else "गैर-आदर्श"
            else:
                value_text = f"{value:.2f}" if value is not None else "N/A"
                min_val, max_val = IDEAL_RANGES.get(param, (None, None))
                ideal = f"{min_val}-{max_val}" if min_val and max_val else f"≤{max_val}" if max_val else f"≥{min_val}" if min_val else "N/A"
            interpretation = interpretations[param]
            table_data.append([param, value_text, ideal, Paragraph(interpretation, body)])
        tbl = Table(table_data, colWidths=[3*cm, 3*cm, 4*cm, 6*cm])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('FONTNAME', (0,0), (-1,-1), 'NotoSerifDevanagari'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BOX', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 0.5*cm))
        elements.append(PageBreak())
        elements.append(Paragraph("3. दृश्यीकरण", h2))
        for chart, path in [("पोषक तत्व स्तर", nutrient_chart), ("वनस्पति सूचकांक", vegetation_chart), ("मिट्टी के गुण", properties_chart)]:
            if path:
                elements.append(Paragraph(f"{chart}:", body))
                elements.append(Image(path, width=12*cm, height=6*cm))
                elements.append(Spacer(1, 0.2*cm))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(PageBreak())
        elements.append(Paragraph("4. फसल सिफारिशें और उपचार", h2))
        for line in recommendations.split('\n'):
            elements.append(Paragraph(line.strip(), body))
        elements.append(Spacer(1, 0.5*cm))

        elements.append(Paragraph("5. मिट्टी स्वास्थ्य रेटिंग", h2))
        elements.append(Paragraph(f"समग्र रेटिंग: <b>{rating} ({score:.1f}%)</b>", body))
        rating_desc = f"मिट्टी स्वास्थ्य स्कोर दिखाता है कि कितने पैरामीटर आदर्श हैं, जो {rating.lower()} स्थितियों को दर्शाता है।"
        elements.append(Paragraph(rating_desc, body))

        def add_header(canvas, doc):
            canvas.saveState()
            if os.path.exists(LOGO_PATH):
                canvas.drawImage(LOGO_PATH, 2*cm, A4[1] - 3*cm, width=2*cm, height=2*cm)
            canvas.setFont("NotoSerifDevanagari", 12)
            canvas.drawString(5*cm, A4[1] - 2.5*cm, "फार्ममैट्रिक्स मिट्टी स्वास्थ्य रिपोर्ट")
            canvas.setFont("NotoSerifDevanagari", 8)
            canvas.drawRightString(A4[0] - 2*cm, A4[1] - 2.5*cm, f"उत्पन्न किया गया: {datetime.now():%d %B %Y %H:%M}")
            canvas.restoreState()

        def add_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont("NotoSerifDevanagari", 8)
            canvas.drawCentredString(A4[0]/2, cm, f"पृष्ठ {doc.page}")
            canvas.restoreState()

        doc.build(elements, onFirstPage=add_header, onLaterPages=add_header, canvasmaker=canvas.Canvas)
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
    except Exception as e:
        logging.error(f"Error in generate_report: {e}")
        return None

# Streamlit UI
st.set_page_config(layout='wide', page_title="मिट्टी स्वास्थ्य डैशबोर्ड")
st.title("🌾 मिट्टी स्वास्थ्य डैशबोर्ड")
st.markdown("उपग्रह डेटा का उपयोग करके मिट्टी के स्वास्थ्य का विश्लेषण करें और एक विस्तृत रिपोर्ट डाउनलोड करें।")

# Sidebar Inputs
st.sidebar.header("📍 स्थान और पैरामीटर")
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]  # Default: Pune, IN
lat = st.sidebar.number_input("अक्षांश", value=st.session_state.user_location[0], format="%.6f")
lon = st.sidebar.number_input("देशांतर", value=st.session_state.user_location[1], format="%.6f")
st.session_state.user_location = [lat, lon]

st.sidebar.header("🧪 सीईसी मॉडल गुणांक")
cec_intercept = st.sidebar.number_input("अवरोधन", value=5.0, step=0.1)
cec_slope_clay = st.sidebar.number_input("ढलान (मिट्टी सूचकांक)", value=20.0, step=0.1)
cec_slope_om = st.sidebar.number_input("ढलान (ओएम सूचकांक)", value=15.0, step=0.1)

today = date.today()
start_date = st.sidebar.date_input("प्रारंभ तिथि", value=today - timedelta(days=16))
end_date = st.sidebar.date_input("समाप्ति तिथि", value=today)
if start_date > end_date:
    st.sidebar.error("प्रारंभ तिथि समाप्ति तिथि से पहले होनी चाहिए।")
    st.stop()

# Map
m = folium.Map(location=[lat, lon], zoom_start=15)
Draw(export=True).add_to(m)
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google").add_to(m)
folium.Marker([lat, lon], popup="केंद्र").add_to(m)
map_data = st_folium(m, width=700, height=500)

# Process Region
region = None
if map_data and "last_active_drawing" in map_data:
    try:
        sel = map_data["last_active_drawing"]
        if sel and "geometry" in sel and "coordinates" in sel["geometry"]:
            region = ee.Geometry.Polygon(sel["geometry"]["coordinates"])
        else:
            st.error("अमान्य क्षेत्र चयनित। एक मान्य बहुभुज ड्रा करें।")
    except Exception as e:
        st.error(f"क्षेत्र बनाने में त्रुटि: {e}")

if region:
    st.subheader(f"परिणाम: {start_date} से {end_date} तक")
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("सेंटिनल-2 डेटा प्राप्त कर रहा है…")
    all_bands = ["B2", "B3", "B4", "B8", "B11", "B12"]
    comp = sentinel_composite(region, start_date, end_date, all_bands)
    progress_bar.progress(20)

    status_text.text("मिट्टी की बनावट की गणना कर रहा है…")
    texc = get_soil_texture(region)
    progress_bar.progress(40)

    status_text.text("एलएसटी डेटा प्राप्त कर रहा है…")
    lst = get_lst(region, start_date, end_date)
    progress_bar.progress(60)

    if comp is None:
        st.warning("चयनित अवधि के लिए कोई सेंटिनल-2 डेटा उपलब्ध नहीं है।")
        ph = sal = oc = cec = ndwi = ndvi = evi = fvc = n_val = p_val = k_val = None
    else:
        status_text.text("मिट्टी पैरामीटरों की गणना कर रहा है…")
        ph = get_ph(comp, region)
        sal = get_salinity(comp, region)
        oc = get_organic_carbon(comp, region)
        cec = estimate_cec(comp, region, cec_intercept, cec_slope_clay, cec_slope_om)
        ndwi = get_ndwi(comp, region)
        ndvi = get_ndvi(comp, region)
        evi = get_evi(comp, region)
        fvc = get_fvc(comp, region)
        n_val, p_val, k_val = get_npk_for_region(comp, region)
        progress_bar.progress(100)
        status_text.text("पैरामीटर सफलतापूर्वक गणना किए गए।")

    params = {
        "पीएच": ph,
        "लवणता": sal,
        "कार्बनिक कार्बन": oc,
        "सीईसी": cec,
        "मिट्टी की बनावट": texc,
        "एलएसटी": lst,
        "एनडीडब्ल्यूआई": ndwi,
        "एनडीवीआई": ndvi,
        "ईवीआई": evi,
        "एफवीसी": fvc,
        "नाइट्रोजन": n_val,
        "फास्फोरस": p_val,
        "पोटैशियम": k_val
    }

    if st.button("मिट्टी रिपोर्ट उत्पन्न करें"):
        with st.spinner("रिपोर्ट उत्पन्न कर रहा है…"):
            location = f"अक्षांश: {lat:.6f}, देशांतर: {lon:.6f}"
            date_range = f"{start_date} से {end_date} तक"
            pdf_data = generate_report(params, location, date_range)
            if pdf_data:
                st.download_button(
                    label="रिपोर्ट डाउनलोड करें",
                    data=pdf_data,
                    file_name="मिट्टी_स्वास्थ्य_रिपोर्ट.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("रिपोर्ट उत्पन्न करने में विफल। विवरण के लिए लॉग जांचें।")
else:
    st.info("क्षेत्र का चयन करने के लिए मानचित्र पर एक बहुभुज ड्रा करें।")