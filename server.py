#!/usr/bin/env python3
"""server.py - Plume (FastAPI) - LEAD MAGNET via systeme.io (a plat)."""
import os
import csv
import uuid
import secrets
import threading
import pathlib
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

import agent
import systemeio

BASE = pathlib.Path(__file__).parent
# Dossier de donnees PERSISTANT (disque Render) si PLUME_DATA_DIR est defini,
# sinon on retombe sur le dossier local (ephemere).
DATA_DIR = pathlib.Path(os.environ.get("PLUME_DATA_DIR", str(BASE)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR = DATA_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
LEADS_CSV = DATA_DIR / "leads.csv"
ADMIN_TOKEN = os.environ.get("PLUME_ADMIN_TOKEN", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
MAX_MB = int(os.environ.get("PLUME_MAX_UPLOAD_MB", "25"))

app = FastAPI(title="Plume - Correcteur (systeme.io)")
JOBS = {}
LOCK = threading.Lock()


def save_lead(name, email, title, filename, consent):
    new_file = not LEADS_CSV.exists()
    with open(LEADS_CSV, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["date", "nom", "email", "titre_manuscrit", "fichier", "consentement_rgpd"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), name, email, title, filename, consent])


def _set(job_id, **kw):
    with LOCK:
        JOBS.setdefault(job_id, {}).update(kw)


def _log(job_id, msg):
    print(f"[JOB {job_id}] {msg}", flush=True)


def _run(job_id, job_dir, input_docx, name, email, title, filename, token, base_url):
    _set(job_id, status="running")
    _log(job_id, "Demarrage de la correction v5.2...")
    try:
        result = agent.run_job(job_dir, input_docx, progress=lambda m: _log(job_id, m))
        if result["status"] == "ok":
            _set(job_id, status="done",
                 deliverables=[os.path.basename(p) for p in result["deliverables"]])
            _log(job_id, "Correction terminee.")
            # Lien de telechargement du rapport (page protegee par jeton)
            root = PUBLIC_BASE_URL or base_url
            report_link = f"{root}/r/{job_id}/{token}"
            try:
                if os.environ.get("SYSTEMEIO_API_KEY"):
                    dbg = systemeio.push_lead(email, name, report_link=report_link)
                    _log(job_id, "systeme.io (rapport pret): " + dbg)
            except Exception as e:
                _log(job_id, f"systeme.io maj rapport echouee : {e}")
        else:
            _set(job_id, status="error")
            _log(job_id, f"Echec : {result['message']}")
    except Exception as e:
        _set(job_id, status="error")
        _log(job_id, f"Erreur serveur : {e}")


@app.get("/", response_class=HTMLResponse)
def index():
    idx = BASE / "index.html"
    if idx.exists():
        return idx.read_text(encoding="utf-8")
    return "<h1>Plume</h1>"


@app.get("/logo-reviewme.png")
def logo():
    return FileResponse(str(BASE / "logo-reviewme.png"), media_type="image/png")


@app.get("/banner-auteurs.png")
def banner():
    return FileResponse(str(BASE / "banner-auteurs.png"), media_type="image/png")


@app.post("/api/jobs")
async def create_job(request: Request, file: UploadFile = File(...), name: str = Form(""),
                     email: str = Form(""), title: str = Form(""), consent: str = Form("")):
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(400, "Format non pris en charge. Utilisez .docx ou .doc.")
    email = (email or "").strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Une adresse e-mail valide est obligatoire.")
    consent = (consent or "").strip().lower()
    if consent not in ("oui", "true", "1", "on", "yes"):
        raise HTTPException(400, "Vous devez accepter de recevoir votre rapport par e-mail.")
    data = await file.read()
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"Fichier trop volumineux (max {MAX_MB} Mo).")

    save_lead(name.strip(), email, (title or "").strip(), file.filename, "oui")

    job_id = uuid.uuid4().hex[:12]
    token = secrets.token_urlsafe(12)
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "input.docx").write_bytes(data)
    (job_dir / "token.txt").write_text(token, encoding="utf-8")
    _set(job_id, status="queued", token=token)
    _log(job_id, f"Manuscrit recu : {file.filename} ({len(data)//1024} Ko) de {email}.")

    # Capture immediate du lead dans systeme.io (avant meme la correction).
    try:
        if os.environ.get("SYSTEMEIO_API_KEY"):
            dbg = systemeio.push_lead(email, name.strip())
            _log(job_id, "systeme.io (capture): " + dbg)
    except Exception as e:
        _log(job_id, f"systeme.io capture echouee : {e}")

    base_url = str(request.base_url).rstrip("/")
    threading.Thread(target=_run,
                     args=(job_id, str(job_dir), str(job_dir / "input.docx"),
                           name, email, title, file.filename, token, base_url),
                     daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


def _check_token(job_id, t):
    tf = JOBS_DIR / job_id / "token.txt"
    return tf.exists() and t and tf.read_text(encoding="utf-8").strip() == t


@app.get("/r/{job_id}/{token}", response_class=HTMLResponse)
def report_page(job_id: str, token: str = "", sc: str = ""):
    # jeton dans le CHEMIN : robuste au suivi de clics des e-mails (Gmail/systeme.io)
    if not _check_token(job_id, token):
        raise HTTPException(403, "Lien invalide ou expire.")
    out = JOBS_DIR / job_id / "output"
    files = [p.name for p in out.glob("*")] if out.exists() else []
    if not files:
        return "<h2>Votre correction est encore en préparation. Réessayez dans quelques minutes.</h2>"
    links = "".join(
        f'<li><a href="/r/{job_id}/{token}/{f}">{f}</a></li>' for f in files)
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Votre correction Plume</title>
<style>body{{font-family:-apple-system,sans-serif;max-width:640px;margin:40px auto;padding:0 20px;color:#1c1b18}}
h1{{color:#D16927}} a{{color:#D16927;font-weight:600}} li{{margin:10px 0}}</style></head>
<body><h1>Votre correction est prête 🎉</h1>
<p>Voici votre rapport, prêt à télécharger :</p><ul>{links}</ul>
<p style="color:#6b6459;font-size:.9rem">Review Me · review-me.fr</p></body></html>"""


@app.get("/r/{job_id}/{token}/{fname}")
def report_file(job_id: str, token: str, fname: str, sc: str = ""):
    if not _check_token(job_id, token):
        raise HTTPException(403, "Lien invalide.")
    if "/" in fname or ".." in fname:
        raise HTTPException(404, "Introuvable.")
    path = JOBS_DIR / job_id / "output" / fname
    if not path.exists():
        raise HTTPException(404, "Introuvable.")
    return FileResponse(str(path), filename=fname)


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with LOCK:
        j = JOBS.get(job_id)
        return JSONResponse({"status": (j or {}).get("status", "unknown")})


@app.get("/api/test-systeme")
def test_systeme(token: str = "", email: str = "test@exemple.fr"):
    """Teste la connexion systeme.io. /api/test-systeme?token=JETON&email=toi@mail.fr"""
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(403, "Acces refuse.")
    try:
        link = (PUBLIC_BASE_URL or "https://plume-correcteur.onrender.com") + "/r/DEMO/demo"
        return {"ok": True, "result": systemeio.push_lead(email, "Test Plume", report_link=link)}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


@app.get("/api/sio")
def sio(token: str = "", path: str = "/tags", create_name: str = ""):
    """Outil admin d'exploration systeme.io.
    - Lister les tags   : /api/sio?token=JETON&path=/tags
    - Creer un tag      : /api/sio?token=JETON&path=/tags&create_name=plume-rapport-pret
    - Lister les champs : /api/sio?token=JETON&path=/contact_fields
    """
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(403, "Acces refuse.")
    try:
        if create_name:
            status, body = systemeio._req("POST", path, {"name": create_name})
        else:
            status, body = systemeio._req("GET", path)
        return {"status": status, "body": body[:3000]}
    except Exception as e:
        return {"error": repr(e)}


@app.get("/api/leads")
def export_leads(token: str = ""):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(403, "Acces refuse.")
    if not LEADS_CSV.exists():
        raise HTTPException(404, "Aucun lead pour le moment.")
    return FileResponse(str(LEADS_CSV), filename="leads.csv", media_type="text/csv")


@app.get("/api/health")
def health():
    return {"ok": True, "model": os.environ.get("PLUME_MODEL", "claude-opus-4-8"),
            "systemeio": bool(os.environ.get("SYSTEMEIO_API_KEY"))}
