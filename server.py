#!/usr/bin/env python3
"""server.py - Serveur Plume (FastAPI) - MODE LEAD MAGNET - version a plat (racine)."""
import os
import csv
import uuid
import threading
import pathlib
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

import agent
import emailer

BASE = pathlib.Path(__file__).parent
JOBS_DIR = BASE / "jobs"
JOBS_DIR.mkdir(exist_ok=True)
LEADS_CSV = BASE / "leads.csv"
ADMIN_TOKEN = os.environ.get("PLUME_ADMIN_TOKEN", "")
MAX_MB = int(os.environ.get("PLUME_MAX_UPLOAD_MB", "25"))

app = FastAPI(title="Plume - Correcteur (lead magnet)")
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
        JOBS[job_id].setdefault("log", [])


def _log(job_id, msg):
    print(f"[JOB {job_id}] {msg}", flush=True)   # visible dans les logs Render
    with LOCK:
        JOBS[job_id]["log"].append(f"{datetime.now():%H:%M:%S} {msg}")
        JOBS[job_id]["log"] = JOBS[job_id]["log"][-200:]


def _run(job_id, job_dir, input_docx, name, email, title, filename):
    _set(job_id, status="running")
    try:
        if os.environ.get("SMTP_USER"):
            emailer.send_lead_notification(name, email, title, filename)
            _log(job_id, "Notification lead envoyee a l'admin.")
    except Exception as e:
        _log(job_id, f"Notification lead echouee : {e}")
    _log(job_id, "Demarrage de la correction v5.2...")
    try:
        result = agent.run_job(job_dir, input_docx, progress=lambda m: _log(job_id, m))
        _set(job_id, result=result)
        if result["status"] == "ok":
            _set(job_id, status="done",
                 deliverables=[os.path.basename(p) for p in result["deliverables"]])
            _log(job_id, "Correction terminee.")
            try:
                if email and os.environ.get("SMTP_USER"):
                    emailer.send_report(email, name, title or "votre manuscrit",
                                        result["deliverables"],
                                        summary=f"Traitement effectue en {result['turns']} etapes.")
                    _log(job_id, f"Rapport envoye a {email}.")
            except Exception as e:
                _log(job_id, f"Envoi e-mail echoue : {e}")
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
async def create_job(file: UploadFile = File(...), name: str = Form(""),
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
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = job_dir / "input.docx"
    input_path.write_bytes(data)
    _set(job_id, status="queued")
    _log(job_id, f"Manuscrit recu : {file.filename} ({len(data)//1024} Ko).")
    threading.Thread(target=_run,
                     args=(job_id, str(job_dir), str(input_path), name, email, title, file.filename),
                     daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with LOCK:
        j = JOBS.get(job_id)
        if not j:
            raise HTTPException(404, "Job inconnu.")
        return JSONResponse({"status": j.get("status")})


@app.get("/api/leads")
def export_leads(token: str = ""):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(403, "Acces refuse.")
    if not LEADS_CSV.exists():
        raise HTTPException(404, "Aucun lead pour le moment.")
    return FileResponse(str(LEADS_CSV), filename="leads.csv", media_type="text/csv")


@app.get("/api/jobs/{job_id}/download/{fname}")
def download(job_id: str, fname: str, token: str = ""):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(403, "Acces refuse.")
    if "/" in fname or ".." in fname:
        raise HTTPException(404, "Fichier introuvable.")
    path = JOBS_DIR / job_id / "output" / fname
    if not path.exists():
        raise HTTPException(404, "Fichier introuvable.")
    return FileResponse(str(path), filename=fname)


@app.get("/api/test-mail")
def test_mail(token: str = ""):
    """Teste l'envoi d'e-mail en isolation. /api/test-mail?token=TON_JETON"""
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(403, "Acces refuse.")
    try:
        emailer.send_lead_notification("Test Plume", os.environ.get("MAIL_ADMIN", "?"),
                                       "Test", "test.docx")
        return {"ok": True, "message": "E-mail de test envoye. Verifie ta boite (et les spams)."}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


@app.get("/api/health")
def health():
    return {"ok": True, "model": os.environ.get("PLUME_MODEL", "claude-opus-4-8"),
            "smtp": bool(os.environ.get("SMTP_USER")), "leads": LEADS_CSV.exists()}
