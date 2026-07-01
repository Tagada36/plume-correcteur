#!/usr/bin/env python3
"""
unpack.py - Deballe un .docx (archive ZIP) dans un dossier de travail.
Etape 1 du workflow v5.2 : inventaire initial.

Usage :
    python unpack.py <manuscrit.docx> <dossier_sortie>

Affiche un inventaire : nombre de fichiers XML, presence de footnotes/endnotes/styles,
nombre de <w:footnote>, nombre de sections (sectPr), et reperage des glyphes parasites
Symbol (U+F020-U+F0FF).
"""
import sys
import os
import zipfile
import re
import glob

PRIVATE_USE = re.compile("[\uF020-\uF0FF]")


def unpack(docx_path: str, out_dir: str) -> None:
    if not os.path.isfile(docx_path):
        sys.exit(f"[unpack] Fichier introuvable : {docx_path}")

    os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(docx_path) as z:
        z.extractall(out_dir)

    xml_files = glob.glob(os.path.join(out_dir, "**", "*.xml"), recursive=True)
    xml_files += glob.glob(os.path.join(out_dir, "**", "*.rels"), recursive=True)

    print("=== INVENTAIRE INITIAL (etape 1) ===")
    print(f"Dossier de travail : {out_dir}")
    print(f"Nombre de fichiers XML/rels : {len(xml_files)}")

    for name in ("word/footnotes.xml", "word/endnotes.xml", "word/styles.xml",
                 "word/document.xml"):
        present = os.path.isfile(os.path.join(out_dir, name))
        print(f"  {'OK ' if present else '-- '} {name}")

    # Compter les notes de bas de page reelles (hors separateurs)
    fn_path = os.path.join(out_dir, "word/footnotes.xml")
    if os.path.isfile(fn_path):
        with open(fn_path, encoding="utf-8") as f:
            fn = f.read()
        total = len(re.findall(r"<w:footnote\b", fn))
        special = len(re.findall(r'<w:footnote\b[^>]*w:type=', fn))
        real = total - special
        print(f"Notes de bas de page (reference) : {real} "
              f"(total balises : {total}, dont {special} separateurs)")

    # Sections
    doc_path = os.path.join(out_dir, "word/document.xml")
    if os.path.isfile(doc_path):
        with open(doc_path, encoding="utf-8") as f:
            doc = f.read()
        n_sect = len(re.findall(r"<w:sectPr\b", doc))
        print(f"Sections (sectPr) : {n_sect}")

    # Styles
    st_path = os.path.join(out_dir, "word/styles.xml")
    if os.path.isfile(st_path):
        with open(st_path, encoding="utf-8") as f:
            st = f.read()
        n_styles = len(re.findall(r"<w:style\b", st))
        print(f"Styles definis : {n_styles}")

    # Glyphes parasites zone privee Unicode (v5.1)
    hits = 0
    for name in ("word/document.xml", "word/footnotes.xml", "word/endnotes.xml"):
        p = os.path.join(out_dir, name)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                hits += len(PRIVATE_USE.findall(f.read()))
    print(f"Glyphes parasites Symbol (U+F020-U+F0FF) : {hits} "
          f"{'!! a supprimer' if hits else '(aucun)'}")
    print("=====================================")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage : python unpack.py <manuscrit.docx> <dossier_sortie>")
    unpack(sys.argv[1], sys.argv[2])
