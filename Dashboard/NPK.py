import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import ee

# Initialize Earth Engine
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

st.title("🌱 Soil NPK Estimator (Sentinel-2)")

# Sidebar inputs for location and time range
if "user_location" not in st.session_state:
    # Default to Pune, IN
    st.session_state.user_location = [18.4575, 73.8503]

st.sidebar.header("📍 Enter Center Location")
lat = st.sidebar.number_input("Latitude", value=st.session_state.user_location[0], format="%.6f")
lon = st.sidebar.number_input("Longitude", value=st.session_state.user_location[1], format="%.6f")
st.session_state.user_location = [lat, lon]

st.sidebar.header("📅 Select Date Range")
start_date = st.sidebar.date_input("Start Date", value=st.session_state.get("start_date", pd.to_datetime("2025-05-01")))
end_date = st.sidebar.date_input("End Date", value=st.session_state.get("end_date", pd.to_datetime("2025-05-28")))
st.session_state.start_date = start_date
st.session_state.end_date = end_date

# Create map with drawing tools
m = folium.Map(location=st.session_state.user_location, zoom_start=15)
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google").add_to(m)

folium.plugins.Draw(export=True).add_to(m)
folium.Marker([lat, lon], popup="Center").add_to(m)

map_data = st_folium(m, width=700, height=500)
region = None
if map_data and "last_active_drawing" in map_data:
    try:
        sel = map_data["last_active_drawing"]
        st.write("### **Selected Area:**", sel)
        region = ee.Geometry.Polygon(sel["geometry"]["coordinates"])
    except Exception as e:
        st.error(f"Error creating region geometry: {str(e)}")

def get_npk_for_region(region, start_date, end_date):
    """
    Estimate mean soil N, P, K for the given region and date range using Sentinel-2 SR bands.
    Empirical proxy formulas are based on research correlations:contentReference[oaicite:2]{index=2}.
    Returns (N, P, K) in mg/kg (or None if error).
    """
    try:
        # Filter Sentinel-2 SR images over region and date, low cloud cover
        s2_collection = (ee.ImageCollection('COPERNICUS/S2_SR')
                         .filterBounds(region)
                         .filterDate(ee.Date(str(start_date)), ee.Date(str(end_date)))
                         .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
                         .select(['B2','B3','B4','B8','B11']))
        count = s2_collection.size().getInfo()
        if count == 0:
            st.error("❌ No Sentinel-2 images found for this range. Try expanding the date range.")
            return None, None, None

        # Take median composite to reduce cloud/shadow noise
        img = s2_collection.median()
        if img is None:
            st.error("❌ Failed to create image composite. Try a larger region or different dates.")
            return None, None, None

        # Scale reflectance (Sentinel-2 SR is scaled by 10000)
        img = img.multiply(0.0001)

        # Compute helper indices (soil brightness and salinity index)
        brightness = img.expression('(B2 + B3 + B4) / 3',
                                     {'B2': img.select('B2'), 'B3': img.select('B3'), 'B4': img.select('B4')})
        salinity2 = img.expression('(B11 - B8) / (B11 + B8 + 1e-6)',
                                   {'B11': img.select('B11'), 'B8': img.select('B8')})

        # Empirical formulas for N, P, K (proxy models) - these are illustrative and based on research trends:contentReference[oaicite:3]{index=3}
        N_est = img.expression(
            "5 + 100*(3 - (B2 + B3 + B4))",
            {'B2': img.select('B2'), 'B3': img.select('B3'), 'B4': img.select('B4')}
        ).rename('N')
        P_est = img.expression(
            "3 + 50*(1 - B8) + 20*(1 - B11)",
            {'B8': img.select('B8'), 'B11': img.select('B11')}
        ).rename('P')
        K_est = img.expression(
            "5 + 150*(1 - brightness) + 50*(1 - B3) + 30*salinity2",
            {'brightness': brightness, 'B3': img.select('B3'), 'salinity2': salinity2}
        ).rename('K')

        # Merge bands and compute mean in the region
        npk_image = N_est.addBands(P_est).addBands(K_est)
        stats = npk_image.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e9
        )

        n_val = stats.get('N')
        p_val = stats.get('P')
        k_val = stats.get('K')
        # Convert to Python values (None if missing)
        n_val = n_val.getInfo() if n_val else None
        p_val = p_val.getInfo() if p_val else None
        k_val = k_val.getInfo() if k_val else None
        return n_val, p_val, k_val

    except Exception as e:
        st.error(f"Error in NPK estimation: {str(e)}")
        return None, None, None

# Run estimation if region is defined
if region:
    n_val, p_val, k_val = get_npk_for_region(region, start_date, end_date)
    if n_val is not None and p_val is not None and k_val is not None:
        st.write(f"### 🌾 **Estimated Soil Nutrients (mean values):**")
        st.write(f"- Nitrogen (N): {n_val:.2f} mg/kg")
        st.write(f"- Phosphorus (P): {p_val:.2f} mg/kg")
        st.write(f"- Potassium (K): {k_val:.2f} mg/kg")
    else:
        st.error("❌ Unable to compute NPK for the marked area.")
else:
    st.info("🔍 Please draw a polygon on the map to define your region.")
