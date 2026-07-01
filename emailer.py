#!/usr/bin/env python3
"""
emailer.py - Envoi du rapport de correction par e-mail (SMTP).

Configure pour Gmail par defaut, mais compatible tout SMTP.
Variables d'environnement :
  SMTP_HOST     (defaut : smtp.gmail.com)
  SMTP_PORT     (defaut : 587, STARTTLS)
  SMTP_USER     (ex : jeremieprotd@gmail.com)
  SMTP_PASSWORD (mot de passe d'application Gmail, PAS le mot de passe du compte)
  MAIL_FROM     (defaut : SMTP_USER)
  MAIL_ADMIN    (copie admin, ex : jeremieprotd@gmail.com)

Pour Gmail : active la validation en 2 etapes puis cree un "mot de passe d'application"
sur https://myaccount.google.com/apppasswords et utilise-le comme SMTP_PASSWORD.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate


def send_report(to_email: str, author_name: str, manuscript_title: str,
                attachments: list, summary: str = "") -> None:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    mail_from = os.environ.get("MAIL_FROM", user)
    admin = os.environ.get("MAIL_ADMIN")

    msg = EmailMessage()
    msg["Subject"] = f"Votre correction Review Me — {manuscript_title}"
    msg["From"] = f"Review Me <{mail_from}>"
    msg["To"] = to_email
    if admin and admin != to_email:
        msg["Bcc"] = admin
    msg["Date"] = formatdate(localtime=True)

    body = (
        f"Bonjour {author_name or ''},\n\n"
        f"Votre manuscrit « {manuscript_title} » a été relu et corrigé.\n"
        f"Vous trouverez en pièces jointes :\n"
        f"  - le manuscrit corrigé (.docx),\n"
        f"  - le rapport de correction détaillé (.docx),\n"
        f"  - la liste des erreurs (.txt).\n\n"
        f"{summary}\n\n"
        f"Chaque faute est corrigée et remise en contexte, prête à appliquer. "
        f"Votre style et votre mise en page ont été préservés à l'identique.\n\n"
        f"Merci de votre confiance,\n"
        f"L'équipe Review Me · review-me.fr\n"
    )
    msg.set_content(body)

    for path in attachments:
        if not path or not os.path.isfile(path):
            continue
        with open(path, "rb") as f:
            data = f.read()
        name = os.path.basename(path)
        if name.endswith(".docx"):
            maintype, subtype = ("application",
                                 "vnd.openxmlformats-officedocument.wordprocessingml.document")
        elif name.endswith(".txt"):
            maintype, subtype = ("text", "plain")
        else:
            maintype, subtype = ("application", "octet-stream")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls(context=context)
        server.login(user, password)
        server.send_message(msg)


def send_lead_notification(name: str, email: str, title: str, filename: str) -> None:
    """Notifie l'admin d'un NOUVEAU prospect des sa capture (avant meme la correction).
    Garantit que le lead n'est jamais perdu, meme si l'hebergement est ephemere."""
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    mail_from = os.environ.get("MAIL_FROM", user)
    admin = os.environ.get("MAIL_ADMIN", user)

    msg = EmailMessage()
    msg["Subject"] = f"Nouveau lead Plume : {email}"
    msg["From"] = f"Plume <{mail_from}>"
    msg["To"] = admin
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(
        "Nouveau prospect capture sur Plume :\n\n"
        f"  Nom     : {name or '(non renseigne)'}\n"
        f"  E-mail  : {email}\n"
        f"  Titre   : {title or '(non renseigne)'}\n"
        f"  Fichier : {filename}\n\n"
        "Le rapport de correction lui sera envoye automatiquement une fois pret."
    )
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls(context=context)
        server.login(user, password)
        server.send_message(msg)


if __name__ == "__main__":
    # test manuel : python emailer.py destinataire@exemple.fr
    import sys
    to = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MAIL_ADMIN")
    send_report(to, "Testeur", "Manuscrit de test", [], "Ceci est un test d'envoi.")
    print("E-mail de test envoye a", to)
