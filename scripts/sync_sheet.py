#!/usr/bin/env python3
"""Regenera empresas.geojson a partir del Google Sheet público de respuestas
del formulario "Mapa de agentes" y geolocaliza cada dirección con la API de
Geocoding de Mapbox.

El Sheet es de solo lectura para cualquiera con el enlace, así que no hace
falta cuenta de servicio de Google: se descarga como CSV público.

Uso local:
    export SHEET_ID=1vw2hiJVlsvFbPRhmPKPevJe74nA5MPk1U_cWzfbuoU8
    export SHEET_GID=318064612
    export MAPBOX_GEOCODING_TOKEN=sk.xxx   # token SECRETO, scope "Geocoding: Read" únicamente
    python3 scripts/sync_sheet.py
"""
import csv
import io
import json
import os
import re
import sys
import time
import unicodedata
from urllib.parse import quote

import requests

# Columnas del Sheet (por posición, porque el encabezado repite el nombre
# "Política de protección de datos" dos veces y csv.DictReader perdería la
# primera). Actualizar estos índices si cambia el formulario.
COL = {
    "nombre": 2,
    "categoria": 3,       # "Tipología": Servicios / Proyecto / Programa / Plan
    "programa": 4,        # Nombre del Programa, Proyecto o Servicio
    "periodo": 5,
    "municipio": 6,
    "direccion": 7,
    "telefono": 8,
    "email": 9,
    "descripcion": 10,
    "consentimiento_1": 19,
    "consentimiento_2": 21,
}
CONSENT_OK = "si doy mi consentimiento"

# Fuerteventura + margen. El mapa es SOLO de esta isla.
FUERTEVENTURA_BOUNDS = {"lat": (27.9, 28.9), "lng": (-14.75, -13.6)}

CACHE_PATH = os.path.join(os.path.dirname(__file__), "geocode-cache.json")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "empresas.geojson")


def normalize_key(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def cell(row, name):
    i = COL[name]
    return row[i].strip() if i < len(row) and row[i] else ""


def fetch_csv_rows(sheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    if resp.text.lstrip().startswith("<"):
        print("::error::La respuesta no es un CSV (¿el Sheet dejó de ser público?).")
        sys.exit(1)
    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    return rows[0], rows[1:]  # header, data rows


def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def in_fuerteventura(lat, lng):
    return (FUERTEVENTURA_BOUNDS["lat"][0] <= lat <= FUERTEVENTURA_BOUNDS["lat"][1]
            and FUERTEVENTURA_BOUNDS["lng"][0] <= lng <= FUERTEVENTURA_BOUNDS["lng"][1])


def geocode(direccion, municipio, token, cache, stats):
    query = f"{direccion}, {municipio}, Fuerteventura, Canarias, España"
    key = normalize_key(query)
    if key in cache:
        stats["cache_hits"] += 1
        return cache[key]

    stats["api_calls"] += 1
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{quote(query)}.json"
    resp = requests.get(url, params={
        "access_token": token,
        "country": "es",
        "bbox": "-14.75,27.9,-13.6,28.9",
        "limit": 1,
        "language": "es",
    }, timeout=15)
    time.sleep(0.15)  # cortesía, muy por debajo del límite de Mapbox (600 req/min)

    if resp.status_code != 200:
        print(f"::warning::Geocoding API devolvió {resp.status_code} para '{query}'.")
        cache[key] = None
        return None

    features = resp.json().get("features", [])
    if not features:
        cache[key] = None
        return None

    lng, lat = features[0]["center"]
    result = {"lat": lat, "lng": lng, "place_name": features[0].get("place_name", "")}
    cache[key] = result
    return result


def rows_to_features(header, rows, token, cache, stats):
    features = []
    warnings = []
    for row_num, row in enumerate(rows, start=2):
        nombre = cell(row, "nombre")
        if not nombre:
            continue

        c1 = normalize_key(cell(row, "consentimiento_1"))
        c2 = normalize_key(cell(row, "consentimiento_2"))
        if CONSENT_OK not in c1 or CONSENT_OK not in c2:
            warnings.append(f"Fila {row_num} ({nombre}): sin consentimiento de protección de datos, se omite.")
            continue

        direccion = cell(row, "direccion")
        municipio = cell(row, "municipio")
        if not direccion:
            warnings.append(f"Fila {row_num} ({nombre}): sin dirección, se omite.")
            continue

        geo = geocode(direccion, municipio, token, cache, stats)
        if geo is None:
            warnings.append(f"Fila {row_num} ({nombre}): no se pudo geolocalizar '{direccion}, {municipio}'.")
            continue
        if not in_fuerteventura(geo["lat"], geo["lng"]):
            warnings.append(f"Fila {row_num} ({nombre}): geolocalizado fuera de Fuerteventura ({geo['lat']}, {geo['lng']}), se omite.")
            continue

        props = {
            "id": normalize_key(f"{nombre}-{cell(row, 'direccion')}")[:80],
            "nombre": nombre,
            "categoria": cell(row, "categoria") or "Sin clasificar",
            "programa": cell(row, "programa"),
            "periodo": cell(row, "periodo"),
            "municipio": municipio,
            "direccion": direccion,
            "telefono": cell(row, "telefono"),
            "email": cell(row, "email"),
            "descripcion": cell(row, "descripcion"),
        }
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "Point", "coordinates": [geo["lng"], geo["lat"]]},
        })

    for w in warnings:
        print(f"::warning::{w}")
    return features, warnings


def main():
    sheet_id = os.environ.get("SHEET_ID")
    gid = os.environ.get("SHEET_GID")
    token = os.environ.get("MAPBOX_GEOCODING_TOKEN")
    if not sheet_id or not gid:
        print("::error::Faltan SHEET_ID y/o SHEET_GID.")
        sys.exit(1)
    if not token:
        print("::error::Falta MAPBOX_GEOCODING_TOKEN (token secreto sk.xxx, scope Geocoding: Read).")
        sys.exit(1)

    header, rows = fetch_csv_rows(sheet_id, gid)
    cache = load_cache()
    stats = {"cache_hits": 0, "api_calls": 0}

    features, warnings = rows_to_features(header, rows, token, cache, stats)
    save_cache(cache)

    geojson = {
        "type": "FeatureCollection",
        "metadata": {"source": "google-sheet", "sheet_id": sheet_id, "row_count": len(rows)},
        "features": features,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"Filas leídas: {len(rows)}. Puntos publicados: {len(features)}. Avisos: {len(warnings)}.")
    print(f"Geocoding — cache: {stats['cache_hits']}, llamadas nuevas a la API: {stats['api_calls']}.")
    print(f"Escrito {OUT_PATH}")


if __name__ == "__main__":
    main()
