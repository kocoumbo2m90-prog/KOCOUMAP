import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import geopandas as gpd
import pyproj
import json
import tempfile
import os
from datetime import datetime
import time

# Configuration
DEFAULT_CENTER = [48.8566, 2.3522]  # Paris
DEFAULT_ZOOM = 13
COLORS = ['#141414', '#FF6321', '#2E7D32', '#1565C0', '#D84315', '#6A1B9A']

# Map styles for Folium
MAP_STYLES = {
    'Standard': 'OpenStreetMap',
    'Satellite': 'Stamen Terrain',
    'Terrain': 'Stamen Terrain',
    'Dark': 'CartoDB dark_matter'
}

# Coordinate systems
CRS_OPTIONS = {
    'EPSG:4326': 'WGS 84',
    'EPSG:3857': 'Web Mercator',
    'EPSG:32628': 'UTM 28N'
}

class MapService:
    def __init__(self):
        self.boundaries = []
        self.center = DEFAULT_CENTER
        self.zoom = DEFAULT_ZOOM
        self.map_style = 'Standard'
        self.crs = 'EPSG:4326'
        self.export_scale = 2
        self.is_owner = False

    def search_location(self, query):
        """Search for location using Nominatim API"""
        try:
            url = f"https://nominatim.openstreetmap.org/search?format=json&polygon_geojson=1&q={query}"
            response = requests.get(url)
            return response.json()
        except Exception as e:
            st.error(f"Search failed: {e}")
            return []

    def add_boundary_from_search(self, result):
        """Add boundary from search result"""
        if 'geojson' in result:
            boundary = {
                'id': f"{result['osm_type']}-{result['osm_id']}",
                'name': result['display_name'].split(',')[0],
                'data': result['geojson'],
                'type': 'search',
                'color': COLORS[len(self.boundaries) % len(COLORS)]
            }
            self.boundaries.append(boundary)
            return boundary
        return None

    def process_shapefile(self, file_path):
        """Process uploaded shapefile"""
        try:
            gdf = gpd.read_file(file_path)
            geojson = json.loads(gdf.to_json())

            boundary = {
                'id': f"shp-{int(time.time())}",
                'name': os.path.basename(file_path),
                'data': geojson,
                'type': 'shapefile',
                'color': COLORS[len(self.boundaries) % len(COLORS)]
            }
            self.boundaries.append(boundary)
            return boundary
        except Exception as e:
            st.error(f"Shapefile processing failed: {e}")
            return None

    def create_map(self):
        """Create Folium map with current configuration"""
        # Create map
        m = folium.Map(
            location=self.center,
            zoom_start=self.zoom,
            tiles=MAP_STYLES.get(self.map_style, 'OpenStreetMap')
        )

        # Add boundaries
        for boundary in self.boundaries:
            geojson_data = boundary['data']
            color = boundary['color']

            folium.GeoJson(
                geojson_data,
                style_function=lambda x, color=color: {
                    'color': color,
                    'weight': 2,
                    'fillColor': color,
                    'fillOpacity': 0.15,
                    'dashArray': '5, 5' if boundary['type'] == 'shapefile' else ''
                },
                tooltip=folium.GeoJsonTooltip(fields=list(geojson_data.get('features', [{}])[0].get('properties', {}).keys()) if geojson_data.get('features') else [])
            ).add_to(m)

        # Add scale control
        folium.plugins.MeasureControl().add_to(m)

        return m

    def format_coords(self, lat, lon):
        """Format coordinates based on CRS"""
        if self.crs == 'EPSG:3857':
            transformer = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:3857', always_xy=True)
            x, y = transformer.transform(lon, lat)
            return f"X: {x:.0f} Y: {y:.0f}"
        elif self.crs == 'EPSG:32628':
            transformer = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32628', always_xy=True)
            x, y = transformer.transform(lon, lat)
            return f"E: {x:.0f} N: {y:.0f}"
        return f"LAT: {lat:.6f} LON: {lon:.6f}"

def main():
    st.set_page_config(
        page_title="KOCOUMBOmapservice",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS
    st.markdown("""
    <style>
    .main-header {
        background-color: #E4E3E0;
        border-bottom: 1px solid black;
        padding: 1rem 2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: -1rem -1rem 1rem -1rem;
    }
    .logo {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .logo-icon {
        width: 2.5rem;
        height: 2.5rem;
        background-color: black;
        color: #E4E3E0;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px solid black;
        border-radius: 4px;
    }
    .logo-text h1 {
        font-size: 1.25rem;
        font-weight: bold;
        margin: 0;
        letter-spacing: -0.025em;
        font-family: 'Courier New', monospace;
    }
    .logo-text p {
        font-size: 0.625rem;
        font-weight: 500;
        margin: 0;
        text-transform: uppercase;
        opacity: 0.5;
        font-family: 'Courier New', monospace;
    }
    .stButton>button {
        background-color: black;
        color: #E4E3E0;
        border: 1px solid black;
        font-family: 'Courier New', monospace;
        text-transform: uppercase;
        font-size: 0.625rem;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: transparent;
        color: black;
    }
    .stTextInput>div>div>input {
        border: 1px solid black;
        background-color: transparent;
        font-family: 'Courier New', monospace;
        text-transform: uppercase;
    }
    .stSelectbox>div>div>select {
        border: 1px solid black;
        background-color: transparent;
        font-family: 'Courier New', monospace;
        text-transform: uppercase;
        font-size: 0.5625rem;
        font-weight: bold;
    }
    .sidebar .stMarkdown h3 {
        font-size: 0.6875rem;
        font-style: italic;
        opacity: 0.5;
        text-transform: uppercase;
        font-family: 'Courier New', monospace;
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

    # Initialize session state
    if 'map_service' not in st.session_state:
        st.session_state.map_service = MapService()

    if 'search_results' not in st.session_state:
        st.session_state.search_results = []

    if 'show_payment' not in st.session_state:
        st.session_state.show_payment = False

    if 'transaction_id' not in st.session_state:
        st.session_state.transaction_id = ""

    if 'admin_code' not in st.session_state:
        st.session_state.admin_code = ""

    map_service = st.session_state.map_service

    # Header
    st.markdown("""
    <div class="main-header">
        <div class="logo">
            <div class="logo-icon">🎯</div>
            <div class="logo-text">
                <h1>KOCOUMBOmapservice</h1>
                <p>Advanced Cartography Engine</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Main layout
    col1, col2 = st.columns([1, 3])

    with col1:
        st.markdown("### Configuration & Calques")

        # Search
        with st.expander("🔍 RECHERCHE", expanded=True):
            search_query = st.text_input("RÉGION, COMMUNE, QUARTIER...", key="search_input")
            if st.button("RECHERCHER"):
                if search_query:
                    with st.spinner("Recherche en cours..."):
                        results = map_service.search_location(search_query)
                        st.session_state.search_results = results

            if st.session_state.search_results:
                st.markdown("**RÉSULTATS:**")
                for result in st.session_state.search_results:
                    if st.button(f"➕ {result['display_name'][:50]}...", key=f"add_{result['osm_id']}"):
                        boundary = map_service.add_boundary_from_search(result)
                        if boundary:
                            st.success(f"Ajouté: {boundary['name']}")
                            st.session_state.search_results = []
                            st.rerun()

        # File upload
        with st.expander("📁 IMPORTER SHP", expanded=True):
            uploaded_file = st.file_uploader("Sélectionner un fichier .zip contenant .shp", type=['zip'])
            if uploaded_file is not None:
                if st.button("TRAITER LE FICHIER"):
                    with st.spinner("Traitement du Shapefile..."):
                        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
                            temp_file.write(uploaded_file.read())
                            temp_path = temp_file.name

                        try:
                            boundary = map_service.process_shapefile(temp_path)
                            if boundary:
                                st.success(f"Shapefile ajouté: {boundary['name']}")
                                st.rerun()
                        finally:
                            os.unlink(temp_path)

        # Layers list
        with st.expander("📋 CALQUES ACTIFS", expanded=True):
            if not map_service.boundaries:
                st.markdown("*Aucun calque sélectionné*")
            else:
                for i, boundary in enumerate(map_service.boundaries):
                    col_a, col_b = st.columns([4, 1])
                    with col_a:
                        st.markdown(f"**{boundary['name']}** ({boundary['type'].upper()})")
                        st.markdown(f"<div style='width: 10px; height: 10px; background-color: {boundary['color']}; border-radius: 50%; display: inline-block; margin-right: 5px;'></div> Couleur", unsafe_allow_html=True)
                    with col_b:
                        if st.button("🗑️", key=f"remove_{boundary['id']}"):
                            map_service.boundaries.pop(i)
                            st.rerun()

        # Settings
        with st.expander("⚙️ PARAMÈTRES", expanded=True):
            map_service.map_style = st.selectbox(
                "STYLE DE FOND",
                ['Standard', 'Satellite', 'Terrain', 'Dark'],
                index=['Standard', 'Satellite', 'Terrain', 'Dark'].index(map_service.map_style)
            )

            map_service.crs = st.selectbox(
                "SYSTÈME DE RÉFÉRENCE (CRS)",
                ['EPSG:4326', 'EPSG:3857', 'EPSG:32628'],
                index=['EPSG:4326', 'EPSG:3857', 'EPSG:32628'].index(map_service.crs),
                format_func=lambda x: CRS_OPTIONS[x]
            )

            map_service.export_scale = st.selectbox(
                "QUALITÉ D'EXPORTATION",
                [1, 2, 3],
                index=[1, 2, 3].index(map_service.export_scale),
                format_func=lambda x: f"{x}x"
            )

        # Coordinates display
        with st.expander("📍 COORDONNÉES", expanded=True):
            coords = map_service.format_coords(map_service.center[0], map_service.center[1])
            st.markdown(f"**COORD:** {coords}")
            st.markdown(f"**ZOOM:** {map_service.zoom}")

        # Status
        st.markdown("---")
        if map_service.is_owner:
            st.markdown("🎯 **MODE PROPRIÉTAIRE ACTIF**")
        st.markdown("🧭 GPS Active")
        st.markdown("📊 Vector Engine")

    with col2:
        # Map
        st.markdown("### CARTE")

        # Create and display map
        m = map_service.create_map()
        map_data = st_folium(m, width=800, height=600)

        # Update map center and zoom from user interaction
        if map_data and 'center' in map_data:
            map_service.center = [map_data['center']['lat'], map_data['center']['lng']]
        if map_data and 'zoom' in map_data:
            map_service.zoom = map_data['zoom']

        # Action buttons
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            if st.button("📍 Ma Position"):
                # This would need geolocation API integration
                st.info("Fonctionnalité de géolocalisation à implémenter")
        with col_b:
            if st.button("⛶ Plein Écran"):
                st.info("Mode plein écran")
        with col_c:
            if st.button("⚙️ Paramètres"):
                st.info("Paramètres avancés")
        with col_d:
            if st.button("ℹ️ Info"):
                st.info("Informations sur l'application")

        # Export button
        if st.button("📥 EXPORTER MAP", type="primary"):
            if map_service.is_owner:
                with st.spinner("Génération de l'export..."):
                    # For demo, just show success
                    st.success("Carte exportée avec succès!")
            else:
                st.session_state.show_payment = True

    # Payment modal
    if st.session_state.show_payment:
        with st.expander("💳 PAIEMENT REQUIS", expanded=True):
            st.markdown("### ACCÈS RESTREINT AU TÉLÉCHARGEMENT")
            st.markdown("Pour télécharger cette carte haute résolution, veuillez effectuer un transfert de frais de service vers le numéro suivant :")

            st.markdown("""
            <div style="border: 1px solid black; background-color: white; padding: 1rem; text-align: center; margin: 1rem 0;">
                <div style="font-size: 0.625rem; opacity: 0.5; margin-bottom: 0.25rem;">NUMÉRO DE RÉCEPTION</div>
                <div style="font-size: 1.5rem; font-weight: bold; letter-spacing: 0.1em;">00221772414357</div>
                <div style="display: flex; justify-content: center; gap: 1rem; margin-top: 0.5rem;">
                    <span style="background-color: #ff6b35; color: white; padding: 0.125rem 0.5rem; font-size: 0.625rem; font-weight: bold;">ORANGE MONEY</span>
                    <span style="background-color: #007bff; color: white; padding: 0.125rem 0.5rem; font-size: 0.625rem; font-weight: bold;">WAVE</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.session_state.transaction_id = st.text_input(
                "ID DE TRANSACTION / RÉFÉRENCE",
                value=st.session_state.transaction_id,
                placeholder="SAISISSEZ LA RÉFÉRENCE DU PAIEMENT"
            )

            col_x, col_y = st.columns(2)
            with col_x:
                if st.button("ANNULER"):
                    st.session_state.show_payment = False
                    st.rerun()
            with col_y:
                if st.button("CONFIRMER & TÉLÉCHARGER", disabled=not st.session_state.transaction_id):
                    if st.session_state.transaction_id:
                        st.success("Paiement vérifié! Téléchargement en cours...")
                        st.session_state.show_payment = False
                        st.rerun()

            # Admin access
            if not map_service.is_owner:
                if st.button("🔓 Accès Propriétaire"):
                    st.session_state.admin_code = st.text_input(
                        "CODE SECRET",
                        type="password",
                        key="admin_input"
                    )
                    if st.session_state.admin_code == "KOCOUMBO2026":
                        map_service.is_owner = True
                        st.success("MODE PROPRIÉTAIRE ACTIVÉ : TÉLÉCHARGEMENTS GRATUITS DÉBLOQUÉS.")
                        st.rerun()
                    elif st.session_state.admin_code:
                        st.error("CODE INCORRECT.")

    # Footer
    st.markdown("---")
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown(f"SYSTEM: KOCOUMBO-SERVICE | CRS: {map_service.crs}")
    with col_right:
        st.markdown(f"{datetime.now().isoformat()} | LOC: {map_service.format_coords(map_service.center[0], map_service.center[1])}")

if __name__ == "__main__":
    main()