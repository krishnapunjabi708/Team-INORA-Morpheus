import logging
from datetime import datetime, timezone, timedelta
import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import pandas as pd
import plotly.express as px
from folium.plugins import Draw
import earthaccess
import h5py
import numpy as np
import os

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
# Initialize Earth Engine
# ---------------------------
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# ---------------------------
# Soil Texture Dataset & Classes
# ---------------------------
# Using USDA soil texture classes at 0 cm from OpenLandMap (v02)
SOIL_TEXTURE_IMG = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0')
TEXTURE_CLASSES = {
    1: "Clay",           2: "Silty Clay",      3: "Sandy Clay",
    4: "Clay Loam",      5: "Silty Clay Loam", 6: "Sandy Clay Loam",
    7: "Loam",           8: "Silty Loam",      9: "Sandy Loam",
    10: "Silt",          11: "Loamy Sand",     12: "Sand"
}

# ---------------------------
# Streamlit UI
# ---------------------------
st.title("🌍 Advanced Crop & Soil Parameter Mapping + pH, Soil Moisture & Texture Scanner")
st.write("Integrates satellite indices, synthetic pH, recent SMAP soil moisture, and soil texture for crop management.")

# Default location (VIIT Pune)
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]

st.sidebar.header("📍 Enter Location")
lat = st.sidebar.number_input("Latitude", value=st.session_state.user_location[0], format='%.6f')
lon = st.sidebar.number_input("Longitude", value=st.session_state.user_location[1], format='%.6f')
st.session_state.user_location = [lat, lon]

st.sidebar.header("📅 Select Time Range")
start_date = st.sidebar.date_input("Start Date", pd.to_datetime('2024-01-01'))
end_date = st.sidebar.date_input("End Date", pd.to_datetime('2024-12-31'))

# Map with Draw tool
m = folium.Map(location=st.session_state.user_location, zoom_start=15)
folium.TileLayer(
    tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    attr='Google', name='Satellite').add_to(m)
Draw(export=True).add_to(m)
folium.Marker(st.session_state.user_location, popup='Your Location').add_to(m)
map_data = st_folium(m, width=700, height=500)

# Geometry Extraction
region = None
if map_data and 'last_active_drawing' in map_data:
    coords = map_data['last_active_drawing']['geometry']['coordinates']
    region = ee.Geometry.Polygon(coords)
    st.write('### Selected Area Coordinates:', coords)

# ---------------------------
# Synthetic Soil-pH Estimation
# ---------------------------
def get_ph(region, start, end):
    s2 = (ee.ImageCollection('COPERNICUS/S2_SR')
          .filterBounds(region)
          .filterDate(str(start), str(end))
          .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE',5))
          .select(['B2','B3','B4','B8','B11'])
          .median().multiply(0.0001))
    brightness = s2.expression('(B2+B3+B4)/3',{'B2':s2.select('B2'),'B3':s2.select('B3'),'B4':s2.select('B4')})
    sal2 = s2.expression('(B11-B8)/(B11+B8+1e-6)',{'B11':s2.select('B11'),'B8':s2.select('B8')})
    ph_expr = s2.expression('7.1+0.15*B2-0.32*B11+1.2*br-0.7*sa',
                             {'B2':s2.select('B2'),'B11':s2.select('B11'),'br':brightness,'sa':sal2})
    val = ph_expr.reduceRegion(ee.Reducer.mean(), region, scale=10).get('constant')
    return val.getInfo() if val else None

# ---------------------------
# SMAP Soil Moisture via Earthaccess
# ---------------------------
def get_smap_moisture(lat, lon, days=7):
    for d in range(days):
        dt = datetime.now(timezone.utc) - timedelta(days=d)
        date_str = dt.strftime('%Y.%m.%d')
        try:
            res = earthaccess.search_data(
                short_name='SPL3SMP',
                temporal=(date_str, date_str),
                bounding_box=(lon-0.5, lat-0.5, lon+0.5, lat+0.5)
            )
        except Exception:
            continue
        if res:
            path = earthaccess.download(res[:1])[0]
            with h5py.File(path,'r') as f:
                sm = f['Soil_Moisture_Retrieval_Data_AM/soil_moisture'][:]
                lats = f['Soil_Moisture_Retrieval_Data_AM/latitude'][:]
                lons = f['Soil_Moisture_Retrieval_Data_AM/longitude'][:]
                dist = np.sqrt((lats-lat)**2 + (lons-lon)**2)
                idx = np.unravel_index(np.argmin(dist), dist.shape)
                return float(sm[idx]), date_str
    return None, None

# ---------------------------
# Soil Texture Extraction
# ---------------------------
def get_soil_texture(region):
    try:
        clipped = SOIL_TEXTURE_IMG.clip(region.buffer(50000))
        mode = clipped.reduceRegion(
            reducer=ee.Reducer.mode(),
            geometry=region,
            scale=250,
            maxPixels=1e9
        ).get('b0')
        return mode.getInfo() if mode else None
    except Exception as e:
        st.error(f"Error fetching soil texture: {e}")
        return None

# ---------------------------
# Run analyses if region selected
# ---------------------------
if region:
    # pH
    ph = get_ph(region, start_date, end_date)
    if ph is not None:
        st.write(f"### 🌱 Estimated Soil pH: {ph:.2f}")
        if ph < 5.5:
            st.warning("⚠ Acidic Soil - Add lime to neutralize pH.")
        elif ph > 7.5:
            st.warning("⚠ Alkaline Soil - Add sulfur or organic matter.")
        else:
            st.success("✅ Optimal Soil pH for most crops.")

    # Soil Moisture
    sm_val, sm_date = get_smap_moisture(lat, lon)
    if sm_val is not None:
        st.write(f"### 💧 SMAP Soil Moisture ({sm_date}): {sm_val:.3f} m³/m³")
    else:
        st.warning("⚠ Unable to retrieve SMAP data for your location.")

    # Soil Texture
    code = get_soil_texture(region)
    label = TEXTURE_CLASSES.get(code)
    if label:
        st.write(f"### 🏖️ Dominant Soil Texture: {label} (class {code})")
    else:
        st.warning("⚠ Could not classify soil texture for the selected area.")

    # Optional: overlay texture on map
    try:
        vis = SOIL_TEXTURE_IMG.visualize(
            bands=['b0'],
            min=1, max=12,
            palette=[
                '#d5c36b','#b96947','#9d3706','#ae868f','#f86714','#46d143',
                '#368f20','#3e5a14','#ffd557','#fff72e','#ff5a9d','#ff005b'
            ]
        )
        m.add_child(folium.raster_layers.ImageOverlay(
            image=vis.getMapId(),
            bounds=[[lat-0.5, lon-0.5], [lat+0.5, lon+0.5]],
            name='Soil Texture',
            opacity=0.6
        ))
        folium.LayerControl().add_to(m)
        st_folium(m, width=700, height=500)
    except Exception:
        pass
else:
    st.info('Select an area to analyze pH, soil moisture, and texture.')
