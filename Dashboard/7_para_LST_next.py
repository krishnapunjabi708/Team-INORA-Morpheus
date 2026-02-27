import logging
import os
from datetime import datetime, timezone, timedelta

import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import pandas as pd
import earthaccess
import h5py
import numpy as np
from folium.plugins import Draw

# ---------------------------
# Logging Configuration
# ---------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------------
# Earthdata Credentials (for SMAP)
# ---------------------------
USERNAME = "krishnapunjabi"
PASSWORD = "Krishna708333@"
netrc_content = f"""machine urs.earthdata.nasa.gov
  login {USERNAME}
  password {PASSWORD}
"""
with open('.netrc', 'w') as f:
    f.write(netrc_content)
try:
    os.chmod('.netrc', 0o600)
except Exception as exc:
    logging.warning("Unable to secure .netrc: %s", exc)
os.environ['NETRC'] = os.path.abspath('.netrc')

# Earthaccess login
try:
    earthaccess.login(strategy='netrc')
    logging.info("Logged into Earthdata via Earthaccess.")
except Exception as e:
    logging.error("Earthaccess login failed: %s", e)

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
# Streamlit UI Setup
# ---------------------------
st.set_page_config(layout='wide')
st.title("🌾 Comprehensive Soil & Crop Parameter Dashboard")
st.markdown("""
This application computes seven soil and crop parameters:
1. Synthetic Soil pH
2. SMAP Soil Moisture
3. Soil Texture
4. Salinity (NDSI)
5. Organic Carbon (OC)
6. Cation Exchange Capacity (CEC)
7. Land Surface Temperature (LST)
""")

# Sidebar inputs
st.sidebar.header("📍 Location & Time Range")
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]
lat = st.sidebar.number_input("Latitude", value=st.session_state.user_location[0], format="%.6f")
lon = st.sidebar.number_input("Longitude", value=st.session_state.user_location[1], format="%.6f")
st.session_state.user_location = [lat, lon]
start_date = st.sidebar.date_input("Start Date", pd.to_datetime("2024-01-01"))
end_date   = st.sidebar.date_input("End Date",   pd.to_datetime("2024-12-31"))
start_str  = start_date.strftime("%Y-%m-%d")
end_str    = end_date.strftime("%Y-%m-%d")

st.sidebar.header("🧪 CEC Model Coefficients")
cec_intercept   = st.sidebar.number_input("Intercept", value=5.0, step=0.1)
cec_slope_clay  = st.sidebar.number_input("Slope (Clay Index)", value=20.0, step=0.1)
cec_slope_om    = st.sidebar.number_input("Slope (OM Index)",   value=15.0, step=0.1)

# ---------------------------
# Map with Draw tool
# ---------------------------
m = folium.Map(location=[lat, lon], zoom_start=13)
Draw(export=True).add_to(m)
folium.TileLayer(
    "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", 
    attr="Google"
).add_to(m)
folium.Marker([lat, lon], popup="Center").add_to(m)
map_data = st_folium(m, width=700, height=500)

# Define region geometry
if map_data and map_data.get("last_active_drawing"):
    coords = map_data["last_active_drawing"]["geometry"]["coordinates"]
    region = ee.Geometry.Polygon(
        coords if isinstance(coords[0][0], (float, int)) else coords[0]
    )
else:
    region = ee.Geometry.Point(lon, lat).buffer(5000)

# ---------------------------
# Parameter Functions
# ---------------------------

def get_ph(region, start, end):
    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start, end)
        .filterBounds(region)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .select(["B2","B3","B4","B8","B11"])
        .median()
        .multiply(0.0001)
    )
    br = col.expression("(B2+B3+B4)/3", {
        "B2":col.select("B2"), "B3":col.select("B3"), "B4":col.select("B4")
    })
    sa = col.expression("(B11-B8)/(B11+B8+1e-6)", {
        "B11":col.select("B11"), "B8":col.select("B8")
    })
    ph_img = col.expression(
        "7.1 + 0.15 * B2 - 0.32 * B11 + 1.2 * br - 0.7 * sa", {
        "B2":col.select("B2"), "B11":col.select("B11"), "br":br, "sa":sa
    }).rename("ph")
    val = ph_img.reduceRegion(
        ee.Reducer.mean(), region, scale=10, maxPixels=1e13
    ).get("ph")
    return float(val.getInfo()) if val else None

def get_salinity(region, start, end):
    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start, end)
        .filterBounds(region)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .select(["B3","B11"])
        .median()
        .multiply(0.0001)
    )
    ndsi = col.expression("(B11-B3)/(B11+B3+1e-6)", {
        "B11":col.select("B11"), "B3":col.select("B3")
    }).rename("ndsi")
    val = ndsi.reduceRegion(
        ee.Reducer.mean(), region, scale=10, maxPixels=1e13
    ).get("ndsi")
    return float(val.getInfo()) if val else None

def get_organic_carbon(region, start, end):
    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start, end)
        .filterBounds(region)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .select(["B4","B8"])
        .median()
        .multiply(0.0001)
    )
    ndvi = col.expression("(B8-B4)/(B8+B4+1e-6)", {
        "B8":col.select("B8"), "B4":col.select("B4")
    })
    oc = ndvi.multiply(0.05).rename("oc")
    val = oc.reduceRegion(
        ee.Reducer.mean(), region, scale=10, maxPixels=1e13
    ).get("oc")
    return float(val.getInfo()) if val else None

def estimate_cec(region, start, end, intercept, slope_clay, slope_om):
    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start, end)
        .filterBounds(region)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .select(["B2","B4","B8","B11","B12"])
        .map(lambda img: img.cast({
            "B2":"float","B4":"float","B8":"float","B11":"float","B12":"float"
        }))
        .median()
        .multiply(0.0001)
        .clip(region)
    )
    clay = col.expression("(B11-B8)/(B11+B8+1e-6)", {
        "B11":col.select("B11"), "B8":col.select("B8")
    }).rename("clay")
    om   = col.expression("(B8-B4)/(B8+B4+1e-6)", {
        "B8":col.select("B8"), "B4":col.select("B4")
    }).rename("om")
    clay_m = clay.reduceRegion(
        ee.Reducer.mean(), region, scale=20, maxPixels=1e13
    ).get("clay")
    om_m   = om.reduceRegion(
        ee.Reducer.mean(), region, scale=20, maxPixels=1e13
    ).get("om")
    if clay_m is None or om_m is None:
        return None
    return intercept + slope_clay * float(clay_m.getInfo()) + slope_om * float(om_m.getInfo())

def get_smap_moisture(lat, lon, days=30):
    """Search & download SMAP L3 moisture for the past `days`."""
    PRODUCT = "SPL3SMP"
    bbox = (lon-0.5, lat-0.5, lon+0.5, lat+0.5)

    for d in range(days):
        dt = datetime.now(timezone.utc) - timedelta(days=d)
        ds = dt.strftime("%Y.%m.%d")
        try:
            results = earthaccess.search_data(
                short_name=PRODUCT,
                temporal=(ds, ds),
                bounding_box=bbox,
                cloud_hosted=True
            )
        except Exception:
            continue

        if not results:
            continue

        # Download first match
        path = earthaccess.download(results[:1])[0]
        with h5py.File(path, "r") as f:
            sm  = f["Soil_Moisture_Retrieval_Data_AM/soil_moisture"][:]
            lats= f["Soil_Moisture_Retrieval_Data_AM/latitude"][:]
            lons= f["Soil_Moisture_Retrieval_Data_AM/longitude"][:]

        # nearest‐pixel
        dist = np.sqrt((lats-lat)**2 + (lons-lon)**2)
        idx  = np.unravel_index(np.argmin(dist), dist.shape)
        val  = float(sm[idx])
        if 0 <= val <= 1:
            return val, ds

    return None, None

def get_soil_texture(region):
    mode = SOIL_TEXTURE_IMG.clip(region.buffer(50000)).reduceRegion(
        ee.Reducer.mode(), region, scale=250, maxPixels=1e13
    ).get("b0")
    return int(mode.getInfo()) if mode else None

def get_lst(region, start, end):
    def fetch(r, sd, ed):
        coll = (
            ee.ImageCollection("MODIS/061/MOD11A2")
            .filterBounds(r.buffer(5000))
            .filterDate(sd, ed)
            .select("LST_Day_1km")
        )
        return coll, coll.size().getInfo()

    coll, cnt = fetch(region, start, end)
    st.write(f"LST composites in window: {cnt}")
    if cnt == 0:
        s_exp = (pd.to_datetime(start) - timedelta(days=30)).strftime("%Y-%m-%d")
        e_exp = (pd.to_datetime(end)   + timedelta(days=30)).strftime("%Y-%m-%d")
        coll, cnt = fetch(region, s_exp, e_exp)
        st.write(f"Expanded LST window: {s_exp} – {e_exp}, found {cnt}")
    if cnt == 0:
        return None

    img = coll.median().multiply(0.02).subtract(273.15).rename("lst").clip(region.buffer(5000))
    stats = img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region.buffer(5000),
        scale=1000,
        maxPixels=1e13,
        bestEffort=True
    ).getInfo()
    return float(stats.get("lst")) if stats.get("lst") is not None else None

# ---------------------------
# Display Results
# ---------------------------
if region:
    st.subheader("Analysis Results")

    ph = get_ph(region, start_str, end_str)
    st.write(f"**Soil pH:** {ph:.2f}" if ph else "**Soil pH:** N/A")

    sm_val, sm_date = get_smap_moisture(lat, lon)
    if sm_val is not None:
        st.write(f"**SMAP Soil Moisture ({sm_date}):** {sm_val:.3f} m³/m³")
    else:
        st.write("**SMAP Soil Moisture:** N/A")

    tc = get_soil_texture(region)
    st.write(f"**Soil Texture:** {TEXTURE_CLASSES.get(tc, 'N/A')} (class {tc})")

    sal = get_salinity(region, start_str, end_str)
    st.write(f"**Salinity (NDSI):** {sal:.3f}" if sal else "**Salinity:** N/A")

    oc = get_organic_carbon(region, start_str, end_str)
    st.write(f"**Organic Carbon (%):** {oc*100:.2f}" if oc else "**Organic Carbon:** N/A")

    cec = estimate_cec(region, start_str, end_str, cec_intercept, cec_slope_clay, cec_slope_om)
    st.write(f"**CEC (cmolc/kg):** {cec:.2f}" if cec else "**CEC:** N/A")

    lst_val = get_lst(region, start_str, end_str)
    st.write(f"**LST (°C):** {lst_val:.2f}" if lst_val else "**LST:** N/A")
else:
    st.info("Draw a polygon on the map to analyze all parameters.")
