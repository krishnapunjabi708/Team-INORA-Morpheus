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
    import os
    os.chmod('.netrc', 0o600)
except Exception as exc:
    logging.warning("Unable to secure .netrc: %s", exc)

environ = {'NETRC': os.path.abspath('.netrc')} if 'os' in globals() else {}
for k, v in environ.items():
    import os; os.environ[k] = v

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
# Streamlit UI
# ---------------------------
st.title("🌍 Advanced Crop & Soil Parameter Mapping + pH & Soil Moisture Scanner")
st.write("Integrates satellite indices, synthetic pH, and recent SMAP soil moisture for crop management.")

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
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr='Google', name='Satellite').add_to(m)
Draw(export=True).add_to(m)
folium.Marker(st.session_state.user_location, popup='Your Location').add_to(m)
map_data = st_folium(m, width=700, height=500)

region = None
if map_data and 'last_active_drawing' in map_data:
    coords = map_data['last_active_drawing']['geometry']['coordinates']
    region = ee.Geometry.Polygon(coords)
    st.write('### Selected Area Coordinates:', coords)

# Function: Synthetic pH estimation
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

# Function: SMAP soil moisture via Earthaccess
def get_smap_moisture(lat, lon, days=7):
    for d in range(days):
        dt = datetime.now(timezone.utc) - timedelta(days=d)
        date_str = dt.strftime('%Y.%m.%d')
        try:
            res = earthaccess.search_data(short_name='SPL3SMP', temporal=(date_str,date_str),
                                         bounding_box=(lon-0.5, lat-0.5, lon+0.5, lat+0.5))
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

# Run analyses if region selected
if region:
    ph = get_ph(region, start_date, end_date)
    if ph:
        st.write(f"### 🌱 Estimated Soil pH: {ph:.2f}")
    sm_val, sm_date = get_smap_moisture(lat, lon)
    if sm_val is not None:
        st.write(f"### 💧 SMAP Soil Moisture ({sm_date}): {sm_val:.3f} m³/m³")
else:
    st.info('Select an area to analyze pH and soil moisture.')
