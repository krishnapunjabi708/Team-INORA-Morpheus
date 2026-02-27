import logging
import os
from datetime import datetime

import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import pandas as pd
from folium.plugins import Draw
import numpy as np

# ---------------------------
# Logging Configuration
# ---------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Earth Engine
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# ---------------------------
# Streamlit App: CEC Estimation
# ---------------------------
st.title("🌾 Farmer Tool: Estimate Soil CEC Using Satellites Only")
st.markdown("""
This tool calculates **Cation Exchange Capacity (CEC)** of your soil using **only satellite data (Sentinel-2)**.

- 🚁️ **No lab testing required**
- 🗘️ Just draw your farm on the map
- 📈 Get an instant CEC estimate to understand your soil's ability to hold nutrients

**What is CEC?**
> CEC tells how well your soil holds nutrients like calcium and magnesium. Higher CEC is better for crops.

👉 **Draw your farm area on the map below to begin.**
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

# Sidebar: CEC Model Coefficients
st.sidebar.header("🧪 Linear Model Coefficients")
intercept = st.sidebar.number_input("Intercept", value=5.0, step=0.1)
slope_clay = st.sidebar.number_input("Slope (Clay Index)", value=20.0, step=0.1)
slope_om = st.sidebar.number_input("Slope (OM Index)", value=15.0, step=0.1)

# Sidebar: Interpretation Ranges
st.sidebar.header("📈 Interpretation Ranges")
poor_max = st.sidebar.number_input("Poor max (cmolc/kg)", value=10.0, step=0.1)
good_min = st.sidebar.number_input("Good min (cmolc/kg)", value=15.0, step=0.1)
good_max = st.sidebar.number_input("Good max (cmolc/kg)", value=25.0, step=0.1)

# Map with Draw Tool
m = folium.Map(location=[lat, lon], zoom_start=13)
Draw(export=True).add_to(m)
folium.TileLayer(
    "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr='Google'
).add_to(m)
folium.Marker(st.session_state.user_location, popup='Your Location').add_to(m)
map_data = st_folium(m, width=700, height=500)

# Region Detection
coords_raw = None
if map_data and map_data.get('last_active_drawing'):
    coords_raw = map_data['last_active_drawing'].get('geometry', {}).get('coordinates')

region = None
if coords_raw:
    st.write("✅ Polygon drawn.")
    try:
        if isinstance(coords_raw[0][0], (float, int)):
            region = ee.Geometry.Polygon([coords_raw])
        else:
            region = ee.Geometry.Polygon(coords_raw)
    except Exception as e:
        st.error("⚠️ Could not create region polygon. Try drawing a new one.")
        logging.error(f"Polygon creation error: {e}")

# Estimate CEC Using Sentinel-2
def estimate_cec(region, start, end, intercept, slope_clay, slope_om):
    try:
        # Standardize band selection and casting
        collection = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(region)
            .filterDate(str(start), str(end))
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            .select(['B2', 'B4', 'B8', 'B11', 'B12'])
            .map(lambda img: img.cast({
                'B2': 'float', 'B4': 'float', 
                'B8': 'float', 'B11': 'float', 'B12': 'float'
            }))
        )

        count = collection.size().getInfo()
        if count == 0:
            logging.warning("No Sentinel-2 images found in the selected range.")
            return None

        # Compute median with explicit band handling
        s2 = collection.median().multiply(0.0001).clip(region)

        # Calculate indices with named outputs
        clay = s2.expression(
            '(B11 - B8) / (B11 + B8 + 1e-6)',
            {'B11': s2.select('B11'), 'B8': s2.select('B8')}
        ).rename('clay_index')

        om = s2.expression(
            '(B8 - B4) / (B8 + B4 + 1e-6)',
            {'B8': s2.select('B8'), 'B4': s2.select('B4')}
        ).rename('om_index')

        reducer = ee.Reducer.mean()
        logging.info("Reducing region for clay and OM values")
        
        clay_info = clay.reduceRegion(
            reducer=reducer,
            geometry=region,
            scale=20,  # Match Sentinel-2 SWIR resolution
            bestEffort=True,
            maxPixels=1e9
        ).getInfo()

        om_info = om.reduceRegion(
            reducer=reducer,
            geometry=region,
            scale=20,
            bestEffort=True,
            maxPixels=1e9
        ).getInfo()

        clay_mean = clay_info.get('clay_index')
        om_mean = om_info.get('om_index')

        if clay_mean is None or om_mean is None:
            logging.warning("Missing data for clay or OM indices")
            return None

        logging.info(f"Clay Index: {clay_mean}, OM Index: {om_mean}")
        return intercept + slope_clay * clay_mean + slope_om * om_mean

    except Exception as e:
        logging.error(f"Failed to estimate CEC: {str(e)}")
        return None

# Show CEC Estimate
if region:
    with st.spinner("Calculating CEC using Sentinel-2 data..."):
        cec_val = estimate_cec(region, start_date, end_date, intercept, slope_clay, slope_om)

    if cec_val is None:
        st.error("⚠️ Could not compute CEC. Try a larger area or different dates.")
    else:
        st.write(f"### 🧪 Estimated CEC: {cec_val:.2f} cmolc/kg")

        if cec_val < poor_max:
            st.warning(f"⚠️ Poor CEC: Below {poor_max:.1f} cmolc/kg")
        elif good_min <= cec_val <= good_max:
            st.success(f"✅ Good CEC: Between {good_min:.1f} and {good_max:.1f} cmolc/kg")
        else:
            st.info("ℹ️ Moderate CEC: Outside ideal range")
else:
    st.info("🗺️ Draw a polygon on the map to start the calculation.")

# Footer
st.caption("📡 Estimated using Sentinel-2 satellite data via Google Earth Engine. No ground data or lab input used.")
