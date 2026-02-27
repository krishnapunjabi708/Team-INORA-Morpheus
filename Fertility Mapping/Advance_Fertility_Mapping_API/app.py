import os
import certifi
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

import logging
import base64
import datetime
import ee
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional

logging.basicConfig(level=logging.INFO)

# ----------------------------------------
# Initialize Earth Engine
# ----------------------------------------
# try:
#     # On Hugging Face, use service account or env-based auth
#     # Set GEE_SERVICE_ACCOUNT and GEE_PRIVATE_KEY in HF secrets
#     service_account = os.getenv("GEE_SERVICE_ACCOUNT")
#     private_key     = os.getenv("GEE_PRIVATE_KEY")

#     if service_account and private_key:
#         # Write key to temp file (GEE requires file path)
#         import json, tempfile
#         key_data = json.loads(private_key)
#         with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
#             json.dump(key_data, f)
#             key_file = f.name
#         credentials = ee.ServiceAccountCredentials(service_account, key_file)
#         ee.Initialize(credentials)
#         logging.info("GEE initialized with service account.")
#     else:
#         ee.Initialize()
#         logging.info("GEE initialized with default credentials.")
# except Exception as e:
#     logging.error(f"GEE initialization failed: {e}")
#     raise RuntimeError(f"GEE init error: {e}")

def initialize_ee():
    global ee_initialized
    try:
        credentials_base64 = os.getenv("GEE_SERVICE_ACCOUNT_KEY")
        if not credentials_base64:
            raise ValueError("❌ Google Earth Engine credentials are missing.")
        credentials_json_str = base64.b64decode(credentials_base64).decode("utf-8")
        credentials_dict = json.loads(credentials_json_str)
        from ee import ServiceAccountCredentials
        credentials = ServiceAccountCredentials(credentials_dict['client_email'], key_data=credentials_json_str)
        ee.Initialize(credentials)
        ee_initialized = True
        logging.info("✅ Google Earth Engine initialized successfully.")
    except Exception as e:
        ee_initialized = False
        logging.error(f"❌ Google Earth Engine initialization failed: {e}")
        raise

initialize_ee()

# ----------------------------------------
# App Setup
# ----------------------------------------
app = FastAPI(
    title="Field Fertility Map API",
    description="Soil fertility mapping using Sentinel-2 and Google Earth Engine",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------
# Parameter Metadata
# ----------------------------------------
PARAM_META = {
    "Fertility Index (Default)": {
        "unit": "index",
        "palette": ["#7f0000", "#c0392b", "#e74c3c", "#f1c40f", "#27ae60", "#1e8449", "#145a32"],
        "min": -0.5, "max": 0.8,
        "labels": ["Very Low", "Low", "Below Avg", "Moderate", "Good", "High", "Very High"],
        "note": "Combined MSAVI − BSI index. Higher = better natural fertility.",
        "invert": False,
    },
    "Nitrogen (N)": {
        "unit": "kg/ha",
        "palette": ["#67000d","#a50026","#d73027","#f46d43","#74c476","#238b45","#00441b"],
        "min": 50, "max": 400,
        "labels": ["<80", "80–130", "130–180", "180–230", "230–280", "280–330", ">330"],
        "note": "Estimated available N via NDRE, EVI, and red-edge indices.",
        "invert": False,
    },
    "Phosphorus (P)": {
        "unit": "kg/ha",
        "palette": ["#67000d","#a50026","#d73027","#f46d43","#74c476","#238b45","#00441b"],
        "min": 2, "max": 50,
        "labels": ["<8", "8–14", "14–20", "20–26", "26–32", "32–38", ">38"],
        "note": "Estimated available P via brightness, NDVI, and SWIR inversion.",
        "invert": False,
    },
    "Potassium (K)": {
        "unit": "kg/ha",
        "palette": ["#67000d","#a50026","#d73027","#f46d43","#74c476","#238b45","#00441b"],
        "min": 40, "max": 450,
        "labels": ["<100", "100–160", "160–220", "220–280", "280–340", "340–400", ">400"],
        "note": "Estimated exchangeable K via SWIR clay index and K mineral proxies.",
        "invert": False,
    },
    "Organic Carbon (OC)": {
        "unit": "%",
        "palette": ["#67000d","#a50026","#d73027","#f46d43","#74c476","#238b45","#00441b"],
        "min": 0.1, "max": 3.5,
        "labels": ["<0.5", "0.5–0.9", "0.9–1.3", "1.3–1.7", "1.7–2.1", "2.1–2.5", ">2.5"],
        "note": "Soil OC %. Dark soils = high OC. Inversely related to brightness and SWIR.",
        "invert": False,
    },
    "Electrical Conductivity (EC)": {
        "unit": "dS/m",
        "palette": ["#00441b","#238b45","#74c476","#f46d43","#d73027","#a50026","#67000d"],
        "min": 0, "max": 8,
        "labels": ["<1", "1–2", "2–3", "3–4", "4–5", "5–6", ">6"],
        "note": "Soil salinity. Green = safe for crops. Red = high salinity (harmful).",
        "invert": True,
    },
    "Calcium (Ca)": {
        "unit": "kg/ha",
        "palette": ["#67000d","#a50026","#d73027","#f46d43","#74c476","#238b45","#00441b"],
        "min": 100, "max": 900,
        "labels": ["<200", "200–330", "330–460", "460–590", "590–720", "720–850", ">850"],
        "note": "Exchangeable Ca via carbonate and SWIR indices.",
        "invert": False,
    },
    "Magnesium (Mg)": {
        "unit": "kg/ha",
        "palette": ["#67000d","#a50026","#d73027","#f46d43","#74c476","#238b45","#00441b"],
        "min": 10, "max": 300,
        "labels": ["<50", "50–90", "90–130", "130–170", "170–210", "210–250", ">250"],
        "note": "Exchangeable Mg via red-edge chlorophyll and SWIR clay indices.",
        "invert": False,
    },
    "Sulphur (S)": {
        "unit": "kg/ha",
        "palette": ["#67000d","#a50026","#d73027","#f46d43","#74c476","#238b45","#00441b"],
        "min": 2, "max": 60,
        "labels": ["<10", "10–18", "18–26", "26–34", "34–42", "42–50", ">50"],
        "note": "Available S via gypsum and salinity indices.",
        "invert": False,
    },
    "Soil pH": {
        "unit": "",
        "palette": ["#67000d","#a50026","#d73027","#238b45","#00441b","#08519c","#08306b"],
        "min": 4.5, "max": 8.5,
        "labels": ["<5.0", "5.0–5.5", "5.5–6.0", "6.0–6.5", "6.5–7.0", "7.0–7.5", ">7.5"],
        "note": "Soil pH. Red = strongly acidic, Green = neutral (ideal ~6.5), Blue = alkaline.",
        "invert": False,
    },
}

# ----------------------------------------
# Pydantic Models
# ----------------------------------------
class AnalyzeRequest(BaseModel):
    coordinates: List[List[float]]   # [[lon, lat], [lon, lat], ...]
    parameter: str = "Fertility Index (Default)"

class StatsResult(BaseModel):
    mean: Optional[float]
    min: Optional[float]
    max: Optional[float]
    unit: str
    interpretation: str
    variability_warning: bool

class AnalyzeResponse(BaseModel):
    tile_url: str
    stats: StatsResult
    date_range: dict
    parameter: str
    meta: dict

# ----------------------------------------
# GEE Layer Builder
# ----------------------------------------
def build_layer(image, param):
    img = image.multiply(0.0001)

    B2  = img.select('B2');  B3  = img.select('B3')
    B4  = img.select('B4');  B5  = img.select('B5')
    B6  = img.select('B6');  B7  = img.select('B7')
    B8  = img.select('B8');  B8A = img.select('B8A')
    B11 = img.select('B11'); B12 = img.select('B12')

    meta = PARAM_META[param]
    viz  = {'min': meta['min'], 'max': meta['max'], 'palette': meta['palette']}

    if param == "Fertility Index (Default)":
        msavi = img.expression(
            '(2*B8 + 1 - sqrt((2*B8+1)**2 - 8*(B8-B4))) / 2',
            {'B8': B8, 'B4': B4})
        bsi = img.expression(
            '((B4+B11) - (B8+B2)) / ((B4+B11) + (B8+B2) + 1e-6)',
            {'B4': B4, 'B11': B11, 'B8': B8, 'B2': B2})
        out = msavi.subtract(bsi).rename('layer')

    elif param == "Nitrogen (N)":
        ndre  = img.expression('(B8A-B5)/(B8A+B5+1e-6)', {'B8A': B8A,'B5': B5})
        evi   = img.expression('2.5*(B8-B4)/(B8+6*B4-7.5*B2+1+1e-6)', {'B8': B8,'B4': B4,'B2': B2})
        ci_re = img.expression('(B7/(B5+1e-6))-1.0', {'B7': B7,'B5': B5})
        mcari = img.expression('((B5-B4)-0.2*(B5-B3))*(B5/(B4+1e-6))', {'B5': B5,'B4': B4,'B3': B3})
        out = (ndre.multiply(180).add(evi.multiply(120))
               .add(ci_re.multiply(15)).add(mcari.multiply(25)).add(200)).rename('layer')

    elif param == "Phosphorus (P)":
        ndvi       = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        brightness = img.expression('(B2+B3+B4)/3.0', {'B2': B2,'B3': B3,'B4': B4})
        si         = B3.multiply(B4).sqrt()
        re_slope   = img.expression('(B7-B5)/(B7+B5+1e-6)', {'B7': B7,'B5': B5})
        swir2_inv  = ee.Image(1.0).subtract(B12)
        out = (ndvi.multiply(20).add(swir2_inv.multiply(15))
               .add(re_slope.multiply(10)).subtract(brightness.multiply(10))
               .add(si.multiply(8)).add(22)).rename('layer')

    elif param == "Potassium (K)":
        ndvi       = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        k_idx      = img.expression('B11/(B5+B6+1e-6)', {'B11': B11,'B5': B5,'B6': B6})
        swir_ratio = img.expression('(B11-B12)/(B11+B12+1e-6)', {'B11': B11,'B12': B12})
        nir_red    = img.expression('B8/(B4+1e-6)', {'B8': B8,'B4': B4})
        out = (k_idx.multiply(180).add(swir_ratio.multiply(60))
               .add(ndvi.multiply(80)).add(nir_red.multiply(10)).add(160)).rename('layer')

    elif param == "Organic Carbon (OC)":
        brightness = img.expression('(B2+B3+B4)/3.0', {'B2': B2,'B3': B3,'B4': B4})
        ndvi       = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        savi       = img.expression('((B8-B4)/(B8+B4+0.5+1e-6))*1.5', {'B8': B8,'B4': B4})
        swir_avg   = B11.add(B12).divide(2)
        ndre       = img.expression('(B8A-B5)/(B8A+B5+1e-6)', {'B8A': B8A,'B5': B5})
        out = (ee.Image(1.0).subtract(brightness).multiply(2.5)
               .add(ndvi.multiply(1.2)).add(savi.multiply(0.8))
               .subtract(swir_avg.multiply(1.5)).add(ndre.multiply(0.6)).add(0.8)).rename('layer')

    elif param == "Electrical Conductivity (EC)":
        ndvi       = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        brightness = img.expression('(B2+B3+B4)/3.0', {'B2': B2,'B3': B3,'B4': B4})
        si1        = B3.multiply(B4).sqrt()
        si2        = B3.pow(2).add(B4.pow(2)).sqrt()
        si_comb    = si1.add(si2).divide(2)
        veg_stress = ee.Image(1.0).subtract(ndvi.clamp(0, 1))
        out = (si_comb.multiply(5.0).add(veg_stress.multiply(3.0))
               .add(brightness.multiply(2.0)).add(0.3)).rename('layer')

    elif param == "Calcium (Ca)":
        carbonate  = img.expression('(B11+B12)/(B4+B3+1e-6)', {'B11': B11,'B12': B12,'B4': B4,'B3': B3})
        brightness = img.expression('(B2+B3+B4)/3.0', {'B2': B2,'B3': B3,'B4': B4})
        ndvi       = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        clay_idx   = img.expression('(B11-B8)/(B11+B8+1e-6)', {'B11': B11,'B8': B8})
        out = (carbonate.multiply(300).add(brightness.multiply(200))
               .subtract(ndvi.multiply(80)).subtract(clay_idx.multiply(60)).add(350)).rename('layer')

    elif param == "Magnesium (Mg)":
        ndre     = img.expression('(B8A-B5)/(B8A+B5+1e-6)', {'B8A': B8A,'B5': B5})
        re_chl   = img.expression('(B7/(B5+1e-6))-1.0', {'B7': B7,'B5': B5})
        mg_clay  = img.expression('(B11-B12)/(B11+B12+1e-6)', {'B11': B11,'B12': B12})
        ndvi     = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        out = (ndre.multiply(80).add(re_chl.multiply(30))
               .add(mg_clay.multiply(25)).add(ndvi.multiply(20)).add(100)).rename('layer')

    elif param == "Sulphur (S)":
        gypsum  = img.expression('B11/(B3+B4+1e-6)', {'B11': B11,'B3': B3,'B4': B4})
        si1     = B3.multiply(B4).sqrt()
        si2     = B3.pow(2).add(B4.pow(2)).sqrt()
        sal_idx = si1.add(si2).divide(2)
        re_red  = img.expression('B5/(B4+1e-6)', {'B5': B5,'B4': B4})
        swir_r  = img.expression('B12/(B11+1e-6)', {'B12': B12,'B11': B11})
        ndvi    = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        out = (gypsum.multiply(18).add(sal_idx.multiply(12))
               .add(re_red.subtract(1).multiply(6)).subtract(swir_r.multiply(8))
               .add(ndvi.multiply(6)).add(18)).rename('layer')

    elif param == "Soil pH":
        ndvi_re    = img.expression(
            '((B8-B5)/(B8+B5+1e-6) + (B8-B4)/(B8+B4+1e-6))/2',
            {'B8': B8,'B5': B5,'B4': B4})
        swir_ratio = img.expression('B11/(B8+1e-6)', {'B11': B11,'B8': B8})
        nir_ratio  = img.expression('B8/(B4+1e-6)', {'B8': B8,'B4': B4})
        brightness = img.expression('(B2+B3+B4)/3.0', {'B2': B2,'B3': B3,'B4': B4})
        out = (ndvi_re.multiply(1.0).add(swir_ratio.multiply(0.6))
               .subtract(nir_ratio.multiply(0.3))
               .add(ee.Image(1.0).subtract(brightness).multiply(0.12)).add(6.2)).rename('layer')
    else:
        return None, None

    return out, viz


# ----------------------------------------
# Helper: interpret stats
# ----------------------------------------
def interpret(mean_val, param):
    meta   = PARAM_META[param]
    mn, mx = meta['min'], meta['max']
    invert = meta['invert']
    low_t  = mn + (mx - mn) * 0.33
    high_t = mn + (mx - mn) * 0.66

    if invert:
        if mean_val < low_t:
            return "Low — Ideal range. Crops should perform well."
        elif mean_val < high_t:
            return "Moderate — Monitor closely. Sensitive crops may be affected."
        else:
            return "High — Soil stress likely. Consider leaching or remediation."
    else:
        if mean_val < low_t:
            return "Low — Deficient. Consider applying inputs to boost levels."
        elif mean_val < high_t:
            return "Moderate — Below optimal. Targeted application recommended."
        else:
            return "Adequate — Good levels. Minimal intervention needed."


# ----------------------------------------
# API Endpoints
# ----------------------------------------

@app.get("/", response_class=HTMLResponse)
def root():
    """Simple HTML test page"""
    params_options = "".join(f'<option value="{p}">{p}</option>' for p in PARAM_META)
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Field Fertility Map API</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js"></script>
        <link rel="stylesheet" href="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css"/>
        <style>
            body {{ font-family: sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            h1 {{ color: #2d6a4f; }}
            #map {{ height: 400px; border-radius: 10px; margin: 20px 0; }}
            select, button {{ padding: 10px 20px; font-size: 1rem; border-radius: 6px; }}
            button {{ background: #2d6a4f; color: white; border: none; cursor: pointer; margin-left: 10px; }}
            button:hover {{ background: #1b4332; }}
            #result {{ background: white; padding: 20px; border-radius: 10px; margin-top: 20px; display: none; }}
            .stat {{ display: inline-block; margin: 10px; padding: 12px 20px; background: #f0f4f0;
                     border-left: 4px solid #2d6a4f; border-radius: 6px; }}
        </style>
    </head>
    <body>
        <h1>🗺️ Field Fertility Map API</h1>
        <p>Draw your field on the map, select a parameter, and click Analyze.</p>
        <div id="map"></div>
        <div>
            <select id="param">{params_options}</select>
            <button onclick="analyze()">🔍 Analyze Field</button>
        </div>
        <div id="result">
            <h3 id="res-title"></h3>
            <div id="stats"></div>
            <p id="interp"></p>
            <div id="map2" style="height:400px; border-radius:10px; margin-top:10px;"></div>
        </div>
        <script>
        var map = L.map('map').setView([18.4575, 73.8503], 14);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);
        var drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);
        var drawControl = new L.Control.Draw({{
            draw: {{ polygon: true, rectangle: true, circle: false, marker: false, polyline: false }},
            edit: {{ featureGroup: drawnItems }}
        }});
        map.addControl(drawControl);
        map.on(L.Draw.Event.CREATED, function(e) {{
            drawnItems.clearLayers();
            drawnItems.addLayer(e.layer);
        }});
        var map2 = null;
        async function analyze() {{
            var layers = drawnItems.getLayers();
            if (layers.length === 0) {{ alert('Please draw a field first!'); return; }}
            var coords = layers[0].toGeoJSON().geometry.coordinates[0];
            var param  = document.getElementById('param').value;
            document.getElementById('result').style.display = 'block';
            document.getElementById('res-title').innerText = '⏳ Analyzing...';
            var res = await fetch('/analyze', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ coordinates: coords, parameter: param }})
            }});
            var data = await res.json();
            if (!res.ok) {{ document.getElementById('res-title').innerText = 'Error: ' + (data.detail || 'Unknown'); return; }}
            document.getElementById('res-title').innerText = data.parameter + ' Analysis';
            document.getElementById('stats').innerHTML = `
                <div class="stat">📊 Mean: <b>${{data.stats.mean?.toFixed(2)}} ${{data.stats.unit}}</b></div>
                <div class="stat">📉 Min: <b>${{data.stats.min?.toFixed(2)}} ${{data.stats.unit}}</b></div>
                <div class="stat">📈 Max: <b>${{data.stats.max?.toFixed(2)}} ${{data.stats.unit}}</b></div>
                ${{data.stats.variability_warning ? '<div class="stat">⚠️ High spatial variability</div>' : ''}}
            `;
            document.getElementById('interp').innerText = '🧪 ' + data.stats.interpretation;
            if (!map2) {{ map2 = L.map('map2').setView([18.4575, 73.8503], 14); L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map2); }}
            L.tileLayer(data.tile_url, {{attribution: 'GEE', opacity: 0.75}}).addTo(map2);
            var poly = L.geoJSON(layers[0].toGeoJSON()).addTo(map2);
            map2.fitBounds(poly.getBounds());
        }}
        </script>
    </body>
    </html>
    """


@app.get("/params")
def get_params():
    """Return all available soil parameters and their metadata"""
    return {
        "parameters": list(PARAM_META.keys()),
        "metadata": PARAM_META
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    """
    Analyze soil fertility for a given field polygon.
    - **coordinates**: List of [lon, lat] pairs forming a closed polygon
    - **parameter**: Soil property to compute (default: Fertility Index)
    """
    param = request.parameter
    if param not in PARAM_META:
        raise HTTPException(status_code=400, detail=f"Unknown parameter: '{param}'. Use GET /params for valid options.")

    if len(request.coordinates) < 3:
        raise HTTPException(status_code=400, detail="Polygon must have at least 3 coordinate pairs.")

    try:
        region = ee.Geometry.Polygon(request.coordinates)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid coordinates: {e}")

    # Date range
    end_date   = datetime.date.today() - datetime.timedelta(days=7)
    start_date = end_date - datetime.timedelta(days=16)

    try:
        coll = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                .filterBounds(region)
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)))

        count = coll.size().getInfo()
        extended = False
        if count == 0:
            start_date = end_date - datetime.timedelta(days=45)
            coll = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                    .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                    .filterBounds(region)
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)))
            extended = True

        image = coll.median().clip(region)

        layer_image, viz = build_layer(image, param)
        if layer_image is None:
            raise HTTPException(status_code=500, detail="Could not build layer for this parameter.")

        # Get tile URL
        tile_dict = layer_image.getMapId(viz)
        tile_url  = tile_dict['tile_fetcher'].url_format

        # Get statistics
        stats_dict = layer_image.reduceRegion(
            reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), sharedInputs=True),
            geometry=region,
            scale=20,
            maxPixels=1e13
        )

        def safe_get(key):
            try:
                return stats_dict.get(key).getInfo()
            except:
                return None

        mean_val = safe_get('layer_mean')
        min_val  = safe_get('layer_min')
        max_val  = safe_get('layer_max')

        # Variability check
        variability_warning = False
        if min_val is not None and max_val is not None:
            spread     = max_val - min_val
            range_span = PARAM_META[param]['max'] - PARAM_META[param]['min']
            variability_warning = spread > range_span * 0.5

        interpretation = interpret(mean_val, param) if mean_val is not None else "No data available."

        return AnalyzeResponse(
            tile_url=tile_url,
            parameter=param,
            date_range={
                "start": start_date.strftime('%Y-%m-%d'),
                "end": end_date.strftime('%Y-%m-%d'),
                "extended_window": extended
            },
            stats=StatsResult(
                mean=round(mean_val, 3) if mean_val is not None else None,
                min=round(min_val, 3) if min_val is not None else None,
                max=round(max_val, 3) if max_val is not None else None,
                unit=PARAM_META[param]['unit'],
                interpretation=interpretation,
                variability_warning=variability_warning,
            ),
            meta={
                "note": PARAM_META[param]['note'],
                "labels": PARAM_META[param]['labels'],
                "palette": PARAM_META[param]['palette'],
                "viz_min": PARAM_META[param]['min'],
                "viz_max": PARAM_META[param]['max'],
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)