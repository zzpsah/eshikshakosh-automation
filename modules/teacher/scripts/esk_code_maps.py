#!/usr/bin/env python3
"""Code -> label maps for e-ShikshaKosh list exports.

The teacher-list API returns numeric codes for some fields (for example
`appointedSubject: 46`) and no label. The portal exposes no subject master endpoint, so
the labels are learned from the portal's own service-history records, which carry both
`appointedSubjectId` and the readable `appointedSubject`.

Maps are stored in `esk_code_maps.json` next to this file. Learned once, reused by every
list export; a code that is not in the map is left unchanged rather than guessed.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAP_FILE = ROOT / 'esk_code_maps.json'

# section name -> (code key, label key) inside a service-history record
SERVICE_SUBJECT_KEYS = ('appointedSubjectId', 'appointedSubject')


def load() -> dict:
    try:
        data = json.loads(MAP_FILE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save(maps: dict) -> None:
    MAP_FILE.write_text(json.dumps(maps, indent=2, ensure_ascii=False, sort_keys=True), encoding='utf-8')


def learn_from_service_history(records) -> dict:
    """Return {code: label} pairs found in service-history records."""
    code_key, label_key = SERVICE_SUBJECT_KEYS
    learned = {}
    for rec in records if isinstance(records, list) else []:
        if not isinstance(rec, dict):
            continue
        code = rec.get(code_key)
        label = rec.get(label_key)
        if code in (None, '', 0) or not label:
            continue
        learned[str(code)] = str(label)
    return learned


def merge(maps: dict, section: str, learned: dict) -> dict:
    if not learned:
        return maps
    section_map = dict(maps.get(section) or {})
    section_map.update({str(k): v for k, v in learned.items()})
    maps[section] = section_map
    return maps


def apply_to_workbook(path: str, column_header: str, code_map: dict) -> int:
    """Rewrite one column of a workbook, replacing codes with labels. Returns replacements."""
    if not code_map:
        return 0
    import openpyxl

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    headers = {cell.value: idx for idx, cell in enumerate(ws[1], start=1) if cell.value}
    col = headers.get(column_header)
    if not col:
        wb.close()
        return 0
    replaced = 0
    for row in range(2, ws.max_row + 1):
        cell = ws.cell(row=row, column=col)
        key = str(cell.value).strip() if cell.value is not None else ''
        if key in code_map:
            cell.value = code_map[key]
            replaced += 1
    wb.save(path)
    wb.close()
    return replaced


def subject_map() -> dict:
    return {str(k): v for k, v in (load().get('appointedSubject') or {}).items()}
