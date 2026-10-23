"""Ordres envoyés depuis le site (boutons) : appliqués aux données puis enregistrés dans le dépôt.

    ACTION=publiee ID=… TEXTE=lien  python -m robot.commande
Actions : publiee, a_publier, ecarter, supprimer, legende, personnage, reglages, portrait, pause, reprise.
"""
import json
import os
import shutil
import sys

from . import budget, depot, principal
from .commun import DONNEES, JOURS, MINIATURES, SORTIE, ecrire, iso, lire, noter, personnage, reglages

CHAMPS_PERSO = {"nom": 60, "age": 3, "ville": 120, "apparence": 600, "voix": 300, "personnalite": 600,
                "phrase_fetiche": 120, "ton": 200}


def _video(file, vid):
    for v in file["videos"]:
        if v["id"] == vid:
            return v
    raise ValueError(f"vidéo {vid} introuvable")


def appliquer(action, vid, texte):
    file = lire("file.json") or {"videos": []}
    if action in ("publiee", "a_publier", "ecarter", "legende", "supprimer"):
        v = _video(file, vid)
        if action == "publiee":
            v.update(statut="publiee", publiee_le=iso())
            if texte.startswith("https://"):
                v["lien_tiktok"] = texte[:300]
            noter(f"🚀 « {v['titre']} » marquée publiée sur TikTok.")
        elif action == "a_publier":
            v["statut"] = "a_publier"
            noter(f"↩️ « {v['titre']} » remise dans la file.")
        elif action == "ecarter":
            v["statut"] = "ecartee"
            noter(f"🛑 « {v['titre']} » écartée (ne sera pas publiée).")
        elif action == "legende":
            v["legende"] = texte.strip()[:300]
            noter(f"✏️ Légende de « {v['titre']} » modifiée.")
        elif action == "supprimer":
            depot.supprimer_release(v.get("tag"))
            mini = os.path.join(MINIATURES, f"{v['id']}.jpg")
            if os.path.exists(mini):
                os.remove(mini)
            file["videos"].remove(v)
            noter(f"🗑️ « {v['titre']} » supprimée.")
        ecrire("file.json", file)
    elif action == "personnage":
        appliquer_personnage(json.loads(texte))
    elif action == "reglages":
        appliquer_reglages(json.loads(texte))
    elif action in ("pause", "reprise"):
        R = reglages()
        R["planning"]["pause"] = action == "pause"
        ecrire("reglages.json", R)
        noter("⏸️ Robot mis en pause." if action == "pause" else "▶️ Robot relancé.")
    elif action == "portrait_pret":                          # étape interne de « portrait »
        shutil.copy(texte, os.path.join(DONNEES, "portrait.jpg"))
    else:
        raise ValueError(f"action inconnue : {action}")


def appliquer_personnage(d):
    P = personnage()
    for k, n in CHAMPS_PERSO.items():
        if k in d and str(d[k]).strip():
            P[k] = int(d[k]) if k == "age" else str(d[k]).strip()[:n]
    if isinstance(d.get("gags_recurrents"), list):
        P["gags_recurrents"] = [str(g).strip()[:150] for g in d["gags_recurrents"] if str(g).strip()][:8]
    ecrire("personnage.json", P)
    noter("🎭 Fiche du personnage modifiée. Pense à régénérer le portrait si son apparence a changé.")


def appliquer_reglages(d):
    R = reglages()
    pl = R["planning"]
    if "plafond_mensuel_usd" in d:
        R["budget"]["plafond_mensuel_usd"] = max(1.0, min(200.0, float(d["plafond_mensuel_usd"])))
    if "courte_chaque_jour" in d:
        pl["courte_chaque_jour"] = bool(d["courte_chaque_jour"])
    if "jours_longue" in d:
        pl["jours_longue"] = [j for j in JOURS if j in d["jours_longue"]]
    if "heures_publication" in d:
        h = sorted({int(x) for x in d["heures_publication"] if 0 <= int(x) <= 23})
        pl["heures_publication"] = h or pl["heures_publication"]
    if "sous_titres" in d:
        R["montage"]["sous_titres"] = bool(d["sous_titres"])
    ecrire("reglages.json", R)
    noter(f"⚙️ Réglages modifiés (plafond {R['budget']['plafond_mensuel_usd']:.0f} $/mois).")


def portrait():
    """Régénère le portrait de référence (payant : une image)."""
    R, P = reglages(), personnage()
    caisse = budget.Caisse(R, "portrait")
    os.makedirs(SORTIE, exist_ok=True)
    dest = os.path.join(SORTIE, "portrait.jpg")
    try:
        principal.fabriquer_portrait(R, P, caisse, dest)
    except Exception as e:
        depot.enregistrer(lambda: (budget.ajouter(R, caisse.lignes), noter(f"❌ Portrait pas refait : {e}", "erreur")),
                          "Robot : portrait raté")
        return 1

    def ranger():
        budget.ajouter(reglages(), caisse.lignes)
        appliquer("portrait_pret", "", dest)
        noter(f"🖼️ Nouveau portrait de {P['nom']} ({caisse.depense:.2f} $).")
    depot.enregistrer(ranger, "Robot : nouveau portrait")
    return 0


def main():
    action, vid, texte = os.environ.get("ACTION", ""), os.environ.get("ID", ""), os.environ.get("TEXTE", "")
    if action == "portrait":
        return portrait()
    depot.enregistrer(lambda: appliquer(action, vid, texte), f"Site : {action} {vid}".strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
