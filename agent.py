#!/usr/bin/env python3
"""
agent.py - Moteur agentique v5.2.

Lance une boucle d'agent Claude qui execute le workflow de correction en 8 etapes
(prompt_v5.txt) sur un manuscrit .docx, dans un dossier de travail isole. L'agent
dispose de 4 outils locaux : run_bash, read_file, write_file, str_replace.

Il produit, dans <job_dir>/output/ :
  - manuscrit_corrige.docx
  - rapport_correction.docx
  - liste_erreurs.txt

Config par variables d'environnement :
  ANTHROPIC_API_KEY  (obligatoire)
  PLUME_MODEL        (defaut : claude-opus-4-8)
  PLUME_MAX_TURNS    (defaut : 120)
"""
import os
import re
import subprocess
import pathlib

from anthropic import Anthropic

MODEL = os.environ.get("PLUME_MODEL", "claude-opus-4-8")
MAX_TURNS = int(os.environ.get("PLUME_MAX_TURNS", "120"))
SCRIPTS_DIR = pathlib.Path(__file__).parent
PROMPT_FILE = pathlib.Path(__file__).parent / "prompt_v5.txt"

TOOLS = [
    {
        "name": "run_bash",
        "description": "Execute une commande shell (bash) dans le dossier de travail du job. "
                       "Utilise pour lancer les scripts Python (unpack.py, pack.py, audit.py), "
                       "pandoc, grep, ou tout script d'analyse/correction que tu ecris.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "Commande bash a executer."}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Lit le contenu d'un fichier texte (UTF-8) du dossier de travail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Chemin relatif au dossier de travail."},
                "max_bytes": {"type": "integer", "description": "Optionnel : limite d'octets a lire."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Ecrit (ou remplace) un fichier texte UTF-8 dans le dossier de travail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "str_replace",
        "description": "Remplace une occurrence exacte de old_str par new_str dans un fichier XML. "
                       "count controle le nombre de remplacements (defaut 1). Echoue si old_str "
                       "n'existe pas ou apparait plus de count fois quand count est fixe.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string"},
                "new_str": {"type": "string"},
                "count": {"type": "integer", "description": "Nombre d'occurrences a remplacer (defaut 1)."},
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
]

# Mise en cache (prompt caching) : le dernier outil porte le marqueur, ce qui met en
# cache la definition des outils ET le system prompt (facturees ~10% en relecture).
TOOLS[-1]["cache_control"] = {"type": "ephemeral"}


def _safe_path(job_dir: pathlib.Path, rel: str) -> pathlib.Path:
    p = (job_dir / rel).resolve()
    if not str(p).startswith(str(job_dir.resolve())):
        raise ValueError("Chemin hors du dossier de travail refuse.")
    return p


def _exec_tool(name: str, args: dict, job_dir: pathlib.Path) -> str:
    try:
        if name == "run_bash":
            r = subprocess.run(
                args["command"], shell=True, cwd=str(job_dir),
                capture_output=True, text=True, timeout=300,
            )
            out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
            out = out.strip() or "(aucune sortie)"
            return f"exit={r.returncode}\n{out[:12000]}"

        if name == "read_file":
            p = _safe_path(job_dir, args["path"])
            data = p.read_text(encoding="utf-8", errors="replace")
            mx = args.get("max_bytes")
            if mx:
                data = data[:mx]
            return data

        if name == "write_file":
            p = _safe_path(job_dir, args["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"], encoding="utf-8")
            return f"ecrit : {args['path']} ({len(args['content'])} caracteres)"

        if name == "str_replace":
            p = _safe_path(job_dir, args["path"])
            txt = p.read_text(encoding="utf-8")
            old = args["old_str"]
            count = int(args.get("count", 1))
            occ = txt.count(old)
            if occ == 0:
                return "ERREUR : old_str introuvable (count=0). Verifie le contexte exact."
            if count and occ > count and count != 0:
                # on remplace count occurrences seulement
                pass
            new_txt = txt.replace(old, args["new_str"], count if count else -1)
            p.write_text(new_txt, encoding="utf-8")
            return f"remplace {min(occ, count) if count else occ} occurrence(s) dans {args['path']}."

        return f"Outil inconnu : {name}"
    except Exception as e:  # noqa: BLE001
        return f"ERREUR outil {name} : {e}"


def build_system_prompt() -> str:
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    return (
        "Tu es le correcteur du service Review Me. Tu travailles de facon autonome via les "
        "outils fournis (run_bash, read_file, write_file, str_replace) et python-docx.\n\n"
        "ENVIRONNEMENT : le dossier de travail contient le manuscrit input.docx, l'image "
        "logo-reviewme.png (a inserer dans le rapport) et un sous-dossier scripts/ avec "
        "unpack.py (extraction facultative). Tu dois produire UN SEUL fichier : "
        "output/rapport_correction.docx. Aucun autre fichier.\n\n"
        "OBJECTIF TOKENS : va au plus court, un minimum d'etapes, pas de relecture multiple, "
        "pas de boucle d'audit, pas de reecriture du manuscrit.\n\n"
        "Quand output/rapport_correction.docx est pret, termine par le marqueur exact : "
        "<<TERMINE>>.\n\n"
        "=== CONSIGNES ===\n" + prompt
    )


def run_job(job_dir: str, input_docx: str, progress=None) -> dict:
    """
    Execute le workflow complet. Renvoie un dict :
      {status, deliverables:[...], turns, message}
    progress : callable(str) optionnelle pour remonter l'avancement.
    """
    job = pathlib.Path(job_dir).resolve()
    job.mkdir(parents=True, exist_ok=True)
    (job / "output").mkdir(exist_ok=True)

    # copie des scripts dans le dossier de travail
    dst_scripts = job / "scripts"
    dst_scripts.mkdir(exist_ok=True)
    for _name in ("unpack.py",):
        (dst_scripts / _name).write_text((SCRIPTS_DIR / _name).read_text(encoding="utf-8"), encoding="utf-8")

    # copie du manuscrit en input.docx (sauf s'il y est deja)
    import shutil, os as _os
    dest = job / "input.docx"
    if _os.path.abspath(str(input_docx)) != _os.path.abspath(str(dest)):
        shutil.copy(input_docx, dest)
    # copie du logo pour l'inserer dans le rapport
    _logo = pathlib.Path(__file__).parent / "logo-reviewme.png"
    if _logo.exists():
        shutil.copy(str(_logo), str(job / "logo-reviewme.png"))

    def log(msg):
        if progress:
            progress(msg)

    client = Anthropic()  # lit ANTHROPIC_API_KEY
    system_text = build_system_prompt()
    # System prompt mis en cache
    system = [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}]

    def _mark_cache(msgs):
        # retire les anciens marqueurs sur les messages utilisateur
        for m in msgs:
            c = m.get("content")
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict):
                        b.pop("cache_control", None)
        # pose un marqueur sur le dernier message s'il est modifiable (texte ou tool_result)
        if msgs:
            last = msgs[-1]
            c = last.get("content")
            if isinstance(c, str):
                last["content"] = [{"type": "text", "text": c,
                                    "cache_control": {"type": "ephemeral"}}]
            elif isinstance(c, list) and c and isinstance(c[-1], dict):
                c[-1]["cache_control"] = {"type": "ephemeral"}
    messages = [{
        "role": "user",
        "content": (
            "Analyse input.docx et produis UNIQUEMENT output/rapport_correction.docx, "
            "avec le logo logo-reviewme.png en en-tete, aux couleurs Review Me. "
            "Ne reecris pas le manuscrit, ne cree aucun autre fichier. Va au plus court."
        ),
    }]

    turns = 0
    while turns < MAX_TURNS:
        turns += 1
        _mark_cache(messages)
        resp = client.messages.create(
            model=MODEL, max_tokens=8000, system=system, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        # journaliser le texte
        for block in resp.content:
            if block.type == "text" and block.text.strip():
                log(f"[tour {turns}] {block.text.strip()[:300]}")

        if resp.stop_reason != "tool_use":
            # fin possible
            final_text = " ".join(b.text for b in resp.content if b.type == "text")
            if "<<TERMINE>>" in final_text:
                break
            # sinon, on relance en demandant de continuer
            messages.append({"role": "user", "content": "Continue jusqu'a produire output/rapport_correction.docx, puis ecris <<TERMINE>>."})
            continue

        # executer les outils demandes
        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                log(f"  -> {block.name}: {str(block.input)[:160]}")
                result = _exec_tool(block.name, block.input, job)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        messages.append({"role": "user", "content": tool_results})

    # verifier les livrables
    out = job / "output"
    expected = ["rapport_correction.docx"]
    delivered = [str(out / n) for n in expected if (out / n).exists()]
    status = "ok" if len(delivered) == len(expected) else "incomplet"
    return {
        "status": status,
        "deliverables": delivered,
        "turns": turns,
        "message": "Livraison complete." if status == "ok"
                   else f"Livrables manquants (obtenus : {len(delivered)}/3).",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        sys.exit("Usage : python agent.py <job_dir> <input.docx>")
    res = run_job(sys.argv[1], sys.argv[2], progress=lambda m: print(m))
    print("\nRESULTAT :", res)
