# Review Me — Correcteur de manuscrits automatisé (v5.2)

Service en ligne qui reçoit un manuscrit `.docx`, applique **votre workflow de correction
exhaustive v5.2** via l'API Claude (avec exécution de code), puis renvoie **3 livrables** :

1. `manuscrit_corrige.docx` — le manuscrit corrigé, mise en page préservée
2. `rapport_correction.docx` — le rapport détaillé (charte Review Me)
3. `liste_erreurs.txt` — la liste brute des corrections

Le rapport est aussi **envoyé par e-mail** à l'auteur (et en copie à l'admin).

---

## Architecture

```
plume-correcteur/
├── frontend/
│   └── index.html          Landing page + formulaire de dépôt + suivi en direct
└── backend/
    ├── server.py           API FastAPI (upload, jobs, téléchargement)
    ├── agent.py            Boucle agentique Claude (outils bash/edit) = moteur v5.2
    ├── emailer.py          Envoi du rapport par e-mail (SMTP Gmail)
    ├── prompt_v5.txt       Votre prompt de correction v5.2 (system prompt)
    ├── scripts/
    │   ├── unpack.py       Déballe le .docx + inventaire (étape 1)
    │   ├── pack.py         Repackage le .docx corrigé
    │   └── audit.py        Audit final automatisé (étape 8, objectif 0)
    ├── requirements.txt
    └── .env.example
```

Le manuscrit n'est jamais envoyé à un tiers non sollicité : seul l'API Claude d'Anthropic
le traite, et les fichiers restent sur votre serveur (dossier `backend/jobs/<id>/`).

---

## Installation (local)

```bash
cd backend
python3 -m venv venv && source venv/bin/activate   # Windows : venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # puis éditez .env (voir ci-dessous)
# charger les variables :  (Linux/Mac)  export $(grep -v '^#' .env | xargs)
uvicorn server:app --host 0.0.0.0 --port 8000
```

Ouvrez http://localhost:8000

### Variables `.env` à remplir

| Variable | Rôle |
|---|---|
| `ANTHROPIC_API_KEY` | **Obligatoire.** Votre clé API Anthropic (console.anthropic.com). |
| `PLUME_MODEL` | Modèle utilisé (défaut `claude-opus-4-8`). |
| `SMTP_USER` / `SMTP_PASSWORD` | Compte Gmail + **mot de passe d'application** (pas le mot de passe du compte). |
| `MAIL_ADMIN` | Votre e-mail, reçoit une copie de chaque rapport. |

> **Mot de passe d'application Gmail** : activez la validation en 2 étapes, puis créez-en un
> sur https://myaccount.google.com/apppasswords . Sans SMTP configuré, le service fonctionne
> quand même : l'auteur télécharge simplement ses fichiers depuis la page.

---

## Déploiement en ligne

Le backend est un serveur Python **persistant** (il exécute un agent long). Choisissez un
hébergement qui supporte les processus longs, pas une plateforme purement « serverless » :

- **Render / Railway / Fly.io** (simple) : déployez le dossier `backend`, commande de
  démarrage `uvicorn server:app --host 0.0.0.0 --port $PORT`, ajoutez les variables d'env.
- **VPS (OVH, Scaleway, Hetzner)** : installez Python, lancez avec `systemd` + `nginx` en
  reverse proxy devant `uvicorn`.

Servez ensuite `frontend/index.html` via le backend (déjà géré par la route `/`) ou via un
CDN qui pointe les appels `/api/...` vers votre backend.

---

## Coût

Chaque correction consomme des tokens API Claude proportionnels à la taille du manuscrit
(entrée + sorties + tours d'agent). Comptez plusieurs dizaines de centimes à quelques euros
par roman selon le modèle. Surveillez votre usage sur console.anthropic.com et fixez un
plafond de dépenses. `PLUME_MODEL=claude-sonnet-5` réduit le coût si besoin.

---

## Tests rapides des scripts (sans API)

```bash
cd backend/scripts
python unpack.py mon.docx /tmp/work   # inventaire
python audit.py /tmp/work             # doit lister les fautes ; 0 = propre
python pack.py /tmp/work /tmp/out.docx
```

---

## Limites & notes

- L'agent suit le prompt v5.2 mais reste un système probabiliste : gardez une relecture
  humaine finale pour les manuscrits à fort enjeu (l'audit §8 garantit l'absence de fautes
  mécaniques, pas le jugement littéraire — ce qui est justement l'intention du prompt).
- La production du `rapport_correction.docx` à la charte exacte peut demander un ou deux
  essais de calibrage : le prompt décrit la charte (orange #D16927, jaune #F7CA00, A4 paysage),
  l'agent la construit via `python-docx`.
- Pensez à purger périodiquement `backend/jobs/` (manuscrits traités).

---

## Mode LEAD MAGNET (version définitive)

Le service est un **aimant à prospects** : le rapport n'est jamais affiché à l'écran, il
part **uniquement par e-mail**. L'objectif est de collecter des adresses.

- L'e-mail du prospect est **obligatoire** (sinon l'envoi est refusé).
- Chaque dépôt enregistre le prospect dans **`backend/leads.csv`**
  (colonnes : date, nom, email, titre_manuscrit, fichier).
- Aucun résultat ni lien de téléchargement n'est exposé côté public : l'écran affiche
  seulement « Votre correction arrive par e-mail ».

### Récupérer vos prospects

Deux façons :

1. **Le fichier** `backend/leads.csv` (ouvrable dans Excel) — la source de vérité.
2. **En ligne** : `https://VOTRE-SITE/api/leads?token=VOTRE_JETON`
   où `VOTRE_JETON` = la valeur de `PLUME_ADMIN_TOKEN` dans `.env`.
   Le téléchargement des manuscrits corrigés (réservé admin) suit la même logique :
   `.../api/jobs/<id>/download/<fichier>?token=VOTRE_JETON`.

> Choisissez un `PLUME_ADMIN_TOKEN` long et secret : c'est lui qui protège l'accès à vos
> leads et aux fichiers.

### Bon à savoir (RGPD)

Vous collectez des e-mails : prévoyez une mention de consentement et une politique de
confidentialité, et n'utilisez ces adresses que pour ce que le prospect a accepté.
