#!/usr/bin/env python3
"""
systemeio.py - Integration systeme.io via son API HTTP (port 443, non bloque par Render).

Sert a :
  - creer / retrouver un contact (le prospect),
  - lui poser une etiquette (tag) pour declencher une automatisation,
  - (best effort) enregistrer le lien du rapport dans un champ personnalise.

Variables d'environnement :
  SYSTEMEIO_API_KEY     (obligatoire)
  SYSTEMEIO_TAG_NEW     (optionnel) id du tag "nouveau lead" a poser a la capture
  SYSTEMEIO_TAG_READY   (optionnel) id du tag "rapport pret" a poser quand le rapport est pret
  SYSTEMEIO_FIELD_SLUG  (optionnel) slug du champ perso ou stocker le lien (defaut: lien_rapport)
"""
import os
import json
import urllib.request
import urllib.error
import urllib.parse

BASE = "https://api.systeme.io/api"


def _req(method, path, payload=None):
    key = os.environ["SYSTEMEIO_API_KEY"]
    url = BASE + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-API-Key", key)
    req.add_header("accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode(errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def get_contact_id(email):
    status, body = _req("GET", f"/contacts?email={urllib.parse.quote(email)}")
    try:
        items = json.loads(body).get("items", [])
        if items:
            return items[0].get("id")
    except Exception:
        pass
    return None


def create_or_get_contact(email, name=""):
    """Cree le contact (ou le recupere s'il existe). Renvoie (contact_id, debug_str)."""
    fields = []
    if name:
        fields.append({"slug": "first_name", "value": name})
    status, body = _req("POST", "/contacts", {"email": email, "fields": fields})
    debug = f"POST /contacts -> {status}: {body[:300]}"
    if status in (200, 201):
        try:
            return json.loads(body).get("id"), debug
        except Exception:
            pass
    # Existe deja (souvent 422) -> on le recupere
    cid = get_contact_id(email)
    return cid, debug + f" | lookup id={cid}"


def add_tag(contact_id, tag_id):
    status, body = _req("POST", f"/contacts/{contact_id}/tags", {"tagId": int(tag_id)})
    return f"add_tag {tag_id} -> {status}: {body[:200]}"


def set_field(contact_id, slug, value):
    """Best effort : enregistre une valeur dans un champ perso du contact."""
    status, body = _req("PATCH", f"/contacts/{contact_id}",
                        {"fields": [{"slug": slug, "value": value}]})
    return f"set_field {slug} -> {status}: {body[:200]}"


def push_lead(email, name="", report_link=None):
    """Capture/maj d'un lead. Renvoie un texte de debug (a logguer)."""
    logs = []
    cid, dbg = create_or_get_contact(email, name)
    logs.append(dbg)
    if not cid:
        return "ECHEC creation contact. " + " | ".join(logs)
    tag_new = os.environ.get("SYSTEMEIO_TAG_NEW")
    if tag_new:
        logs.append(add_tag(cid, tag_new))
    if report_link:
        slug = os.environ.get("SYSTEMEIO_FIELD_SLUG", "lien_rapport")
        logs.append(set_field(cid, slug, report_link))
        tag_ready = os.environ.get("SYSTEMEIO_TAG_READY")
        if tag_ready:
            logs.append(add_tag(cid, tag_ready))
    return f"contact_id={cid} | " + " | ".join(logs)


if __name__ == "__main__":
    import sys
    print(push_lead(sys.argv[1] if len(sys.argv) > 1 else "test@exemple.fr", "Test"))
