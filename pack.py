#!/usr/bin/env python3
"""
pack.py - Reconstruit un .docx a partir d'un dossier deballe par unpack.py.
Etape finale : packaging du manuscrit corrige.

Usage :
    python pack.py <dossier_deballe> <sortie.docx>

Respecte l'ordre ZIP attendu par Word : [Content_Types].xml en premier, sans compression
excessive des parties critiques. Utilise un ZIP DEFLATE standard, accepte par Word.
"""
import sys
import os
import zipfile


def pack(src_dir: str, out_docx: str) -> None:
    if not os.path.isdir(src_dir):
        sys.exit(f"[pack] Dossier introuvable : {src_dir}")

    # Collecte de toutes les parties
    parts = []
    for root, _, files in os.walk(src_dir):
        for name in files:
            full = os.path.join(root, name)
            arc = os.path.relpath(full, src_dir).replace(os.sep, "/")
            parts.append((arc, full))

    # [Content_Types].xml doit venir en premier
    parts.sort(key=lambda p: (p[0] != "[Content_Types].xml", p[0]))

    if os.path.exists(out_docx):
        os.remove(out_docx)

    with zipfile.ZipFile(out_docx, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, full in parts:
            z.write(full, arc)

    print(f"[pack] Ecrit : {out_docx} ({len(parts)} parties)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage : python pack.py <dossier_deballe> <sortie.docx>")
    pack(sys.argv[1], sys.argv[2])
