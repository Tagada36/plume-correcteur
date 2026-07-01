# Mettre Plume en ligne sur Render — guide en clics (sans ligne de commande)

Objectif : obtenir une **adresse internet** (ex. `https://plume-correcteur.onrender.com`)
que tu mettras dans ta pub Facebook. Compte ~30 minutes la première fois.

Tu vas utiliser **2 comptes gratuits** : GitHub (pour héberger les fichiers) et Render
(pour faire tourner le moteur). Aucune ligne de commande.

---

## AVANT DE COMMENCER — à avoir sous la main

1. **Ta clé API Anthropic** (commence par `sk-ant-...`) — console.anthropic.com → API Keys.
   ⚠️ **Mets un plafond de dépense** : Settings → Limits → « Monthly spend limit » (ex. 20 €).
   C'est ta sécurité contre les mauvaises surprises.
2. **Ton mot de passe d'application Gmail** (16 lettres) —
   myaccount.google.com/apppasswords (nécessite la validation en 2 étapes activée).
3. **Ton identifiant de pixel Facebook** (un numéro, ex. `123456789012345`).
4. **Un jeton admin** : invente une longue phrase secrète (ex. `plume-2026-Xk9-secret-motdepasse`).
   Elle protégera l'accès à ta liste de prospects.

---

## ÉTAPE 1 — Mettre les fichiers sur GitHub

1. Va sur **github.com** → crée un compte gratuit (ou connecte-toi).
2. En haut à droite, clique **+** → **New repository**.
3. Nom : `plume-correcteur`. Laisse en **Public**. Clique **Create repository**.
4. Sur la page suivante, clique le lien **« uploading an existing file »**.
5. **Décompresse** d'abord `plume-correcteur.zip` sur ton ordinateur (clic droit → Extraire).
6. Ouvre le dossier décompressé, **sélectionne tout ce qu'il contient**
   (les dossiers `backend`, `frontend` + les fichiers `render.yaml`, `README.md`, etc.)
   et **glisse-les** dans la zone d'upload de GitHub.
7. En bas, clique **Commit changes**. Les fichiers sont maintenant sur GitHub.

> Astuce : si le glisser-déposer d'un dossier ne marche pas dans ton navigateur, installe
> **GitHub Desktop** (application avec boutons, sans commande) : il publie le dossier en 2 clics.

---

## ÉTAPE 2 — Coller ton pixel Facebook

Toujours sur GitHub :

1. Ouvre le fichier `frontend/index.html` (clique dessus).
2. Clique l'icône **crayon** (✏️ « Edit this file ») en haut à droite.
3. Utilise Ctrl+F pour trouver **`VOTRE_PIXEL_ID`** (il apparaît **2 fois**).
4. Remplace **les deux** par ton vrai numéro de pixel (ex. `123456789012345`).
5. Clique **Commit changes**.

---

## ÉTAPE 3 — Déployer sur Render

1. Va sur **render.com** → **Get Started** → connecte-toi **avec GitHub**
   (bouton « GitHub » : le plus simple, ça relie les deux comptes).
2. Dans le tableau de bord Render, clique **New +** → **Blueprint**.
3. Render affiche tes dépôts GitHub → choisis **`plume-correcteur`** → **Connect**.
4. Render lit le fichier `render.yaml` et propose de créer le service **plume-correcteur**.
   Clique **Apply** / **Create**.

---

## ÉTAPE 4 — Saisir tes clés secrètes (variables d'environnement)

Render va te demander de remplir les variables marquées « secret ». Renseigne :

| Variable | Valeur à mettre |
|---|---|
| `ANTHROPIC_API_KEY` | ta clé `sk-ant-...` |
| `PLUME_ADMIN_TOKEN` | ta phrase secrète (étape 0) |
| `SMTP_USER` | ton adresse Gmail (ex. jeremieprotd@gmail.com) |
| `SMTP_PASSWORD` | ton mot de passe d'application Gmail (16 lettres) |
| `MAIL_FROM` | ton adresse Gmail |
| `MAIL_ADMIN` | ton adresse Gmail (tu y recevras chaque lead) |

Puis clique **Create / Deploy**. Render installe et démarre (3-5 min la 1re fois).
Quand c'est vert (« Live »), tu vois ton **adresse** en haut, du type
`https://plume-correcteur.onrender.com`.

---

## ÉTAPE 5 — Tester comme un client

1. Ouvre ton adresse Render dans Chrome.
2. Remplis le formulaire, coche le consentement, dépose un petit `.docx`, envoie.
3. Tu dois : voir l'écran « Votre correction arrive par e-mail »,
   recevoir **tout de suite** un e-mail « Nouveau lead Plume »,
   puis quelques minutes après, l'e-mail avec le rapport corrigé.

> Sur l'offre gratuite, si personne n'a utilisé le site depuis un moment, le **premier
> chargement prend ~50 secondes** (le serveur se réveille). C'est normal.

---

## ÉTAPE 6 — Brancher la pub Facebook

1. Dans Meta (Gestionnaire de publicités), crée ta campagne.
2. Comme **URL de destination**, mets ton adresse Render.
3. Vérifie que le pixel se déclenche : installe l'extension Chrome
   **« Meta Pixel Helper »**, ouvre ton site → elle doit montrer **PageView**,
   et **Lead** après un envoi de formulaire.
4. Dans Meta, tu peux alors optimiser la campagne sur l'événement **Lead**.

---

## ÉTAPE 7 — Récupérer tes prospects

- **Le plus simple** : chaque prospect t'arrive **par e-mail** (« Nouveau lead Plume »).
  Crée un dossier/filtre Gmail pour les regrouper.
- **La liste complète** : ouvre dans ton navigateur
  `https://TON-ADRESSE.onrender.com/api/leads?token=TA_PHRASE_SECRETE`
  → télécharge le fichier `leads.csv` (ouvrable dans Excel).

---

## RAPPELS IMPORTANTS

- **Coût réel = l'API Claude**, pas l'hébergement. Chaque correction coûte quelques
  dizaines de centimes à ~3 € selon la taille. Garde ton **plafond** sur Anthropic.
- L'offre gratuite Render « s'endort » et son disque est **temporaire** : c'est pourquoi on
  s'appuie sur l'**e-mail** pour ne jamais perdre un lead. Pour de gros volumes, passe à un
  petit plan payant Render et/ou branche ta liste sur systeme.io plus tard.
- **RGPD** : la case de consentement et la mention sont déjà en place. Pense à ajouter une
  page « Politique de confidentialité » et un lien de désinscription dans tes e-mails.
