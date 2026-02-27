import logging
import os
from datetime import date, timedelta

import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import pandas as pd
from folium.plugins import Draw

# ---------------------------
# Logging Configuration
# ---------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------------
# Initialize Google Earth Engine
# ---------------------------
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# ---------------------------
# Constants & Lookups
# ---------------------------
SOIL_TEXTURE_IMG = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0')
TEXTURE_CLASSES = {
    1: "Clay", 2: "Silty Clay", 3: "Sandy Clay",
    4: "Clay Loam", 5: "Silty Clay Loam", 6: "Sandy Clay Loam",
    7: "Loam", 8: "Silty Loam", 9: "Sandy Loam",
    10: "Silt", 11: "Loamy Sand", 12: "Sand"
}

# ---------------------------
# Utility: Safe Server Call
# ---------------------------
def safe_get_info(computed_obj, name="value"):
    if computed_obj is None:
        return None
    try:
        info = computed_obj.getInfo()
        return float(info) if info is not None else None
    except Exception as e:
        logging.warning(f"Failed to fetch {name}: {e}")
        return None

# ---------------------------
# Utility: Sentinel-2 Composite with Fallback
# ---------------------------
def sentinel_composite(region, start, end, bands, max_days=30, step=5):
    coll = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start, end)
        .filterBounds(region)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .select(bands)
    )
    if coll.size().getInfo() > 0:
        return coll.median().multiply(0.0001)
    for days in range(step, max_days+1, step):
        sd = (pd.to_datetime(start) - timedelta(days=days)).strftime("%Y-%m-%d")
        ed = (pd.to_datetime(end)   + timedelta(days=days)).strftime("%Y-%m-%d")
        coll = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(sd, ed)
            .filterBounds(region)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
            .select(bands)
        )
        if coll.size().getInfo() > 0:
            logging.info(f"Sentinel window expanded to {sd}–{ed} for bands {bands}")
            return coll.median().multiply(0.0001)
    return None

# ---------------------------
# Streamlit UI Setup
# ---------------------------
st.set_page_config(layout='wide', page_title="Small Farm Soil & Crop Dashboard")
st.title("🌾 Small-Farm Near-Real-Time Soil Dashboard")
st.markdown("""
Use the drawing tool to trace your farm boundary.  
This dashboard uses a 5-day window for Sentinel-1 soil moisture and 16-day for other parameters.  
Parameters: pH, Texture, Salinity (NDSI), Organic Carbon, CEC, LST, Soil Moisture Index (% via S1)
""")

# Sidebar Inputs
st.sidebar.header("📍 Location & Model Parameters")
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]
lat = st.sidebar.number_input("Latitude", value=st.session_state.user_location[0], format="%.6f")
lon = st.sidebar.number_input("Longitude", value=st.session_state.user_location[1], format="%.6f")
st.session_state.user_location = [lat, lon]

st.sidebar.header("🧪 CEC Model Coefficients")
cec_intercept  = st.sidebar.number_input("Intercept",          value=5.0,  step=0.1)
cec_slope_clay = st.sidebar.number_input("Slope (Clay Index)", value=20.0, step=0.1)
cec_slope_om   = st.sidebar.number_input("Slope (OM Index)",   value=15.0, step=0.1)

# Date Windows
today       = date.today()
start_s1    = today - timedelta(days=5)
end_s1      = today
start_s2    = today - timedelta(days=16)
end_s2      = today
start_s1_str= start_s1.strftime("%Y-%m-%d")
end_s1_str  = end_s1.strftime("%Y-%m-%d")
start_s2_str= start_s2.strftime("%Y-%m-%d")
end_s2_str  = end_s2.strftime("%Y-%m-%d")

# Map & Drawing
m = folium.Map(location=[lat, lon], zoom_start=14)
Draw(export=True).add_to(m)
folium.TileLayer(
    "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", 
    attr="Google"
).add_to(m)
folium.Marker([lat, lon], popup="Center").add_to(m)
map_data = st_folium(m, width=700, height=500)
if map_data and map_data.get("last_active_drawing"):
    coords = map_data["last_active_drawing"]["geometry"]["coordinates"]
    region = ee.Geometry.Polygon(coords if isinstance(coords[0][0], (float,int)) else coords[0])
else:
    region = ee.Geometry.Point(lon, lat).buffer(10)

# ---------------------------
# Parameter Functions
# ---------------------------

def get_ph(region, start, end):
    comp = sentinel_composite(region, start, end, ["B2","B3","B4","B8","B11"])
    if comp is None: return None
    br = comp.expression("(B2+B3+B4)/3", {"B2":comp.select("B2"),"B3":comp.select("B3"),"B4":comp.select("B4")})
    sa = comp.expression("(B11-B8)/(B11+B8+1e-6)", {"B11":comp.select("B11"),"B8":comp.select("B8")})
    img = comp.expression(
        "7.1 + 0.15*B2 - 0.32*B11 + 1.2*br - 0.7*sa",
        {"B2":comp.select("B2"),"B11":comp.select("B11"),"br":br,"sa":sa}
    ).rename("ph")
    return safe_get_info(
        img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ph"),
        "pH"
    )

def get_salinity(region, start, end):
    comp = sentinel_composite(region, start, end, ["B3","B11"])
    if comp is None: return None
    img = comp.expression("(B11-B3)/(B11+B3+1e-6)", {"B11":comp.select("B11"),"B3":comp.select("B3")}).rename("ndsi")
    return safe_get_info(
        img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndsi"),
        "salinity"
    )

def get_organic_carbon(region, start, end):
    comp = sentinel_composite(region, start, end, ["B4","B8"])
    if comp is None: return None
    ndvi = comp.normalizedDifference(["B8","B4"])
    img = ndvi.multiply(0.05).rename("oc")
    return safe_get_info(
        img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("oc"),
        "organic carbon"
    )

def estimate_cec(region, start, end, intercept, slope_clay, slope_om):
    comp = sentinel_composite(region, start, end, ["B2","B4","B8","B11","B12"])
    if comp is None: return None
    clay = comp.expression("(B11-B8)/(B11+B8+1e-6)", {"B11":comp.select("B11"),"B8":comp.select("B8")}).rename("clay")
    om   = comp.expression("(B8-B4)/(B8+B4+1e-6)", {"B8":comp.select("B8"),"B4":comp.select("B4")}).rename("om")
    c_m = safe_get_info(clay.reduceRegion(ee.Reducer.mean(), geometry=region, scale=20, maxPixels=1e13).get("clay"), "clay")
    o_m = safe_get_info(om  .reduceRegion(ee.Reducer.mean(), geometry=region, scale=20, maxPixels=1e13).get("om"),   "om")
    return None if c_m is None or o_m is None else intercept + slope_clay*c_m + slope_om*o_m

def get_soil_texture(region):
    mode = SOIL_TEXTURE_IMG.clip(region.buffer(500)).reduceRegion(
        ee.Reducer.mode(), geometry=region, scale=250, maxPixels=1e13
    ).get("b0")
    val = safe_get_info(mode, "texture")
    return int(val) if val is not None else None

def get_lst(region, start, end):
    def fetch(r, sd, ed):
        coll = ee.ImageCollection("MODIS/061/MOD11A2").filterBounds(r.buffer(5000)).filterDate(sd, ed).select("LST_Day_1km")
        return coll, coll.size().getInfo()
    coll, cnt = fetch(region, start, end)
    if cnt == 0:
        sd = (pd.to_datetime(start) - timedelta(days=8)).strftime("%Y-%m-%d")
        ed = (pd.to_datetime(end)   + timedelta(days=8)).strftime("%Y-%m-%d")
        coll, cnt = fetch(region, sd, ed)
    if cnt == 0: return None
    img = coll.median().multiply(0.02).subtract(273.15).rename("lst").clip(region.buffer(5000))
    stats = img.reduceRegion(ee.Reducer.mean(), geometry=region.buffer(5000), scale=1000, maxPixels=1e13, bestEffort=True).getInfo()
    return float(stats.get("lst", None)) if stats else None

def get_soil_moisture(region, start, end):
    coll = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterDate(start, end)
        .filterBounds(region)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .select(["VV","VH"])
    )
    count = coll.size().getInfo()
    logging.info(f"Found {count} S1 images for moisture.")
    if count == 0:
        return None
    img = coll.median()
    ratio = img.expression("(VV - VH)/(VV + VH + 1e-6)", {"VV":img.select("VV"),"VH":img.select("VH")}).rename("sm_index")
    sm_pct = ratio.add(1).divide(2).multiply(100).rename("soil_moisture")
    return safe_get_info(
        sm_pct.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("soil_moisture"),
        "soil moisture"
    )

# ---------------------------
# Display Results
# ---------------------------
if region:
    st.subheader(f"Results: S1 {start_s1_str}–{end_s1_str}, S2 {start_s2_str}–{end_s2_str}")
    with st.spinner("Computing parameters…"):
        ph   = get_ph(region, start_s2_str, end_s2_str)
        sal  = get_salinity(region, start_s2_str, end_s2_str)
        oc   = get_organic_carbon(region, start_s2_str, end_s2_str)
        cec  = estimate_cec(region, start_s2_str, end_s2_str, cec_intercept, cec_slope_clay, cec_slope_om)
        lst  = get_lst(region, start_s2_str, end_s2_str)
        texc = get_soil_texture(region)
        sm   = get_soil_moisture(region, start_s1_str, end_s1_str)

    def fmt(name, val, fmt_str):
        return f"**{name}:** {fmt_str.format(val)}" if val is not None else f"**{name}:** N/A"

    st.write(fmt("Soil pH", ph, "{:.2f}"))
    st.write(fmt("Soil Texture", texc, "{} (class {})".format(TEXTURE_CLASSES.get(texc,'N/A'), texc)))
    st.write(fmt("Salinity (NDSI)", sal, "{:.3f}"))
    st.write(fmt("Organic Carbon (%)", oc*100 if oc is not None else None, "{:.2f}"))
    st.write(fmt("CEC (cmolc/kg)", cec, "{:.2f}"))
    st.write(fmt("LST (°C)", lst, "{:.2f}"))
    st.write(fmt("Soil Moisture Index (%)", sm, "{:.1f}%"))
else:
    st.info("Draw your farm boundary to analyze!")
