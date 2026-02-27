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

ee.Initialize()
# ---------------------------
# Secure Earthdata Credentials Setup
# ---------------------------
def setup_earthdata_credentials():
    """Secure setup for Earthdata credentials"""
    username = st.secrets.get("krishnapunjabi", "")
    password = st.secrets.get("Krishna708333@", "")
    
    if not username or not password:
        st.error("Please configure Earthdata credentials in Streamlit secrets")
        st.stop()
    
    netrc_content = f"""machine urs.earthdata.nasa.gov
  login {username}
  password {password}
"""
    
    netrc_path = os.path.expanduser('~/.netrc')
    with open(netrc_path, 'w') as f:
        f.write(netrc_content)
    
    try:
        os.chmod(netrc_path, 0o600)
    except Exception as exc:
        logging.warning("Unable to secure .netrc: %s", exc)
    
    # Earthaccess login
    try:
        earthaccess.login(strategy='netrc')
        logging.info("Logged into Earthdata via Earthaccess.")
        return True
    except Exception as e:
        logging.error("Earthaccess login failed: %s", e)
        return False

# ---------------------------
# Initialize Google Earth Engine
# ---------------------------
def initialize_earth_engine():
    """Initialize Google Earth Engine with proper error handling"""
    try:
        ee.Initialize()
        return True
    except Exception:
        try:
            ee.Authenticate()
            ee.Initialize()
            return True
        except Exception as e:
            st.error(f"Failed to initialize Google Earth Engine: {e}")
            return False

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
# Parameter Functions
# ---------------------------
def get_ph(region, start, end):
    """Calculate synthetic soil pH using Sentinel-2 data"""
    try:
        s2 = (ee.ImageCollection('COPERNICUS/S2_SR')
              .filterBounds(region)
              .filterDate(str(start), str(end))
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5))
              .select(['B2', 'B3', 'B4', 'B8', 'B11'])
              .median().multiply(0.0001))
        
        brightness = s2.expression('(B2+B3+B4)/3', {
            'B2': s2.select('B2'), 
            'B3': s2.select('B3'), 
            'B4': s2.select('B4')
        })
        
        sal2 = s2.expression('(B11-B8)/(B11+B8+1e-6)', {
            'B11': s2.select('B11'), 
            'B8': s2.select('B8')
        })
        
        ph_expr = s2.expression('7.1+0.15*B2-0.32*B11+1.2*br-0.7*sa', {
            'B2': s2.select('B2'), 
            'B11': s2.select('B11'), 
            'br': brightness, 
            'sa': sal2
        }).rename('ph')
        
        val = ph_expr.reduceRegion(ee.Reducer.mean(), region, scale=10).get('ph')
        return float(val.getInfo()) if val else None
    except Exception as e:
        logging.error(f"Error calculating pH: {e}")
        return None

def get_salinity(region, start, end):
    """Calculate salinity using Normalized Difference Salinity Index (NDSI)"""
    try:
        s2 = (ee.ImageCollection('COPERNICUS/S2_SR')
              .filterBounds(region)
              .filterDate(str(start), str(end))
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5))
              .select(['B3', 'B11'])
              .median().multiply(0.0001))
        
        ndsi = s2.expression('(B11-B3)/(B11+B3+1e-6)', {
            'B11': s2.select('B11'), 
            'B3': s2.select('B3')
        }).rename('ndsi')
        
        val = ndsi.reduceRegion(ee.Reducer.mean(), region, scale=10).get('ndsi')
        return float(val.getInfo()) if val else None
    except Exception as e:
        logging.error(f"Error calculating salinity: {e}")
        return None

def get_organic_carbon(region, start, end):
    """Calculate organic carbon using NDVI-based estimation"""
    try:
        s2 = (ee.ImageCollection('COPERNICUS/S2_SR')
              .filterBounds(region)
              .filterDate(str(start), str(end))
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5))
              .select(['B4', 'B8'])
              .median().multiply(0.0001))
        
        ndvi = s2.expression('(B8-B4)/(B8+B4+1e-6)', {
            'B8': s2.select('B8'), 
            'B4': s2.select('B4')
        })
        
        oc = ndvi.multiply(0.05).rename('oc')
        val = oc.reduceRegion(ee.Reducer.mean(), region, scale=10).get('oc')
        return float(val.getInfo()) if val else None
    except Exception as e:
        logging.error(f"Error calculating organic carbon: {e}")
        return None

def estimate_cec(region, start, end, intercept, slope_clay, slope_om):
    """Estimate Cation Exchange Capacity using clay and organic matter indices"""
    try:
        coll = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterBounds(region)
                .filterDate(str(start), str(end))
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                .select(['B2', 'B4', 'B8', 'B11', 'B12'])
                .map(lambda img: img.cast({
                    'B2': 'float', 'B4': 'float', 'B8': 'float', 
                    'B11': 'float', 'B12': 'float'
                })))
        
        if coll.size().getInfo() == 0:
            return None
        
        s2 = coll.median().multiply(0.0001).clip(region)
        
        clay = s2.expression('(B11-B8)/(B11+B8+1e-6)', {
            'B11': s2.select('B11'), 
            'B8': s2.select('B8')
        }).rename('clay')
        
        om = s2.expression('(B8-B4)/(B8+B4+1e-6)', {
            'B8': s2.select('B8'), 
            'B4': s2.select('B4')
        }).rename('om')
        
        clay_m = clay.reduceRegion(ee.Reducer.mean(), region, scale=20).get('clay')
        om_m = om.reduceRegion(ee.Reducer.mean(), region, scale=20).get('om')
        
        if clay_m is None or om_m is None:
            return None
        
        return intercept + slope_clay * float(clay_m.getInfo()) + slope_om * float(om_m.getInfo())
    except Exception as e:
        logging.error(f"Error estimating CEC: {e}")
        return None

def get_smap_moisture(lat, lon, days=7):
    """Retrieve SMAP soil moisture data for given coordinates"""
    try:
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
                    
                    idx = np.unravel_index(
                        np.argmin(np.sqrt((lats-lat)**2+(lons-lon)**2)), 
                        sm.shape
                    )
                    return float(sm[idx]), date_str
        
        return None, None
    except Exception as e:
        logging.error(f"Error retrieving SMAP moisture: {e}")
        return None, None

def get_soil_texture(region):
    """Get predominant soil texture class for the region"""
    try:
        mode = SOIL_TEXTURE_IMG.clip(region.buffer(50000)).reduceRegion(
            reducer=ee.Reducer.mode(), 
            geometry=region, 
            scale=250, 
            maxPixels=1e9
        ).get('b0')
        return int(mode.getInfo()) if mode else None
    except Exception as e:
        logging.error(f"Error getting soil texture: {e}")
        return None

def get_lst(region, start, end):
    """Get Land Surface Temperature from MODIS data"""
    try:
        coll = (ee.ImageCollection('MODIS/006/MOD11A2')
                .filterBounds(region)
                .filterDate(str(start), str(end))
                .select('LST_Day_1km'))
        
        if coll.size().getInfo() == 0:
            return None
        
        lst = coll.median().multiply(0.02).subtract(273.15).rename('lst')
        val = lst.reduceRegion(ee.Reducer.mean(), region, scale=1000).get('lst')
        return float(val.getInfo()) if val else None
    except Exception as e:
        logging.error(f"Error getting LST: {e}")
        return None

def create_polygon_from_coordinates(coords):
    """Create Earth Engine Geometry from map coordinates"""
    try:
        if isinstance(coords[0][0], list):
            # Multi-dimensional array case
            if isinstance(coords[0][0][0], (float, int)):
                return ee.Geometry.Polygon(coords)
            else:
                return ee.Geometry.Polygon(coords[0])
        else:
            # Simple coordinate list
            return ee.Geometry.Polygon([coords])
    except Exception as e:
        logging.error(f"Error creating polygon: {e}")
        return None

# ---------------------------
# Main Streamlit Application
# ---------------------------
def main():
    st.set_page_config(layout='wide', page_title="Soil & Crop Parameter Dashboard")
    
    st.title("🌾 Comprehensive Soil & Crop Parameter Dashboard")
    st.markdown("""
    This application integrates seven key soil and crop parameters using satellite data:
    1. **Synthetic Soil pH** - Estimated from Sentinel-2 spectral indices
    2. **Soil Moisture (SMAP)** - NASA's Soil Moisture Active Passive mission data
    3. **Soil Texture** - OpenLandMap global soil texture classification
    4. **Salinity (NDSI)** - Normalized Difference Salinity Index from Sentinel-2
    5. **Organic Carbon (OC)** - NDVI-based estimation from Sentinel-2
    6. **Cation Exchange Capacity (CEC)** - Modeled from clay and organic matter indices
    7. **Land Surface Temperature (LST)** - MODIS thermal data
    """)
    
    # Initialize services
    if not setup_earthdata_credentials():
        st.error("Failed to setup Earthdata credentials")
        return
    
    if not initialize_earth_engine():
        st.error("Failed to initialize Google Earth Engine")
        return
    
    # Sidebar configuration
    st.sidebar.header("📍 Location & Time Range")
    
    # Initialize session state for location
    if 'user_location' not in st.session_state:
        st.session_state.user_location = [18.4575, 73.8503]  # Default: Pune, India
    
    # Location inputs with proper session state handling
    lat = st.sidebar.number_input(
        "Latitude", 
        value=st.session_state.user_location[0], 
        format='%.6f',
        min_value=-90.0,
        max_value=90.0
    )
    lon = st.sidebar.number_input(
        "Longitude", 
        value=st.session_state.user_location[1], 
        format='%.6f',
        min_value=-180.0,
        max_value=180.0
    )
    
    # Update session state
    st.session_state.user_location = [lat, lon]
    
    # Date range selection
    start_date = st.sidebar.date_input("Start Date", pd.to_datetime('2024-01-01'))
    end_date = st.sidebar.date_input("End Date", pd.to_datetime('2024-12-31'))
    
    # CEC Model Configuration
    st.sidebar.header("🧪 CEC Model Coefficients & Ranges")
    intercept = st.sidebar.number_input("Intercept", value=5.0, step=0.1)
    slope_clay = st.sidebar.number_input("Slope (Clay Index)", value=20.0, step=0.1)
    slope_om = st.sidebar.number_input("Slope (OM Index)", value=15.0, step=0.1)
    
    # Interpretation ranges
    poor_max = st.sidebar.number_input("Poor max (cmolc/kg)", value=10.0, step=0.1)
    good_min = st.sidebar.number_input("Good min (cmolc/kg)", value=15.0, step=0.1)
    good_max = st.sidebar.number_input("Good max (cmolc/kg)", value=25.0, step=0.1)
    
    # Create interactive map
    st.header("🗺️ Interactive Map - Draw Analysis Region")
    
    m = folium.Map(location=[lat, lon], zoom_start=13)
    Draw(export=True).add_to(m)
    
    # Add satellite imagery
    folium.TileLayer(
        "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", 
        attr='Google Satellite', 
        name='Satellite'
    ).add_to(m)
    
    # Add location marker
    folium.Marker([lat, lon], popup='Selected Location', tooltip='Click to see coordinates').add_to(m)
    
    # Render map with streamlit-folium
    map_data = st_folium(m, width=700, height=500, returned_objects=["last_active_drawing"])
    
    # Extract region polygon with improved error handling
    region = None
    if map_data and map_data.get('last_active_drawing'):
        coords = map_data['last_active_drawing']['geometry']['coordinates']
        region = create_polygon_from_coordinates(coords)
        
        if region:
            st.success("✅ Analysis region defined successfully!")
        else:
            st.error("❌ Failed to create analysis region from drawn polygon")
    
    # Analysis section
    if region:
        st.header("📊 Analysis Results")
        
        # Create progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = {}
        total_steps = 7
        current_step = 0
        
        # pH Analysis
        status_text.text("Analyzing soil pH...")
        progress_bar.progress((current_step + 1) / total_steps)
        results['ph'] = get_ph(region, start_date, end_date)
        current_step += 1
        
        # Soil Moisture Analysis
        status_text.text("Retrieving SMAP soil moisture...")
        progress_bar.progress((current_step + 1) / total_steps)
        sm_val, sm_date = get_smap_moisture(lat, lon)
        results['soil_moisture'] = (sm_val, sm_date)
        current_step += 1
        
        # Soil Texture Analysis
        status_text.text("Determining soil texture...")
        progress_bar.progress((current_step + 1) / total_steps)
        results['texture'] = get_soil_texture(region)
        current_step += 1
        
        # Salinity Analysis
        status_text.text("Calculating salinity index...")
        progress_bar.progress((current_step + 1) / total_steps)
        results['salinity'] = get_salinity(region, start_date, end_date)
        current_step += 1
        
        # Organic Carbon Analysis
        status_text.text("Estimating organic carbon...")
        progress_bar.progress((current_step + 1) / total_steps)
        results['organic_carbon'] = get_organic_carbon(region, start_date, end_date)
        current_step += 1
        
        # CEC Analysis
        status_text.text("Calculating cation exchange capacity...")
        progress_bar.progress((current_step + 1) / total_steps)
        results['cec'] = estimate_cec(region, start_date, end_date, intercept, slope_clay, slope_om)
        current_step += 1
        
        # LST Analysis
        status_text.text("Retrieving land surface temperature...")
        progress_bar.progress((current_step + 1) / total_steps)
        results['lst'] = get_lst(region, start_date, end_date)
        current_step += 1
        
        progress_bar.progress(1.0)
        status_text.text("Analysis complete!")
        
        # Display results in organized format
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🧪 Chemical Properties")
            
            # pH
            ph_val = results['ph']
            if ph_val:
                ph_color = "🟢" if 6.0 <= ph_val <= 7.5 else "🟡" if 5.5 <= ph_val <= 8.0 else "🔴"
                st.metric("Soil pH", f"{ph_val:.2f}", help="Optimal range: 6.0-7.5")
                st.write(f"{ph_color} pH Status: {'Optimal' if 6.0 <= ph_val <= 7.5 else 'Acceptable' if 5.5 <= ph_val <= 8.0 else 'Problematic'}")
            else:
                st.metric("Soil pH", "N/A")
            
            # Salinity
            sal_val = results['salinity']
            if sal_val:
                sal_status = "Low" if sal_val < 0.1 else "Moderate" if sal_val < 0.2 else "High"
                sal_color = "🟢" if sal_val < 0.1 else "🟡" if sal_val < 0.2 else "🔴"
                st.metric("Salinity (NDSI)", f"{sal_val:.3f}")
                st.write(f"{sal_color} Salinity Level: {sal_status}")
            else:
                st.metric("Salinity (NDSI)", "N/A")
            
            # Organic Carbon
            oc_val = results['organic_carbon']
            if oc_val:
                oc_percent = oc_val * 100
                oc_status = "High" if oc_percent > 2.0 else "Medium" if oc_percent > 1.0 else "Low"
                oc_color = "🟢" if oc_percent > 2.0 else "🟡" if oc_percent > 1.0 else "🔴"
                st.metric("Organic Carbon", f"{oc_percent:.2f}%")
                st.write(f"{oc_color} OC Level: {oc_status}")
            else:
                st.metric("Organic Carbon", "N/A")
            
            # CEC
            cec_val = results['cec']
            if cec_val:
                if cec_val <= poor_max:
                    cec_status, cec_color = "Poor", "🔴"
                elif good_min <= cec_val <= good_max:
                    cec_status, cec_color = "Good", "🟢"
                else:
                    cec_status, cec_color = "Moderate", "🟡"
                st.metric("CEC (cmolc/kg)", f"{cec_val:.2f}")
                st.write(f"{cec_color} CEC Status: {cec_status}")
            else:
                st.metric("CEC (cmolc/kg)", "N/A")
        
        with col2:
            st.subheader("🌍 Physical Properties")
            
            # Soil Moisture
            sm_val, sm_date = results['soil_moisture']
            if sm_val:
                sm_status = "High" if sm_val > 0.3 else "Medium" if sm_val > 0.15 else "Low"
                sm_color = "🟢" if sm_val > 0.15 else "🟡" if sm_val > 0.1 else "🔴"
                st.metric("SMAP Soil Moisture", f"{sm_val:.3f} m³/m³", help=f"Date: {sm_date}")
                st.write(f"{sm_color} Moisture Level: {sm_status}")
            else:
                st.metric("SMAP Soil Moisture", "N/A")
            
            # Soil Texture
            tex_code = results['texture']
            if tex_code and tex_code in TEXTURE_CLASSES:
                texture_name = TEXTURE_CLASSES[tex_code]
                st.metric("Soil Texture", f"{texture_name}")
                st.write(f"🏺 Texture Class: {tex_code}")
            else:
                st.metric("Soil Texture", "N/A")
            
            # Land Surface Temperature
            lst_val = results['lst']
            if lst_val:
                lst_status = "Hot" if lst_val > 35 else "Warm" if lst_val > 25 else "Cool"
                lst_color = "🔴" if lst_val > 35 else "🟡" if lst_val > 25 else "🟢"
                st.metric("Land Surface Temperature", f"{lst_val:.1f}°C")
                st.write(f"{lst_color} Temperature: {lst_status}")
            else:
                st.metric("Land Surface Temperature", "N/A")
        
        # Summary interpretation
        st.header("📋 Summary & Recommendations")
        
        valid_results = sum(1 for v in [results['ph'], results['salinity'], 
                                      results['organic_carbon'], results['cec'], 
                                      sm_val, results['texture'], results['lst']] if v is not None)
        
        if valid_results >= 4:
            st.success(f"✅ Successfully analyzed {valid_results}/7 parameters for your region.")
            
            # Generate basic recommendations
            recommendations = []
            
            if results['ph'] and (results['ph'] < 6.0 or results['ph'] > 7.5):
                recommendations.append("Consider soil pH adjustment through liming or sulfur application")
            
            if results['organic_carbon'] and results['organic_carbon'] * 100 < 1.0:
                recommendations.append("Increase organic matter through compost or cover cropping")
            
            if results['salinity'] and results['salinity'] > 0.2:
                recommendations.append("Implement drainage improvements to reduce salinity")
            
            if sm_val and sm_val < 0.1:
                recommendations.append("Consider irrigation to improve soil moisture levels")
            
            if recommendations:
                st.write("**Recommended Actions:**")
                for i, rec in enumerate(recommendations, 1):
                    st.write(f"{i}. {rec}")
            else:
                st.write("**Assessment:** Soil conditions appear to be within acceptable ranges.")
        
        else:
            st.warning(f"⚠️ Only {valid_results}/7 parameters could be analyzed. Try a different region or date range.")
    
    else:
        st.info("👆 Draw a polygon on the map above to analyze soil and crop parameters for your area of interest.")
        
        st.markdown("""
        ### How to use this application:
        1. **Adjust the location** using the latitude/longitude inputs in the sidebar
        2. **Select a date range** for your analysis period
        3. **Draw a polygon** on the map to define your analysis region
        4. **Review the results** in the comprehensive analysis section
        
        ### Data Sources:
        - **Sentinel-2**: European Space Agency optical imagery for pH, salinity, and organic carbon estimation[1]
        - **SMAP**: NASA Soil Moisture Active Passive mission for direct soil moisture measurements[11][16]
        - **OpenLandMap**: Global soil texture classification[1]
        - **MODIS**: NASA Terra satellite for land surface temperature[1]
        """)

if __name__ == "__main__":
    main()
