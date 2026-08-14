# Mapa de Agentes — Fuerteventura Protagonista

Mapa interactivo (Mapbox GL) de las entidades y servicios comunitarios de
Fuerteventura recogidos en el formulario "Mapa de agentes". Se incrusta
mediante `<iframe>` en una página en blanco de WordPress, igual que el
"Mapa de agentes" de [Canarias Convive](https://canariasconvive.com/mapa-interactivo/)
(mismo tema Divi/echeide-child) — de hecho `index.html` está adaptado
directamente de ese mismo visor, con la paleta y los datos propios de
Fuerteventura Protagonista.

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
entities.geojson
        │
        ▼
index.html  (servido por GitHub Pages)
        │
        ▼
<iframe> en la página en blanco de WordPress
```

El geocoding y la normalización de municipios **ya los hace el Apps
Script del Sheet**, no nuestro pipeline — así que la Action de este repo
no necesita ninguna credencial de Mapbox ni de Google: el Sheet migrado
es de solo lectura para cualquiera con el enlace, y solo hace falta
descargarlo como CSV.

### Columnas del Sheet → propiedades de entities.geojson
`scripts/sync_sheet.py` lee el Sheet migrado por posición de columna
(`COL` en el propio script) y las traduce a los nombres que espera
`index.html`:

| Columna del Sheet | Propiedad en el geojson |
|---|---|
| Nombre | `name` |
| Tipología | `sector` (única categoría disponible — alimenta color y el filtro "Tipología") |
| Municipio | `municipality` |
| Provincia | `province` |
| Isla | `island` |
| Dirección | `address` |
| Latitud, Longitud | `geometry.coordinates` |
| Teléfonos | `phones` (array) |
| Emails | `emails` (array) |
| Web | `url` |

`index.html` también sabe leer `protagonist`, `facebook`, `instagram`,
`twitter` y `logo`, heredados de la plantilla de Canarias Convive, pero
el Sheet de Fuerteventura no tiene esas columnas — se quedan vacíos y
esas secciones simplemente no se muestran.

Si el Apps Script cambia el orden de columnas, actualizar los índices en
`COL`. Filas sin coordenadas válidas o con coordenadas fuera de
Fuerteventura se descartan con un aviso (`::warning::`) en el log de la
Action.

## El único token que hace falta: Mapbox público (para pintar el mapa)

| Token | Tipo | Dónde vive | Para qué |
|---|---|---|---|
| Público (`pk.xxx`) | restringido por dominio (URL) | `index.html` → `mapboxgl.accessToken`, visible en el navegador | Pintar el mapa en el navegador del visitante |

No hace falta ningún token secreto: el geocoding ya está hecho por el
Apps Script, así que esta Action no llama a ninguna API de pago.

**Nota sobre el escáner de secretos de GitHub:** cualquier token de
Mapbox con este formato (aunque sea público, `pk.`) puede aparecer
etiquetado como "Mapbox Secret Access Token" al hacer `git push` —
comprobado que es un falso positivo del escáner, no un problema real
del token. Si bloquea el push, usar el enlace "allow secret" que ofrece
el propio error.

## Puesta en marcha

### 1. Mapbox — un único token público
1. [account.mapbox.com/access-tokens](https://account.mapbox.com/access-tokens/) → **Create a token**, dentro de la cuenta compartida `canarias-convive`.
2. No tocar la sección "Secret scopes" (déjala colapsada) — solo así se genera un token realmente público.
3. En "URL restrictions" añadir (sin `/*`, solo el dominio): `fuerteventuraprotagonista.com` y `proyectoscomunitarios.github.io`.
4. Pegarlo en `index.html` → `mapboxgl.accessToken`.

### 2. GitHub — variables del repo
`Settings → Secrets and variables → Actions → Variables` (ya configuradas):
- `SHEET_ID` = `1m1UVzUPzZdOBWmSFShpe8835YpWmHdWXnVtW7531tUY`
- `SHEET_GID` = `1122673843`

### 3. GitHub Pages
Ya activado sobre `main` / `(root)`, con `index.html` como entrada directa
(hay un `.nojekyll` para que Pages sirva los archivos tal cual, sin pasar
por el build de Jekyll). Visor en producción:
`https://proyectoscomunitarios.github.io/fuerteventura-mapa-agentes/`

### 4. WordPress
Ver [`wordpress-embed.html`](wordpress-embed.html): página nueva con
**plantilla en blanco** (sin header/footer), módulo de código de Divi con
ese `<iframe>` apuntando a la URL de GitHub Pages, enlazada desde el menú
("Mapa de agentes", junto a Inicio / El proyecto / Formaciones / Noticias).

## Estructura

```
index.html                       # Visor (HTML+CSS+JS, sin build) — entrada directa de GitHub Pages
styles.css                       # Estilos del visor
entities.geojson                 # Datos — los regenera la Action, NO editar a mano
scripts/sync_sheet.py            # Sheet migrado (CSV público) → entities.geojson
scripts/requirements.txt
.github/workflows/sync-sheet.yml # Sync diaria
wordpress-embed.html             # Snippet de iframe para pegar en WordPress
.nojekyll                        # Sirve los archivos tal cual en GitHub Pages
```

## Probarlo en local

```bash
python3 -m http.server 8000
# abrir http://localhost:8000/
```

En `localhost` el propio `index.html` detecta que no está en producción
y usa un mapa base de OpenStreetMap en vez de Mapbox (`USE_LOCAL_BASEMAP`),
así que se puede probar sin gastar cuota de Mapbox ni pelear con
restricciones de dominio. Añadir `?mapbox` a la URL fuerza el estilo de
Mapbox también en local.

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
