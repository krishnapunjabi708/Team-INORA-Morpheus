import os
import json
import base64
import ee
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# =====================
# GEE Initialization Function
# =====================
ee_initialized = False

def initialize_ee():
    global ee_initialized
    try:
        # Fetch Base64-encoded credentials from the environment variable
        credentials_base64 = os.getenv("GEE_CREDENTIALS")
        if not credentials_base64:
            raise ValueError("❌ Google Earth Engine credentials are missing. Set 'GEE_CREDENTIALS' in Hugging Face Secrets.")
        
        # Decode the Base64 string to get the JSON credentials
        try:
            credentials_json_str = base64.b64decode(credentials_base64).decode("utf-8")
            credentials_dict = json.loads(credentials_json_str)
        except Exception as e:
            raise ValueError(f"❌ Failed to decode Base64 credentials: {e}")
        
        # Use ServiceAccountCredentials from Earth Engine's client library
        from ee import ServiceAccountCredentials
        credentials = ServiceAccountCredentials(credentials_dict['client_email'], key_data=credentials_json_str)
        ee.Initialize(credentials)
        ee_initialized = True
        print("✅ Google Earth Engine initialized successfully.")
    except Exception as e:
        ee_initialized = False
        print(f"❌ Google Earth Engine initialization failed: {e}")

# Call the initialization at startup
initialize_ee()

# =====================
# FastAPI Setup
# =====================
app = FastAPI(
    title="Soil & Crop Parameter API",
    description="FastAPI app using Google Earth Engine to provide soil and crop parameters",
    version="1.0"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to your Flutter frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================
# Utility Functions
# =====================
def safe_get_info(ee_object, default_value=None):
    try:
        return ee_object.getInfo()
    except Exception:
        return default_value

def sentinel_composite(start_date, end_date):
    collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterDate(start_date, end_date) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
        .median() \
        .divide(10000)
    return collection

def get_ndwi(region, start_date, end_date):
    composite = sentinel_composite(start_date, end_date)
    ndwi = composite.normalizedDifference(['B3', 'B8']).rename('NDWI')
    return safe_get_info(ndwi.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=30
    ).get('NDWI'), 0.0)

def get_lst(region, start_date, end_date):
    collection = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
        .filterDate(start_date, end_date).filterBounds(region)

    def convert_temp(img):
        lst = img.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15)
        return lst.set("system:time_start", img.get("system:time_start"))

    temp_collection = collection.map(convert_temp)
    mean_lst = temp_collection.mean()

    return safe_get_info(mean_lst.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=30
    ).values().get(0), 0.0)

# =====================
# Request Schema
# =====================
class LocationQuery(BaseModel):
    lat: float
    lon: float
    start_date: Optional[str] = "2023-01-01"
    end_date: Optional[str] = "2023-12-31"

# =====================
# API Endpoints
# =====================
@app.post("/get_soil_crop_params")
def get_soil_crop_parameters(data: LocationQuery):
    if not ee_initialized:
        return {"error": "Google Earth Engine is not initialized."}

    point = ee.Geometry.Point(data.lon, data.lat)

    # NDWI
    ndwi = get_ndwi(point, data.start_date, data.end_date)

    # LST
    lst = get_lst(point, data.start_date, data.end_date)

    return {
        "latitude": data.lat,
        "longitude": data.lon,
        "NDWI": ndwi,
        "Land_Surface_Temp_C": lst
    }

@app.get("/")
def root():
    return {"message": "Welcome to the Soil & Crop Parameters API"}
