"""Ce qu'il faut fabriquer aujourd'hui, et à quelle heure conseiller de publier chaque vidéo."""
import datetime

from .commun import JOURS, lire, maintenant

ESSAIS_MAX = 2          # par format et par jour : un échec est retenté une fois au réveil suivant, pas plus


def a_faire(R, file, etat):
    """Formats à fabriquer aujourd'hui (réveil automatique)."""
    pl, now = R["planning"], maintenant()
    jour = now.date().isoformat()
    voulu = []
    if pl.get("courte_chaque_jour"):
        voulu.append("courte")
    if JOURS[now.weekday()] in pl.get("jours_longue", []):
        voulu.append("longue")
    faits = {v["format"] for v in file.get("videos", []) if v.get("auto") and v.get("cree_le", "")[:10] == jour}
    essais = (etat.get("essais") or {}).get(jour, {})
    return [f for f in voulu if f not in faits and essais.get(f, 0) < ESSAIS_MAX]


def creneau(R, file, format_):
    """Prochain créneau de publication libre (au moins 1 h après maintenant). Les longues visent le dernier créneau du jour."""
    heures = sorted(set(int(h) for h in R["planning"]["heures_publication"])) or [19]
    if format_ == "longue":
        heures = heures[-1:]
    pris = {v.get("publier_le", "")[:13] for v in file.get("videos", [])
            if v.get("statut") in ("a_publier", "publiee")}
    now = maintenant()
    for j in range(0, 60):
        jour = (now + datetime.timedelta(days=j)).date()
        for h in heures:
            d = datetime.datetime(jour.year, jour.month, jour.day, h, tzinfo=now.tzinfo)
            if d >= now + datetime.timedelta(hours=1) and d.isoformat()[:13] not in pris:
                return d.isoformat(timespec="seconds")
    return (now + datetime.timedelta(hours=2)).isoformat(timespec="seconds")


def etat():
    return lire("etat.json") or {"essais": {}}
