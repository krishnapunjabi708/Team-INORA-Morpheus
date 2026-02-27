import logging
import os
from datetime import datetime, date, timedelta
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
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, ListFlowable, ListItem, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfgen import canvas
from io import BytesIO
import json
try:
    import google.generativeai as genai
except ImportError:
    genai = None
    logging.warning("google-generativeai not installed. Using placeholder data.")

# Configuration
API_KEY = "AIzaSyAWA9Kqh2FRtBmxRZmNlZ7pcfasG5RJmR8"  # Replace with your actual Gemini API key
MODEL = "gemini-1.5-flash"
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
    1: "Clay", 2: "Silty Clay", 3: "Sandy Clay",
    4: "Clay Loam", 5: "Silty Clay Loam", 6: "Sandy Clay Loam",
    7: "Loam", 8: "Silty Loam", 9: "Sandy Loam",
    10: "Silt", 11: "Loamy Sand", 12: "Sand"
}
IDEAL_RANGES = {
    "pH": (6.0, 7.5),
    "Salinity": (None, 0.2),
    "Organic Carbon": (0.02, 0.05),  # 2-5%
    "CEC": (10, 30),
    "Soil Texture": 7,  # Loam
    "LST": (10, 30),
    "NDWI": (0, 0.5),
    "NDVI": (0.2, 0.8),
    "EVI": (0.2, 0.8),
    "FVC": (0.3, 0.8),
    "Nitrogen": (20, 40),
    "Phosphorus": (10, 30),
    "Potassium": (15, 40)
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
    coll = (
        ee.ImageCollection("COPERNICUS/S2_SR")
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
            ee.ImageCollection("COPERNICUS/S2_SR")
            .filterDate(sd, ed)
            .filterBounds(region)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
            .select(bands)
        )
        if coll.size().getInfo() > 0:
            logging.info(f"Sentinel window expanded to {sd}–{ed}")
            return coll.median().multiply(0.0001)
    return None

# Updated get_lst Function
def get_lst(region, start, end):
    current_date = date.today()
    
    # Adjust end date if it’s in the future
    if end > current_date:
        logging.warning(f"End date {end} is in the future. Adjusting to {current_date}.")
        end = current_date
    
    # Ensure start date isn’t after end date
    if start > end:
        logging.warning(f"Start date {start} is after end date {end}. Setting start to end date.")
        start = end

    # Convert dates to strings for Earth Engine
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    
    # Fetch MODIS LST collection
    coll = (ee.ImageCollection("MODIS/061/MOD11A2")
            .filterBounds(region.buffer(5000))
            .filterDate(start_str, end_str)
            .select("LST_Day_1km"))
    
    # Check if the collection has data
    cnt = coll.size().getInfo()
    if cnt > 0:
        # Compute median LST over the range
        img = coll.median()
    else:
        # Fetch the most recent image before the end date if no data exists
        logging.info("No data in range. Fetching most recent image before end date.")
        coll = (ee.ImageCollection("MODIS/061/MOD11A2")
                .filterBounds(region.buffer(5000))
                .filterDate("2000-01-01", end_str)
                .select("LST_Day_1km")
                .sort('system:time_start', False))
        if coll.size().getInfo() == 0:
            logging.warning("No MODIS LST data available up to the end date.")
            return None
        img = coll.first()
    
    # Convert LST from Kelvin to Celsius and clip to region
    img = img.multiply(0.02).subtract(273.15).rename("lst").clip(region.buffer(5000))
    
    # Compute mean LST over the region
    stats = img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=1000,
        maxPixels=1e13
    ).getInfo()
    
    # Safely retrieve and return the LST value
    lst_value = stats.get("lst", None)
    if lst_value is not None:
        return float(lst_value)
    else:
        logging.warning("No LST data found for the region.")
        return None
# Parameter Functions
def get_ph(comp, region):
    if comp is None: return None
    br = comp.expression("(B2+B3+B4)/3", {"B2": comp.select("B2"), "B3": comp.select("B3"), "B4": comp.select("B4")})
    sa = comp.expression("(B11-B8)/(B11+B8+1e-6)", {"B11": comp.select("B11"), "B8": comp.select("B8")})
    img = comp.expression("7.1 + 0.15*B2 - 0.32*B11 + 1.2*br - 0.7*sa", {"B2": comp.select("B2"), "B11": comp.select("B11"), "br": br, "sa": sa}).rename("ph")
    return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ph"), "pH")

def get_salinity(comp, region):
    if comp is None: return None
    img = comp.expression("(B11-B3)/(B11+B3+1e-6)", {"B11": comp.select("B11"), "B3": comp.select("B3")}).rename("ndsi")
    return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndsi"), "salinity")

def get_organic_carbon(comp, region):
    if comp is None: return None
    ndvi = comp.normalizedDifference(["B8", "B4"])
    img = ndvi.multiply(0.05).rename("oc")
    return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("oc"), "organic carbon")

def estimate_cec(comp, region, intercept, slope_clay, slope_om):
    if comp is None: return None
    clay = comp.expression("(B11-B8)/(B11+B8+1e-6)", {"B11": comp.select("B11"), "B8": comp.select("B8")}).rename("clay")
    om = comp.expression("(B8-B4)/(B8+B4+1e-6)", {"B8": comp.select("B8"), "B4": comp.select("B4")}).rename("om")
    c_m = safe_get_info(clay.reduceRegion(ee.Reducer.mean(), geometry=region, scale=20, maxPixels=1e13).get("clay"), "clay")
    o_m = safe_get_info(om.reduceRegion(ee.Reducer.mean(), geometry=region, scale=20, maxPixels=1e13).get("om"), "om")
    if c_m is None or o_m is None:
        return None
    return intercept + slope_clay * c_m + slope_om * o_m

def get_soil_texture(region):
    mode = SOIL_TEXTURE_IMG.clip(region.buffer(500)).reduceRegion(ee.Reducer.mode(), geometry=region, scale=250, maxPixels=1e13).get("b0")
    val = safe_get_info(mode, "texture")
    return int(val) if val is not None else None

def get_ndwi(comp, region):
    if comp is None: return None
    img = comp.expression("(B3-B8)/(B3+B8+1e-6)", {"B3": comp.select("B3"), "B8": comp.select("B8")}).rename("ndwi")
    return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndwi"), "NDWI")

def get_ndvi(comp, region):
    if comp is None: return None
    ndvi = comp.normalizedDifference(["B8", "B4"]).rename("ndvi")
    return safe_get_info(ndvi.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndvi"), "NDVI")

def get_evi(comp, region):
    if comp is None: return None
    evi = comp.expression(
        "2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)",
        {"NIR": comp.select("B8"), "RED": comp.select("B4"), "BLUE": comp.select("B2")}
    ).rename("evi")
    return safe_get_info(evi.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("evi"), "EVI")

def get_fvc(comp, region):
    if comp is None: return None
    ndvi = comp.normalizedDifference(["B8", "B4"])
    ndvi_min = 0.2
    ndvi_max = 0.8
    fvc = ndvi.subtract(ndvi_min).divide(ndvi_max - ndvi_min).pow(2).clamp(0, 1).rename("fvc")
    return safe_get_info(fvc.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("fvc"), "FVC")

def get_npk_for_region(comp, region):
    if comp is None: return None, None, None
    brightness = comp.expression('(B2 + B3 + B4) / 3', {'B2': comp.select('B2'), 'B3': comp.select('B3'), 'B4': comp.select('B4')})
    salinity2 = comp.expression('(B11 - B8) / (B11 + B8 + 1e-6)', {'B11': comp.select('B11'), 'B8': comp.select('B8')})
    N_est = comp.expression("5 + 100*(3 - (B2 + B3 + B4))", {'B2': comp.select('B2'), 'B3': comp.select('B3'), 'B4': comp.select('B4')}).rename('N')
    P_est = comp.expression("3 + 50*(1 - B8) + 20*(1 - B11)", {'B8': comp.select('B8'), 'B11': comp.select('B11')}).rename('P')
    K_est = comp.expression("5 + 150*(1 - brightness) + 50*(1 - B3) + 30*salinity2", {'brightness': brightness, 'B3': comp.select('B3'), 'salinity2': salinity2}).rename('K')
    npk_image = N_est.addBands(P_est).addBands(K_est)
    stats = npk_image.reduceRegion(reducer=ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e9).getInfo()
    return stats.get('N', None), stats.get('P', None), stats.get('K', None)

# Report Generation Functions
def calculate_soil_health_score(params):
    score = 0
    total_params = len(params)
    for param, value in params.items():
        if value is None:
            continue
        if param == "Soil Texture":
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
    rating = "Excellent" if percentage >= 80 else "Good" if percentage >= 60 else "Fair" if percentage >= 40 else "Poor"
    return percentage, rating

def generate_interpretation(param, value):
    if value is None:
        return "Data unavailable."
    if param == "Soil Texture":
        return TEXTURE_CLASSES.get(value, "Unknown texture class.")
    min_val, max_val = IDEAL_RANGES.get(param, (float('-inf'), float('inf')))
    if min_val is None:
        range_text = f"<= {max_val}"
        return f"Optimal; within ideal range ({range_text})." if value <= max_val else f"High; above ideal range (> {max_val})."
    elif max_val is None:
        range_text = f">= {min_val}"
        return f"Optimal; within ideal range ({range_text})." if value >= min_val else f"Low; below ideal range (< {min_val})."
    else:
        range_text = f"{min_val}-{max_val}"
        if min_val <= value <= max_val:
            return f"Optimal; within ideal range ({range_text})."
        elif value < min_val:
            return f"Low; below ideal range (< {min_val})."
        else:
            return f"High; above ideal range (> {max_val})."

def make_nutrient_chart(n_val, p_val, k_val):
    nutrients = ["Nitrogen", "Phosphorus", "Potassium"]
    values = [n_val or 0, p_val or 0, k_val or 0]
    plt.figure(figsize=(6, 4))
    bars = plt.bar(nutrients, values, color='forestgreen', alpha=0.7)
    plt.title("Soil Nutrient Levels (ppm)", fontsize=12)
    plt.ylabel("Concentration (ppm)")
    plt.ylim(0, max(values) * 1.2 if any(values) else 100)
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.5, f"{yval:.1f}", ha='center', va='bottom')
    plt.tight_layout()
    chart_path = "nutrient_chart.png"
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path

def make_vegetation_chart(ndvi, evi, fvc):
    indices = ["NDVI", "EVI", "FVC"]
    values = [ndvi or 0, evi or 0, fvc or 0]
    plt.figure(figsize=(6, 4))
    bars = plt.bar(indices, values, color='darkgreen', alpha=0.7)
    plt.title("Vegetation Indices", fontsize=12)
    plt.ylabel("Value")
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.01, f"{yval:.2f}", ha='center', va='bottom')
    plt.tight_layout()
    chart_path = "vegetation_chart.png"
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path

def make_soil_properties_chart(ph, sal, oc, cec, lst):
    properties = ["pH", "Salinity", "Organic Carbon (%)", "CEC", "LST"]
    values = [ph or 0, sal or 0, (oc * 100 if oc else 0), cec or 0, lst or 0]
    plt.figure(figsize=(8, 4))
    bars = plt.bar(properties, values, color='sandybrown', alpha=0.7)
    plt.title("Soil Properties", fontsize=12)
    plt.ylabel("Value")
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.05 * max(values, default=1), f"{yval:.2f}", ha='center', va='bottom')
    plt.tight_layout()
    chart_path = "properties_chart.png"
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path

def generate_report(params, location, date_range):
    score, rating = calculate_soil_health_score(params)
    interpretations = {param: generate_interpretation(param, value) for param, value in params.items()}

    nutrient_chart = make_nutrient_chart(params["Nitrogen"], params["Phosphorus"], params["Potassium"])
    vegetation_chart = make_vegetation_chart(params["NDVI"], params["EVI"], params["FVC"])
    properties_chart = make_soil_properties_chart(params["pH"], params["Salinity"], params["Organic Carbon"], params["CEC"], params["LST"])

    if genai:
        try:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel(MODEL)
            prompt = f"""
            Generate an executive summary for a soil health report with:
            - Location: {location}
            - Date Range: {date_range}
            - Soil Health Score: {score:.1f}% ({rating})
            - Parameters: pH={params['pH'] or 'N/A'}, Salinity={params['Salinity'] or 'N/A'}, Organic Carbon={params['Organic Carbon']*100 if params['Organic Carbon'] else 'N/A'}%, CEC={params['CEC'] or 'N/A'}, Soil Texture={TEXTURE_CLASSES.get(params['Soil Texture'], 'N/A')}, N={params['Nitrogen'] or 'N/A'}, P={params['Phosphorus'] or 'N/A'}, K={params['Potassium'] or 'N/A'}
            Provide a brief overview and critical issues.
            """
            response = model.generate_content(prompt)
            executive_summary = response.text if response and response.text else "Summary unavailable."
            
            prompt_recommendations = f"""
            Based on:
            - pH: {params['pH'] or 'N/A'}
            - Salinity: {params['Salinity'] or 'N/A'}
            - Organic Carbon: {params['Organic Carbon']*100 if params['Organic Carbon'] else 'N/A'}%
            - CEC: {params['CEC'] or 'N/A'}
            - Soil Texture: {TEXTURE_CLASSES.get(params['Soil Texture'], 'N/A')}
            - Nitrogen: {params['Nitrogen'] or 'N/A'} ppm
            - Phosphorus: {params['Phosphorus'] or 'N/A'} ppm
            - Potassium: {params['Potassium'] or 'N/A'} ppm
            - NDVI: {params['NDVI'] or 'N/A'}
            - EVI: {params['EVI'] or 'N/A'}
            - FVC: {params['FVC'] or 'N/A'}
            Suggest crops and soil treatments.
            """
            response = model.generate_content(prompt_recommendations)
            recommendations = response.text if response and response.text else "Recommendations unavailable."
        except Exception as e:
            logging.error(f"Gemini API error: {e}")
            executive_summary = "Summary unavailable due to API error."
            recommendations = "Recommendations unavailable due to API error."
    else:
        executive_summary = "Summary unavailable; Gemini API not configured."
        recommendations = "Recommendations unavailable; Gemini API not configured."

    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=3*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, spaceAfter=12, alignment=TA_CENTER)
    h2 = ParagraphStyle('Heading2', parent=styles['Heading2'], fontSize=12, spaceAfter=10)
    body = ParagraphStyle('Body', parent=styles['BodyText'], fontSize=10, leading=12)

    elements = []

    elements.append(Paragraph("FarmMatrix Soil Health Report", title_style))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(f"Location: {location}", body))
    elements.append(Paragraph(f"Date Range: {date_range}", body))
    elements.append(Paragraph(f"Generated on: {datetime.now():%B %d, %Y %H:%M}", body))
    elements.append(PageBreak())

    elements.append(Paragraph("1. Executive Summary", h2))
    elements.append(Paragraph(executive_summary, body))
    elements.append(Spacer(1, 0.5*cm))

    elements.append(Paragraph("2. Soil Parameter Analysis", h2))
    table_data = [["Parameter", "Value", "Ideal Range", "Interpretation"]]
    for param, value in params.items():
        if param == "Soil Texture":
            value_text = TEXTURE_CLASSES.get(value, 'N/A')
            ideal = "Loam" if value == 7 else "Non-ideal"
        else:
            value_text = f"{value:.2f}" if value is not None else "N/A"
            min_val, max_val = IDEAL_RANGES.get(param, (None, None))
            ideal = f"{min_val}-{max_val}" if min_val and max_val else f"<= {max_val}" if max_val else f">= {min_val}" if min_val else "N/A"
        table_data.append([param, value_text, ideal, interpretations[param]])
    tbl = Table(table_data, colWidths=[3*cm, 3*cm, 4*cm, 6*cm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOX', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.5*cm))

    elements.append(Paragraph("3. Visualizations", h2))
    elements.append(Image(nutrient_chart, width=12*cm, height=6*cm))
    elements.append(Image(vegetation_chart, width=12*cm, height=6*cm))
    elements.append(Image(properties_chart, width=12*cm, height=6*cm))
    elements.append(Spacer(1, 0.5*cm))

    elements.append(Paragraph("4. Crop Recommendations & Treatments", h2))
    elements.append(Paragraph(recommendations, body))
    elements.append(Spacer(1, 0.5*cm))

    elements.append(Paragraph("5. Soil Health Rating", h2))
    elements.append(Paragraph(f"Overall Rating: <b>{rating} ({score:.1f}%)</b>", body))
    rating_desc = f"The soil health score reflects the proportion of parameters within ideal ranges, indicating {rating.lower()} conditions."
    elements.append(Paragraph(rating_desc, body))

    def add_header(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(5*cm, A4[1] - 2.5*cm, "FarmMatrix Soil Health Report")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(A4[0] - 2*cm, A4[1] - 2.5*cm, f"Generated: {datetime.now():%B %d, %Y %H:%M}")
        canvas.restoreState()

    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(A4[0]/2, cm, f"Page {doc.page}")
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_header, onLaterPages=add_header, canvasmaker=canvas.Canvas)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()

# Streamlit UI
st.set_page_config(layout='wide', page_title="Soil Health Dashboard")
st.title("🌾 Soil Health Dashboard")
st.markdown("Analyze soil parameters and generate a detailed report based on satellite data.")

# Sidebar Inputs
st.sidebar.header("📍 Location & Parameters")
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]  # Default: Pune, IN
lat = st.sidebar.number_input("Latitude", value=st.session_state.user_location[0], format="%.6f")
lon = st.sidebar.number_input("Longitude", value=st.session_state.user_location[1], format="%.6f")
st.session_state.user_location = [lat, lon]

st.sidebar.header("🧪 CEC Model Coefficients")
cec_intercept = st.sidebar.number_input("Intercept", value=5.0, step=0.1)
cec_slope_clay = st.sidebar.number_input("Slope (Clay Index)", value=20.0, step=0.1)
cec_slope_om = st.sidebar.number_input("Slope (OM Index)", value=15.0, step=0.1)

today = date.today()
start_date = st.sidebar.date_input("Start Date", value=today - timedelta(days=16))
end_date = st.sidebar.date_input("End Date", value=today)

# Map
m = folium.Map(location=[lat, lon], zoom_start=15)
Draw(export=True).add_to(m)
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google").add_to(m)
folium.Marker([lat, lon], popup="Center").add_to(m)
map_data = st_folium(m, width=700, height=500)

# Process Region
region = None
if map_data and "last_active_drawing" in map_data:
    try:
        sel = map_data["last_active_drawing"]
        region = ee.Geometry.Polygon(sel["geometry"]["coordinates"])
    except Exception as e:
        st.error(f"Error creating region: {e}")

if region:
    st.subheader(f"Results: {start_date} to {end_date}")
    with st.spinner("Computing parameters…"):
        all_bands = ["B2", "B3", "B4", "B8", "B11", "B12"]
        comp = sentinel_composite(region, start_date, end_date, all_bands)
        texc = get_soil_texture(region)
        lst = get_lst(region, start_date, end_date)
        if comp is None:
            st.warning("No Sentinel-2 data available.")
            ph = sal = oc = cec = ndwi = ndvi = evi = fvc = n_val = p_val = k_val = None
        else:
            ph = get_ph(comp, region)
            sal = get_salinity(comp, region)
            oc = get_organic_carbon(comp, region)
            cec = estimate_cec(comp, region, cec_intercept, cec_slope_clay, cec_slope_om)
            ndwi = get_ndwi(comp, region)
            ndvi = get_ndvi(comp, region)
            evi = get_evi(comp, region)
            fvc = get_fvc(comp, region)
            n_val, p_val, k_val = get_npk_for_region(comp, region)

    params = {
        "pH": ph,
        "Salinity": sal,
        "Organic Carbon": oc,
        "CEC": cec,
        "Soil Texture": texc,
        "LST": lst,
        "NDWI": ndwi,
        "NDVI": ndvi,
        "EVI": evi,
        "FVC": fvc,
        "Nitrogen": n_val,
        "Phosphorus": p_val,
        "Potassium": k_val
    }

    if st.button("Generate Soil Report"):
        with st.spinner("Generating report…"):
            location = f"Lat: {lat}, Lon: {lon}"
            date_range = f"{start_date} to {end_date}"
            pdf_data = generate_report(params, location, date_range)
            st.download_button(
                label="Download Report",
                data=pdf_data,
                file_name="soil_health_report.pdf",
                mime="application/pdf"
            )
else:
    st.info("Please draw a polygon on the map to define your region.")