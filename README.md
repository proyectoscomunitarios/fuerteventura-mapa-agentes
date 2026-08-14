# Mapa de Agentes — Fuerteventura Protagonista

Mapa interactivo (Mapbox GL) de las entidades y servicios comunitarios de
Fuerteventura recogidos en el formulario "Mapa de agentes". Se incrusta
mediante `<iframe>` en una página en blanco de WordPress, igual que el
"Mapa de agentes" de [Canarias Convive](https://canariasconvive.com/mapa-interactivo/)
(mismo tema Divi/echeide-child), pero con datos, estilo y token propios de
esta isla.

## Datos siempre al día (sin tocar código)

```
Google Sheet "Mapa de agentes (respuestas)"     ← formulario, respuestas en bruto
        │
        ▼  Apps Script "Fuerteventura Protagonista" (cada noche ~03:00)
        │   - geocodifica cada dirección
        │   - normaliza Municipio a los 6 oficiales
        ▼
Google Sheet "TEST - Fuerteventura Protagonista" ← ya con Latitud/Longitud
        │  (público solo lectura por enlace)
        │
        ▼  GitHub Actions (.github/workflows/sync-sheet.yml, diario 04:30 UTC)
        │   scripts/sync_sheet.py: descarga el CSV, valida que las
        │   coordenadas caen dentro de Fuerteventura, descarta el resto
        ▼
empresas.geojson
        │
        ▼
mapa.html  (servido por GitHub Pages)
        │
        ▼
<iframe> en la página en blanco de WordPress
```

El geocoding y la normalización de municipios **ya los hace el Apps
Script del Sheet**, no nuestro pipeline — así que la Action de este repo
no necesita ninguna credencial de Mapbox ni de Google: el Sheet migrado
es de solo lectura para cualquiera con el enlace, y solo hace falta
descargarlo como CSV.

### Columnas que usa el script (por posición, ver `scripts/sync_sheet.py::COL`)
`ID, Nombre, Tipología, Municipio, Provincia, Isla, Dirección, Latitud,
Longitud, Teléfonos, Emails, Web, Descripción, Periodo`. Si el Apps
Script cambia el orden de columnas, actualizar los índices en `COL`.

Filas sin coordenadas válidas o con coordenadas fuera de Fuerteventura se
descartan con un aviso (`::warning::`) en el log de la Action — por
ejemplo, una entidad con sede fuera de la isla no debe aparecer en este
mapa aunque esté en el Sheet.

## El único token que hace falta: Mapbox público (para pintar el mapa)

| Token | Tipo | Dónde vive | Para qué |
|---|---|---|---|
| Público (`pk.xxx`) | restringido por dominio (URL) | `mapa.html` → `CONFIG.MAPBOX_TOKEN`, visible en el navegador | Pintar el mapa en el navegador del visitante |

No hace falta ningún token secreto: el geocoding ya está hecho por el
Apps Script, así que esta Action no llama a ninguna API de pago.

## Puesta en marcha

### 1. Mapbox — un único token público
1. [account.mapbox.com/access-tokens](https://account.mapbox.com/access-tokens/) → **Create a token**.
2. Scopes públicos por defecto → en "URL restrictions" añadir `fuerteventuraprotagonista.com/*` y `proyectoscomunitarios.github.io/*`.
3. Pegarlo en `mapa.html` → `CONFIG.MAPBOX_TOKEN`.
4. (Opcional) estilo propio en Mapbox Studio con la paleta de Fuerteventura Protagonista → su URL en `CONFIG.MAP_STYLE`.

### 2. GitHub — variables del repo
`Settings → Secrets and variables → Actions → Variables` (ya configuradas):
- `SHEET_ID` = `1m1UVzUPzZdOBWmSFShpe8835YpWmHdWXnVtW7531tUY`
- `SHEET_GID` = `1122673843`

Si en algún momento se creó el secret `MAPBOX_GEOCODING_TOKEN` de una
versión anterior de este pipeline, ya no se usa — se puede borrar.

### 3. GitHub Pages
Ya activado sobre `main` / `(root)`. Visor en producción:
`https://proyectoscomunitarios.github.io/fuerteventura-mapa-agentes/mapa.html`

### 4. WordPress
Ver [`wordpress-embed.html`](wordpress-embed.html): página nueva con
**plantilla en blanco** (sin header/footer), módulo de código de Divi con
ese `<iframe>` apuntando a la URL de GitHub Pages, enlazada desde el menú
("Mapa de agentes", junto a Inicio / El proyecto / Formaciones / Noticias).

## Estructura

```
mapa.html                        # Visor self-contained (HTML+CSS+JS, sin build)
empresas.geojson                 # Datos — los regenera la Action, NO editar a mano
scripts/sync_sheet.py            # Sheet migrado (CSV público) → empresas.geojson
scripts/requirements.txt
.github/workflows/sync-sheet.yml # Sync diaria
wordpress-embed.html             # Snippet de iframe para pegar en WordPress
```

## Probarlo en local

```bash
python3 -m http.server 8000
# abrir http://localhost:8000/mapa.html
```

Con el token placeholder de `mapa.html` el mapa no carga (401) pero la
búsqueda, el filtro y las tarjetas de la barra lateral funcionan igual
porque leen directamente `empresas.geojson`.

Para probar la sincronización sin esperar a la Action:

```bash
export SHEET_ID=1m1UVzUPzZdOBWmSFShpe8835YpWmHdWXnVtW7531tUY
export SHEET_GID=1122673843
python3 scripts/sync_sheet.py
```

## Por qué GitHub y no solo WordPress

- **GitHub Pages**: hosting estático gratuito para el visor — no ocupa espacio ni PHP del hosting de WordPress.
- **GitHub Actions**: automatiza el último paso (Sheet migrado → geojson). El geocoding en sí ya lo resuelve el Apps Script del equipo.

WordPress solo aloja la página que enmarca el mapa con un `<iframe>`; no
necesita ningún plugin de Mapbox.
