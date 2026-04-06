import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import json
from datetime import datetime
import geopandas as gpd
from pathlib import Path
import base64
import io
from PIL import Image
import time

st.set_page_config(
    page_title="KocouMap - Cartographie Géospatiale du Sénégal",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Titre et description
st.title("🗺️ KocouMap - Cartographie Géospatiale du Sénégal")
st.markdown("Interface interactive pour l'exploration des données administratives du Sénégal")

# Sidebar pour les contrôles
st.sidebar.header("⚙️ Paramètres")

# Localisation par défaut (Dakar, Sénégal)
default_lat = 14.7167  # Dakar
default_lon = -17.4674
default_zoom = 7

# Contrôles de la carte
col1, col2 = st.sidebar.columns(2)
with col1:
    zoom_level = st.slider("Niveau de zoom", 1, 18, default_zoom)
with col2:
    map_style = st.selectbox(
        "Style de carte",
        ["OpenStreetMap", "Satellite", "Terrain"]
    )

# Chargement des données administratives du Sénégal
@st.cache_resource
def load_senegal_data():
    """Charge les données administratives du Sénégal"""
    data_dir = Path("SEN_adm")
    shapefiles = {}
    
    for level in range(0, 5):
        shp_path = data_dir / f"SEN_adm{level}.shp"
        csv_path = data_dir / f"SEN_adm{level}.csv"
        
        if shp_path.exists():
            try:
                gdf = gpd.read_file(shp_path)
                shapefiles[f"adm{level}"] = gdf
            except Exception as e:
                st.sidebar.error(f"Erreur chargement adm{level}: {e}")
    
    return shapefiles

# Section données Sénégal
st.sidebar.header("🇸🇳 Données Sénégal")
adm_data = load_senegal_data()

if adm_data:
    selected_level = st.sidebar.selectbox(
        "Niveau administratif",
        options=[
            ("Pays", "adm0"),
            ("Régions", "adm1"),
            ("Départements", "adm2"),
            ("Communes / Arrondissements", "adm3"),
            ("Quartiers / Districts", "adm4")
        ],
        format_func=lambda x: x[0],
        key="adm_level"
    )

# Recherche de lieux
st.sidebar.header("🔍 Recherche")
search_query = st.sidebar.text_input("Rechercher un lieu", key="search_input")

# Initialiser les états de session si nécessaire
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'show_search_layer' not in st.session_state:
    st.session_state.show_search_layer = False
if 'selected_search_result' not in st.session_state:
    st.session_state.selected_search_result = None
if 'selected_entity' not in st.session_state:
    st.session_state.selected_entity = None
if 'selected_entity_level' not in st.session_state:
    st.session_state.selected_entity_level = None

search_results = []
if search_query:
    try:
        response = requests.get(
            f"https://nominatim.openstreetmap.org/search?format=json&polygon_geojson=1&q={search_query}",
            headers={'User-Agent': 'KocouMap'}
        )
        search_results = response.json()
        st.session_state.search_results = search_results
    except Exception as e:
        st.sidebar.error(f"Erreur de recherche: {e}")

# Affichage des résultats de recherche
if search_results:
    st.sidebar.subheader("📍 Résultats trouvés")

    # Contrôle global pour afficher/masquer la couche de recherche
    if st.sidebar.checkbox("🗺️ Afficher calque de recherche", value=st.session_state.show_search_layer, key="toggle_search_layer"):
        st.session_state.show_search_layer = True
    else:
        st.session_state.show_search_layer = False
        st.session_state.selected_search_result = None

    if st.session_state.show_search_layer:
        st.sidebar.markdown("**Sélectionnez une zone à afficher:**")

        # Liste des résultats avec boutons radio pour sélection unique
        result_options = [f"{result['display_name'][:50]}..." for result in search_results[:5]]
        selected_option = st.sidebar.radio(
            "Zones disponibles:",
            options=result_options,
            index=None,
            key="search_result_radio"
        )

        # Trouver le résultat correspondant à la sélection
        if selected_option:
            for result in search_results[:5]:
                if selected_option.startswith(result['display_name'][:50]):
                    st.session_state.selected_search_result = result
                    break

# Section pour l'upload de fichiers
st.sidebar.header("📤 Import de données")
uploaded_file = st.sidebar.file_uploader(
    "Uploader un fichier GeoJSON ou Shapefile",
    type=["geojson", "json", "zip", "shp"]
)

# Création de la carte Folium
if map_style == "OpenStreetMap":
    tiles = "OpenStreetMap"
    attr = None
elif map_style == "Satellite":
    tiles = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    attr = "Tiles &copy; Esri"
else:  # Terrain
    tiles = "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
    attr = "&copy; OpenTopoMap contributors"

m = folium.Map(
    location=[default_lat, default_lon],
    zoom_start=zoom_level,
    tiles=tiles,
    attr=attr
)

# Ajouter les données administratives du Sénégal
# Ne les afficher que si aucune entité n'est sélectionnée
if adm_data and selected_level:
    level_key = selected_level[1]
    if level_key in adm_data:
        gdf = adm_data[level_key]
        
        # Ne pas afficher les limites lorsque l'utilisateur a sélectionné une entité.
        if st.session_state.selected_entity is None:
            # Convertir GeoDataFrame en GeoJSON pour Folium
            geojson_data = json.loads(gdf.to_json())
            
            # Ajouter la couche GeoJSON à la carte
            folium.GeoJson(
                geojson_data,
                name=f"Limite {selected_level[0]}",
                style_function=lambda x: {
                    'fillColor': '#2ecc71',
                    'color': '#27ae60',
                    'weight': 2,
                    'fillOpacity': 0.3
                }
            ).add_to(m)

# Afficher le calque de la zone recherchée si activé
search_geojson_bounds = None
if st.session_state.show_search_layer and st.session_state.selected_search_result:
    search_result = st.session_state.selected_search_result

    # Afficher la géométrie de la zone recherchée
    if 'geojson' in search_result and search_result['geojson']:
        geojson_feature = search_result['geojson']

        # Ajouter le GeoJSON à la carte avec style distinctif
        folium.GeoJson(
            geojson_feature,
            name=f"🔍 Zone recherchée: {search_result['display_name'][:30]}",
            style_function=lambda x: {
                'fillColor': '#e74c3c',
                'color': '#c0392b',
                'weight': 3,
                'fillOpacity': 0.25,
                'dashArray': '8, 8'
            },
            tooltip=f"""
            <b>Zone recherchée:</b><br>
            {search_result['display_name']}<br>
            <b>Type:</b> {search_result.get('type', 'N/A')}<br>
            <b>Classe:</b> {search_result.get('class', 'N/A')}
            """
        ).add_to(m)

        # Calculer les limites pour centrer la carte
        try:
            from shapely.geometry import shape
            geom = shape(geojson_feature)
            bounds = geom.bounds  # (minx, miny, maxx, maxy)
            if bounds and len(bounds) == 4:
                # Format pour fit_bounds: [[min_lat, min_lon], [max_lat, max_lon]]
                search_geojson_bounds = [[bounds[1], bounds[0]], [bounds[3], bounds[2]]]
        except:
            # Fallback si le calcul de bounds échoue
            if 'boundingbox' in search_result:
                bbox = search_result['boundingbox']
                try:
                    # Format: [min_lat, max_lat, min_lon, max_lon]
                    search_geojson_bounds = [[float(bbox[0]), float(bbox[2])], [float(bbox[1]), float(bbox[3])]]
                except:
                    pass

# Si on a les limites du GeoJSON, centrer la carte sur ces limites
if search_geojson_bounds:
    m.fit_bounds(search_geojson_bounds, padding=(0.05, 0.05))

# Afficher l'entité sélectionnée si elle existe
if st.session_state.selected_entity is not None and st.session_state.selected_entity_level is not None:
    level_key = st.session_state.selected_entity_level
    if level_key in adm_data:
        gdf = adm_data[level_key]
        # Récupérer la ligne sélectionnée
        selected_row = gdf.iloc[st.session_state.selected_entity]
        
        # Créer un GeoDataFrame avec juste cette ligne
        selected_gdf = gdf.iloc[[st.session_state.selected_entity]]
        selected_geojson = json.loads(selected_gdf.to_json())
        
        # Afficher sur la carte avec un style distinctif
        folium.GeoJson(
            selected_geojson,
            name=f"📍 Entité sélectionnée: {selected_row.get('NAME_1', selected_row.get('NAME_2', 'Entité'))[:40]}",
            style_function=lambda x: {
                'fillColor': '#3498db',
                'color': '#2980b9',
                'weight': 3,
                'fillOpacity': 0.35,
                'dashArray': '3, 3'
            },
            tooltip=f"Entité sélectionnée: {selected_row.get('NAME_1', selected_row.get('NAME_2', 'N/A'))}"
        ).add_to(m)
        
        # Centrer la carte sur l'entité sélectionnée
        try:
            from shapely.geometry import shape, mapping
            geom = shape(selected_geojson['features'][0]['geometry'])
            bounds = geom.bounds
            if bounds and len(bounds) == 4:
                # Calculer le centre de l'entité
                entity_lat = (bounds[1] + bounds[3]) / 2
                entity_lon = (bounds[0] + bounds[2]) / 2
                
                # Mettre à jour les coordonnées affichées
                default_lat = entity_lat
                default_lon = entity_lon
                
                m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.05, 0.05))
        except:
            pass

# Ajouter un marqueur au centre
folium.Marker(
    location=[default_lat, default_lon],
    popup="📍 Centre de la carte",
    tooltip="Position actuelle",
    icon=folium.Icon(color='blue', icon='info-sign')
).add_to(m)

# Traitement des fichiers uploadés
if uploaded_file is not None:
    try:
        if uploaded_file.type == "application/json" or uploaded_file.name.endswith('.geojson'):
            geojson_data = json.load(uploaded_file)
            folium.GeoJson(
                geojson_data,
                name="GeoJSON importé"
            ).add_to(m)
            st.sidebar.success("✅ GeoJSON importé avec succès")
    except Exception as e:
        st.sidebar.error(f"Erreur lors du traitement du fichier: {e}")

# Ajouter le contrôle de couches à la carte
folium.LayerControl(position='topleft', collapsed=True).add_to(m)

# Affichage des contrôles de la carte
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Carte Interactive")
    map_data = st_folium(m, width=1400, height=600)

with col2:
    st.subheader("📊 Informations")
    st.info(f"""
    **Zone actuelle**
    
    Latitude: {default_lat:.4f}
    Longitude: {default_lon:.4f}
    Zoom: {zoom_level}
    """)
    
    # Afficher l'entité sélectionnée si elle existe
    if st.session_state.selected_entity is not None and st.session_state.selected_entity_level is not None:
        level_key = st.session_state.selected_entity_level
        if level_key in adm_data:
            gdf = adm_data[level_key]
            selected_row = gdf.iloc[st.session_state.selected_entity]
            
            # Récupérer le nom de l'entité
            entity_name = (selected_row.get('NAME_1') or 
                          selected_row.get('NAME_2') or 
                          selected_row.get('NAME_3') or 
                          selected_row.get('NAME_4') or 
                          selected_row.get('NAME_0') or 
                          'Entité sélectionnée')
            
            st.success(f"""
            **📍 Entité sélectionnée**
            
            **{entity_name}**
            
            Limite affichée sur la carte
            """)
            
            if st.button("❌ Désélectionner l'entité", key="deselect_entity"):
                st.session_state.selected_entity = None
                st.session_state.selected_entity_level = None
                st.rerun()
    
    # Afficher la zone recherchée si elle est affichée
    if st.session_state.show_search_layer and st.session_state.selected_search_result:
        result = st.session_state.selected_search_result
        st.success(f"""
        **🔍 Zone recherchée affichée**
        
        📍 **{result['display_name']}**
        
        **Type:** {result.get('type', 'N/A')}
        **Classe:** {result.get('class', 'N/A')}
        **OSM ID:** {result.get('osm_id', 'N/A')}
        **OSM Type:** {result.get('osm_type', 'N/A')}
        """)

        # Bouton pour masquer la couche
        if st.button("❌ Masquer la zone recherchée", key="hide_search_layer"):
            st.session_state.show_search_layer = False
            st.session_state.selected_search_result = None
            st.rerun()

# Section Export
st.sidebar.header("📥 Export & Téléchargement")

# Fonctions d'export
def create_export_map(include_search_layer=True):
    """Crée une carte pour l'export avec ou sans la couche de recherche"""
    # Création de la carte Folium pour export
    if map_style == "OpenStreetMap":
        tiles = "OpenStreetMap"
        attr = None
    elif map_style == "Satellite":
        tiles = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        attr = "Tiles &copy; Esri"
    else:  # Terrain
        tiles = "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
        attr = "&copy; OpenTopoMap contributors"

    export_map = folium.Map(
        location=[default_lat, default_lon],
        zoom_start=zoom_level,
        tiles=tiles,
        attr=attr
    )

    # Ajouter les données administratives du Sénégal
    if adm_data and selected_level:
        level_key = selected_level[1]
        if level_key in adm_data:
            gdf = adm_data[level_key]
            geojson_data = json.loads(gdf.to_json())
            folium.GeoJson(
                geojson_data,
                name=f"Limite {selected_level[0]}",
                style_function=lambda x: {
                    'fillColor': '#2ecc71',
                    'color': '#27ae60',
                    'weight': 2,
                    'fillOpacity': 0.3
                }
            ).add_to(export_map)

    # Ajouter la couche de recherche si demandée
    if include_search_layer and st.session_state.show_search_layer and st.session_state.selected_search_result:
        search_result = st.session_state.selected_search_result
        if 'geojson' in search_result and search_result['geojson']:
            folium.GeoJson(
                search_result['geojson'],
                name=f"Zone recherchée: {search_result['display_name'][:30]}",
                style_function=lambda x: {
                    'fillColor': '#e74c3c',
                    'color': '#c0392b',
                    'weight': 3,
                    'fillOpacity': 0.25,
                    'dashArray': '8, 8'
                }
            ).add_to(export_map)

    # Centrer sur la zone recherchée si elle existe
    if include_search_layer and st.session_state.show_search_layer and st.session_state.selected_search_result:
        search_result = st.session_state.selected_search_result
        if 'geojson' in search_result and search_result['geojson']:
            try:
                from shapely.geometry import shape
                geom = shape(search_result['geojson'])
                bounds = geom.bounds
                if bounds and len(bounds) == 4:
                    export_map.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(0.05, 0.05))
            except:
                pass

    return export_map

def export_map_as_html(map_object, filename="kocoumap_export.html"):
    """Exporte la carte au format HTML"""
    html_content = map_object.get_root().render()
    return html_content, filename

def get_map_download_link(map_object, filename="kocoumap_export.html", text="📥 Télécharger la carte"):
    """Génère un lien de téléchargement pour la carte"""
    html_content, filename = export_map_as_html(map_object, filename)
    b64 = base64.b64encode(html_content.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="{filename}" style="text-decoration: none;">{text}</a>'
    return href

# Options d'export
export_option = st.sidebar.selectbox(
    "Type d'export",
    ["Carte complète", "Zone recherchée uniquement"],
    key="export_type"
)

if st.sidebar.button("📸 Exporter en HTML", key="export_html"):
    try:
        include_search = export_option == "Carte complète"
        export_map = create_export_map(include_search)

        filename = f"kocoumap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        html_content, filename = export_map_as_html(export_map, filename)

        # Créer le fichier temporaire et le proposer au téléchargement
        st.sidebar.download_button(
            label="📥 Télécharger HTML",
            data=html_content,
            file_name=filename,
            mime="text/html",
            key="download_html"
        )
        st.sidebar.success("✅ Export HTML prêt!")

    except Exception as e:
        st.sidebar.error(f"Erreur lors de l'export HTML: {e}")

# Export PNG (capture d'écran simulée)
if st.sidebar.button("🖼️ Exporter en PNG", key="export_png"):
    try:
        include_search = export_option == "Carte complète"
        export_map = create_export_map(include_search)

        # Créer un nom de fichier
        filename = f"kocoumap_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        st.sidebar.info("""
        **📋 Instructions pour l'export PNG:**

        1. La carte s'ouvrira dans un nouvel onglet
        2. Utilisez les outils de votre navigateur (Ctrl+S ou Clic droit > Enregistrer)
        3. Choisissez "Enregistrer en tant qu'image" ou "Capture d'écran"
        """)

        # Ouvrir la carte dans un nouvel onglet
        html_content, _ = export_map_as_html(export_map, f"{filename}.html")
        st.sidebar.components.v1.html(
            f"""
            <div style="text-align: center; margin: 10px 0;">
                <button onclick="window.open('data:text/html;base64,{base64.b64encode(html_content.encode()).decode()}', '_blank')"
                        style="background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;">
                    🖼️ Ouvrir la carte pour capture PNG
                </button>
            </div>
            """,
            height=50
        )

    except Exception as e:
        st.sidebar.error(f"Erreur lors de l'export PNG: {e}")

# Export des données GeoJSON
if st.sidebar.button("📄 Exporter GeoJSON", key="export_geojson"):
    try:
        if st.session_state.show_search_layer and st.session_state.selected_search_result:
            search_result = st.session_state.selected_search_result
            if 'geojson' in search_result and search_result['geojson']:
                geojson_data = search_result['geojson']
                filename = f"zone_{search_result['display_name'].replace(' ', '_')[:30]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"

                st.sidebar.download_button(
                    label="📥 Télécharger GeoJSON",
                    data=json.dumps(geojson_data, indent=2),
                    file_name=filename,
                    mime="application/json",
                    key="download_geojson"
                )
                st.sidebar.success("✅ GeoJSON prêt!")
            else:
                st.sidebar.warning("Aucune géométrie disponible pour cette zone.")
        else:
            st.sidebar.warning("Veuillez d'abord sélectionner une zone à rechercher.")

    except Exception as e:
        st.sidebar.error(f"Erreur lors de l'export GeoJSON: {e}")

st.sidebar.markdown("---")

if adm_data:
    # Créer des onglets pour chaque niveau
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Pays", "Régions", "Départements", "Communes", "Quartiers"])
    
    with tab1:
        if "adm0" in adm_data:
            st.subheader("📍 Niveau Pays")
            df_display = adm_data["adm0"].drop(columns=['geometry'])
            
            # Sélecteur d'entité
            col_select, col_info = st.columns([2, 1])
            with col_select:
                selected_idx = st.selectbox(
                    "Sélectionner une entité pour l'afficher sur la carte:",
                    options=range(len(df_display)),
                    format_func=lambda x: f"{df_display.iloc[x].get('NAME_0', 'N/A')}",
                    key="select_adm0"
                )
                if st.button("Afficher cette entité", key="show_adm0"):
                    st.session_state.selected_entity = selected_idx
                    st.session_state.selected_entity_level = "adm0"
                    st.success("✅ Entité sélectionnée affichée sur la carte")
                    st.experimental_rerun()
    
    with tab2:
        if "adm1" in adm_data:
            st.subheader("📍 Niveau Régions")
            df_display = adm_data["adm1"].drop(columns=['geometry'])
            
            # Sélecteur d'entité
            col_select, col_info = st.columns([2, 1])
            with col_select:
                selected_idx = st.selectbox(
                    "Sélectionner une entité pour l'afficher sur la carte:",
                    options=range(len(df_display)),
                    format_func=lambda x: f"{df_display.iloc[x].get('NAME_1', 'N/A')}",
                    key="select_adm1"
                )
                if st.button("Afficher cette entité", key="show_adm1"):
                    st.session_state.selected_entity = selected_idx
                    st.session_state.selected_entity_level = "adm1"
                    st.success("✅ Entité sélectionnée affichée sur la carte")
                    st.experimental_rerun()
    
    with tab3:
        if "adm2" in adm_data:
            st.subheader("📍 Niveau Départements")
            df_display = adm_data["adm2"].drop(columns=['geometry'])
            
            # Sélecteur d'entité
            col_select, col_info = st.columns([2, 1])
            with col_select:
                selected_idx = st.selectbox(
                    "Sélectionner une entité pour l'afficher sur la carte:",
                    options=range(len(df_display)),
                    format_func=lambda x: f"{df_display.iloc[x].get('NAME_2', 'N/A')}",
                    key="select_adm2"
                )
                if st.button("Afficher cette entité", key="show_adm2"):
                    st.session_state.selected_entity = selected_idx
                    st.session_state.selected_entity_level = "adm2"
                    st.success("✅ Entité sélectionnée affichée sur la carte")
                    st.experimental_rerun()
    
    with tab4:
        if "adm3" in adm_data:
            st.subheader("📍 Niveau Communes/Arrondissements")
            df_display = adm_data["adm3"].drop(columns=['geometry'])
            
            # Sélecteur d'entité
            col_select, col_info = st.columns([2, 1])
            with col_select:
                selected_idx = st.selectbox(
                    "Sélectionner une entité pour l'afficher sur la carte:",
                    options=range(len(df_display)),
                    format_func=lambda x: f"{df_display.iloc[x].get('NAME_3', 'N/A')}",
                    key="select_adm3"
                )
                if st.button("Afficher cette entité", key="show_adm3"):
                    st.session_state.selected_entity = selected_idx
                    st.session_state.selected_entity_level = "adm3"
                    st.success("✅ Entité sélectionnée affichée sur la carte")
                    st.experimental_rerun()
    
    with tab5:
        if "adm4" in adm_data:
            st.subheader("📍 Niveau Quartiers/Districts")
            df_display = adm_data["adm4"].drop(columns=['geometry'])
            
            # Sélecteur d'entité
            col_select, col_info = st.columns([2, 1])
            with col_select:
                selected_idx = st.selectbox(
                    "Sélectionner une entité pour l'afficher sur la carte:",
                    options=range(len(df_display)),
                    format_func=lambda x: f"{df_display.iloc[x].get('NAME_4', 'N/A')}",
                    key="select_adm4"
                )
                if st.button("Afficher cette entité", key="show_adm4"):
                    st.session_state.selected_entity = selected_idx
                    st.session_state.selected_entity_level = "adm4"
                    st.success("✅ Entité sélectionnée affichée sur la carte")
                    st.experimental_rerun()

# Section Export Rapide
st.header("📥 Export Rapide")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🖼️ Image (PNG)")
    st.markdown("""
    **Pour exporter en image:**
    1. Utilisez le bouton dans la sidebar
    2. La carte s'ouvre dans un nouvel onglet
    3. Capturez l'écran avec votre navigateur
    """)
    if st.button("📸 Ouvrir pour capture PNG", key="quick_png"):
        try:
            include_search = True
            export_map = create_export_map(include_search)
            html_content, _ = export_map_as_html(export_map, "temp.html")
            st.components.v1.html(
                f"""
                <div style="text-align: center; margin: 10px 0;">
                    <button onclick="window.open('data:text/html;base64,{base64.b64encode(html_content.encode()).decode()}', '_blank')"
                            style="background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;">
                        🖼️ Ouvrir la carte
                    </button>
                </div>
                """,
                height=50
            )
        except Exception as e:
            st.error(f"Erreur: {e}")

with col2:
    st.subheader("📄 Carte Interactive (HTML)")
    st.markdown("""
    **Carte HTML interactive:**
    - Préserve tous les contrôles
    - Peut être ouverte dans n'importe quel navigateur
    - Idéale pour partage et archivage
    """)
    if st.button("📥 Télécharger HTML", key="quick_html"):
        try:
            include_search = True
            export_map = create_export_map(include_search)
            filename = f"kocoumap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            html_content, filename = export_map_as_html(export_map, filename)
            st.download_button(
                label="📥 Télécharger maintenant",
                data=html_content,
                file_name=filename,
                mime="text/html",
                key="quick_download_html"
            )
        except Exception as e:
            st.error(f"Erreur: {e}")

with col3:
    st.subheader("📄 Données (GeoJSON)")
    st.markdown("""
    **Données géographiques brutes:**
    - Format GeoJSON standard
    - Compatible avec tous les SIG
    - Uniquement la zone recherchée
    """)
    if st.button("📥 Télécharger GeoJSON", key="quick_geojson"):
        try:
            if st.session_state.show_search_layer and st.session_state.selected_search_result:
                search_result = st.session_state.selected_search_result
                if 'geojson' in search_result and search_result['geojson']:
                    geojson_data = search_result['geojson']
                    filename = f"zone_{search_result['display_name'].replace(' ', '_')[:30]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"
                    st.download_button(
                        label="📥 Télécharger maintenant",
                        data=json.dumps(geojson_data, indent=2),
                        file_name=filename,
                        mime="application/json",
                        key="quick_download_geojson"
                    )
                else:
                    st.warning("Aucune géométrie disponible pour cette zone.")
            else:
                st.warning("Veuillez d'abord rechercher et sélectionner une zone.")
        except Exception as e:
            st.error(f"Erreur: {e}")

# Pied de page
st.divider()
st.markdown(f"""
    <div style='text-align: center; color: #888; font-size: 12px;'>
    KocouMap © 2024 | Données : Sénégal Administratif | Mise à jour: {datetime.now().strftime('%d/%m/%Y %H:%M')}
    </div>
""", unsafe_allow_html=True)
