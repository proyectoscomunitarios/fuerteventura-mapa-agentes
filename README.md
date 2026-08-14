# Mapa de Agentes — Fuerteventura Protagonista

Mapa interactivo (Mapbox GL) de las entidades y servicios comunitarios de
Fuerteventura recogidos en el formulario "Mapa de agentes". Se incrusta
mediante `<iframe>` en una página en blanco de WordPress, igual que el
"Mapa de agentes" de [Canarias Convive](https://canariasconvive.com/mapa-interactivo/)
(mismo tema Divi/echeide-child), pero con datos, estilo y token propios de
esta isla.

## Datos siempre al día (sin tocar código)

```
Google Sheet "Mapa de agentes (respuestas)"   ← formulario público, sin login
        │  cada hora
        ▼
GitHub Actions (.github/workflows/sync-sheet.yml)
        │  scripts/sync_sheet.py:
        │    1. descarga el Sheet como CSV público (sin credenciales)
        │    2. filtra filas sin consentimiento de protección de datos
        │    3. geolocaliza "Dirección + Municipio" con Mapbox Geocoding API
        │       (cache en scripts/geocode-cache.json para no repetir llamadas)
        ▼
empresas.geojson
        │
        ▼
mapa.html  (servido por GitHub Pages)
        │
        ▼
<iframe> en la página en blanco de WordPress
```

El Sheet original es de solo lectura para cualquiera con el enlace — por
eso no hace falta cuenta de servicio de Google ni OAuth, a diferencia del
mapa de Canarias Convive (ese Sheet sí es privado).

### Columnas que usa el script (por posición, ver `scripts/sync_sheet.py::COL`)
`Nombre de la entidad`, `Tipología`, `Nombre del Programa/Proyecto/Servicio`,
`Periodo de ejecución`, `Municipio`, `Dirección`, `Teléfono`, `Correo
electrónico`, `Descripción` y las dos columnas `Política de protección de
datos` (una fila solo se publica si ambas dicen "Si doy mi consentimiento").
Si el formulario cambia de orden de columnas, actualizar los índices en
`COL`.

## Dos tokens de Mapbox — no confundir

| Token | Tipo | Dónde vive | Para qué |
|---|---|---|---|
| Público (`pk.xxx`) | restringido por dominio (URL) | `mapa.html` → `CONFIG.MAPBOX_TOKEN`, visible en el navegador | Pintar el mapa en el navegador del visitante |
| Secreto (`sk.xxx`) | scope **Geocoding: Read** únicamente | Secret de GitHub Actions `MAPBOX_GEOCODING_TOKEN` | Geolocalizar direcciones desde la Action (llamada servidor-a-servidor) |

Ambos se crean en la **misma cuenta de Mapbox** que ya tenéis — no hace
falta una cuenta nueva, solo dos tokens separados y con permisos distintos
(el público nunca debe tener scopes de más; el secreto nunca debe pegarse
en el HTML).

## Puesta en marcha

### 1. Mapbox
1. [account.mapbox.com/access-tokens](https://account.mapbox.com/access-tokens/) → **Create a token**.
2. Token público → marcar solo scopes públicos por defecto → en "URL restrictions" añadir vuestro dominio y el de GitHub Pages → pegarlo en `mapa.html` (`CONFIG.MAPBOX_TOKEN`).
3. Otro token → desmarcar todo → activar solo **Geocoding: Read** (bajo "Secret scopes") → se genera como `sk.xxx`, cópialo una vez (no se puede volver a ver) → va como secret `MAPBOX_GEOCODING_TOKEN` en GitHub (paso 4).
4. (Opcional) estilo propio en Mapbox Studio con la paleta de Fuerteventura Protagonista → su URL en `CONFIG.MAP_STYLE`.

### 2. GitHub — variables y secretos del repo
`Settings → Secrets and variables → Actions`:
- **Variables**: `SHEET_ID` = `1vw2hiJVlsvFbPRhmPKPevJe74nA5MPk1U_cWzfbuoU8`, `SHEET_GID` = `318064612`.
- **Secrets**: `MAPBOX_GEOCODING_TOKEN` = el `sk.xxx` del paso anterior.

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
scripts/sync_sheet.py            # Sheet (CSV público) → geocoding → empresas.geojson
scripts/geocode-cache.json       # Cache de geocoding — SÍ se commitea (evita re-geocodificar)
scripts/requirements.txt
.github/workflows/sync-sheet.yml # Sync horaria
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
export SHEET_ID=1vw2hiJVlsvFbPRhmPKPevJe74nA5MPk1U_cWzfbuoU8
export SHEET_GID=318064612
export MAPBOX_GEOCODING_TOKEN=sk.xxx
python3 scripts/sync_sheet.py
```

## Por qué GitHub y no solo WordPress

- **GitHub Pages**: hosting estático gratuito para el visor — no ocupa espacio ni PHP del hosting de WordPress.
- **GitHub Actions**: automatiza Sheet → geocoding → geojson. Sin esto, cada alta habría que geolocalizarla y subirla a mano.

WordPress solo aloja la página que enmarca el mapa con un `<iframe>`; no
necesita ningún plugin de Mapbox.
