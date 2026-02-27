import os
import logging
import certifi
import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import pandas as pd
import datetime
import time
import h5py
import numpy as np
# Earthaccess import wrapped for environments without it
try:
    import earthaccess
    EARTHACCESS_AVAILABLE = True
except ModuleNotFoundError:
    EARTHACCESS_AVAILABLE = False
from folium.plugins import Draw

# -------------------------------
# Configuration & Logging
# -------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Manually set Earthdata credentials
NASA_USERNAME = "krishnapunjabi"
NASA_PASSWORD = "Krishna708333@"

# Create .netrc for Earthaccess if available
if EARTHACCESS_AVAILABLE:
    netrc_path = os.path.expanduser("~/.netrc")
    netrc_contents = f"""machine urs.earthdata.nasa.gov
  login {NASA_USERNAME}
  password {NASA_PASSWORD}
"""
    with open(netrc_path, "w") as f:
        f.write(netrc_contents)
    os.chmod(netrc_path, 0o600)
    os.environ["NETRC"] = netrc_path

# Use certifi for HTTPS
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Initialize Earth Engine
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# -------------------------------
# App Title & Description
# -------------------------------
st.title("Real-Time Crop, Soil Fertility & Moisture Mapping")
st.write("""
This application uses Sentinel-2 data (via GEE) to compute vegetation and fertility indices, and NASA SMAP for soil moisture.
After drawing your field boundary, capture your location and fetch both fertility overlays and moisture (if available).
""")

# -------------------------------
# Geolocation
# -------------------------------
use_geo = False
try:
    from streamlit_geolocation import st_geolocation
    use_geo = True
except ModuleNotFoundError:
    pass

if use_geo and st.button("Get Real-Time Location"):
    loc = st_geolocation(timeout=10)
    if loc:
        st.session_state.user_location = [loc['lat'], loc['lon']]
        st.success(f"Location: {loc['lat']:.6f}, {loc['lon']:.6f}")
    else:
        st.error("Allow location or enter manually.")
else:
    lat = st.sidebar.number_input("Latitude", value=18.4575, format="%.6f")
    lon = st.sidebar.number_input("Longitude", value=73.8503, format="%.6f")
    st.session_state.user_location = [lat, lon]

if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]

st.sidebar.write(f"Current Location: {st.session_state.user_location[0]:.6f}, {st.session_state.user_location[1]:.6f}")

# -------------------------------
# Date Range & Composite Period
# -------------------------------
mode = st.sidebar.radio("Mode", ("Real-Time", "Custom Range"))
if mode == "Real-Time":
    today = datetime.datetime.today()
    end_date = today - datetime.timedelta(days=7)
    start_date = today - datetime.timedelta(days=14)
    st.sidebar.info(f"Using data {start_date:%Y-%m-%d} to {end_date:%Y-%m-%d}")
else:
    start_date = pd.to_datetime(st.sidebar.date_input("Start Date", pd.to_datetime("2023-05-01")))
    end_date   = pd.to_datetime(st.sidebar.date_input("End Date", pd.to_datetime("2023-05-07")))

comp_days = st.sidebar.number_input("Composite Period (days)", value=7, min_value=1, max_value=30)

# -------------------------------
# Field Boundary Drawing
# -------------------------------
m = folium.Map(location=st.session_state.user_location, zoom_start=15)
folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google").add_to(m)
Draw(export=True).add_to(m)
folium.Marker(st.session_state.user_location, icon=folium.Icon(color="blue", icon="user")).add_to(m)
map_data = st_folium(m, width=700, height=500)

selected_boundary = None
if map_data and map_data.get("last_active_drawing"):
    selected_boundary = map_data["last_active_drawing"]
    st.write("### Field Boundary Selected", selected_boundary)
else:
    st.warning("Draw a field boundary to proceed.")
    st.stop()

# -------------------------------
# Compute Vegetation & Fertility Indices
# -------------------------------
@st.cache_data
def compute_indices(region, start_date, end_date, comp_days):
    # Insert your existing GEE index computation logic here
    raise NotImplementedError("compute_indices() needs your implementation")

# -------------------------------
# Fetch NASA SMAP Soil Moisture
# -------------------------------
@st.cache_data
def get_soil_moisture(lat, lon, days=30):
    if not EARTHACCESS_AVAILABLE:
        return None
    try:
        earthaccess.login()
    except:
        pass
    bb = (lon-0.5, lat-0.5, lon+0.5, lat+0.5)
    prod = "SPL3SMP"
    for i in range(days):
        date = datetime.datetime.utcnow() - datetime.timedelta(days=i)
        dstr = date.strftime("%Y.%m.%d")
        results = earthaccess.search_data(short_name=prod, temporal=(dstr, dstr), bounding_box=bb)
        if results:
            files = earthaccess.download(results[:1])
            with h5py.File(files[0], 'r') as f:
                sm = f["Soil_Moisture_Retrieval_Data_AM"]["soil_moisture"][:]
                lats = f["Soil_Moisture_Retrieval_Data_AM"]["latitude"][:]
                lons = f["Soil_Moisture_Retrieval_Data_AM"]["longitude"][:]
                dist = np.sqrt((lats-lat)**2 + (lons-lon)**2)
                idx = np.unravel_index(np.argmin(dist), dist.shape)
                return round(float(sm[idx]), 4)
    return None

# ----------------------------------------
# Main Execution
# ----------------------------------------
_region = ee.Geometry.Polygon(selected_boundary["geometry"]["coordinates"])
with st.spinner("Processing GEE composites..."):
    df, used_collection, bands = compute_indices(_region, start_date, end_date, comp_days)

# Display map overlays (NDVI, Fertility, etc.)
# [Insert your overlay map code here]

# Soil Moisture Button
if st.button("Get Soil Moisture at Field Center"):
    lat, lon = st.session_state.user_location
    if not EARTHACCESS_AVAILABLE:
        st.error("earthaccess library not installed. Install via `pip install earthaccess` to enable SMAP retrieval.")
    else:
        with st.spinner("Fetching SMAP data..."):
            moisture = get_soil_moisture(lat, lon)
        if moisture is not None:
            st.success(f"Soil Moisture: {moisture} m³/m³")
        else:
            st.error("No SMAP data available.")
