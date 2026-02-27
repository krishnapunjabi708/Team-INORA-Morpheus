import os
import certifi
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

import logging
import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import datetime
from folium.plugins import Draw

logging.basicConfig(level=logging.INFO)

# ----------------------------------------
# 1. Initialize Earth Engine
# ----------------------------------------
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# ----------------------------------------
# App Config & Title
# ----------------------------------------
st.set_page_config(layout="wide", page_title="Field Fertility Map")

st.markdown("""
    <style>
    .main-title { font-size: 2rem; font-weight: 700; color: #2d6a4f; margin-bottom: 0; }
    .sub-title  { font-size: 1rem; color: #555; margin-top: 0; }
    .legend-bar {
        height: 24px; border-radius: 6px;
        margin: 6px 0 2px 0;
        border: 1px solid #ccc;
    }
    .legend-labels { display: flex; justify-content: space-between; font-size: 0.78rem; color: #333; }
    .metric-box {
        background: #f0f4f0; border-radius: 10px;
        padding: 14px 20px; margin: 6px 0;
        border-left: 5px solid #2d6a4f;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🗺️ Field Fertility Focus Map</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Draw your field boundary, select a fertility parameter, and visualize soil health across your field.</div>', unsafe_allow_html=True)
st.markdown("---")

# ----------------------------------------
# Helper
# ----------------------------------------
def safe_get_info(val, label=""):
    try:
        return val.getInfo()
    except Exception as e:
        logging.error(f"safe_get_info error [{label}]: {e}")
        return None

# ----------------------------------------
# PARAMETER DEFINITIONS
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
# GEE Layer Builders
# All bands scaled to 0–1 reflectance first
# ----------------------------------------
def build_layer(image, param):
    # KEY FIX: Sentinel-2 SR DN are 0–10000, divide by 10000 for reflectance
    img = image.multiply(0.0001)

    B2  = img.select('B2');  B3  = img.select('B3')
    B4  = img.select('B4');  B5  = img.select('B5')
    B6  = img.select('B6');  B7  = img.select('B7')
    B8  = img.select('B8');  B8A = img.select('B8A')
    B11 = img.select('B11'); B12 = img.select('B12')

    meta = PARAM_META[param]
    viz  = {'min': meta['min'], 'max': meta['max'], 'palette': meta['palette']}

    # ── Fertility Index (Default) ──────────────────────────────────
    if param == "Fertility Index (Default)":
        msavi = img.expression(
            '(2*B8 + 1 - sqrt((2*B8+1)**2 - 8*(B8-B4))) / 2',
            {'B8': B8, 'B4': B4})
        bsi = img.expression(
            '((B4+B11) - (B8+B2)) / ((B4+B11) + (B8+B2) + 1e-6)',
            {'B4': B4, 'B11': B11, 'B8': B8, 'B2': B2})
        out = msavi.subtract(bsi).rename('layer')
        return out, viz

    # ── Nitrogen (N) ───────────────────────────────────────────────
    elif param == "Nitrogen (N)":
        # NDRE: best single-band N proxy from Sentinel-2
        ndre  = img.expression('(B8A-B5)/(B8A+B5+1e-6)', {'B8A': B8A,'B5': B5})
        # EVI: vegetation density / biomass
        evi   = img.expression('2.5*(B8-B4)/(B8+6*B4-7.5*B2+1+1e-6)', {'B8': B8,'B4': B4,'B2': B2})
        # Red-edge CI: chlorophyll content
        ci_re = img.expression('(B7/(B5+1e-6))-1.0', {'B7': B7,'B5': B5})
        # MCARI: chlorophyll absorption sensitivity
        mcari = img.expression('((B5-B4)-0.2*(B5-B3))*(B5/(B4+1e-6))', {'B5': B5,'B4': B4,'B3': B3})
        # Calibrated for 0–1 reflectance → output 50–400 kg/ha
        out = (ndre.multiply(180)
               .add(evi.multiply(120))
               .add(ci_re.multiply(15))
               .add(mcari.multiply(25))
               .add(200)).rename('layer')
        return out, viz

    # ── Phosphorus (P) ─────────────────────────────────────────────
    elif param == "Phosphorus (P)":
        ndvi       = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        brightness = img.expression('(B2+B3+B4)/3.0', {'B2': B2,'B3': B3,'B4': B4})
        si         = B3.multiply(B4).sqrt()
        re_slope   = img.expression('(B7-B5)/(B7+B5+1e-6)', {'B7': B7,'B5': B5})
        swir2_inv  = ee.Image(1.0).subtract(B12)
        # Calibrated for 0–1 reflectance → output 2–50 kg/ha
        out = (ndvi.multiply(20)
               .add(swir2_inv.multiply(15))
               .add(re_slope.multiply(10))
               .subtract(brightness.multiply(10))
               .add(si.multiply(8))
               .add(22)).rename('layer')
        return out, viz

    # ── Potassium (K) ──────────────────────────────────────────────
    elif param == "Potassium (K)":
        ndvi       = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        k_idx      = img.expression('B11/(B5+B6+1e-6)', {'B11': B11,'B5': B5,'B6': B6})
        swir_ratio = img.expression('(B11-B12)/(B11+B12+1e-6)', {'B11': B11,'B12': B12})
        nir_red    = img.expression('B8/(B4+1e-6)', {'B8': B8,'B4': B4})
        # Calibrated for 0–1 reflectance → output 40–450 kg/ha
        out = (k_idx.multiply(180)
               .add(swir_ratio.multiply(60))
               .add(ndvi.multiply(80))
               .add(nir_red.multiply(10))
               .add(160)).rename('layer')
        return out, viz

    # ── Organic Carbon (OC) ────────────────────────────────────────
    elif param == "Organic Carbon (OC)":
        brightness = img.expression('(B2+B3+B4)/3.0', {'B2': B2,'B3': B3,'B4': B4})
        ndvi       = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        savi       = img.expression('((B8-B4)/(B8+B4+0.5+1e-6))*1.5', {'B8': B8,'B4': B4})
        swir_avg   = B11.add(B12).divide(2)
        ndre       = img.expression('(B8A-B5)/(B8A+B5+1e-6)', {'B8A': B8A,'B5': B5})
        # OC inversely related to brightness and SWIR; positively to vegetation
        # Calibrated for 0–1 reflectance → output 0.1–3.5 %
        out = (ee.Image(1.0).subtract(brightness).multiply(2.5)
               .add(ndvi.multiply(1.2))
               .add(savi.multiply(0.8))
               .subtract(swir_avg.multiply(1.5))
               .add(ndre.multiply(0.6))
               .add(0.8)).rename('layer')
        return out, viz

    # ── Electrical Conductivity (EC) ───────────────────────────────
    elif param == "Electrical Conductivity (EC)":
        ndvi       = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        brightness = img.expression('(B2+B3+B4)/3.0', {'B2': B2,'B3': B3,'B4': B4})
        si1        = B3.multiply(B4).sqrt()
        si2        = B3.pow(2).add(B4.pow(2)).sqrt()
        si_comb    = si1.add(si2).divide(2)
        veg_stress = ee.Image(1.0).subtract(ndvi.clamp(0, 1))
        # High brightness + stress + SI → saline
        # Calibrated for 0–1 reflectance → output 0–8 dS/m
        out = (si_comb.multiply(5.0)
               .add(veg_stress.multiply(3.0))
               .add(brightness.multiply(2.0))
               .add(0.3)).rename('layer')
        return out, viz

    # ── Calcium (Ca) ───────────────────────────────────────────────
    elif param == "Calcium (Ca)":
        carbonate  = img.expression('(B11+B12)/(B4+B3+1e-6)', {'B11': B11,'B12': B12,'B4': B4,'B3': B3})
        brightness = img.expression('(B2+B3+B4)/3.0', {'B2': B2,'B3': B3,'B4': B4})
        ndvi       = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        clay_idx   = img.expression('(B11-B8)/(B11+B8+1e-6)', {'B11': B11,'B8': B8})
        # Calibrated for 0–1 reflectance → output 100–900 kg/ha
        out = (carbonate.multiply(300)
               .add(brightness.multiply(200))
               .subtract(ndvi.multiply(80))
               .subtract(clay_idx.multiply(60))
               .add(350)).rename('layer')
        return out, viz

    # ── Magnesium (Mg) ─────────────────────────────────────────────
    elif param == "Magnesium (Mg)":
        ndre     = img.expression('(B8A-B5)/(B8A+B5+1e-6)', {'B8A': B8A,'B5': B5})
        re_chl   = img.expression('(B7/(B5+1e-6))-1.0', {'B7': B7,'B5': B5})
        mg_clay  = img.expression('(B11-B12)/(B11+B12+1e-6)', {'B11': B11,'B12': B12})
        ndvi     = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        # Calibrated for 0–1 reflectance → output 10–300 kg/ha
        out = (ndre.multiply(80)
               .add(re_chl.multiply(30))
               .add(mg_clay.multiply(25))
               .add(ndvi.multiply(20))
               .add(100)).rename('layer')
        return out, viz

    # ── Sulphur (S) ────────────────────────────────────────────────
    elif param == "Sulphur (S)":
        gypsum  = img.expression('B11/(B3+B4+1e-6)', {'B11': B11,'B3': B3,'B4': B4})
        si1     = B3.multiply(B4).sqrt()
        si2     = B3.pow(2).add(B4.pow(2)).sqrt()
        sal_idx = si1.add(si2).divide(2)
        re_red  = img.expression('B5/(B4+1e-6)', {'B5': B5,'B4': B4})
        swir_r  = img.expression('B12/(B11+1e-6)', {'B12': B12,'B11': B11})
        ndvi    = img.expression('(B8-B4)/(B8+B4+1e-6)', {'B8': B8,'B4': B4})
        # Calibrated for 0–1 reflectance → output 2–60 kg/ha
        out = (gypsum.multiply(18)
               .add(sal_idx.multiply(12))
               .add(re_red.subtract(1).multiply(6))
               .subtract(swir_r.multiply(8))
               .add(ndvi.multiply(6))
               .add(18)).rename('layer')
        return out, viz

    # ── Soil pH ────────────────────────────────────────────────────
    elif param == "Soil pH":
        ndvi_re    = img.expression(
            '((B8-B5)/(B8+B5+1e-6) + (B8-B4)/(B8+B4+1e-6))/2',
            {'B8': B8,'B5': B5,'B4': B4})
        swir_ratio = img.expression('B11/(B8+1e-6)', {'B11': B11,'B8': B8})
        nir_ratio  = img.expression('B8/(B4+1e-6)', {'B8': B8,'B4': B4})
        brightness = img.expression('(B2+B3+B4)/3.0', {'B2': B2,'B3': B3,'B4': B4})
        # Calibrated for 0–1 reflectance → output 4.5–8.5
        out = (ndvi_re.multiply(1.0)
               .add(swir_ratio.multiply(0.6))
               .subtract(nir_ratio.multiply(0.3))
               .add(ee.Image(1.0).subtract(brightness).multiply(0.12))
               .add(6.2)).rename('layer')
        return out, viz

    return None, None


# ----------------------------------------
# Legend HTML
# ----------------------------------------
def render_legend(param):
    meta     = PARAM_META[param]
    colors   = meta['palette']
    labels   = meta['labels']
    unit     = meta['unit']
    note     = meta['note']
    gradient = ", ".join(colors)

    bar_html = f"""
    <div style="margin-top:10px; margin-bottom:16px;">
      <b>Legend — {param} {'(' + unit + ')' if unit else ''}</b><br>
      <div class="legend-bar" style="background: linear-gradient(to right, {gradient});"></div>
      <div class="legend-labels">
        {''.join(f'<span>{l}</span>' for l in labels)}
      </div>
      <small style="color:#666; margin-top:4px; display:block;">{note}</small>
    </div>
    """
    st.markdown(bar_html, unsafe_allow_html=True)


# ============================================================
# MAIN UI
# ============================================================

# ── Step 1: Draw Field ──────────────────────────────────────
st.subheader("Step 1 — Draw Your Field")
map1 = folium.Map(location=[18.4575, 73.8503], zoom_start=15, tiles=None)
folium.TileLayer(
    tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attr='© OpenStreetMap contributors', name='OpenStreetMap', control=False
).add_to(map1)
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri', name='ESRI World Imagery', overlay=True, control=True
).add_to(map1)
Draw(export=True).add_to(map1)
st_map = st_folium(map1, width=700, height=450, key="draw_map")
polygon = st_map.get('last_active_drawing')

if not polygon:
    st.info("👆 Draw a polygon on the map to define your field, then proceed.")
    st.stop()
st.success("✅ Field boundary captured!")

# ── Step 2: Select Parameter ────────────────────────────────
st.markdown("---")
st.subheader("Step 2 — Select Fertility Parameter")

col_sel, col_info = st.columns([2, 3])
with col_sel:
    selected_param = st.selectbox(
        "Soil property to map:",
        list(PARAM_META.keys()),
        index=0,
    )

with col_info:
    m = PARAM_META[selected_param]
    st.markdown(f"""
    <div class="metric-box">
      <b>{selected_param}</b><br>
      Unit: <code>{m['unit'] if m['unit'] else 'dimensionless'}</code> &nbsp;|&nbsp;
      Range: <code>{m['min']} – {m['max']} {m['unit']}</code><br>
      <small style="color:#555;">{m['note']}</small>
    </div>
    """, unsafe_allow_html=True)

# ── Step 3: Load Imagery & Compute ──────────────────────────
st.markdown("---")
st.subheader(f"Step 3 — {selected_param} Map")

coords     = polygon['geometry']['coordinates'][0]
region     = ee.Geometry.Polygon(coords)
end_date   = datetime.date.today() - datetime.timedelta(days=7)
start_date = end_date - datetime.timedelta(days=16)

with st.spinner("Fetching Sentinel-2 imagery..."):
    coll = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            .filterBounds(region)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)))

    count = coll.size().getInfo()
    if count == 0:
        start_date = end_date - datetime.timedelta(days=45)
        coll = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                .filterBounds(region)
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)))
        st.warning("⚠️ No recent low-cloud imagery found. Extended to 45-day window.")

    image = coll.median().clip(region)

with st.spinner(f"Computing {selected_param} layer..."):
    layer_image, viz = build_layer(image, selected_param)

if layer_image is None:
    st.error("Could not build this layer. Please try another parameter.")
    st.stop()

# ── Step 4: Display Map ─────────────────────────────────────
lon_vals = [pt[0] for pt in coords]
lat_vals = [pt[1] for pt in coords]
center   = [sum(lat_vals)/len(lat_vals), sum(lon_vals)/len(lon_vals)]

map2 = folium.Map(location=center, zoom_start=16, tiles=None)
folium.TileLayer(
    tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attr='© OpenStreetMap contributors', name='OpenStreetMap', control=False
).add_to(map2)
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri', name='ESRI World Imagery', overlay=True, control=True
).add_to(map2)

folium.GeoJson(
    region.getInfo(),
    name='Field Boundary',
    style_function=lambda x: {'color': '#ffffff', 'weight': 2, 'fillOpacity': 0}
).add_to(map2)

with st.spinner("Rendering map tile from GEE..."):
    tile_dict = layer_image.getMapId(viz)

folium.TileLayer(
    tiles=tile_dict['tile_fetcher'].url_format,
    attr='Google Earth Engine',
    name=selected_param,
    overlay=True,
    opacity=0.75,
).add_to(map2)

folium.LayerControl().add_to(map2)
st_folium(map2, width=700, height=500, key="result_map")

# ── Legend ──────────────────────────────────────────────────
render_legend(selected_param)

# ── Step 5: Field Statistics ────────────────────────────────
st.markdown("---")
st.subheader("Step 4 — Field Statistics")

with st.spinner("Extracting field statistics..."):
    stats_dict = layer_image.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), sharedInputs=True),
        geometry=region,
        scale=20,
        maxPixels=1e13
    )
    mean_val = safe_get_info(stats_dict.get('layer_mean'), "mean")
    min_val  = safe_get_info(stats_dict.get('layer_min'),  "min")
    max_val  = safe_get_info(stats_dict.get('layer_max'),  "max")

unit   = PARAM_META[selected_param]['unit']
mn     = PARAM_META[selected_param]['min']
mx     = PARAM_META[selected_param]['max']
invert = PARAM_META[selected_param]['invert']

if mean_val is not None:
    c1, c2, c3 = st.columns(3)
    c1.metric("📊 Field Mean", f"{mean_val:.2f} {unit}")
    c2.metric("📉 Field Min",  f"{min_val:.2f} {unit}"  if min_val  is not None else "N/A")
    c3.metric("📈 Field Max",  f"{max_val:.2f} {unit}"  if max_val  is not None else "N/A")

    low_t  = mn + (mx - mn) * 0.33
    high_t = mn + (mx - mn) * 0.66

    st.markdown("#### 🧪 Interpretation")
    if invert:
        if mean_val < low_t:
            st.success(f"🟢 **Low {selected_param}** — Ideal range. Crops should perform well.")
        elif mean_val < high_t:
            st.warning(f"🟡 **Moderate {selected_param}** — Monitor closely. Sensitive crops may be affected.")
        else:
            st.error(f"🔴 **High {selected_param}** — Soil stress likely. Consider leaching or remediation.")
    else:
        if mean_val < low_t:
            st.error(f"🔴 **Low {selected_param}** — Deficient. Consider applying inputs to boost levels.")
        elif mean_val < high_t:
            st.warning(f"🟡 **Moderate {selected_param}** — Below optimal. Targeted application recommended.")
        else:
            st.success(f"🟢 **Adequate {selected_param}** — Good levels. Minimal intervention needed.")

    # Spatial variability warning
    if min_val is not None and max_val is not None:
        spread     = max_val - min_val
        range_span = mx - mn
        if spread > range_span * 0.5:
            st.info("📍 **High spatial variability detected** — Consider variable-rate application across zones rather than uniform treatment.")
else:
    st.warning("Could not extract field statistics. Check that the drawn polygon is valid and imagery is available.")

st.markdown("---")
st.caption(f"🛰️ Sentinel-2 SR data: {start_date} → {end_date}  |  Pixel scale: 20 m")
st.caption("⚠️ All values are spectral estimates from Sentinel-2 — validate with ground-truth soil samples before precision agriculture decisions.")