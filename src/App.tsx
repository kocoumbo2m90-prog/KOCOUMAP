import React, { useState, useRef, useEffect, FormEvent, ChangeEvent } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, GeoJSON, ScaleControl } from 'react-leaflet';
import L from 'leaflet';
import { toPng } from 'html-to-image';
import { Search, Download, Map as MapIcon, Layers, Navigation, Info, Settings, Maximize2, Upload, Trash2, Filter, ChevronRight, List, Globe, Ruler, Target, LocateFixed } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import shp from 'shpjs';
import proj4 from 'proj4';

// Register EPSG:32628 (UTM Zone 28N)
proj4.defs("EPSG:32628", "+proj=utm +zone=28 +datum=WGS84 +units=m +no_defs");

// @ts-ignore
import markerIcon from 'leaflet/dist/images/marker-icon.png';
// @ts-ignore
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

L.Marker.prototype.options.icon = DefaultIcon;

// Component to change map view
function ChangeView({ center, zoom, bounds }: { center: [number, number], zoom: number, bounds?: L.LatLngBoundsExpression }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) {
      map.fitBounds(bounds);
    } else {
      map.setView(center, zoom);
    }
  }, [center, zoom, bounds, map]);
  return null;
}

interface SearchResult {
  display_name: string;
  lat: string;
  lon: string;
  osm_id: string;
  osm_type: string;
  geojson?: any;
}

interface BoundaryLayer {
  id: string;
  name: string;
  data: any;
  type: 'search' | 'shapefile';
  color: string;
}

const COLORS = ['#141414', '#FF6321', '#2E7D32', '#1565C0', '#D84315', '#6A1B9A'];

const SCALES = [
  { label: '1/5 000', value: 5000 },
  { label: '1/10 000', value: 10000 },
  { label: '1/25 000', value: 25000 },
  { label: '1/50 000', value: 50000 },
  { label: '1/100 000', value: 100000 },
  { label: '1/200 000', value: 200000 },
  { label: '1/500 000', value: 500000 },
];

export default function App() {
  const [center, setCenter] = useState<[number, number]>([48.8566, 2.3522]); // Paris
  const [zoom, setZoom] = useState(13);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [mapStyle, setMapStyle] = useState('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png');
  const [boundaries, setBoundaries] = useState<BoundaryLayer[]>([]);
  const [mapBounds, setMapBounds] = useState<L.LatLngBoundsExpression | undefined>(undefined);
  const [crs, setCrs] = useState('EPSG:4326'); // WGS84
  const [unit, setUnit] = useState<'metric' | 'imperial'>('metric');
  const [exportScale, setExportScale] = useState(2);
  const [userLocation, setUserLocation] = useState<[number, number] | null>(null);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [isOwner, setIsOwner] = useState(false);
  const [adminCode, setAdminCode] = useState('');
  const [showAdminInput, setShowAdminInput] = useState(false);
  const [transactionId, setTransactionId] = useState('');
  const mapRef = useRef<HTMLDivElement>(null);

  const locateUser = () => {
    if (!navigator.geolocation) {
      alert("La géolocalisation n'est pas supportée par votre navigateur.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        setUserLocation([latitude, longitude]);
        setCenter([latitude, longitude]);
        setZoom(16);
      },
      (error) => {
        console.error("Error getting location:", error);
        alert("Impossible de récupérer votre position. Assurez-vous d'avoir autorisé l'accès à la localisation.");
      }
    );
  };

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!searchQuery) return;
    setIsSearching(true);
    try {
      const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&polygon_geojson=1&q=${encodeURIComponent(searchQuery)}`);
      const data = await response.json();
      setSearchResults(data);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setIsSearching(false);
    }
  };

  const addBoundary = (result: SearchResult) => {
    if (result.geojson) {
      const newBoundary: BoundaryLayer = {
        id: `${result.osm_type}-${result.osm_id}`,
        name: result.display_name.split(',')[0],
        data: result.geojson,
        type: 'search',
        color: COLORS[boundaries.length % COLORS.length]
      };
      setBoundaries(prev => [...prev, newBoundary]);
      
      const geojsonLayer = L.geoJSON(result.geojson);
      setMapBounds(geojsonLayer.getBounds().pad(0.1));
    }
    setCenter([parseFloat(result.lat), parseFloat(result.lon)]);
    setZoom(15);
    setSearchResults([]);
    setSearchQuery('');
  };

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const buffer = event.target?.result as ArrayBuffer;
        const geojson = await shp(buffer);
        
        const newBoundary: BoundaryLayer = {
          id: `shp-${Date.now()}`,
          name: file.name,
          data: geojson,
          type: 'shapefile',
          color: COLORS[boundaries.length % COLORS.length]
        };
        setBoundaries(prev => [...prev, newBoundary]);
        
        const geojsonLayer = L.geoJSON(geojson);
        setMapBounds(geojsonLayer.getBounds().pad(0.1));
      } catch (error) {
        console.error('Shapefile parsing failed:', error);
        alert('Erreur lors de la lecture du Shapefile. Assurez-vous qu\'il s\'agit d\'un fichier .zip contenant .shp, .dbf, etc.');
      }
    };
    reader.readAsArrayBuffer(file);
  };

  const removeBoundary = (id: string) => {
    setBoundaries(prev => prev.filter(b => b.id !== id));
  };

  const downloadMap = () => {
    if (isOwner) {
      executeDownload();
    } else {
      setShowPaymentModal(true);
    }
  };

  const handleAdminAuth = () => {
    if (adminCode === 'KOCOUMBO2026') {
      setIsOwner(true);
      setShowAdminInput(false);
      setShowPaymentModal(false);
      alert("MODE PROPRIÉTAIRE ACTIVÉ : TÉLÉCHARGEMENTS GRATUITS DÉBLOQUÉS.");
    } else {
      alert("CODE INCORRECT.");
    }
  };
  const executeDownload = async () => {
    if (mapRef.current === null) return;
    
    try {
      const dataUrl = await toPng(mapRef.current, {
        cacheBust: true,
        quality: 1,
        pixelRatio: exportScale,
      });
      const link = document.createElement('a');
      link.download = `kocoumbo-map-${Date.now()}.png`;
      link.href = dataUrl;
      link.click();
      setShowPaymentModal(false);
      setTransactionId('');
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  const styles = [
    { name: 'Standard', url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png' },
    { name: 'Satellite', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', overlay: 'https://stamen-tiles.a.ssl.fastly.net/toner-labels/{z}/{x}/{y}.png' },
    { name: 'Terrain', url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png' },
    { name: 'Dark', url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png' },
  ];

  const currentStyle = styles.find(s => s.url === mapStyle) || styles[0];

  const formatCoords = (lat: number, lon: number) => {
    if (crs === 'EPSG:3857') {
      const [x, y] = proj4('EPSG:4326', 'EPSG:3857', [lon, lat]);
      return `X: ${x.toFixed(0)} Y: ${y.toFixed(0)}`;
    } else if (crs === 'EPSG:32628') {
      const [x, y] = proj4('EPSG:4326', 'EPSG:32628', [lon, lat]);
      return `E: ${x.toFixed(0)} N: ${y.toFixed(0)}`;
    }
    return `LAT: ${lat.toFixed(6)} LON: ${lon.toFixed(6)}`;
  };

  const setScale = (scaleValue: number) => {
    // Standard web map zoom calculation for a given scale
    // Assuming 96 DPI (0.000264583 meters per pixel)
    const circumference = 40075017;
    const latRad = center[0] * Math.PI / 180;
    const resolution = scaleValue * 0.000264583;
    const z = Math.log2((circumference * Math.cos(latRad)) / (256 * resolution));
    setZoom(Math.round(z));
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-black bg-[#E4E3E0] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-sm border border-black bg-black text-[#E4E3E0]">
            <Target size={20} />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tighter">KOCOUMBOmapservice</h1>
            <p className="text-[10px] font-medium uppercase opacity-50">Advanced Cartography Engine</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <form onSubmit={handleSearch} className="relative flex items-center">
            <input
              type="text"
              placeholder="RÉGION, COMMUNE, QUARTIER..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-10 w-64 border border-black bg-transparent px-4 text-xs font-mono uppercase focus:outline-none"
            />
            <button 
              type="submit"
              disabled={isSearching}
              className="flex h-10 w-10 items-center justify-center border-y border-r border-black hover:bg-black hover:text-[#E4E3E0] transition-colors"
            >
              <Search size={16} />
            </button>

            <AnimatePresence>
              {searchResults.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="absolute top-12 left-0 z-[1000] w-full border border-black bg-[#E4E3E0] shadow-xl"
                >
                  {searchResults.map((result, idx) => (
                    <div
                      key={idx}
                      onClick={() => addBoundary(result)}
                      className="cursor-pointer border-b border-black/10 p-3 hover:bg-black hover:text-[#E4E3E0] transition-colors group flex justify-between items-center"
                    >
                      <div>
                        <p className="text-[10px] font-bold uppercase truncate">{result.display_name}</p>
                        <p className="text-[9px] font-mono opacity-60">OSM: {result.osm_type}/{result.osm_id}</p>
                      </div>
                      <ChevronRight size={14} className="opacity-0 group-hover:opacity-100" />
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </form>

          <label className="flex h-10 cursor-pointer items-center gap-2 border border-black bg-transparent px-4 text-[10px] font-bold uppercase hover:bg-black hover:text-[#E4E3E0] transition-all">
            <Upload size={14} />
            Importer SHP
            <input type="file" accept=".zip" onChange={handleFileUpload} className="hidden" />
          </label>

          <button
            onClick={downloadMap}
            className="flex h-10 items-center gap-2 border border-black bg-black px-4 text-[10px] font-bold uppercase text-[#E4E3E0] hover:bg-transparent hover:text-black transition-all"
          >
            <Download size={14} />
            Exporter Map
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-72 border-r border-black bg-[#E4E3E0] flex flex-col">
          <div className="p-4 flex-1 overflow-y-auto">
            <h2 className="text-[11px] font-serif italic opacity-50 uppercase mb-4">Configuration & Calques</h2>
            
            <div className="space-y-6">
              {/* Layers List */}
              <div>
                <label className="text-[9px] font-bold uppercase mb-2 flex items-center gap-2">
                  <Filter size={10} />
                  Calques actifs ({boundaries.length})
                </label>
                <div className="space-y-2">
                  {boundaries.length === 0 ? (
                    <div className="border border-dashed border-black/20 p-4 text-center">
                      <p className="text-[9px] uppercase opacity-40 italic">Aucun calque sélectionné</p>
                    </div>
                  ) : (
                    boundaries.map((b) => (
                      <div key={b.id} className="flex items-center justify-between border border-black p-2 bg-white/50">
                        <div className="flex items-center gap-2 overflow-hidden">
                          <div className="h-2 w-2 rounded-full" style={{ backgroundColor: b.color }}></div>
                          <div className="overflow-hidden">
                            <p className="text-[9px] font-bold uppercase truncate">{b.name}</p>
                            <p className="text-[8px] font-mono opacity-50">{b.type === 'shapefile' ? 'SHP' : 'BOUNDARY'}</p>
                          </div>
                        </div>
                        <button 
                          onClick={() => removeBoundary(b.id)}
                          className="text-red-600 hover:bg-red-50 p-1"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Legend */}
              {boundaries.length > 0 && (
                <div className="border border-black p-3 bg-white/30">
                  <label className="text-[9px] font-bold uppercase mb-2 flex items-center gap-2">
                    <List size={10} />
                    Légende
                  </label>
                  <div className="space-y-2">
                    {boundaries.map((b) => {
                      // Detect geometry type for legend icon
                      let geomType = 'Polygon';
                      if (b.data.features && b.data.features.length > 0) {
                        geomType = b.data.features[0].geometry.type;
                      } else if (b.data.geometry) {
                        geomType = b.data.geometry.type;
                      }

                      return (
                        <div key={b.id} className="flex items-center gap-3 text-[8px] font-bold uppercase">
                          <div className="flex items-center justify-center w-6 h-4">
                            {geomType.includes('Point') ? (
                              <div className="w-2 h-2 rounded-full border border-black" style={{ backgroundColor: b.color }}></div>
                            ) : geomType.includes('Line') ? (
                              <div className="w-full h-[2px]" style={{ backgroundColor: b.color }}></div>
                            ) : (
                              <div className="w-4 h-3 border border-black" style={{ backgroundColor: b.color, opacity: 0.4 }}></div>
                            )}
                          </div>
                          <span className="truncate flex-1">{b.name}</span>
                          <span className="opacity-40 text-[7px]">{geomType}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              <div>
                <label className="text-[9px] font-bold uppercase mb-2 block">Qualité d'Exportation (Scale)</label>
                <div className="flex gap-1">
                  {[1, 2, 3].map((s) => (
                    <button
                      key={s}
                      onClick={() => setExportScale(s)}
                      className={`flex-1 h-8 border border-black text-[9px] font-bold uppercase transition-all ${
                        exportScale === s ? 'bg-black text-[#E4E3E0]' : 'hover:bg-black/5'
                      }`}
                    >
                      {s}x
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-[9px] font-bold uppercase mb-2 block">Style de Fond</label>
                <div className="grid grid-cols-2 gap-2">
                  {styles.map((style) => (
                    <button
                      key={style.name}
                      onClick={() => setMapStyle(style.url)}
                      className={`h-12 border border-black text-[9px] font-bold uppercase transition-all ${
                        mapStyle === style.url ? 'bg-black text-[#E4E3E0]' : 'hover:bg-black/5'
                      }`}
                    >
                      {style.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* CRS Selection */}
              <div className="pt-4 border-t border-black/10 space-y-4">
                <div>
                  <label className="text-[9px] font-bold uppercase mb-2 flex items-center gap-2">
                    <Globe size={10} />
                    Système de Référence (CRS)
                  </label>
                  <select 
                    value={crs}
                    onChange={(e) => setCrs(e.target.value)}
                    className="w-full h-8 border border-black bg-transparent px-2 text-[9px] font-bold uppercase focus:outline-none"
                  >
                    <option value="EPSG:4326">WGS 84 (EPSG:4326)</option>
                    <option value="EPSG:3857">Web Mercator (EPSG:3857)</option>
                    <option value="EPSG:32628">UTM 28N (EPSG:32628)</option>
                  </select>
                </div>

                {/* Scale Selection */}
                <div>
                  <label className="text-[9px] font-bold uppercase mb-2 flex items-center gap-2">
                    <Ruler size={10} />
                    Échelle Cartographique
                  </label>
                  <div className="grid grid-cols-2 gap-1">
                    {SCALES.map((s) => (
                      <button
                        key={s.label}
                        onClick={() => setScale(s.value)}
                        className="h-8 border border-black/20 text-[9px] font-bold uppercase hover:bg-black hover:text-[#E4E3E0] transition-colors"
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-[9px] font-bold uppercase mb-2 block">Unités de Mesure</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setUnit('metric')}
                      className={`flex-1 h-8 border border-black text-[9px] font-bold uppercase ${unit === 'metric' ? 'bg-black text-[#E4E3E0]' : ''}`}
                    >
                      m/km
                    </button>
                    <button
                      onClick={() => setUnit('imperial')}
                      className={`flex-1 h-8 border border-black text-[9px] font-bold uppercase ${unit === 'imperial' ? 'bg-black text-[#E4E3E0]' : ''}`}
                    >
                      ft/mi
                    </button>
                  </div>
                </div>
              </div>

              {/* Administrative Search Helper */}
              <div className="pt-4 border-t border-black/10">
                <label className="text-[9px] font-bold uppercase mb-2 block">Aide à la Sélection</label>
                <div className="grid grid-cols-1 gap-1">
                  {['Région', 'Département', 'Arrondissement', 'Commune', 'Village', 'Quartier'].map((level) => (
                    <button
                      key={level}
                      onClick={() => setSearchQuery(level + " ")}
                      className="flex items-center justify-between border border-black/20 p-2 text-[9px] uppercase hover:bg-black hover:text-[#E4E3E0] transition-colors"
                    >
                      <span>{level}</span>
                      <ChevronRight size={10} />
                    </button>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t border-black/10">
                <div className="bg-black/5 p-3 font-mono text-[10px] space-y-1">
                  <div className="flex justify-between">
                    <span className="opacity-50">COORD:</span>
                    <span className="truncate">{formatCoords(center[0], center[1])}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="opacity-50">ZOOM:</span>
                    <span>{zoom}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-auto p-4 border-t border-black">
            <div className="flex flex-col gap-2">
              {isOwner && (
                <div className="mb-2 border border-black bg-black p-2 text-[9px] font-bold uppercase text-[#E4E3E0] flex items-center gap-2">
                  <Target size={12} className="text-red-500" />
                  <span>Mode Propriétaire Actif</span>
                </div>
              )}
              <div className="flex items-center gap-2 text-[10px] font-bold uppercase opacity-50">
                <Navigation size={12} />
                <span>GPS Active</span>
              </div>
              <div className="flex items-center gap-2 text-[10px] font-bold uppercase opacity-50">
                <Layers size={12} />
                <span>Vector Engine</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Map Area */}
        <section className="relative flex-1 bg-white" ref={mapRef}>
          <MapContainer center={center} zoom={zoom} scrollWheelZoom={true} className="h-full w-full">
            <ChangeView center={center} zoom={zoom} bounds={mapBounds} />
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url={mapStyle}
            />
            {currentStyle.overlay && (
              <TileLayer
                url={currentStyle.overlay}
                opacity={0.8}
              />
            )}
            
            <ScaleControl position="bottomleft" metric={unit === 'metric'} imperial={unit === 'imperial'} />
            
            {/* Dynamic Scale Overlay for Export */}
            <div className="absolute bottom-12 left-6 z-[1000] bg-white/80 border border-black px-2 py-1 text-[10px] font-mono font-bold uppercase">
              Échelle: 1/{Math.round((40075017 * Math.cos(center[0] * Math.PI / 180)) / (256 * Math.pow(2, zoom) * 0.000264583) / 100) * 100}
            </div>
            
            {boundaries.map((b) => (
              <GeoJSON 
                key={b.id} 
                data={b.data} 
                style={{
                  color: b.color,
                  weight: 2,
                  fillColor: b.color,
                  fillOpacity: 0.15,
                  dashArray: b.type === 'shapefile' ? '5, 5' : ''
                }}
                onEachFeature={(feature, layer) => {
                  if (feature.properties) {
                    const popupContent = Object.entries(feature.properties)
                      .map(([key, val]) => `<div class="flex justify-between gap-4 border-b border-black/10 py-1"><span class="font-bold uppercase text-[8px]">${key}</span><span class="text-[8px] font-mono">${val}</span></div>`)
                      .join('');
                    layer.bindPopup(`<div class="max-h-48 overflow-y-auto w-48">${popupContent}</div>`);
                  }
                }}
              />
            ))}

            {userLocation && (
              <Marker position={userLocation}>
                <Popup>
                  <div className="text-[10px] font-bold uppercase">
                    Ma Position Actuelle
                  </div>
                </Popup>
              </Marker>
            )}

            <Marker position={center}>
              <Popup>
                <div className="text-[10px] font-bold uppercase">
                  Point de Référence
                </div>
              </Popup>
            </Marker>
          </MapContainer>

          {/* Overlay UI */}
          <div className="absolute bottom-6 right-6 z-[1000] flex flex-col gap-2">
            <button 
              onClick={locateUser}
              className="flex h-10 w-10 items-center justify-center border border-black bg-[#E4E3E0] hover:bg-black hover:text-[#E4E3E0] transition-colors"
              title="Ma Position"
            >
              <LocateFixed size={16} />
            </button>
            <button className="flex h-10 w-10 items-center justify-center border border-black bg-[#E4E3E0] hover:bg-black hover:text-[#E4E3E0] transition-colors">
              <Maximize2 size={16} />
            </button>
            <button className="flex h-10 w-10 items-center justify-center border border-black bg-[#E4E3E0] hover:bg-black hover:text-[#E4E3E0] transition-colors">
              <Settings size={16} />
            </button>
            <button className="flex h-10 w-10 items-center justify-center border border-black bg-[#E4E3E0] hover:bg-black hover:text-[#E4E3E0] transition-colors">
              <Info size={16} />
            </button>
          </div>

          {/* Grid Overlay for aesthetic */}
          <div className="pointer-events-none absolute inset-0 z-[999] opacity-[0.03]" 
               style={{ backgroundImage: 'radial-gradient(circle, black 1px, transparent 1px)', backgroundSize: '30px 30px' }}>
          </div>
        </section>
      </main>

      {/* Footer Status Bar */}
      <footer className="flex h-8 items-center justify-between border-t border-black bg-black px-6 text-[9px] font-mono text-[#E4E3E0]">
        <div className="flex items-center gap-4">
          <span>SYSTEM: KOCOUMBO-SERVICE</span>
          <span className="opacity-50">|</span>
          <span>CRS: {crs}</span>
        </div>
        <div className="flex items-center gap-4">
          <span>{new Date().toISOString()}</span>
          <span className="opacity-50">|</span>
          <span>LOC: {formatCoords(center[0], center[1])}</span>
        </div>
      </footer>

      {/* Payment Modal */}
      <AnimatePresence>
        {showPaymentModal && (
          <div className="fixed inset-0 z-[5000] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="w-full max-w-md border border-black bg-[#E4E3E0] p-8 shadow-2xl"
            >
              <div className="mb-6 flex items-center gap-4 border-b border-black pb-4">
                <div className="flex h-12 w-12 items-center justify-center bg-black text-[#E4E3E0]">
                  <Download size={24} />
                </div>
                <div>
                  <h2 className="text-xl font-bold uppercase tracking-tighter">Paiement Requis</h2>
                  <p className="text-[10px] font-mono opacity-60 text-red-600 font-bold">ACCÈS RESTREINT AU TÉLÉCHARGEMENT</p>
                </div>
              </div>

              <div className="space-y-4 text-xs font-medium uppercase leading-relaxed">
                <p>Pour télécharger cette carte haute résolution, veuillez effectuer un transfert de frais de service vers le numéro suivant :</p>
                
                <div className="border border-black bg-white p-4 text-center">
                  <p className="text-[10px] opacity-50 mb-1">NUMÉRO DE RÉCEPTION</p>
                  <p className="text-2xl font-bold tracking-widest">00221772414357</p>
                  <div className="mt-2 flex justify-center gap-4 text-[10px] font-bold">
                    <span className="bg-orange-500 text-white px-2 py-0.5">ORANGE MONEY</span>
                    <span className="bg-blue-500 text-white px-2 py-0.5">WAVE</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-[9px] font-bold block">ID DE TRANSACTION / RÉFÉRENCE</label>
                  <input 
                    type="text" 
                    value={transactionId}
                    onChange={(e) => setTransactionId(e.target.value)}
                    placeholder="SAISISSEZ LA RÉFÉRENCE DU PAIEMENT"
                    className="w-full h-10 border border-black bg-white px-4 text-[10px] font-mono focus:outline-none"
                  />
                </div>

                <div className="flex gap-2 pt-4">
                  <button 
                    onClick={() => {
                      setShowPaymentModal(false);
                      setShowAdminInput(false);
                    }}
                    className="flex-1 h-12 border border-black text-[10px] font-bold hover:bg-black hover:text-[#E4E3E0] transition-all"
                  >
                    ANNULER
                  </button>
                  <button 
                    onClick={executeDownload}
                    disabled={!transactionId}
                    className="flex-1 h-12 bg-black text-[#E4E3E0] text-[10px] font-bold hover:bg-transparent hover:text-black border border-black transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    CONFIRMER & TÉLÉCHARGER
                  </button>
                </div>
              </div>
              
              <div className="mt-6 border-t border-black pt-4 text-center">
                {!showAdminInput ? (
                  <button 
                    onClick={() => setShowAdminInput(true)}
                    className="text-[8px] font-mono uppercase opacity-40 hover:opacity-100 underline"
                  >
                    Accès Propriétaire
                  </button>
                ) : (
                  <div className="flex gap-2">
                    <input 
                      type="password" 
                      value={adminCode}
                      onChange={(e) => setAdminCode(e.target.value)}
                      placeholder="CODE SECRET"
                      className="flex-1 h-8 border border-black bg-white px-2 text-[9px] font-mono focus:outline-none"
                    />
                    <button 
                      onClick={handleAdminAuth}
                      className="bg-black text-[#E4E3E0] px-3 text-[8px] font-bold uppercase"
                    >
                      OK
                    </button>
                  </div>
                )}
              </div>
              
              <p className="mt-4 text-center text-[8px] font-mono opacity-40">
                L'ID DE TRANSACTION SERA VÉRIFIÉ PAR NOTRE SYSTÈME.
              </p>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
