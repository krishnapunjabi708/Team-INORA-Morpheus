import logging
from pathlib import Path
import numpy as np
from datetime import datetime, timedelta
import os
import time
import asyncio
try:
    import earthaccess
    from pyhdf.SD import SD, SDC
    EARTH_AVAILABLE = True
except ModuleNotFoundError:
    EARTH_AVAILABLE = False
import folium
from folium.plugins import Draw
import streamlit as st
from streamlit_folium import st_folium

# -------------------------------
# Configuration & Logging
# -------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# Earthdata credentials
NASA_USERNAME = "krishnapunjabi"
NASA_PASSWORD = "Krishna708333@"

# Check dependencies
if not EARTH_AVAILABLE:
    logger.error("earthaccess or pyhdf not found. Install using 'pip install earthaccess pyhdf'.")
    st.error("earthaccess or pyhdf not found. Install using 'pip install earthaccess pyhdf'.")
    raise ImportError("earthaccess and pyhdf are required")

# Authenticate with Earthdata
def setup_earthdata_auth():
    netrc_path = Path.home() / ".netrc"
    start_time = time.time()
    try:
        os.environ["EARTHDATA_USERNAME"] = NASA_USERNAME
        os.environ["EARTHDATA_PASSWORD"] = NASA_PASSWORD
        auth = earthaccess.login(strategy="environment")
        if auth.authenticated:
            logger.info(f"Authenticated using environment variables in {time.time() - start_time:.2f}s")
            return auth
    except Exception as e:
        logger.warning(f"Environment variable auth failed: {e}")

    try:
        if not netrc_path.exists():
            with netrc_path.open("w") as f:
                f.write(f"machine urs.earthdata.nasa.gov login {NASA_USERNAME} password {NASA_PASSWORD}\n")
            try:
                netrc_path.chmod(0o600)
            except Exception as e:
                logger.warning(f"Failed to set .netrc permissions: {e}")
            logger.info(f"Created .netrc at {netrc_path}")
        auth = earthaccess.login(strategy="netrc")
        if auth.authenticated:
            logger.info(f"Authenticated using .netrc in {time.time() - start_time:.2f}s")
            return auth
        else:
            raise ValueError("Failed to authenticate with .netrc")
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        st.error(
            f"Authentication failed: {e}. "
            f"Verify credentials at https://urs.earthdata.nasa.gov or create .netrc at {netrc_path} "
            "with: machine urs.earthdata.nasa.gov login krishnapunjabi password Krishna708333@"
        )
        raise

auth = setup_earthdata_auth()

# Async data fetching
async def fetch_nrt_data_async(dataset_shortname, start_date, end_date, bbox, extended=False):
    start_time = time.time()
    try:
        results = earthaccess.search_data(
            short_name=dataset_shortname,
            temporal=(start_date, end_date),
            bounding_box=bbox,
            cloud_hosted=True,
            count=1
        )
        if not results:
            logger.warning(f"No data found for {dataset_shortname}")
            return None
        files = earthaccess.download(results, local_path=str(Path("nrt_data")))
        logger.info(f"Downloaded {dataset_shortname} in {time.time() - start_time:.2f}s: {files}")
        return files[0] if files else None
    except Exception as e:
        logger.error(f"Failed to fetch {dataset_shortname}: {e}")
        return None

# Read MODIS band with pyhdf
def read_modis_band(hdf_path, subdataset_path, scale_factor=0.0001):
    start_time = time.time()
    try:
        hdf = SD(hdf_path, SDC.READ)
        dataset = hdf.select(subdataset_path)
        data = dataset.get().astype(np.float32)
        data = data * scale_factor
        data[data < 0] = np.nan
        dataset.endaccess()
        hdf.end()
        logger.info(f"Read {subdataset_path} in {time.time() - start_time:.2f}s")
        return data
    except Exception as e:
        logger.error(f"Failed to read {subdataset_path} from {hdf_path}: {e}")
        raise

# Read HLS band with pyhdf
def read_hls_band(hdf_path, band_name):
    subdataset = f"Level2:band{band_name}"
    start_time = time.time()
    try:
        hdf = SD(hdf_path, SDC.READ)
        dataset = hdf.select(subdataset)
        data = dataset.get().astype(np.float32)
        data[data < 0] = np.nan
        dataset.endaccess()
        hdf.end()
        logger.info(f"Read {subdataset} in {time.time() - start_time:.2f}s")
        return data
    except Exception as e:
        logger.error(f"Failed to read band {band_name} from {hdf_path}: {e}")
        raise

# Vegetation index calculations
def calculate_ndvi(nir, red):
    return (nir - red) / (nir + red + 1e-10)

def calculate_evi(nir, red, blue):
    return 2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1 + 1e-10)

def calculate_savi(nir, red, L=0.5):
    return (nir - red) * (1 + L) / (nir + red + L + 1e-10)

def calculate_msavi(nir, red):
    return (2 * nir + 1 - np.sqrt((2 * nir + 1)**2 - 8 * (nir - red))) / 2

def calculate_ndmi(nir, swir1):
    return (nir - swir1) / (nir + swir1 + 1e-10)

def calculate_ndwi(green, nir):
    return (green - nir) / (green + nir + 1e-10)

def calculate_nbr(nir, swir2):
    return (nir - swir2) / (nir + swir2 + 1e-10)

def calculate_nbr2(swir1, swir2):
    return (swir1 - swir2) / (swir1 + swir2 + 1e-10)

def calculate_tvi(green, red, nir):
    return np.sqrt(np.abs((nir - red) / (nir + red + 0.5) + 0.5))

# Process indices
@st.cache_data(show_spinner=False)
def process_nrt_vegetation_indices(output_dir="nrt_indices", bbox=(-180, -90, 180, 90), use_hls=True, indices=None):
    total_start = time.time()
    output_path = Path(output_dir)
    data_path = Path("nrt_data")
    output_path.mkdir(exist_ok=True)
    data_path.mkdir(exist_ok=True)

    # Time ranges
    end_date = datetime.utcnow()
    start_date_16 = end_date - timedelta(days=16)
    start_date_30 = end_date - timedelta(days=30)
    logger.info(f"Fetching data for {start_date_16} to {end_date}")

    # Progress bar
    progress = st.progress(0)
    status_text = st.empty()
    steps = 10 if use_hls else 7  # Adjust steps based on HLS
    step = 0

    # Async fetch
    async def fetch_all():
        mod13q1_task = fetch_nrt_data_async("MOD13Q1", start_date_16, end_date, bbox)
        mod09ga_task = fetch_nrt_data_async("MOD09GA", start_date_16, end_date, bbox)
        hls_task = None
        if use_hls:
            hls_task = fetch_nrt_data_async("HLSL30", start_date_16, end_date, bbox)
        return await asyncio.gather(mod13q1_task, mod09ga_task, hls_task if use_hls else None)

    status_text.text("Fetching NRT data...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    mod13q1_file, mod09ga_file, hls_file = loop.run_until_complete(fetch_all())
    loop.close()

    step += 3 if use_hls else 2
    progress.progress(step / steps)

    # HLS fallback
    if use_hls and not hls_file:
        logger.info("No HLSL30 data, trying HLSS30...")
        hls_file = loop.run_until_complete(fetch_nrt_data_async("HLSS30", start_date_16, end_date, bbox))
        if not hls_file:
            logger.info("No HLSS30 data, extending to 30 days...")
            hls_file = loop.run_until_complete(fetch_nrt_data_async("HLSL30", start_date_30, end_date, bbox, extended=True))
            if not hls_file:
                hls_file = loop.run_until_complete(fetch_nrt_data_async("HLSS30", start_date_30, end_date, bbox, extended=True))

    if not mod13q1_file or not mod09ga_file:
        st.error("Failed to fetch required MODIS datasets")
        logger.error("Failed to fetch required MODIS datasets")
        raise ValueError("Failed to fetch MODIS datasets")

    # Process MOD13Q1
    status_text.text("Processing MOD13Q1...")
    try:
        ndvi_modis = read_modis_band(mod13q1_file, "MODIS_Grid_16DAY_250m_500m_VI/1")
        evi_modis = read_modis_band(mod13q1_file, "MODIS_Grid_16DAY_250m_500m_VI/2")
        np.save(output_path / "NDVI_MOD13Q1.npy", ndvi_modis)
        np.save(output_path / "EVI_MOD13Q1.npy", evi_modis)
        step += 1; progress.progress(step / steps)
    except Exception as e:
        st.error(f"MOD13Q1 processing failed: {e}")
        raise

    # Process MOD09GA
    status_text.text("Processing MOD09GA...")
    try:
        red_mod09 = read_modis_band(mod09ga_file, "MODIS_Grid_500m_2D/sur_refl_b01")
        nir_mod09 = read_modis_band(mod09ga_file, "MODIS_Grid_500m_2D/sur_refl_b02")
        blue_mod09 = read_modis_band(mod09ga_file, "MODIS_Grid_500m_2D/sur_refl_b03")
        green_mod09 = read_modis_band(mod09ga_file, "MODIS_Grid_500m_2D/sur_refl_b04")
        swir1_mod09 = read_modis_band(mod09ga_file, "MODIS_Grid_500m_2D/sur_refl_b06")
        swir2_mod09 = read_modis_band(mod09ga_file, "MODIS_Grid_500m_2D/sur_refl_b07")
        step += 1; progress.progress(step / steps)
    except Exception as e:
        st.error(f"MOD09GA processing failed: {e}")
        raise

    # Calculate MOD09GA indices
    status_text.text("Calculating MOD09GA indices...")
    mod09ga_indices = {}
    if indices:
        for idx in indices:
            if idx == "SAVI": mod09ga_indices["SAVI"] = calculate_savi(nir_mod09, red_mod09)
            elif idx == "MSAVI": mod09ga_indices["MSAVI"] = calculate_msavi(nir_mod09, red_mod09)
            elif idx == "NDMI": mod09ga_indices["NDMI"] = calculate_ndmi(nir_mod09, swir1_mod09)
            elif idx == "NDWI": mod09ga_indices["NDWI"] = calculate_ndwi(green_mod09, nir_mod09)
            elif idx == "NBR": mod09ga_indices["NBR"] = calculate_nbr(nir_mod09, swir2_mod09)
            elif idx == "NBR2": mod09ga_indices["NBR2"] = calculate_nbr2(swir1_mod09, swir2_mod09)
            elif idx == "TVI": mod09ga_indices["TVI"] = calculate_tvi(green_mod09, red_mod09, nir_mod09)
    step += 1; progress.progress(step / steps)

    # Save MOD09GA results
    status_text.text("Saving MOD09GA results...")
    for idx, data in mod09ga_indices.items():
        np.save(output_path / f"{idx}_MOD09GA.npy", data)
    step += 1; progress.progress(step / steps)

    # Process HLS if available and enabled
    if use_hls and hls_file:
        status_text.text("Processing HLS...")
        try:
            blue_hls = read_hls_band(hls_file, "02")
            green_hls = read_hls_band(hls_file, "03")
            red_hls = read_hls_band(hls_file, "04")
            nir_hls = read_hls_band(hls_file, "05")
            swir1_hls = read_hls_band(hls_file, "11")
            swir2_hls = read_hls_band(hls_file, "12")
            step += 1; progress.progress(step / steps)

            # Calculate HLS indices
            status_text.text("Calculating HLS indices...")
            hls_indices = {}
            if indices:
                for idx in indices:
                    if idx == "NDVI": hls_indices["NDVI"] = calculate_ndvi(nir_hls, red_hls)
                    elif idx == "EVI": hls_indices["EVI"] = calculate_evi(nir_hls, red_hls, blue_hls)
                    elif idx == "SAVI": hls_indices["SAVI"] = calculate_savi(nir_hls, red_hls)
                    elif idx == "MSAVI": hls_indices["MSAVI"] = calculate_msavi(nir_hls, red_hls)
                    elif idx == "NDMI": hls_indices["NDMI"] = calculate_ndmi(nir_hls, swir1_hls)
                    elif idx == "NDWI": hls_indices["NDWI"] = calculate_ndwi(green_hls, nir_hls)
                    elif idx == "NBR": hls_indices["NBR"] = calculate_nbr(nir_hls, swir2_hls)
                    elif idx == "NBR2": hls_indices["NBR2"] = calculate_nbr2(swir1_hls, swir2_hls)
                    elif idx == "TVI": hls_indices["TVI"] = calculate_tvi(green_hls, red_hls, nir_hls)
            step += 1; progress.progress(step / steps)

            # Save HLS results
            status_text.text("Saving HLS results...")
            for idx, data in hls_indices.items():
                np.save(output_path / f"{idx}_HLS.npy", data)
            step += 1; progress.progress(step / steps)
        except Exception as e:
            st.warning(f"HLS processing failed: {e}. Skipping HLS indices.")
            logger.warning(f"HLS processing failed: {e}")
    else:
        st.warning("HLS data not found or disabled. Skipping HLS indices.")
        logger.warning("HLS data not found or disabled")
        if use_hls: step += 3; progress.progress(step / steps)

    status_text.text("Processing complete!")
    logger.info(f"Total processing time: {time.time() - total_start:.2f}s")
    st.success(f"Processing complete. Results saved in {output_path}")

# Streamlit app
def main():
    st.title("NASA NRT Vegetation Index Processor")
    st.write("Select a region and indices for processing NASA satellite data.")

    # Map setup (Pune, India)
    lat, lon = 18.5204, 73.8567
    m = folium.Map(location=[lat, lon], zoom_start=12)
    Draw(export=True).add_to(m)
    folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google").add_to(m)
    folium.Marker([lat, lon], popup="Pune").add_to(m)

    # Display map
    map_data = st_folium(m, width=700, height=500)

    # Extract bounding box
    bbox = get_bbox_from_map_data(map_data)
    if bbox == (-180, -90, 180, 90):
        bbox = (73.7, 18.4, 74.0, 18.6)  # Pune default
    st.write(f"Selected bounding box: {bbox}")

    # HLS toggle
    use_hls = st.checkbox("Include HLS data (may be slow or unavailable)", value=False)

    # Index selection
    indices = st.multiselect(
        "Select indices to compute",
        ["NDVI", "EVI", "SAVI", "MSAVI", "NDMI", "NDWI", "NBR", "NBR2", "TVI"],
        default=["NDVI", "EVI"]
    )

    # Process button
    if st.button("Process NRT Data"):
        try:
            process_nrt_vegetation_indices(output_dir="nrt_indices", bbox=bbox, use_hls=use_hls, indices=indices)
        except Exception as e:
            st.error(f"Error during processing: {e}")
            logger.error(f"Processing error: {e}")

def get_bbox_from_map_data(map_data):
    if map_data and "last_active_drawing" in map_data and map_data["last_active_drawing"]:
        bounds = map_data["last_active_drawing"]["geometry"]["coordinates"][0]
        lons = [point[0] for point in bounds]
        lats = [point[1] for point in bounds]
        return (min(lons), min(lats), max(lons), max(lats))
    return (-180, -90, 180, 90)

if __name__ == "__main__":
    main()