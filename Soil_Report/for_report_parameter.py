import logging
import os
from datetime import datetime, date, timedelta
import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import pandas as pd
from folium.plugins import Draw

# --------------------------- Logging Configuration ---------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --------------------------- Initialize Google Earth Engine -------------------
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
    """Safely retrieve information from Earth Engine computed objects."""
    if computed_obj is None:
        return None
    try:
        info = computed_obj.getInfo()
        return float(info) if info is not None else None
    except Exception as e:
        logging.warning(f"Failed to fetch {name}: {e}")
        return None

def sentinel_composite(region, start, end, bands, max_days=30, step=5):
    """Fetch Sentinel-2 composite with fallback to expanded date ranges."""
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

# --------------------------- Parameter Functions -----------------------------
def get_ph(comp, region):
    """Estimate soil pH (6.0-7.5 ideal) using empirical formula from Sentinel-2 bands."""
    if comp is None: return None
    br = comp.expression("(B2+B3+B4)/3", {"B2": comp.select("B2"), "B3": comp.select("B3"), "B4": comp.select("B4")})
    sa = comp.expression("(B11-B8)/(B11+B8+1e-6)", {"B11": comp.select("B11"), "B8": comp.select("B8")})
    img = comp.expression("7.1 + 0.15*B2 - 0.32*B11 + 1.2*br - 0.7*sa", {"B2": comp.select("B2"), "B11": comp.select("B11"), "br": br, "sa": sa}).rename("ph")
    return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ph"), "pH")

def get_salinity(comp, region):
    """Estimate soil salinity (NDSI, <0.2 ideal) using Sentinel-2 bands."""
    if comp is None: return None
    img = comp.expression("(B11-B3)/(B11+B3+1e-6)", {"B11": comp.select("B11"), "B3": comp.select("B3")}).rename("ndsi")
    return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndsi"), "salinity")

def get_organic_carbon(comp, region):
    """Estimate soil organic carbon (2-5% ideal) using NDVI-based proxy."""
    if comp is None: return None
    ndvi = comp.normalizedDifference(["B8", "B4"])
    img = ndvi.multiply(0.05).rename("oc")
    return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("oc"), "organic carbon")

def estimate_cec(comp, region, intercept, slope_clay, slope_om):
    """Estimate Cation Exchange Capacity (10-30 cmolc/kg ideal) using clay and organic matter indices."""
    if comp is None: return None
    clay = comp.expression("(B11-B8)/(B11+B8+1e-6)", {"B11": comp.select("B11"), "B8": comp.select("B8")}).rename("clay")
    om = comp.expression("(B8-B4)/(B8+B4+1e-6)", {"B8": comp.select("B8"), "B4": comp.select("B4")}).rename("om")
    c_m = safe_get_info(clay.reduceRegion(ee.Reducer.mean(), geometry=region, scale=20, maxPixels=1e13).get("clay"), "clay")
    o_m = safe_get_info(om.reduceRegion(ee.Reducer.mean(), geometry=region, scale=20, maxPixels=1e13).get("om"), "om")
    if c_m is None or o_m is None:
        return None
    return intercept + slope_clay * c_m + slope_om * o_m

def get_soil_texture(region):
    """Get soil texture class (loam ideal) from OpenLandMap dataset."""
    mode = SOIL_TEXTURE_IMG.clip(region.buffer(500)).reduceRegion(ee.Reducer.mode(), geometry=region, scale=250, maxPixels=1e13).get("b0")
    val = safe_get_info(mode, "texture")
    return int(val) if val is not None else None

def get_lst(region, start, end):
    """Get Land Surface Temperature (10-30°C ideal) from MODIS."""
    def fetch(r, sd, ed):
        sd_str = sd.strftime("%Y-%m-%d")
        ed_str = ed.strftime("%Y-%m-%d")
        coll = ee.ImageCollection("MODIS/061/MOD11A2").filterBounds(r.buffer(5000)).filterDate(sd_str, ed_str).select("LST_Day_1km")
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
    stats = img.reduceRegion(reducer=ee.Reducer.mean(), geometry=region.buffer(5000), scale=1000, maxPixels=1e13, bestEffort=True).getInfo()
    return float(stats.get("lst", None)) if stats else None

def get_ndwi(comp, region):
    """Calculate Normalized Difference Water Index (0-0.5 ideal for moist soils)."""
    if comp is None: return None
    img = comp.expression("(B3-B8)/(B3+B8+1e-6)", {"B3": comp.select("B3"), "B8": comp.select("B8")}).rename("ndwi")
    return safe_get_info(img.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndwi"), "ndwi")

def get_ndvi(comp, region):
    """Calculate Normalized Difference Vegetation Index (0.2-0.8 ideal for healthy crops)."""
    if comp is None: return None
    ndvi = comp.normalizedDifference(["B8", "B4"]).rename("ndvi")
    return safe_get_info(ndvi.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("ndvi"), "NDVI")

def get_evi(comp, region):
    """Calculate Enhanced Vegetation Index (0.2-0.8 ideal for healthy crops)."""
    if comp is None: return None
    evi = comp.expression(
        "2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)",
        {"NIR": comp.select("B8"), "RED": comp.select("B4"), "BLUE": comp.select("B2")}
    ).rename("evi")
    return safe_get_info(evi.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("evi"), "EVI")

def get_fvc(comp, region):
    """Calculate Fraction of Vegetation Cover (0.3-0.8 ideal for crop cover)."""
    if comp is None: return None
    ndvi = comp.normalizedDifference(["B8", "B4"])
    ndvi_min = 0.2
    ndvi_max = 0.8
    fvc = ndvi.subtract(ndvi_min).divide(ndvi_max - ndvi_min).pow(2).clamp(0, 1).rename("fvc")
    return safe_get_info(fvc.reduceRegion(ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e13).get("fvc"), "FVC")

def get_npk_for_region(comp, region):
    """Estimate soil NPK levels (N: 20-40 ppm, P: 10-30 ppm, K: 15-40 ppm ideal)."""
    if comp is None: return None, None, None
    brightness = comp.expression('(B2 + B3 + B4) / 3', {'B2': comp.select('B2'), 'B3': comp.select('B3'), 'B4': comp.select('B4')})
    salinity2 = comp.expression('(B11 - B8) / (B11 + B8 + 1e-6)', {'B11': comp.select('B11'), 'B8': comp.select('B8')})
    N_est = comp.expression("5 + 100*(3 - (B2 + B3 + B4))", {'B2': comp.select('B2'), 'B3': comp.select('B3'), 'B4': comp.select('B4')}).rename('N')
    P_est = comp.expression("3 + 50*(1 - B8) + 20*(1 - B11)", {'B8': comp.select('B8'), 'B11': comp.select('B11')}).rename('P')
    K_est = comp.expression("5 + 150*(1 - brightness) + 50*(1 - B3) + 30*salinity2", {'brightness': brightness, 'B3': comp.select('B3'), 'salinity2': salinity2}).rename('K')
    npk_image = N_est.addBands(P_est).addBands(K_est)
    stats = npk_image.reduceRegion(reducer=ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e9).getInfo()
    n_val = stats.get('N', None)
    p_val = stats.get('P', None)
    k_val = stats.get('K', None)
    return n_val, p_val, k_val

# --------------------------- Streamlit UI Setup ------------------------------
st.set_page_config(layout='wide', page_title="Near Real-Time Soil & Crop Dashboard")
st.title("🌾 Near Real-Time Soil & Crop Parameter Dashboard")
st.markdown("""
This dashboard provides near real-time analysis of soil and crop parameters using satellite data (16-day window, with 30-day fallback).
**Parameters**: pH, Soil Texture, Salinity (NDSI), Organic Carbon, CEC, LST, NDWI, NDVI, EVI, FVC, NPK levels. Ideal ranges are shown with each parameter.
""")

# Sidebar Inputs
st.sidebar.header("📍 Location & Model Parameters")
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]  # Default to Pune, IN
lat = st.sidebar.number_input("Latitude", value=st.session_state.user_location[0], format="%.6f")
lon = st.sidebar.number_input("Longitude", value=st.session_state.user_location[1], format="%.6f")
st.session_state.user_location = [lat, lon]

st.sidebar.header("🧪 CEC Model Coefficients")
cec_intercept = st.sidebar.number_input("Intercept", value=5.0, step=0.1)
cec_slope_clay = st.sidebar.number_input("Slope (Clay Index)", value=20.0, step=0.1)
cec_slope_om = st.sidebar.number_input("Slope (OM Index)", value=15.0, step=0.1)

# Date Window
today = date.today()
start = today - timedelta(days=16)
end = today
start_date = st.sidebar.date_input("Start Date", value=start)
end_date = st.sidebar.date_input("End Date", value=end)

# Map Setup
m = folium.Map(location=[lat, lon], zoom_start=15)
Draw(export=True).add_to(m)
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google").add_to(m)
folium.Marker([lat, lon], popup="Center").add_to(m)
map_data = st_folium(m, width=700, height=500)

# Extract region from map
region = None
if map_data and "last_active_drawing" in map_data:
    try:
        sel = map_data["last_active_drawing"]
        region = ee.Geometry.Polygon(sel["geometry"]["coordinates"])
    except Exception as e:
        st.error(f"Error creating region geometry: {str(e)}")

# --------------------------- Display Results ---------------------------------
if region:
    st.subheader(f"Analysis Results: {start_date} to {end_date}")
    with st.spinner("Computing parameters…"):
        all_bands = ["B2", "B3", "B4", "B8", "B11", "B12"]
        comp = sentinel_composite(region, start_date, end_date, all_bands)
        texc = get_soil_texture(region)
        lst = get_lst(region, start_date, end_date)
        if comp is None:
            st.warning("⚠️ No Sentinel-2 images found for this range. Some parameters may be unavailable.")
            ph = sal = oc = cec = ndwi = ndvi = evi = fvc = None
            n_val = p_val = k_val = None
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

    def fmt(name, val, fmt_str):
        return f"{name}:** {fmt_str.format(val)}" if val is not None else f"{name}:** N/A"

    st.write("### Soil Parameters")
    st.write(fmt("Soil pH (Ideal: 6.0-7.5)", ph, "{:.2f}"))
    st.write(fmt("Soil Texture (Ideal: Loam)", texc, "{} (class {})".format(TEXTURE_CLASSES.get(texc, 'N/A'), texc)))
    st.write(fmt("Salinity (NDSI, Ideal: <0.2)", sal, "{:.3f}"))
    st.write(fmt("Organic Carbon (Ideal: 2-5%)", oc * 100 if oc is not None else None, "{:.2f}"))
    st.write(fmt("CEC (Ideal: 10-30 cmolc/kg)", cec, "{:.2f}"))
    st.write(fmt("LST (Ideal: 10-30°C)", lst, "{:.2f}"))
    st.write("### Vegetation and Water Indices")
    st.write(fmt("NDWI (Ideal: 0-0.5 for moist soils)", ndwi, "{:.3f}"))
    st.write(fmt("NDVI (Ideal: 0.2-0.8 for healthy crops)", ndvi, "{:.3f}"))
    st.write(fmt("EVI (Ideal: 0.2-0.8 for healthy crops)", evi, "{:.3f}"))
    st.write(fmt("FVC (Ideal: 0.3-0.8 for crop cover)", fvc, "{:.3f}"))
    if n_val is not None and p_val is not None and k_val is not None:
        st.write("### 🌾 Estimated Soil Nutrients (mean values)")
        st.write(f"- Nitrogen (N, Ideal: 20-40 ppm): {n_val:.2f} mg/kg")
        st.write(f"- Phosphorus (P, Ideal: 10-30 ppm): {p_val:.2f} mg/kg")
        st.write(f"- Potassium (K, Ideal: 15-40 ppm): {k_val:.2f} mg/kg")
    else:
        st.error("❌ Unable to compute NPK for the marked area.")
else:
    st.info("🔍 Please draw a polygon on the map to define your region.")