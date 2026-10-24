"""Avancement en temps réel de la vidéo en cours de création, affiché par le site (barre de progression).

Le robot écrit un petit fichier avancement.json sur une branche à part du dépôt (« avancement »), remplacée à chaque mise
à jour (aucun historique, la branche main n'est jamais touchée). Pendant que Grok filme, le pourcentage de Grok est relayé :
une mise à jour toutes les 10 s environ. Le site relit ce fichier toutes les 8 s.
"""
import json
import os
import subprocess
import time

from .commun import RACINE, SORTIE, iso, maintenant

BRANCHE = "avancement"
INTERVALLE = 10                 # secondes entre deux envois (sauf changement d'étape, envoyé tout de suite)
TYPIQUE = {"courte": 12 * 60, "longue": 30 * 60, "tiktok": 18 * 60}   # durée habituelle d'une création, en secondes

_etat = {}
_dernier_envoi = 0.0


def demarrer(vid, format_, titre=""):
    global _dernier_envoi
    _etat.clear()
    _etat.update(id=vid, format=format_, titre=titre, etat="en_cours", etape="Démarrage du robot", detail="", pourcent=1,
                 debut=iso(), debut_s=time.time(), run=os.environ.get("GITHUB_RUN_ID", ""))
    _dernier_envoi = 0.0
    _envoyer(force=True)


def etape(texte, pourcent, detail="", titre=None):
    """Nouvelle étape (envoyée tout de suite)."""
    if not _etat:
        return
    if titre:
        _etat["titre"] = titre
    _etat.update(etape=texte, detail=detail, pourcent=max(_etat.get("pourcent", 0), min(99, round(pourcent, 1))))
    _envoyer(force=True)


def progres(pourcent, detail=None):
    """Progrès à l'intérieur d'une étape (envoyé au plus toutes les 10 s)."""
    if not _etat:
        return
    _etat["pourcent"] = max(_etat.get("pourcent", 0), min(99, round(pourcent, 1)))
    if detail is not None:
        _etat["detail"] = detail
    _envoyer()


def finir(ok, texte):
    if not _etat:
        return
    _etat.update(etat="fini" if ok else "erreur", etape=texte, detail="", pourcent=100 if ok else _etat.get("pourcent", 0))
    _envoyer(force=True)


def contenu():
    """Ce que lit le site, avec l'heure de fin estimée (d'après le temps déjà passé et le pourcentage)."""
    ecoule = time.time() - _etat["debut_s"]
    p = _etat["pourcent"]
    typique = TYPIQUE.get(_etat["format"], 15 * 60)
    if _etat["etat"] != "en_cours":
        reste = 0
    elif p < 12:                                        # début : on se fie à la durée habituelle
        reste = max(60, typique - ecoule)
    else:                                               # ensuite : au rythme réel de cette création
        reste = max(20, ecoule * (100 - p) / p)
    d = {k: v for k, v in _etat.items() if k != "debut_s"}
    d.update(maj=iso(), ecoule_s=round(ecoule), reste_s=round(reste))
    return d


def _envoyer(force=False):
    global _dernier_envoi
    if not force and time.time() - _dernier_envoi < INTERVALLE:
        return
    _dernier_envoi = time.time()
    texte = json.dumps(contenu(), ensure_ascii=False)
    try:
        os.makedirs(SORTIE, exist_ok=True)
        with open(os.path.join(SORTIE, "avancement.json"), "w", encoding="utf-8") as f:
            f.write(texte)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            _pousser(texte)
    except Exception as e:                              # l'avancement ne doit jamais gêner la création de la vidéo
        print(f"  (avancement non envoyé : {e})", flush=True)


def _git(*args, entree=None):
    return subprocess.run(["git", *args], cwd=RACINE, input=entree, capture_output=True, text=True, check=True,
                          timeout=30).stdout.strip()


def _pousser(texte):
    """Remplace la branche « avancement » par un seul commit contenant avancement.json (sans toucher au dossier de travail)."""
    blob = _git("hash-object", "-w", "--stdin", entree=texte)
    arbre = _git("mktree", entree=f"100644 blob {blob}\tavancement.json\n")
    env = dict(os.environ, GIT_AUTHOR_NAME="robot-gilbert", GIT_AUTHOR_EMAIL="robot-gilbert@users.noreply.github.com",
               GIT_COMMITTER_NAME="robot-gilbert", GIT_COMMITTER_EMAIL="robot-gilbert@users.noreply.github.com")
    commit = subprocess.run(["git", "commit-tree", arbre, "-m", f"avancement {maintenant():%H:%M:%S}"], cwd=RACINE,
                            capture_output=True, text=True, check=True, env=env, timeout=30).stdout.strip()
    _git("push", "-q", "--force", "origin", f"{commit}:refs/heads/{BRANCHE}")
