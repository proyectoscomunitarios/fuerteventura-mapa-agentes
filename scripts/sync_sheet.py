#!/usr/bin/env python3
"""Regenera entities.geojson a partir del Google Sheet YA MIGRADO (con
Latitud/Longitud y Municipio normalizado), que a su vez se genera cada
noche por el Apps Script "Fuerteventura Protagonista" a partir de las
respuestas del formulario.

Ese Sheet es de solo lectura para cualquiera con el enlace, así que no
hace falta ninguna credencial: se descarga como CSV público.

Las propiedades de salida usan los nombres que espera index.html
(name, sector, municipality, province, island, address, phones, emails,
url) — "sector" es la columna Tipología del Sheet, "initiative" es el
nombre del Programa/Proyecto/Servicio (columna E) y "subjectType" es la
Tipología de Sujeto (columna W).

"Tipología de Sujeto" (columna W) y "Programa/Proyecto/Servicio" (columna
E, el nombre del supuesto que desarrolla la entidad) del Sheet de
respuestas del formulario NO pasan por el Apps Script de migración, así
que este script lee TAMBIÉN el Sheet de respuestas directamente (es
público igual que el migrado) y las cruza por nombre de entidad — sin
tocar el Apps Script ni depender de que alguien lo actualice. Funciona
igual para altas nuevas que para las que ya existen.

Uso local:
    export SHEET_ID=1m1UVzUPzZdOBWmSFShpe8835YpWmHdWXnVtW7531tUY
    export SHEET_GID=1122673843
    export FORM_SHEET_ID=1vw2hiJVlsvFbPRhmPKPevJe74nA5MPk1U_cWzfbuoU8
    export FORM_SHEET_GID=318064612
    python3 scripts/sync_sheet.py
"""
import csv
import io
import json
import os
import re
import sys
import unicodedata

import requests

# Columnas del Sheet migrado (por posición — más robusto que por nombre,
# porque los acentos del encabezado dan problemas de encoding en algunos
# entornos). Actualizar estos índices si el Apps Script cambia el formato.
COL = {
    "id": 0,
    "nombre": 1,
    "tipologia": 2,
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

# Columnas del Sheet de respuestas del formulario (bruto, el de la jefa)
# que necesitamos aparte porque el Apps Script no las copia al migrado.
FORM_COL = {
    "nombre": 2,
    "supuesto": 4,
    "tipologia_sujeto": 22,
}

# Fuerteventura + margen. El mapa es SOLO de esta isla, aunque el Sheet
# pueda incluir en el futuro alguna entidad con sede en otra isla.
FUERTEVENTURA_BOUNDS = {"lat": (27.9, 28.9), "lng": (-14.75, -13.6)}

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "entities.geojson")


def cell(row, name):
    i = COL[name]
    return row[i].strip() if i < len(row) and row[i] else ""


def normalize_name(s):
    """Normaliza un nombre de entidad para cruzar entre los dos Sheets
    (sin acentos, sin dobles espacios, minusculas) -- tolera pequenas
    diferencias de tipeo entre el Sheet de respuestas y el migrado."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def fetch_form_extra(form_sheet_id, form_gid):
    """Nombre de entidad -> {subjectType, initiative}, leído directamente
    del Sheet de respuestas del formulario (columnas W y E, que el Apps
    Script de migración no copia al Sheet oficial)."""
    if not form_sheet_id or not form_gid:
        print("::warning::Faltan FORM_SHEET_ID/FORM_SHEET_GID, se omiten Tipología de Sujeto y Programa/Proyecto/Servicio.")
        return {}
    _, rows = fetch_csv_rows(form_sheet_id, form_gid)
    lookup = {}
    for row in rows:
        nombre = row[FORM_COL["nombre"]].strip() if len(row) > FORM_COL["nombre"] else ""
        if not nombre:
            continue
        tipo = row[FORM_COL["tipologia_sujeto"]].strip() if len(row) > FORM_COL["tipologia_sujeto"] else ""
        supuesto = row[FORM_COL["supuesto"]].strip() if len(row) > FORM_COL["supuesto"] else ""
        lookup[normalize_name(nombre)] = {"subjectType": tipo, "initiative": supuesto}
    return lookup


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
    # Google no manda charset en el Content-Type (text/csv a secas), asi que
    # requests cae a ISO-8859-1 por defecto y destroza los acentos/enies del
    # UTF-8 real. Decodificar los bytes crudos explicitamente como utf-8.
    text = resp.content.decode("utf-8")
    if text.lstrip().startswith("<"):
        print("::error::La respuesta no es un CSV (¿el Sheet dejó de ser público?).")
        sys.exit(1)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    return rows[0], rows[1:]


def rows_to_features(rows, form_extra=None):
    form_extra = form_extra or {}
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

        telefono = cell(row, "telefono")
        email = cell(row, "email")
        extra = form_extra.get(normalize_name(nombre), {})

        props = {
            "id": entity_id,
            "name": nombre,
            "sector": cell(row, "tipologia"),
            "subjectType": extra.get("subjectType", ""),
            "initiative": extra.get("initiative", ""),
            "municipality": cell(row, "municipio"),
            "province": cell(row, "provincia"),
            "island": cell(row, "isla"),
            "address": cell(row, "direccion"),
            "phones": [telefono] if telefono else [],
            "emails": [email] if email else [],
            "url": cell(row, "web"),
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

    form_sheet_id = os.environ.get("FORM_SHEET_ID")
    form_gid = os.environ.get("FORM_SHEET_GID")
    form_extra = fetch_form_extra(form_sheet_id, form_gid)

    header, rows = fetch_csv_rows(sheet_id, gid)
    features, warnings = rows_to_features(rows, form_extra)

    missing_subject = [f["properties"]["name"] for f in features if not f["properties"]["subjectType"]]
    if missing_subject:
        print(f"::warning::{len(missing_subject)} entidad(es) sin Tipología de Sujeto: {', '.join(missing_subject[:10])}"
              + (f" y {len(missing_subject) - 10} más." if len(missing_subject) > 10 else "."))

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
