"""Outils partagés : chemins, lecture/écriture des fichiers de données, heure de Paris, journal."""
import datetime
import json
import os
from zoneinfo import ZoneInfo

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.environ.get("ROBOT_DOCS") or os.path.join(RACINE, "docs")   # ROBOT_DOCS : dossier de test
DONNEES = os.path.join(DOCS, "donnees")                      # lues aussi par le site (GitHub Pages)
MINIATURES = os.path.join(DOCS, "miniatures")
SORTIE = os.environ.get("ROBOT_SORTIE") or os.path.join(RACINE, "sortie")   # fichiers de travail (jamais enregistrés)
POLICES = os.path.join(RACINE, "polices")
PARIS = ZoneInfo("Europe/Paris")
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def maintenant():
    """Heure de Paris. ROBOT_MAINTENANT (format ISO) permet aux tests de fixer l'heure."""
    fixe = os.environ.get("ROBOT_MAINTENANT")
    if fixe:
        d = datetime.datetime.fromisoformat(fixe)
        return d if d.tzinfo else d.replace(tzinfo=PARIS)
    return datetime.datetime.now(PARIS)


def iso(d=None):
    return (d or maintenant()).isoformat(timespec="seconds")


def lire(nom, defaut=None):
    try:
        with open(os.path.join(DONNEES, nom), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def ecrire(nom, contenu):
    os.makedirs(DONNEES, exist_ok=True)
    chemin = os.path.join(DONNEES, nom)
    with open(chemin + ".tmp", "w", encoding="utf-8") as f:
        json.dump(contenu, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(chemin + ".tmp", chemin)


def reglages():
    return lire("reglages.json")


def personnage():
    return lire("personnage.json")


def noter(texte, niveau="info"):
    """Ajoute une ligne au journal affiché sur le site (200 dernières gardées)."""
    j = lire("journal.json", {"evenements": []})
    j["evenements"].insert(0, {"date": iso(), "niveau": niveau, "texte": texte})
    del j["evenements"][200:]
    ecrire("journal.json", j)
    print(f"[{niveau}] {texte}", flush=True)


def simulation():
    return os.environ.get("SIMULATION", "0") == "1"
