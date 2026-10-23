"""Enregistrement dans le dépôt GitHub et rangement des vidéos dans les « Releases ».

Plusieurs tâches peuvent écrire en même temps (robot du matin, boutons du site) : chaque écriture repart de la
dernière version en ligne, applique son changement, puis envoie. Si quelqu'un est passé entre-temps, on recommence.
"""
import os
import subprocess
import time

from .commun import RACINE


def en_ligne():
    return os.environ.get("GITHUB_ACTIONS") == "true"


def _git(*args, verifier=True):
    return subprocess.run(["git", *args], cwd=RACINE, capture_output=True, text=True, check=verifier)


def enregistrer(appliquer, message, essais=6):
    """Applique `appliquer()` sur la dernière version du dépôt puis l'envoie. Hors GitHub : applique seulement."""
    if not en_ligne():
        return appliquer()
    branche = os.environ.get("GITHUB_REF_NAME", "main")
    _git("config", "user.name", "robot-gilbert")
    _git("config", "user.email", "robot-gilbert@users.noreply.github.com")
    for n in range(essais):
        _git("fetch", "-q", "origin", branche)
        _git("reset", "-q", "--hard", f"origin/{branche}")
        resultat = appliquer()
        _git("add", "-A", "docs")
        if _git("diff", "--cached", "--quiet", verifier=False).returncode == 0:
            return resultat
        _git("commit", "-q", "-m", message)
        if _git("push", "-q", "origin", f"HEAD:{branche}", verifier=False).returncode == 0:
            return resultat
        time.sleep(3 + 4 * n)
    raise RuntimeError("impossible d'enregistrer dans le dépôt après plusieurs essais")


def depot():
    return os.environ.get("GITHUB_REPOSITORY", "")


def publier_release(tag, titre, fichiers):
    """Range la vidéo dans une Release du dépôt. Renvoie l'adresse de téléchargement du premier fichier."""
    if not en_ligne():
        return "file://" + fichiers[0]
    subprocess.run(["gh", "release", "create", tag, *fichiers, "--title", titre[:120],
                    "--notes", "Vidéo fabriquée par le robot (contenu généré par IA)."], cwd=RACINE, check=True)
    return f"https://github.com/{depot()}/releases/download/{tag}/{os.path.basename(fichiers[0])}"


def supprimer_release(tag):
    if en_ligne() and tag:
        subprocess.run(["gh", "release", "delete", tag, "--yes", "--cleanup-tag"], cwd=RACINE)
