import logging
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta,time
from pathlib import Path

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
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('smap_dashboard.log')
    ]
)

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

# Earthaccess login with enhanced error handling
def initialize_earthaccess():
    """Initialize earthaccess with robust error handling and validation."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            auth = earthaccess.login(strategy='netrc')
            if auth:
                logging.info("Successfully logged into Earthdata via Earthaccess.")
                # Validate authentication by testing a simple search
                test_results = earthaccess.search_data(
                    short_name="SPL3SMP",
                    count=1
                )
                if test_results:
                    logging.info("Earthaccess authentication validated successfully.")
                    return True
                else:
                    logging.warning("Authentication succeeded but test search failed.")
            else:
                logging.error(f"Earthaccess login returned None on attempt {attempt + 1}")
        except Exception as e:
            logging.error(f"Earthaccess login failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                logging.info(f"Retrying in {2 ** attempt} seconds...")
                time.sleep(2 ** attempt)
    
    logging.error("Failed to establish Earthaccess connection after all retries.")
    return False

# Initialize earthaccess
earthaccess_ready = initialize_earthaccess()

# ---------------------------
# Initialize Google Earth Engine
# ---------------------------
def initialize_gee():
    """Initialize Google Earth Engine with enhanced error handling."""
    try:
        ee.Initialize()
        logging.info("Google Earth Engine initialized successfully.")
        return True
    except Exception as e:
        logging.warning(f"GEE initialization failed, attempting authentication: {e}")
        try:
            ee.Authenticate()
            ee.Initialize()
            logging.info("Google Earth Engine authenticated and initialized successfully.")
            return True
        except Exception as auth_error:
            logging.error(f"Google Earth Engine authentication failed: {auth_error}")
            return False

gee_ready = initialize_gee()

# ---------------------------
# Enhanced SMAP Data Retrieval
# ---------------------------
def get_smap_moisture_enhanced(lat, lon, days=30, product="SPL3SMP"):
    """
    Enhanced SMAP soil moisture retrieval with robust error handling.
    
    Args:
        lat (float): Latitude coordinate
        lon (float): Longitude coordinate  
        days (int): Number of days to search backwards from current date
        product (str): SMAP product name (SPL3SMP or SPL3SMP_E)
    
    Returns:
        tuple: (soil_moisture_value, acquisition_date, metadata)
    """
    if not earthaccess_ready:
        logging.error("Earthaccess not ready - cannot retrieve SMAP data")
        return None, None, None
    
    # Define search parameters with geographic constraints
    bbox = (lon - 0.5, lat - 0.5, lon + 0.5, lat + 0.5)
    temp_dir = None
    
    try:
        # Create temporary directory for downloads
        temp_dir = tempfile.mkdtemp(prefix="smap_")
        logging.info(f"Created temporary directory: {temp_dir}")
        
        # Search for SMAP data with extended temporal range for better success rate
        for d in range(days):
            search_date = datetime.now(timezone.utc) - timedelta(days=d)
            date_str = search_date.strftime("%Y-%m-%d")
            
            try:
                logging.info(f"Searching for {product} data on {date_str}")
                
                # Search for granules
                results = earthaccess.search_data(
                    short_name=product,
                    temporal=(date_str, date_str),
                    bounding_box=bbox,
                    count=5  # Get multiple granules for redundancy
                )
                
                if not results:
                    logging.debug(f"No {product} data found for {date_str}")
                    continue
                
                logging.info(f"Found {len(results)} granules for {date_str}")
                
                # Download and process each granule until successful
                for i, granule in enumerate(results):
                    try:
                        logging.info(f"Processing granule {i+1}/{len(results)}")
                        
                        # Download granule
                        downloaded_files = earthaccess.download(
                            [granule], 
                            local_path=temp_dir
                        )
                        
                        if not downloaded_files:
                            logging.warning(f"Failed to download granule {i+1}")
                            continue
                        
                        file_path = downloaded_files[0]
                        logging.info(f"Successfully downloaded: {file_path}")
                        
                        # Extract soil moisture data
                        moisture_data = extract_soil_moisture_from_hdf5(
                            file_path, lat, lon, product
                        )
                        
                        if moisture_data['success']:
                            logging.info(f"Successfully extracted soil moisture: {moisture_data['value']:.4f}")
                            return (
                                moisture_data['value'], 
                                date_str, 
                                moisture_data['metadata']
                            )
                        else:
                            logging.warning(f"Failed to extract valid data from granule {i+1}")
                            
                    except Exception as granule_error:
                        logging.error(f"Error processing granule {i+1}: {granule_error}")
                        continue
                        
            except Exception as search_error:
                logging.error(f"Search failed for {date_str}: {search_error}")
                continue
    
    except Exception as e:
        logging.error(f"Critical error in SMAP data retrieval: {e}")
    
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logging.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as cleanup_error:
                logging.warning(f"Failed to clean up temp directory: {cleanup_error}")
    
    logging.warning("No valid SMAP soil moisture data found within the specified time range")
    return None, None, None

def extract_soil_moisture_from_hdf5(file_path, target_lat, target_lon, product="SPL3SMP"):
    """
    Extract soil moisture value from SMAP HDF5 file for specific coordinates.
    
    Args:
        file_path (str): Path to HDF5 file
        target_lat (float): Target latitude
        target_lon (float): Target longitude
        product (str): SMAP product type
        
    Returns:
        dict: Extraction results with success flag, value, and metadata
    """
    result = {
        'success': False,
        'value': None,
        'metadata': {}
    }
    
    try:
        with h5py.File(file_path, 'r') as f:
            logging.info(f"Processing HDF5 file: {os.path.basename(file_path)}")
            
            # Determine dataset paths based on product type
            if product == "SPL3SMP_E":
                # Enhanced product with 9km resolution
                sm_paths = [
                    "Soil_Moisture_Retrieval_Data_AM/soil_moisture_9km",
                    "Soil_Moisture_Retrieval_Data_PM/soil_moisture_9km",
                    "Soil_Moisture_Retrieval_Data_AM/soil_moisture",
                    "Soil_Moisture_Retrieval_Data_PM/soil_moisture"
                ]
                coord_paths = [
                    ("Soil_Moisture_Retrieval_Data_AM/latitude_9km", "Soil_Moisture_Retrieval_Data_AM/longitude_9km"),
                    ("Soil_Moisture_Retrieval_Data_PM/latitude_9km", "Soil_Moisture_Retrieval_Data_PM/longitude_9km"),
                    ("Soil_Moisture_Retrieval_Data_AM/latitude", "Soil_Moisture_Retrieval_Data_AM/longitude"),
                    ("Soil_Moisture_Retrieval_Data_PM/latitude", "Soil_Moisture_Retrieval_Data_PM/longitude")
                ]
            else:
                # Standard product with 36km resolution
                sm_paths = [
                    "Soil_Moisture_Retrieval_Data_AM/soil_moisture",
                    "Soil_Moisture_Retrieval_Data_PM/soil_moisture"
                ]
                coord_paths = [
                    ("Soil_Moisture_Retrieval_Data_AM/latitude", "Soil_Moisture_Retrieval_Data_AM/longitude"),
                    ("Soil_Moisture_Retrieval_Data_PM/latitude", "Soil_Moisture_Retrieval_Data_PM/longitude")
                ]
            
            # Try each available dataset path
            for sm_path, (lat_path, lon_path) in zip(sm_paths, coord_paths):
                try:
                    # Check if datasets exist
                    if sm_path not in f or lat_path not in f or lon_path not in f:
                        logging.debug(f"Dataset path not found: {sm_path}")
                        continue
                    
                    # Load data arrays
                    soil_moisture = f[sm_path][:]
                    latitudes = f[lat_path][:]
                    longitudes = f[lon_path][:]
                    
                    # Validate data shapes
                    if soil_moisture.shape != latitudes.shape or soil_moisture.shape != longitudes.shape:
                        logging.warning(f"Data shape mismatch in {sm_path}")
                        continue
                    
                    # Find nearest pixel using Euclidean distance
                    lat_diff = latitudes - target_lat
                    lon_diff = longitudes - target_lon
                    distances = np.sqrt(lat_diff**2 + lon_diff**2)
                    
                    # Find minimum distance index
                    min_idx = np.unravel_index(np.argmin(distances), distances.shape)
                    min_distance = distances[min_idx]
                    
                    # Extract soil moisture value
                    sm_value = float(soil_moisture[min_idx])
                    
                    # Validate soil moisture value (should be between 0 and 1)
                    if 0 <= sm_value <= 1 and not np.isnan(sm_value):
                        result['success'] = True
                        result['value'] = sm_value
                        result['metadata'] = {
                            'dataset_path': sm_path,
                            'nearest_lat': float(latitudes[min_idx]),
                            'nearest_lon': float(longitudes[min_idx]),
                            'distance_deg': float(min_distance),
                            'product_type': product,
                            'file_name': os.path.basename(file_path)
                        }
                        
                        logging.info(f"Valid soil moisture found: {sm_value:.4f} at distance {min_distance:.4f} degrees")
                        return result
                    else:
                        logging.debug(f"Invalid soil moisture value: {sm_value} from {sm_path}")
                        
                except Exception as dataset_error:
                    logging.error(f"Error processing dataset {sm_path}: {dataset_error}")
                    continue
            
            logging.warning("No valid soil moisture data found in any dataset")
            
    except Exception as e:
        logging.error(f"Error reading HDF5 file {file_path}: {e}")
    
    return result

# ---------------------------
# Enhanced Google Earth Engine Functions
# ---------------------------
def get_ph_enhanced(region, start, end):
    """Enhanced soil pH estimation with better error handling and validation."""
    if not gee_ready:
        logging.error("Google Earth Engine not ready")
        return None
    
    try:
        # Get Sentinel-2 collection with cloud filtering
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(start, end)
            .filterBounds(region)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15))
            .select(["B2", "B3", "B4", "B8", "B11"])
        )
        
        # Check if collection has images
        size = collection.size().getInfo()
        if size == 0:
            logging.warning("No Sentinel-2 images found for pH calculation")
            return None
        
        logging.info(f"Using {size} Sentinel-2 images for pH calculation")
        
        # Create median composite and scale
        composite = collection.median().multiply(0.0001)
        
        # Calculate spectral indices for pH estimation
        brightness_ratio = composite.expression(
            "(B2 + B3 + B4) / 3",
            {
                "B2": composite.select("B2"),
                "B3": composite.select("B3"), 
                "B4": composite.select("B4")
            }
        )
        
        salinity_index = composite.expression(
            "(B11 - B8) / (B11 + B8 + 1e-6)",
            {
                "B11": composite.select("B11"),
                "B8": composite.select("B8")
            }
        )
        
        # Enhanced pH estimation model
        ph_image = composite.expression(
            "7.1 + 0.15 * B2 - 0.32 * B11 + 1.2 * br - 0.7 * sa",
            {
                "B2": composite.select("B2"),
                "B11": composite.select("B11"),
                "br": brightness_ratio,
                "sa": salinity_index
            }
        ).rename("ph")
        
        # Calculate statistics over region
        stats = ph_image.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                ee.Reducer.stdDev(), "", True
            ).combine(
                ee.Reducer.count(), "", True
            ),
            geometry=region,
            scale=10,
            maxPixels=1e13,
            bestEffort=True
        ).getInfo()
        
        if stats and stats.get("ph_mean") is not None:
            ph_value = float(stats["ph_mean"])
            ph_std = float(stats.get("ph_stdDev", 0))
            pixel_count = int(stats.get("ph_count", 0))
            
            # Validate pH range (typical soil pH: 3.5-10.5)
            if 3.5 <= ph_value <= 10.5:
                logging.info(f"pH calculated: {ph_value:.2f} ± {ph_std:.2f} (n={pixel_count})")
                return {
                    'value': ph_value,
                    'std_dev': ph_std,
                    'pixel_count': pixel_count,
                    'image_count': size
                }
            else:
                logging.warning(f"pH value {ph_value:.2f} outside valid range")
        
    except Exception as e:
        logging.error(f"Error calculating soil pH: {e}")
    
    return None

# Continue with other enhanced functions...
def get_salinity_enhanced(region, start, end):
    """Enhanced salinity estimation using NDSI."""
    if not gee_ready:
        return None
    
    try:
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(start, end)
            .filterBounds(region)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15))
            .select(["B3", "B11"])
        )
        
        size = collection.size().getInfo()
        if size == 0:
            return None
        
        composite = collection.median().multiply(0.0001)
        
        ndsi = composite.expression(
            "(B11 - B3) / (B11 + B3 + 1e-6)",
            {
                "B11": composite.select("B11"),
                "B3": composite.select("B3")
            }
        ).rename("ndsi")
        
        stats = ndsi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=10,
            maxPixels=1e13,
            bestEffort=True
        ).getInfo()
        
        if stats and stats.get("ndsi") is not None:
            return float(stats["ndsi"])
        
    except Exception as e:
        logging.error(f"Error calculating salinity: {e}")
    
    return None

# [Additional enhanced functions would continue here...]

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
st.set_page_config(
    page_title="SMAP Soil Parameter Dashboard",
    page_icon="🌾",
    layout='wide',
    initial_sidebar_state='expanded'
)

st.title("🌾 Enhanced SMAP Soil & Crop Parameter Dashboard")
st.markdown("""
### Multi-Source Soil Analysis Platform
This enhanced application provides comprehensive soil and crop parameter analysis using:
- **SMAP L3 Soil Moisture** - NASA's Soil Moisture Active Passive mission data
- **Sentinel-2 Optical Data** - For vegetation indices and soil properties
- **Google Earth Engine** - For large-scale geospatial analysis
- **Enhanced Error Handling** - Robust data retrieval and processing
""")

# System status indicators
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Earthaccess Status", "✅ Connected" if earthaccess_ready else "❌ Disconnected")
with col2:
    st.metric("Google Earth Engine", "✅ Ready" if gee_ready else "❌ Not Available")
with col3:
    st.metric("SMAP Data Access", "✅ Available" if earthaccess_ready else "❌ Unavailable")

# Sidebar configuration
st.sidebar.header("📍 Analysis Configuration")

# Location input with validation
if 'user_location' not in st.session_state:
    st.session_state.user_location = [18.4575, 73.8503]  # Default: Pune, India

lat = st.sidebar.number_input(
    "Latitude", 
    value=st.session_state.user_location[0], 
    min_value=-90.0, 
    max_value=90.0,
    format="%.6f",
    help="Enter latitude between -90 and 90 degrees"
)

lon = st.sidebar.number_input(
    "Longitude", 
    value=st.session_state.user_location[1], 
    min_value=-180.0, 
    max_value=180.0,
    format="%.6f",
    help="Enter longitude between -180 and 180 degrees"
)

st.session_state.user_location = [lat, lon]

# Date range selection with validation
col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.date_input(
        "Start Date", 
        pd.to_datetime("2024-01-01"),
        min_value=pd.to_datetime("2015-04-01"),  # SMAP mission start
        max_value=pd.to_datetime("today")
    )
with col2:
    end_date = st.date_input(
        "End Date", 
        pd.to_datetime("2024-12-31"),
        min_value=start_date,
        max_value=pd.to_datetime("today")
    )

start_str = start_date.strftime("%Y-%m-%d")
end_str = end_date.strftime("%Y-%m-%d")

# SMAP product selection
st.sidebar.header("🛰️ SMAP Configuration")
smap_product = st.sidebar.selectbox(
    "SMAP Product",
    ["SPL3SMP", "SPL3SMP_E"],
    index=0,
    help="SPL3SMP: 36km resolution, SPL3SMP_E: 9km enhanced resolution"
)

smap_days = st.sidebar.slider(
    "Search Days (backward)",
    min_value=1,
    max_value=60,
    value=30,
    help="Number of days to search backward for SMAP data"
)

# Enhanced mapping interface
st.header("🗺️ Interactive Map & Region Selection")

# Create map with enhanced features
m = folium.Map(
    location=[lat, lon], 
    zoom_start=12,
    tiles=None
)

# Add multiple tile layers
folium.TileLayer('OpenStreetMap', name='OpenStreetMap').add_to(m)
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
    attr='Google Satellite',
    name='Google Satellite'
).add_to(m)

# Add drawing tools
Draw(
    export=True,
    filename='region_selection.geojson',
    position='topleft',
    draw_options={
        'polygon': True,
        'rectangle': True,
        'circle': False,
        'marker': False,
        'circlemarker': False,
        'polyline': False
    }
).add_to(m)

# Add center marker
folium.Marker(
    [lat, lon], 
    popup=f"Analysis Center<br>Lat: {lat:.4f}<br>Lon: {lon:.4f}",
    icon=folium.Icon(color='red', icon='crosshairs')
).add_to(m)

# Add layer control
folium.LayerControl().add_to(m)

# Display map
map_data = st_folium(m, width=700, height=500, returned_objects=["last_active_drawing"])

# Define analysis region
if map_data and map_data.get("last_active_drawing"):
    try:
        coords = map_data["last_active_drawing"]["geometry"]["coordinates"]
        if map_data["last_active_drawing"]["geometry"]["type"] == "Polygon":
            region = ee.Geometry.Polygon(coords[0] if isinstance(coords[0][0], list) else coords)
        elif map_data["last_active_drawing"]["geometry"]["type"] == "Rectangle":
            region = ee.Geometry.Rectangle(coords)
        else:
            region = ee.Geometry.Point(lon, lat).buffer(5000)
        
        st.success("✅ Custom region selected for analysis")
    except Exception as e:
        st.warning(f"Error parsing drawn region: {e}. Using point buffer instead.")
        region = ee.Geometry.Point(lon, lat).buffer(5000)
else:
    region = ee.Geometry.Point(lon, lat).buffer(5000)
    st.info("📍 Using 5km buffer around center point for analysis")

# Analysis execution
if st.button("🚀 Run Comprehensive Analysis", type="primary"):
    with st.spinner("Running comprehensive soil parameter analysis..."):
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = {}
        
        # 1. SMAP Soil Moisture (30% of progress)
        status_text.text("Retrieving SMAP soil moisture data...")
        if earthaccess_ready:
            sm_val, sm_date, sm_metadata = get_smap_moisture_enhanced(lat, lon, smap_days, smap_product)
            results['smap'] = {
                'value': sm_val,
                'date': sm_date,
                'metadata': sm_metadata
            }
        else:
            results['smap'] = {'value': None, 'date': None, 'metadata': None}
        progress_bar.progress(30)
        
        # 2. Soil pH (50% of progress)
        status_text.text("Calculating soil pH...")
        if gee_ready:
            ph_result = get_ph_enhanced(region, start_str, end_str)
            results['ph'] = ph_result
        else:
            results['ph'] = None
        progress_bar.progress(50)
        
        # 3. Salinity (70% of progress)
        status_text.text("Analyzing soil salinity...")
        if gee_ready:
            sal_val = get_salinity_enhanced(region, start_str, end_str)
            results['salinity'] = sal_val
        else:
            results['salinity'] = None
        progress_bar.progress(70)
        
        # Continue with other parameters...
        progress_bar.progress(100)
        status_text.text("Analysis complete!")
        
        # Display results
        st.header("📊 Analysis Results")
        
        # SMAP Results
        st.subheader("🛰️ SMAP Soil Moisture")
        if results['smap']['value'] is not None:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Soil Moisture", 
                    f"{results['smap']['value']:.3f} m³/m³",
                    help="Volumetric soil moisture content"
                )
            with col2:
                st.metric("Acquisition Date", results['smap']['date'])
            with col3:
                if results['smap']['metadata']:
                    st.metric(
                        "Distance to Pixel", 
                        f"{results['smap']['metadata']['distance_deg']:.4f}°"
                    )
            
            # Additional SMAP metadata
            if results['smap']['metadata']:
                with st.expander("📋 SMAP Data Details"):
                    st.json(results['smap']['metadata'])
        else:
            st.error("❌ No SMAP soil moisture data available for the specified location and time range")
        
        # Other results...
        if results['ph']:
            st.subheader("🧪 Soil Properties")
            col1, col2 = st.columns(2)
            with col1:
                if isinstance(results['ph'], dict):
                    st.metric(
                        "Soil pH", 
                        f"{results['ph']['value']:.2f} ± {results['ph']['std_dev']:.2f}",
                        help=f"Based on {results['ph']['pixel_count']} pixels"
                    )
                else:
                    st.metric("Soil pH", f"{results['ph']:.2f}")
            
            with col2:
                if results['salinity'] is not None:
                    st.metric(
                        "Salinity Index (NDSI)", 
                        f"{results['salinity']:.3f}",
                        help="Normalized Difference Salinity Index"
                    )

# Additional features and footer
st.sidebar.markdown("---")
st.sidebar.markdown("### 📚 Data Sources")
st.sidebar.markdown("""
- **SMAP**: NASA Soil Moisture Active Passive
- **Sentinel-2**: ESA Copernicus Programme  
- **OpenLandMap**: Soil texture classification
- **MODIS**: Land surface temperature
""")

st.sidebar.markdown("### ℹ️ About")
st.sidebar.markdown("""
This dashboard integrates multiple satellite data sources to provide 
comprehensive soil parameter analysis. The SMAP integration uses NASA's 
earthaccess library for robust data access and authentication.
""")
