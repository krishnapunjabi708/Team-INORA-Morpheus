import logging
import os
from datetime import datetime, date, timedelta
import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer, PageBreak
import openai
from folium.plugins import Draw
# --------------------------- Configuration ---------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set your Gemini API Key in Streamlit secrets
openai.api_key = "AIzaSyAWA9Kqh2FRtBmxRZmNlZ7pcfasG5RJmR8"

# --------------------------- Google Earth Engine Init ---------------------------
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# --------------------------- Constants & Lookups -----------------------------
SOIL_TEXTURE_IMG = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0')
TEXTURE_CLASSES = {
    1: "Clay", 2: "Silty Clay", 3: "Sandy Clay",
    4: "Clay Loam", 5: "Silty Clay Loam", 6: "Sandy Clay Loam",
    7: "Loam", 8: "Silty Loam", 9: "Sandy Loam",
    10: "Silt", 11: "Loamy Sand", 12: "Sand"
}

# --------------------------- Utility Functions -------------------------------
def safe_get_info(computed_obj, name="value"):
    if computed_obj is None:
        return None
    try:
        info = computed_obj.getInfo()
        return float(info) if info is not None else None
    except Exception as e:
        logging.warning(f"Failed to fetch {name}: {e}")
        return None

# Sentinel-2 composite with fallback
def sentinel_composite(region, start, end, bands, max_days=30, step=5):
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
    for days in range(step, max_days + 1, step):
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
            logging.info(f"Sentinel window expanded to {sd}–{ed} for bands {bands}")
            return coll.median().multiply(0.0001)
    return None

# Parameter extraction functions

def get_ph(comp, region):
    if comp is None: return None
    br = comp.expression("(B2+B3+B4)/3", {"B2": comp.select("B2"), "B3": comp.select("B3"), "B4": comp.select("B4")})
    sa = comp.expression("(B11-B8)/(B11+B8+1e-6)", {"B11": comp.select("B11"), "B8": comp.select("B8")})
    img = comp.expression(
        "7.1 + 0.15*B2 - 0.32*B11 + 1.2*br - 0.7*sa", 
        {"B2": comp.select("B2"), "B11": comp.select("B11"), "br": br, "sa": sa}
    ).rename("ph")
    return safe_get_info(
        img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ph"),
        "pH"
    )

def get_salinity(comp, region):
    if comp is None: return None
    img = comp.expression("(B11-B3)/(B11+B3+1e-6)", {"B11": comp.select("B11"), "B3": comp.select("B3")}).rename("ndsi")
    return safe_get_info(
        img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndsi"),
        "salinity"
    )

def get_organic_carbon(comp, region):
    if comp is None: return None
    ndvi = comp.normalizedDifference(["B8", "B4"])
    img = ndvi.multiply(0.05).rename("oc")
    return safe_get_info(
        img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("oc"),
        "organic carbon"
    )

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
    mode = SOIL_TEXTURE_IMG.clip(region.buffer(500)).reduceRegion(
        ee.Reducer.mode(), geometry=region, scale=250, maxPixels=1e13
    ).get("b0")
    val = safe_get_info(mode, "texture")
    return int(val) if val is not None else None

def get_lst(region, start, end):
    def fetch(r, sd, ed):
        sd_str = sd.strftime("%Y-%m-%d")
        ed_str = ed.strftime("%Y-%m-%d")
        coll = (
            ee.ImageCollection("MODIS/061/MOD11A2")
            .filterBounds(r.buffer(5000))
            .filterDate(sd_str, ed_str)
            .select("LST_Day_1km")
        )
        return coll, coll.size().getInfo()
    coll, cnt = fetch(region, start, end)
    if cnt == 0:
        sd = start - timedelta(days=8)
        ed = end + timedelta(days=8)
        coll, cnt = fetch(region, sd, ed)
    if cnt == 0:
        logging.warning("No MODIS LST data available.")
        return None
    img = coll.median().multiply(0.02).subtract(273.15).rename("lst").clip(region.buffer(5000))
    stats = img.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=region.buffer(5000), scale=1000,
        maxPixels=1e13, bestEffort=True
    ).getInfo()
    return float(stats.get("lst", None)) if stats else None

def get_ndwi(comp, region):
    if comp is None: return None
    img = comp.expression("(B3-B8)/(B3+B8+1e-6)", {"B3": comp.select("B3"), "B8": comp.select("B8")}).rename("ndwi")
    return safe_get_info(
        img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndwi"),
        "ndwi"
    )

def get_ndvi(comp, region):
    if comp is None: return None
    ndvi = comp.normalizedDifference(["B8", "B4"]).rename("ndvi")
    return safe_get_info(
        ndvi.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndvi"),
        "NDVI"
    )

def get_evi(comp, region):
    if comp is None: return None
    evi = comp.expression(
        "2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)",
        {"NIR": comp.select("B8"), "RED": comp.select("B4"), "BLUE": comp.select("B2")}
    ).rename("evi")
    return safe_get_info(
        evi.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("evi"),
        "EVI"
    )

def get_fvc(comp, region):
    if comp is None: return None
    ndvi = comp.normalizedDifference(["B8", "B4"]);
    ndvi_min, ndvi_max = 0.2, 0.8
    fvc = ndvi.subtract(ndvi_min).divide(nddi_max-nddi_min).pow(2).clamp(0,1).rename("fvc")
    return safe_get_info(
        fvc.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("fvc"),
        "FVC"
    )

def get_npk_for_region(comp, region):
    if comp is None: return None, None, None
    brightness = comp.expression('(B2 + B3 + B4) / 3', {'B2': comp.select('B2'), 'B3': comp.select('B3'), 'B4': comp.select('B4')})
    sal2 = comp.expression('(B11 - B8) / (B11 + B8 + 1e-6)', {'B11': comp.select('B11'), 'B8': comp.select('B8')})
    N_est = comp.expression("5 + 100*(3 - (B2 + B3 + B4))", {'B2': comp.select('B2'),'B3': comp.select('B3'),'B4': comp.select('B4')}).rename('N')
    P_est = comp.expression("3 + 50*(1 - B8) + 20*(1 - B11)", {'B8': comp.select('B8'),'B11': comp.select('B11')}).rename('P')
    K_est = comp.expression("5 + 150*(1 - brightness) + 50*(1 - B3) + 30*sal2", {'brightness': brightness,'B3': comp.select('B3'),'sal2': sal2}).rename('K')
    npk_img = N_est.addBands(P_est).addBands(K_est)
    stats = npk_img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e9).getInfo()
    return stats.get('N'), stats.get('P'), stats.get('K')

# --------------------------- Gemini Report Generation -----------------------------
def generate_report_text(parameters, language="en"):
    prompt = f"Generate a brief, farmer-friendly agricultural report summary in {'Hindi' if language=='hi' else 'English'}. "
    prompt += "For each parameter provide a simple sentence explaining the reading. "
    for p in parameters:
        prompt += f"{p['name']} is {p['value']:.2f}, "
    prompt += "Keep language simple and actionable."
    response = openai.ChatCompletion.create(
        model="gemini-pro",
        messages=[{"role":"user","content":prompt}]
    )
    return response.choices[0].message.content.strip()

# --------------------------- Streamlit UI ------------------------------
st.set_page_config(layout='wide', page_title="Soil & Crop Dashboard + Report")
st.title("🌾 Soil & Crop Parameter Dashboard with Report Generator")

# Sidebar inputs
st.sidebar.header("Settings")
language = st.sidebar.selectbox("Report Language", ['English','Hindi'])
cec_intercept = st.sidebar.number_input("CEC Intercept", value=5.0)
cec_slope_clay = st.sidebar.number_input("CEC Slope (Clay)", value=20.0)
cec_slope_om = st.sidebar.number_input("CEC Slope (OM)", value=15.0)
today = date.today()
start_date = st.sidebar.date_input("Start Date", today - timedelta(days=16))
end_date = st.sidebar.date_input("End Date", today)
logo_file = st.sidebar.file_uploader("Upload Logo (PNG/JPG)", type=['png','jpg','jpeg'])

# Map for ROI
def draw_map():
    m = folium.Map(location=[18.4575,73.8503], zoom_start=13)
    Draw(export=True).add_to(m)
    folium.Marker([18.4575,73.8503], popup="Center").add_to(m)
    return st_folium(m, width=700, height=400)
map_data = draw_map()
region = None
if map_data and map_data.get("last_active_drawing"):
    coords = map_data["last_active_drawing"]["geometry"]["coordinates"]
    region = ee.Geometry.Polygon(coords)
else:
    st.info("🔍 Draw a polygon to analyze.")

if region:
    st.subheader("Computing parameters…")
    comp = sentinel_composite(region, start_date, end_date, ["B2","B3","B4","B8","B11","B12"])
    # compute individual parameters
    tex = get_soil_texture(region)
    lst = get_lst(region, start_date, end_date)
    ph = sal = oc = cec = ndwi = ndvi = evi = fvc = None
    n_val = p_val = k_val = None
    if comp:
        ph = get_ph(comp, region)
        sal = get_salinity(comp, region)
        oc = get_organic_carbon(comp, region)
        cec = estimate_cec(comp, region, cec_intercept, cec_slope_clay, cec_slope_om)
        ndwi = get_ndwi(comp, region)
        ndvi = get_ndvi(comp, region)
        evi = get_evi(comp, region)
        fvc = get_fvc(comp, region)
        n_val, p_val, k_val = get_npk_for_region(comp, region)

    params = [
        {"name":"Soil pH","value":ph or 0,"ideal":"6.0-7.5","info":"मिट्टी अम्लता/क्षारीयता"},
        {"name":"Texture","value":tex or 0,"ideal":"Loam","info":TEXTURE_CLASSES.get(tex)},
        {"name":"Salinity","value":sal or 0,"ideal":"<0.2","info":"मिट्टी लवणता"},
        {"name":"Organic C (%)","value":(oc*100) if oc else 0,"ideal":"2-5%","info":"जैविक पदार्थ"},
        {"name":"CEC","value":cec or 0,"ideal":"10-30","info":"कॅटायन एक्सचेंज क्षमता"},
        {"name":"LST (°C)","value":lst or 0,"ideal":"10-30","info":"पृष्ठ ताप"},
        {"name":"NDWI","value":ndwi or 0,"ideal":"0-0.5","info":"पानी संकेत"},
        {"name":"NDVI","value":ndvi or 0,"ideal":"0.2-0.8","info":"वनस्पति स्वास्थ्य"},
        {"name":"EVI","value":evi or 0,"ideal":"0.2-0.8","info":"विस्तारित वनस्पति"},
        {"name":"FVC","value":fvc or 0,"ideal":"0.3-0.8","info":"पौधा आवरण"},
        {"name":"Nitrogen","value":n_val or 0,"ideal":"20-40 ppm","info":"पोषक"},
        {"name":"Phosphorus","value":p_val or 0,"ideal":"10-30 ppm","info":"पोषक"},
        {"name":"Potassium","value":k_val or 0,"ideal":"15-40 ppm","info":"पोषक"}
    ]

    summary = generate_report_text(params, 'hi' if language=='Hindi' else 'en')
    st.markdown(f"**Report Summary:** {summary}")

    if st.button("Generate PDF Report"):
        pdf_path = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Center', alignment=1))

        # Header
        if logo_file:
            logo = Image(logo_file, width=80, height=80)
            logo.hAlign='RIGHT'
            story.append(logo)
        story.append(Paragraph("Soil & Crop Analysis Report", styles['Title']))
        story.append(Spacer(1,12))

        # Table
        data = [["Parameter","Value","Ideal","Notes"]]
        for p in params:
            data.append([p['name'], f"{p['value']:.2f}", p['ideal'], p['info']])
        tbl = Table(data, hAlign='LEFT')
        tbl.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.grey),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
            ('GRID',(0,0),(-1,-1),1,colors.black)
        ]))
        story.append(tbl)
        story.append(PageBreak())

        # Chart
        names = [p['name'] for p in params]
        values = [p['value'] for p in params]
        plt.figure()
        plt.bar(names, values)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        chart_file = 'chart.png'
        plt.savefig(chart_file)
        story.append(Image(chart_file, width=400, height=200))
        story.append(Spacer(1,12))

        # Summary
        story.append(Paragraph(summary, styles['BodyText']))
        doc.build(story)

        with open(pdf_path, 'rb') as f:
            st.download_button("Download Report", f, file_name=os.path.basename(pdf_path))
