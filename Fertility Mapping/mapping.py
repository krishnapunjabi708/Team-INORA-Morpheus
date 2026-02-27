import os
import certifi
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import pandas as pd
import datetime
import time
from folium.plugins import Draw

# Attempt automatic geolocation.
use_geolocation = False
try:
    from streamlit_geolocation import st_geolocation  # pip install streamlit-geolocation
    use_geolocation = True
except ModuleNotFoundError:
    st.warning("Automatic geolocation module not found. Using manual location input.")

# ----------------------------------------
# 1. Initialize Earth Engine
# ----------------------------------------
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# ----------------------------------------
# 2. App Title & Description
# ----------------------------------------
st.title("Real‑Time Crop & Soil Fertility Mapping")
st.write("""
This application uses near real‑time Sentinel‑2 data to compute key vegetation indices and a Fertility Index 
(for which Fertility = MSAVI – BSI). The Fertility Overlay highlights field zones with different fertilizer needs:
- **Red:** Low fertility (add more fertilizer).
- **Yellow:** Moderate fertility (apply fertilizer moderately).
- **Green:** High fertility (little or no fertilizer needed).

After drawing your field boundary, capture your current location so that the map centers on your field and shows exactly where you are standing.
""")

# ----------------------------------------
# 3. Capture Real‑Time Farmer Location
# ----------------------------------------
if use_geolocation:
    if st.button("Get Real‑Time Location"):
        location = st_geolocation(timeout=10)
        if location is not None:
            st.session_state.user_location = [location["lat"], location["lon"]]
            st.success(f"Location captured: {location['lat']:.6f}, {location['lon']:.6f}")
        else:
            st.error("Unable to get location from browser; please allow location access or use manual input.")
else:
    st.info("Enter your current location manually:")
    lat = st.sidebar.number_input("Latitude", value=18.4575, format="%.6f")
    lon = st.sidebar.number_input("Longitude", value=73.8503, format="%.6f")
    st.session_state.user_location = [lat, lon]

if "user_location" not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]

st.sidebar.header("📍 Current Location")
st.sidebar.write(f"{st.session_state.user_location[0]:.6f}, {st.session_state.user_location[1]:.6f}")

# ----------------------------------------
# 4. Date and Composite Period Settings
# ----------------------------------------
mode = st.sidebar.radio("Select Mode:", ("Real‑Time (Shifted)", "Custom Date Range"))
if mode == "Real‑Time (Shifted)":
    today = datetime.datetime.today()
    # Use data from 14 days ago to 7 days ago for composite (7-day delay ensures data availability)
    end_date = today - datetime.timedelta(days=7)
    start_date = today - datetime.timedelta(days=30)
    st.sidebar.info(f"Data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
else:
    st.sidebar.header("📅 Date Range")
    start_date = pd.to_datetime(st.sidebar.date_input("Start Date", pd.to_datetime("2023-05-01")))
    end_date   = pd.to_datetime(st.sidebar.date_input("End Date", pd.to_datetime("2023-05-07")))

st.sidebar.header("⏳ Composite Period (Days)")
comp_days = st.sidebar.number_input("Composite Period", value=7, min_value=1, max_value=30, step=1)

# ----------------------------------------
# 5. Draw Field Boundary (ROI)
# ----------------------------------------
m = folium.Map(location=st.session_state.user_location, zoom_start=15)
folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="Satellite").add_to(m)
Draw(export=True).add_to(m)
# Mark the current location with a temporary marker
folium.Marker(st.session_state.user_location, popup="Your Location", tooltip="Your Field", icon=folium.Icon(color="blue", icon="user")).add_to(m)
map_data = st_folium(m, width=700, height=500)

selected_boundary = None
if map_data and "last_active_drawing" in map_data:
    selected_boundary = map_data["last_active_drawing"]
    st.write("### Selected Field Boundary", selected_boundary)

# ----------------------------------------
# 6. Process and Compute Indices
# ----------------------------------------
@st.cache_data(show_spinner=False)
def compute_indices(_region, start_date, end_date, comp_days):
    composite_period = datetime.timedelta(days=comp_days)
    current_start = start_date
    ndvi_list, ndwi_list, evi_list, savi_list, ndre_list = [], [], [], [], []
    msavi_list, bsi_list = [], []
    date_list = []
    
    periods = 0
    temp_start = start_date
    while temp_start < end_date:
        periods += 1
        temp_start += composite_period

    st.write(f"Processing {periods} composite periods...")
    progress_bar = st.progress(0)
    count = 0

    # Required Sentinel-2 bands
    required_bands = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11']

    # Use Sentinel-2 Level-2A if available; fallback to L1C.
    collection = ee.ImageCollection("COPERNICUS/S2_SR")
    test_img = collection.filterDate(start_date.strftime("%Y-%m-%d"),
                                     (start_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                                    ).filterBounds(_region).first()
    if test_img is None:
        st.warning("No S2_SR image found; falling back to Sentinel-2 L1C.")
        collection = ee.ImageCollection("COPERNICUS/S2")
    else:
        try:
            band_names = test_img.bandNames().getInfo()
        except Exception:
            st.warning("Error retrieving bands from S2_SR; falling back to Sentinel-2 L1C.")
            collection = ee.ImageCollection("COPERNICUS/S2")
        else:
            if not band_names or not all(b in band_names for b in required_bands):
                st.warning("Required bands missing; falling back to Sentinel-2 L1C.")
                collection = ee.ImageCollection("COPERNICUS/S2")

    while current_start < end_date:
        current_end = current_start + composite_period
        s2 = (collection.filterDate(current_start.strftime("%Y-%m-%d"),
                                    current_end.strftime("%Y-%m-%d"))
              .filterBounds(_region)
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
              .select(required_bands))
        s2_median = s2.median().clip(_region)

        try:
            bands = s2_median.bandNames().getInfo()
        except Exception:
            bands = []
        if not bands:
            st.write(f"No data for period starting {current_start.strftime('%Y-%m-%d')}. Skipping.")
            current_start = current_end
            count += 1
            progress_bar.progress(min(count / periods, 1.0))
            time.sleep(0.3)
            continue

        # Compute various indices.
        ndvi = s2_median.normalizedDifference(['B8', 'B4']).rename('NDVI')
        ndwi = s2_median.normalizedDifference(['B3', 'B11']).rename('NDWI')
        evi = s2_median.expression(
            '2.5 * ((NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1))',
            {'NIR': s2_median.select('B8'),
             'Red': s2_median.select('B4'),
             'Blue': s2_median.select('B2')}
        ).rename('EVI')
        savi = s2_median.expression(
            '((NIR - Red) / (NIR + Red + 0.5)) * 1.5',
            {'NIR': s2_median.select('B8'),
             'Red': s2_median.select('B4')}
        ).rename('SAVI')
        ndre = s2_median.normalizedDifference(['B8', 'B5']).rename('NDRE')
        msavi = s2_median.expression(
            '(2 * NIR + 1 - sqrt(pow(2 * NIR + 1, 2) - 8 * (NIR - Red)))/2',
            {'NIR': s2_median.select('B8'),
             'Red': s2_median.select('B4')}
        ).rename('MSAVI')
        bsi = s2_median.expression(
            '((Red + SWIR) - (NIR + Blue)) / ((Red + SWIR) + (NIR + Blue))',
            {'Red': s2_median.select('B4'),
             'SWIR': s2_median.select('B11'),
             'NIR': s2_median.select('B8'),
             'Blue': s2_median.select('B2')}
        ).rename('BSI')

        stats = ee.Image.cat(ndvi, ndwi, evi, savi, ndre, msavi, bsi).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=_region,
            scale=20,
            maxPixels=1e9
        ).getInfo()

        if stats:
            ndvi_val = stats.get('NDVI')
            ndwi_val = stats.get('NDWI')
            evi_val = stats.get('EVI')
            savi_val = stats.get('SAVI')
            ndre_val = stats.get('NDRE')
            msavi_val = stats.get('MSAVI')
            bsi_val = stats.get('BSI')
            if (ndvi_val is not None and ndwi_val is not None and evi_val is not None and 
                savi_val is not None and ndre_val is not None and msavi_val is not None and bsi_val is not None):
                ndvi_list.append(ndvi_val)
                ndwi_list.append(ndwi_val)
                evi_list.append(evi_val)
                savi_list.append(savi_val)
                ndre_list.append(ndre_val)
                msavi_list.append(msavi_val)
                bsi_list.append(bsi_val)
                date_list.append(current_start.strftime("%Y-%m-%d"))
        else:
            st.write(f"No stats computed for period starting {current_start.strftime('%Y-%m-%d')}.")
            
        current_start = current_end
        count += 1
        progress_bar.progress(min(count / periods, 1.0))
        time.sleep(0.3)

    df = pd.DataFrame({
        "Date": pd.to_datetime(date_list),
        "NDVI": ndvi_list,
        "NDWI": ndwi_list,
        "EVI": evi_list,
        "SAVI": savi_list,
        "NDRE": ndre_list,
        "MSAVI": msavi_list,
        "BSI": bsi_list
    })
    st.write("Composite DataFrame (first few rows):", df.head())
    return df, collection, required_bands

# Proceed only if a field has been drawn.
if selected_boundary:
    try:
        _region = ee.Geometry.Polygon(selected_boundary["geometry"]["coordinates"])
        with st.spinner("Processing composite images..."):
            df, used_collection, required_bands = compute_indices(_region, start_date, end_date, comp_days)

        # ----------------------------------------
        # 7. Create Latest Composite Image and Compute Overlays
        # ----------------------------------------
        st.write("### Latest Composite Map")
        s2_latest = (used_collection.filterDate(
                        end_date.strftime("%Y-%m-%d"),
                        (end_date + datetime.timedelta(days=comp_days)).strftime("%Y-%m-%d")
                     )
                     .filterBounds(_region)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                     .select(required_bands))
        s2_latest_median = s2_latest.median().clip(_region)
        
        ndvi_latest = s2_latest_median.normalizedDifference(['B8', 'B4']).rename('NDVI')
        ndwi_latest = s2_latest_median.normalizedDifference(['B3', 'B11']).rename('NDWI')
        msavi_latest = s2_latest_median.expression(
            '(2 * B8 + 1 - sqrt(pow(2 * B8 + 1,2) - 8*(B8 - B4)))/2',
            {'B8': s2_latest_median.select('B8'),
             'B4': s2_latest_median.select('B4')}
        ).rename('MSAVI')
        bsi_latest = s2_latest_median.expression(
            '((B4 + B11) - (B8 + B2))/((B4 + B11) + (B8 + B2))',
            {'B4': s2_latest_median.select('B4'),
             'B11': s2_latest_median.select('B11'),
             'B8': s2_latest_median.select('B8'),
             'B2': s2_latest_median.select('B2')}
        ).rename('BSI')
        
        # Compute Fertility Index: Fertility = MSAVI - BSI.
        fertility_latest = msavi_latest.subtract(bsi_latest).rename('Fertility')
        
        # ----------------------------------------
        # 8. Select Map Overlay and Mark Farmer's Position
        # ----------------------------------------
        param_choice = st.selectbox("Select Overlay:", ("NDVI", "NDWI", "Fertility"))
        if param_choice == "NDVI":
            vis_params = {'min': 0, 'max': 1, 'palette': ['#f7fcf5','#e5f5e0','#c7e9c0','#74c476','#238b45']}
            param_image = ndvi_latest
            description = "**NDVI Overlay:** White indicates low vegetation; dark green indicates high vegetation."
        elif param_choice == "NDWI":
            vis_params = {'min': -1, 'max': 1, 'palette': ['#f7fbff','#deebf7','#c6dbef','#9ecae1','#6baed6','#3182bd']}
            param_image = ndwi_latest
            description = "**NDWI Overlay:** Light blue indicates low moisture; dark blue indicates high moisture."
        else:
            # Fertility overlay: red indicates low fertility, yellow moderate, green high fertility.
            vis_params = {'min': -1, 'max': 1, 'palette': ['#d73027','#f46d43','#fee08b','#a6d96a','#1a9850']}
            param_image = fertility_latest
            description = "**Fertility Overlay:** Red areas require more fertilizer; green areas require little or none."
            
        st.write(description)
        map_id_dict = ee.Image(param_image).getMapId(vis_params)
        
        m_param = folium.Map(location=st.session_state.user_location, zoom_start=15)
        folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="Satellite").add_to(m_param)
        folium.GeoJson(data=_region.getInfo(), name="Selected Field").add_to(m_param)
        # Add overlay from Earth Engine.
        folium.TileLayer(
            tiles=map_id_dict['tile_fetcher'].url_format,
            attr="Google Earth Engine",
            name=param_choice,
            overlay=True,
            control=True
        ).add_to(m_param)
        # Mark the farmer's current real-time location on the fertility map.
        folium.Marker(
            st.session_state.user_location,
            popup="Farmer's Current Location",
            tooltip="You are here",
            icon=folium.Icon(color="blue", icon="user", prefix="fa")
        ).add_to(m_param)
        folium.LayerControl().add_to(m_param)
        
        st_folium(m_param, width=700, height=500)

    except Exception as e:
        st.error(f"⚠ Error: {str(e)}")
        st.write("Select a different region or check your internet connection.")
else:
    st.write("**🛑 Please select an area on the map for analysis.**")
