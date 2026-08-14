#!/usr/bin/env python3
"""Regenera empresas.geojson a partir del Google Sheet YA MIGRADO (con
Latitud/Longitud y Municipio normalizado), que a su vez se genera cada
noche por el Apps Script "Fuerteventura Protagonista" a partir de las
respuestas del formulario.

Ese Sheet es de solo lectura para cualquiera con el enlace, así que no
hace falta ninguna credencial: se descarga como CSV público.

Uso local:
    export SHEET_ID=1m1UVzUPzZdOBWmSFShpe8835YpWmHdWXnVtW7531tUY
    export SHEET_GID=1122673843
    python3 scripts/sync_sheet.py
"""
import csv
import io
import json
import os
import re
import sys

import requests

# Columnas del Sheet migrado (por posición — más robusto que por nombre,
# porque los acentos del encabezado dan problemas de encoding en algunos
# entornos). Actualizar estos índices si el Apps Script cambia el formato.
COL = {
    "id": 0,
    "nombre": 1,
    "categoria": 2,     # Tipología
    "municipio": 3,
    "provincia": 4,
    "isla": 5,
    "direccion": 6,
    "lat": 7,
    "lng": 8,
    "telefono": 9,
    "email": 10,
    "web": 11,
    "descripcion": 12,
    "periodo": 13,
}

# Fuerteventura + margen. El mapa es SOLO de esta isla, aunque el Sheet
# pueda incluir en el futuro alguna entidad con sede en otra isla.
FUERTEVENTURA_BOUNDS = {"lat": (27.9, 28.9), "lng": (-14.75, -13.6)}

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "empresas.geojson")


def cell(row, name):
    i = COL[name]
    return row[i].strip() if i < len(row) and row[i] else ""


def parse_coord(raw):
    """Tolera coma decimal (es-ES, como llega del Sheet: '28,7388871')."""
    s = str(raw).strip()
    if not s:
        return None
    try:
        v = float(s.replace(",", "."))
    except ValueError:
        return None
    return v if -180 <= v <= 180 else None


def in_fuerteventura(lat, lng):
    return (FUERTEVENTURA_BOUNDS["lat"][0] <= lat <= FUERTEVENTURA_BOUNDS["lat"][1]
            and FUERTEVENTURA_BOUNDS["lng"][0] <= lng <= FUERTEVENTURA_BOUNDS["lng"][1])


def fetch_csv_rows(sheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    if resp.text.lstrip().startswith("<"):
        print("::error::La respuesta no es un CSV (¿el Sheet dejó de ser público?).")
        sys.exit(1)
    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    return rows[0], rows[1:]


def rows_to_features(rows):
    features = []
    warnings = []
    seen_ids = set()

    for row_num, row in enumerate(rows, start=2):
        nombre = cell(row, "nombre")
        if not nombre:
            continue

        lat = parse_coord(cell(row, "lat"))
        lng = parse_coord(cell(row, "lng"))
        if lat is None or lng is None:
            warnings.append(f"Fila {row_num} ({nombre}): coordenadas vacías o ilegibles, se omite.")
            continue
        if not in_fuerteventura(lat, lng):
            warnings.append(f"Fila {row_num} ({nombre}): coordenada fuera de Fuerteventura ({lat}, {lng}), se omite.")
            continue

        entity_id = cell(row, "id") or f"row-{row_num}"
        if entity_id in seen_ids:
            warnings.append(f"Fila {row_num} ({nombre}): ID duplicado '{entity_id}', se omite.")
            continue
        seen_ids.add(entity_id)

        props = {
            "id": entity_id,
            "nombre": nombre,
            "categoria": cell(row, "categoria") or "Sin clasificar",
            "municipio": cell(row, "municipio"),
            "direccion": cell(row, "direccion"),
            "telefono": cell(row, "telefono"),
            "email": cell(row, "email"),
            "web": cell(row, "web"),
            "descripcion": cell(row, "descripcion"),
            "periodo": cell(row, "periodo"),
        }
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
        })

    for w in warnings:
        print(f"::warning::{w}")
    return features, warnings


def main():
    sheet_id = os.environ.get("SHEET_ID")
    gid = os.environ.get("SHEET_GID")
    if not sheet_id or not gid:
        print("::error::Faltan SHEET_ID y/o SHEET_GID.")
        sys.exit(1)

    header, rows = fetch_csv_rows(sheet_id, gid)
    features, warnings = rows_to_features(rows)

    geojson = {
        "type": "FeatureCollection",
        "metadata": {"source": "google-sheet-migrado", "sheet_id": sheet_id, "row_count": len(rows)},
        "features": features,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"Filas leídas: {len(rows)}. Puntos publicados: {len(features)}. Avisos: {len(warnings)}.")
    print(f"Escrito {OUT_PATH}")


if __name__ == "__main__":
    main()
