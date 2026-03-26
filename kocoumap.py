import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import json
import tempfile
import os
from datetime import datetime
import time

st.set_page_config(
    page_title="KOCOUMBOmapservice",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
DEFAULT_CENTER = [48.8566, 2.3522]
DEFAULT_ZOOM = 13
COLORS = ['#141414', '#FF6321', '#2E7D32', '#1565C0', '#D84315', '#6A1B9A']
MAP_STYLES = {
    'Standard': 'OpenStreetMap',
    'Satellite': 'CartoDB positron',
    'Terrain': 'OpenTopoMap',
    'Dark': 'CartoDB voyager'
}
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

    @st.cache_data
    def search_location(self, query):
        """Search for location using Nominatim API"""
        try:
            url = f"https://nominatim.openstreetmap.org/search?format=json&polygon_geojson=1&q={query}"
            response = requests.get(url, timeout=5)
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

    def create_map(self):
        """Create Folium map with current configuration"""
        m = folium.Map(
            location=self.center,
            zoom_start=self.zoom,
            tiles=MAP_STYLES.get(self.map_style, 'OpenStreetMap')
        )

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
                }
            ).add_to(m)

        folium.plugins.MeasureControl().add_to(m)
        return m

def main():
    st.markdown("""
    <style>
    .main-header {
        background-color: #E4E3E0;
        border-bottom: 2px solid black;
        padding: 1rem;
        margin: -1rem -1rem 1rem -1rem;
    }
    .logo-title {
        font-family: 'Courier New', monospace;
        font-size: 1.5rem;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: -0.025em;
    }
    .logo-subtitle {
        font-family: 'Courier New', monospace;
        font-size: 0.625rem;
        opacity: 0.5;
        text-transform: uppercase;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="main-header">
        <div class="logo-title">🎯 KOCOUMBOmapservice</div>
        <div class="logo-subtitle">Advanced Cartography Engine</div>
    </div>
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

    map_service = st.session_state.map_service

    col1, col2 = st.columns([1, 3])

    with col1:
        st.markdown("### ⚙️ Configuration")

        with st.expander("🔍 RECHERCHE", expanded=True):
            search_query = st.text_input("Entrez un lieu...", key="search_input")
            if st.button("RECHERCHER", use_container_width=True):
                if search_query:
                    with st.spinner("Recherche en cours..."):
                        results = map_service.search_location(search_query)
                        st.session_state.search_results = results

            if st.session_state.search_results:
                st.markdown("**Résultats:**")
                for result in st.session_state.search_results[:5]:
                    if st.button(f"➕ {result['display_name'][:40]}", key=f"add_{result['osm_id']}"):
                        boundary = map_service.add_boundary_from_search(result)
                        if boundary:
                            st.success(f"Ajouté: {boundary['name']}")
                            st.session_state.search_results = []
                            st.rerun()

        with st.expander("📋 CALQUES", expanded=True):
            if not map_service.boundaries:
                st.markdown("*Aucun calque*")
            else:
                for i, boundary in enumerate(map_service.boundaries):
                    col_a, col_b = st.columns([4, 1])
                    with col_a:
                        st.markdown(f"**{boundary['name']}** ({boundary['type']})")
                    with col_b:
                        if st.button("🗑️", key=f"remove_{boundary['id']}"):
                            map_service.boundaries.pop(i)
                            st.rerun()

        with st.expander("⚙️ PARAMÈTRES", expanded=True):
            map_service.map_style = st.selectbox(
                "Style de carte",
                ['Standard', 'Satellite', 'Terrain', 'Dark'],
                index=['Standard', 'Satellite', 'Terrain', 'Dark'].index(map_service.map_style)
            )

            map_service.crs = st.selectbox(
                "Système de référence",
                ['EPSG:4326', 'EPSG:3857', 'EPSG:32628'],
                format_func=lambda x: CRS_OPTIONS[x]
            )

        with st.expander("📍 INFOS", expanded=True):
            st.markdown(f"**Zoom:** {map_service.zoom}")
            st.markdown(f"**Centre:** {map_service.center[0]:.4f}, {map_service.center[1]:.4f}")
            st.markdown(f"**CRS:** {map_service.crs}")

        if map_service.is_owner:
            st.success("✅ Mode Propriétaire ACTIF")

    with col2:
        st.markdown("### 🗺️ CARTE")
        m = map_service.create_map()
        map_data = st_folium(m, width=1000, height=600)

        if map_data and 'center' in map_data:
            map_service.center = [map_data['center']['lat'], map_data['center']['lng']]
        if map_data and 'zoom' in map_data:
            map_service.zoom = map_data['zoom']

        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            if st.button("📍 Ma Position"):
                st.info("Géolocalisation (navigateur)")
        with col_b:
            if st.button("⛶ Plein Écran"):
                st.info("Mode plein écran")
        with col_c:
            if st.button("⚙️ Avancé"):
                st.info("Paramètres avancés")
        with col_d:
            if st.button("ℹ️ Info"):
                st.info("À propos de l'app")

        if st.button("📥 EXPORTER", type="primary", use_container_width=True):
            if map_service.is_owner:
                st.success("Export en cours...")
            else:
                st.session_state.show_payment = True

    if st.session_state.show_payment:
        st.markdown("---")
        st.markdown("### 💳 PAIEMENT REQUIS")
        st.markdown("Transférez les frais vers: **00221772414357** (Orange Money / Wave)")
        
        transaction_id = st.text_input("ID de transaction:", value=st.session_state.transaction_id)
        
        if st.button("Vérifier le paiement"):
            if transaction_id:
                st.session_state.transaction_id = transaction_id
                st.success("Paiement vérifié!")
                st.session_state.show_payment = False
                st.rerun()
            else:
                st.warning("Veuillez entrer un ID de transaction")

        if st.button("🔓 Accès Propriétaire"):
            admin_code = st.text_input("Code secret:", type="password")
            if admin_code == "KOCOUMBO2026":
                map_service.is_owner = True
                st.success("Mode Propriétaire ACTIVÉ!")
                st.rerun()
            elif admin_code:
                st.error("Code incorrect")

    st.markdown("---")
    col_footer_a, col_footer_b = st.columns(2)
    with col_footer_a:
        st.markdown(f"**SYSTEM:** KOCOUMBO-SERVICE | **CRS:** {map_service.crs}")
    with col_footer_b:
        st.markdown(f"**TIME:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()