// Inicializar mapa centrado en la Región de Aysén
var map = L.map('map').setView([-45.5712, -72.0685], 8);

// Añadir capa de OpenStreetMap
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

// FIX: mapa de estados para los 4 colores posibles (green, yellow, red, gray)
// Se usa para el texto del popup y el color del borde del marcador
const ESTADO_CONFIG = {
    green:  { label: '✅ Apta',           css: 'color:green',       borde: '#2ecc71' },
    yellow: { label: '⚠️ Advertencia',    css: 'color:darkorange',  borde: '#f39c12' },
    red:    { label: '❌ No apta',         css: 'color:red',         borde: '#e74c3c' },
    gray:   { label: '⬜ Sin mediciones',  css: 'color:gray',        borde: '#95a5a6' },
};

// Función para cargar los puntos desde la API
async function cargarPuntos() {
    try {
        // FIX: URL relativa en lugar de http://127.0.0.1:8000 (funciona en local y en Render)
        const response = await fetch('/mapa/puntos-calidad');

        if (!response.ok) {
            throw new Error(`Error HTTP ${response.status}`);
        }

        const puntos = await response.json();

        puntos.forEach(punto => {
            const estado = ESTADO_CONFIG[punto.color] ?? ESTADO_CONFIG['gray'];

            // Marcador circular con color y borde correspondiente al estado NCh 409
            L.circleMarker([punto.lat, punto.lng], {
                radius:      12,
                fillColor:   punto.color,
                color:       estado.borde,
                weight:      2,
                fillOpacity: 0.9
            })
            .addTo(map)
            .bindPopup(`
                <div style="text-align:center; min-width:160px;">
                    <h3 style="margin:0 0 6px 0;">${punto.nombre}</h3>
                    <hr style="margin:4px 0;">
                    <p style="margin:6px 0;">
                        <b>Estado:</b>
                        <span style="${estado.css}">${estado.label}</span>
                    </p>
                    <p style="font-size:0.85em; color:#666; margin:4px 0;">
                        <i>Historial detallado — Próximamente</i>
                    </p>
                </div>
            `);
        });

    } catch (error) {
        console.error("Error cargando los puntos del mapa:", error);
    }
}

// Ejecutar la carga al iniciar
cargarPuntos();