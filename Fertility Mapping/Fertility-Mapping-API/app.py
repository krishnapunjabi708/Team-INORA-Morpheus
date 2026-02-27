import logging
import os
import base64
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import ee
import datetime

# ---------------------------
# Logging Configuration
# ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ee_initialized = False

def initialize_ee():
    global ee_initialized
    try:
        credentials_base64 = os.getenv("GEE_CREDENTIALS")
        if not credentials_base64:
            raise ValueError(
                "❌ Google Earth Engine credentials are missing. Set 'GEE_CREDENTIALS' environment variable."
            )
        credentials_json_str = base64.b64decode(credentials_base64).decode("utf-8")
        credentials_dict = json.loads(credentials_json_str)
        from ee import ServiceAccountCredentials
        credentials = ServiceAccountCredentials(
            credentials_dict['client_email'], key_data=credentials_json_str
        )
        ee.Initialize(credentials)
        ee_initialized = True
        logging.info("✅ Google Earth Engine initialized successfully.")
    except Exception as e:
        ee_initialized = False
        logging.error(f"❌ Google Earth Engine initialization failed: {e}")

# Initialize Earth Engine with service account
initialize_ee()

app = FastAPI(
    title="Fertility Focus Map API",
    description="Compute field fertility overlay using Google Earth Engine",
    version="1.0.0"
)

# CORS middleware
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error for request {request.url}: {exc!r}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )

class PolygonRequest(BaseModel):
    coordinates: List[List[float]] = Field(
        ..., description="Closed polygon coordinates [lng, lat]"
    )

class FertilityResponse(BaseModel):
    tile_url: str
    start_date: str
    end_date: str
    viz: Dict[str, Any]

@app.post("/fertility", response_model=FertilityResponse)
def compute_fertility(req: PolygonRequest):
    if not ee_initialized:
        raise HTTPException(status_code=500, detail="Earth Engine not initialized")
    try:
        coords = req.coordinates
        # Validate closed polygon
        if len(coords) < 4 or coords[0] != coords[-1]:
            raise HTTPException(status_code=400, detail="Coordinates must form a closed polygon.")

        # Create EE geometry
        region = ee.Geometry.Polygon([coords])

        # Date window
        end_date = datetime.date.today() - datetime.timedelta(days=7)
        start_date = end_date - datetime.timedelta(days=16)

        # Fetch Sentinel-2 collection
        base_coll = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterDate(start_date.isoformat(), end_date.isoformat()) \
            .filterBounds(region) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        size = base_coll.size().getInfo()
        if size == 0:
            # Fallback to 30-day window
            start_date = end_date - datetime.timedelta(days=30)
            base_coll = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterDate(start_date.isoformat(), end_date.isoformat()) \
                .filterBounds(region) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            size = base_coll.size().getInfo()
            if size == 0:
                raise HTTPException(status_code=404, detail="No Sentinel-2 images available for the specified field and dates.")

        # Median composite
        image = base_coll.median().clip(region)

        # Compute indices
        msavi = image.expression(
            '(2*B8 + 1 - sqrt((2*B8 + 1)**2 - 8*(B8 - B4))) / 2',
            {'B8': image.select('B8'), 'B4': image.select('B4')}
        )
        bsi = image.expression(
            '((B4 + B11) - (B8 + B2)) / ((B4 + B11) + (B8 + B2))',
            {'B4': image.select('B4'), 'B11': image.select('B11'), 'B8': image.select('B8'), 'B2': image.select('B2')}
        )
        fertility = msavi.subtract(bsi).rename('Fertility')

        # Visualization
        viz = {'min': -1, 'max': 1, 'palette': ['red', 'yellow', 'green']}
        map_id = fertility.getMapId(viz)

        return FertilityResponse(
            tile_url=map_id['tile_fetcher'].url_format,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            viz=viz
        )

    except HTTPException:
        raise
    except ee.EEException as ee_err:
        logger.error("Earth Engine exception: %s", ee_err, exc_info=True)
        raise HTTPException(status_code=502, detail="Earth Engine request failed")
    except Exception:
        raise

# Uvicorn entrypoint
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)