#!/usr/bin/env python3
"""
audit.py - Audit final automatise (etape 8 du workflow v5.2).
Analyse word/document.xml et word/footnotes.xml d'un manuscrit DEBALLE et
retourne le nombre de problemes residuels. Objectif : ZERO avant livraison.

Usage :
    python audit.py <dossier_deballe>

Code de sortie : 0 si aucun probleme, 1 sinon. Affiche le detail par categorie.

Controles :
  1. Espace normale avant ponctuation double (? ! ; :) au lieu d'insecable
  2. Tiret de dialogue colle au mot (--Bonjour / -Bonjour)
  3. Virgule sans espace apres (mot,mot)
  4. Doubles espaces
  5. Apostrophes droites (') au lieu de typographiques
  6. Glyphes parasites Symbol U+F020-U+F0FF
  7. Ellipse suivie immediatement d'une lettre (mot...mot)
"""
import sys
import os
import re

NBSP = "\u00A0"           # espace insecable
NNBSP = "\u202F"          # espace fine insecable
APO_TYPO = "\u2019"       # apostrophe typographique
ELLIPSIS = "\u2026"       # points de suspension
PRIVATE_USE = re.compile("[\uF020-\uF0FF]")


def get_text_runs(xml: str):
    """Extrait le contenu textuel des balises <w:t>...</w:t>."""
    return re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, flags=re.DOTALL)


def audit_xml(xml: str, label: str):
    problems = {}
    runs = get_text_runs(xml)
    joined = "".join(runs)

    # 1. Ponctuation double precedee d'une espace normale (ni insecable ni fine)
    bad_punct = re.findall(r"[^\s" + NBSP + NNBSP + r"][ ]([?!;:])", joined)
    if bad_punct:
        problems["Espace normale avant ? ! ; :"] = len(bad_punct)

    # 2. Tiret de dialogue colle
    dash_glued = re.findall(r"(?:^|>)[\s]*[—–-]{1,2}(?=\w)", joined)
    if dash_glued:
        problems["Tiret de dialogue colle au mot"] = len(dash_glued)

    # 3. Virgule sans espace apres
    comma = re.findall(r",(?=[A-Za-zA-ÿŒœ])", joined)
    if comma:
        problems["Virgule sans espace apres"] = len(comma)

    # 4. Doubles espaces
    dbl = re.findall(r"  +", joined)
    if dbl:
        problems["Doubles espaces"] = len(dbl)

    # 5. Apostrophes droites
    apo = joined.count("'")
    if apo:
        problems["Apostrophes droites (')"] = apo

    # 6. Glyphes parasites
    priv = len(PRIVATE_USE.findall(xml))
    if priv:
        problems["Glyphes parasites Symbol"] = priv

    # 7. Ellipse suivie d'une lettre
    ell = re.findall(ELLIPSIS + r"(?=[A-Za-zÀ-ÿ])", joined)
    if ell:
        problems["Ellipse sans espace apres"] = len(ell)

    return problems


def main(work_dir: str) -> int:
    targets = ["word/document.xml", "word/footnotes.xml", "word/endnotes.xml"]
    total = 0
    print("=== AUDIT FINAL (etape 8) ===")
    for rel in targets:
        p = os.path.join(work_dir, rel)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as f:
            xml = f.read()
        problems = audit_xml(xml, rel)
        if problems:
            print(f"\n[{rel}]")
            for k, v in problems.items():
                print(f"  - {k} : {v}")
                total += v
        else:
            print(f"\n[{rel}] OK - aucun probleme")

    print("\n-----------------------------")
    print(f"TOTAL PROBLEMES RESIDUELS : {total}")
    print("LIVRAISON AUTORISEE" if total == 0 else "NE PAS LIVRER - corriger puis relancer")
    print("=============================")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage : python audit.py <dossier_deballe>")
    sys.exit(main(sys.argv[1]))
