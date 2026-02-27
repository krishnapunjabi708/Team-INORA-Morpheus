# -----------------------------------------
# Imports
# -----------------------------------------
import streamlit as st
from streamlit_folium import st_folium
import folium
from folium.plugins import Draw
from folium import TileLayer
from shapely.geometry import shape
import geopandas as gpd

# -----------------------------------------
# Streamlit Page Configuration
# -----------------------------------------
st.set_page_config(
    layout="wide",
    page_title="Area Measurement - Sakri, Maharashtra"
)
st.title("🌍 Draw Area on Google Satellite Map (Sakri, Maharashtra)")

# -----------------------------------------
# Default Map Settings
# -----------------------------------------
default_lat = 20.9938517
default_lon = 74.3178317
default_zoom = 17      # Zoom level for map

# -----------------------------------------
# Create Folium Map with Google Satellite
# -----------------------------------------
# Initialize empty map (no base tiles)
m = folium.Map(
    location=[default_lat, default_lon],
    zoom_start=default_zoom,
    tiles=None
)

# Add Google Satellite as base layer
TileLayer(
    tiles="http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    attr="Google Satellite",
    name="Google Satellite",
    overlay=False,
    control=True,
    subdomains=['mt0', 'mt1', 'mt2', 'mt3']
).add_to(m)

# (Optional) Add Google Hybrid labels overlay
TileLayer(
    tiles="http://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    attr="Google Hybrid",
    name="Place Labels",
    overlay=True,
    control=True,
    subdomains=['mt0', 'mt1', 'mt2', 'mt3']
).add_to(m)

# Enable layer control to toggle layers
folium.LayerControl().add_to(m)

# Add drawing tools (polygon, rectangle, etc.)
Draw(
    export=True,
    filename='drawn_shape.geojson',
    position='topleft',
    draw_options={'polyline': False, 'rectangle': True, 'circle': False, 'marker': False}
).add_to(m)

# -----------------------------------------
# Render Map in Streamlit
# -----------------------------------------
map_data = st_folium(
    m,
    width=1000,
    height=600,
)

# -----------------------------------------
# Extract Drawn Feature
# -----------------------------------------
feature = None
if map_data:
    feature = map_data.get("last_drawn_feature") or map_data.get("last_active_drawing")

# -----------------------------------------
# Function: Calculate Area
# -----------------------------------------
def calculate_area(geo_feature):
    """
    Convert GeoJSON feature to shapely polygon,
    re-project to metric CRS, and calculate area.
    Returns: (area_hectares, area_acres)
    """
    try:
        geom = geo_feature.get("geometry") if isinstance(geo_feature, dict) else None
        if not geom:
            return None, None
        polygon = shape(geom)
        gdf = gpd.GeoDataFrame(
            index=[0],
            geometry=[polygon],
            crs="EPSG:4326"
        )
        gdf = gdf.to_crs("EPSG:3857")
        area_m2 = gdf["geometry"].area[0]
        area_hectares = area_m2 / 10000.0
        area_acres = area_m2 / 4046.86
        return area_hectares, area_acres
    except Exception as e:
        st.error(f"Area calculation error: {e}")
        return None, None

# -----------------------------------------
# Display Area Results
# -----------------------------------------
if feature:
    area_ha, area_ac = calculate_area(feature)
    if area_ha is not None:
        st.subheader("📐 Calculated Area")
        st.write(f"**{area_ha:.2f} hectares**")
        st.write(f"**{area_ac:.2f} acres**")
    else:
        st.error("Failed to calculate area. Please draw a valid polygon.")
else:
    st.info("Draw a polygon or rectangle on the map to calculate its area.")
