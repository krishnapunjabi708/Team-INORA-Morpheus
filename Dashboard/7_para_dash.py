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
# Soil Texture Dataset & Classes
# ---------------------------
SOIL_TEXTURE_IMG = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0')
TEXTURE_CLASSES = {
    1: "Clay", 2: "Silty Clay", 3: "Sandy Clay",
    4: "Clay Loam", 5: "Silty Clay Loam", 6: "Sandy Clay Loam",
    7: "Loam", 8: "Silty Loam", 9: "Sandy Loam",
    10: "Silt", 11: "Loamy Sand", 12: "Sand"
}

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(layout='wide')
st.title("🌾 Comprehensive Soil & Crop Parameter Dashboard")
st.markdown("""
This application integrates seven key soil and crop parameters using satellite data:
1. Synthetic Soil pH
2. Soil Moisture (SMAP)
3. Soil Texture
4. Salinity (NDSI)
5. Organic Carbon (OC)
6. Cation Exchange Capacity (CEC)
7. Land Surface Temperature (LST)
""")

# Sidebar: Location & Dates
st.sidebar.header("📍 Location & Time Range")
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]
lat = st.sidebar.number_input("Latitude", value=st.session_state.user_location[0], format='%.6f')
lon = st.sidebar.number_input("Longitude", value=st.session_state.user_location[1], format='%.6f')
st.session_state.user_location = [lat, lon]
start_date = st.sidebar.date_input("Start Date", pd.to_datetime('2024-01-01'))
end_date = st.sidebar.date_input("End Date", pd.to_datetime('2024-12-31'))

# Sidebar: CEC Model Coefficients & Interpretation Ranges
st.sidebar.header("🧪 CEC Model Coefficients & Ranges")
intercept = st.sidebar.number_input("Intercept", value=5.0, step=0.1)
slope_clay = st.sidebar.number_input("Slope (Clay Index)", value=20.0, step=0.1)
slope_om = st.sidebar.number_input("Slope (OM Index)", value=15.0, step=0.1)
poor_max = st.sidebar.number_input("Poor max (cmolc/kg)", value=10.0, step=0.1)
good_min = st.sidebar.number_input("Good min (cmolc/kg)", value=15.0, step=0.1)
good_max = st.sidebar.number_input("Good max (cmolc/kg)", value=25.0, step=0.1)

# Map with Draw Tool
m = folium.Map(location=[lat, lon], zoom_start=13)
Draw(export=True).add_to(m)
folium.TileLayer(
    "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr='Google'
).add_to(m)
folium.Marker([lat, lon], popup='Your Location').add_to(m)
map_data = st_folium(m, width=700, height=500)

# Extract region polygon
region = None
if map_data and map_data.get('last_active_drawing'):
    coords = map_data['last_active_drawing']['geometry']['coordinates']
    try:
        if isinstance(coords[0][0][0], (float, int)):
            region = ee.Geometry.Polygon(coords)
        else:
            region = ee.Geometry.Polygon(coords[0])
    except Exception as e:
        st.error(f"Error creating region polygon: {e}")

# ---------------------------
# Parameter Functions
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
                             {'B2':s2.select('B2'),'B11':s2.select('B11'),'br':brightness,'sa':sal2}).rename('ph')
    val = ph_expr.reduceRegion(ee.Reducer.mean(), region, scale=10).get('ph')
    return float(val.getInfo()) if val else None

def get_salinity(region, start, end):
    s2 = (ee.ImageCollection('COPERNICUS/S2_SR')
          .filterBounds(region)
          .filterDate(str(start), str(end))
          .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE',5))
          .select(['B3','B11'])
          .median().multiply(0.0001))
    ndsi = s2.expression('(B11-B3)/(B11+B3+1e-6)',{'B11':s2.select('B11'),'B3':s2.select('B3')}).rename('ndsi')
    val = ndsi.reduceRegion(ee.Reducer.mean(), region, scale=10).get('ndsi')
    return float(val.getInfo()) if val else None

def get_organic_carbon(region, start, end):
    s2 = (ee.ImageCollection('COPERNICUS/S2_SR')
          .filterBounds(region)
          .filterDate(str(start), str(end))
          .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE',5))
          .select(['B4','B8'])
          .median().multiply(0.0001))
    ndvi = s2.expression('(B8-B4)/(B8+B4+1e-6)',{'B8':s2.select('B8'),'B4':s2.select('B4')})
    oc = ndvi.multiply(0.05).rename('oc')
    val = oc.reduceRegion(ee.Reducer.mean(), region, scale=10).get('oc')
    return float(val.getInfo()) if val else None

def estimate_cec(region, start, end, intercept, slope_clay, slope_om):
    coll = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(region)
            .filterDate(str(start), str(end))
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE',20))
            .select(['B2','B4','B8','B11','B12'])
            .map(lambda img: img.cast({'B2':'float','B4':'float','B8':'float','B11':'float','B12':'float'})))
    if coll.size().getInfo() == 0:
        return None
    s2 = coll.median().multiply(0.0001).clip(region)
    clay = s2.expression('(B11-B8)/(B11+B8+1e-6)',{'B11':s2.select('B11'),'B8':s2.select('B8')}).rename('clay')
    om = s2.expression('(B8-B4)/(B8+B4+1e-6)',{'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('om')
    clay_m = clay.reduceRegion(ee.Reducer.mean(), region, scale=20).get('clay')
    om_m = om.reduceRegion(ee.Reducer.mean(), region, scale=20).get('om')
    if clay_m is None or om_m is None:
        return None
    return intercept + slope_clay * float(clay_m.getInfo()) + slope_om * float(om_m.getInfo())

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
            with h5py.File(path, 'r') as f:
                sm = f['Soil_Moisture_Retrieval_Data_AM/soil_moisture'][:]
                lats = f['Soil_Moisture_Retrieval_Data_AM/latitude'][:]
                lons = f['Soil_Moisture_Retrieval_Data_AM/longitude'][:]
                idx = np.unravel_index(np.argmin(np.sqrt((lats-lat)**2+(lons-lon)**2)), sm.shape)
                return float(sm[idx]), date_str
    return None, None

def get_soil_texture(region):
    mode = SOIL_TEXTURE_IMG.clip(region.buffer(50000)).reduceRegion(
        reducer=ee.Reducer.mode(), geometry=region, scale=250, maxPixels=1e9
    ).get('b0')
    return int(mode.getInfo()) if mode else None

def get_lst(region, start, end):
    coll = (ee.ImageCollection('MODIS/006/MOD11A2')
             .filterBounds(region)
             .filterDate(str(start), str(end))
             .select('LST_Day_1km'))
    if coll.size().getInfo() == 0:
        return None
    lst = coll.median().multiply(0.02).subtract(273.15).rename('lst')
    val = lst.reduceRegion(ee.Reducer.mean(), region, scale=1000).get('lst')
    return float(val.getInfo()) if val else None

# ---------------------------
# Display Results
# ---------------------------
if region:
    st.subheader("Analysis Results")
    # pH
    ph = get_ph(region, start_date, end_date)
    st.write(f"**Soil pH:** {'{:.2f}'.format(ph) if ph else 'N/A'}")
    # Soil Moisture
    sm_val, sm_date = get_smap_moisture(lat, lon)
    st.write(f"**SMAP Soil Moisture ({sm_date}):** {'{:.3f}'.format(sm_val) if sm_val else 'N/A'}")
    # Soil Texture
    tex_code = get_soil_texture(region)
    st.write(f"**Soil Texture:** {TEXTURE_CLASSES.get(tex_code, 'N/A')} (class {tex_code})")
    # Salinity
    sal = get_salinity(region, start_date, end_date)
    st.write(f"**Salinity (NDSI):** {'{:.3f}'.format(sal) if sal else 'N/A'}")
    # Organic Carbon
    oc = get_organic_carbon(region, start_date, end_date)
    st.write(f"**Organic Carbon (%):** {'{:.2f}'.format(oc*100) if oc else 'N/A'}")
    # CEC
    cec = estimate_cec(region, start_date, end_date, intercept, slope_clay, slope_om)
    st.write(f"**Cation Exchange Capacity (cmolc/kg):** {'{:.2f}'.format(cec) if cec else 'N/A'}")
    # LST
    lst = get_lst(region, start_date, end_date)
    st.write(f"**Land Surface Temperature (°C):** {'{:.2f}'.format(lst) if lst else 'N/A'}")
else:
    st.info("Draw a polygon on the map to analyze all parameters.")
