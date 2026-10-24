"""Ordres envoyés depuis le site (boutons) : appliqués aux données puis enregistrés dans le dépôt.

    ACTION=publiee ID=… TEXTE=lien  python -m robot.commande
Actions : publiee, a_publier, ecarter, supprimer, legende, personnage, reglages, portrait, pause, reprise,
buffer_test, tiktok_maintenant, tiktok_programmer, annuler_programmation (publication par Buffer, voir publier.py).
"""
import json
import os
import shutil
import sys

from . import budget, depot, planning, principal, publier
from .commun import DONNEES, JOURS, MINIATURES, SORTIE, ecrire, iso, lire, noter, personnage, reglages

CHAMPS_PERSO = {"nom": 60, "age": 3, "ville": 120, "apparence": 600, "voix": 300, "personnalite": 600,
                "phrase_fetiche": 120, "ton": 200}


def _video(file, vid):
    for v in file["videos"]:
        if v["id"] == vid:
            return v
    raise ValueError(f"vidéo {vid} introuvable")


def appliquer(action, vid, texte):
    file = publier.mettre_a_jour(lire("file.json") or {"videos": []})
    if action in ("publiee", "a_publier", "ecarter", "legende", "supprimer"):
        v = _video(file, vid)
        if v.get("statut") == "programmee" and action in ("a_publier", "ecarter", "supprimer"):
            v.pop("buffer", None)                             # (la programmation Buffer a été annulée juste avant)
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
        noter("✋ Mode manuel : plus aucune création automatique (bouton Créer seulement)." if action == "pause"
              else "🤖 Mode automatique : le robot crée les vidéos du planning chaque matin.")
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
    if isinstance(d.get("publication"), dict):              # Réglages → Publication sur TikTok
        P_, pub = d["publication"], R.setdefault("publication", {"mode": "manuel", "compte": ""})
        if P_.get("mode") in ("manuel", "auto"):
            pub["mode"] = P_["mode"]
        if "compte" in P_:
            pub["compte"] = str(P_["compte"]).strip().lstrip("@")[:60]
    if isinstance(d.get("tiktok"), dict):                    # onglet TikTok du site
        t, T = d["tiktok"], R.setdefault("tiktok", {})
        if "profils" in t:
            from .sons_tiktok import lire_profils
            T["profils"] = lire_profils(t["profils"])
        if "auto" in t:
            T["auto"] = bool(t["auto"])
        if "jours" in t:
            T["jours"] = [j for j in JOURS if j in t["jours"]]
        if "duree_max" in t:
            T["duree_max"] = max(10, min(90, int(t["duree_max"])))
        if "gilbert" in t:
            T["gilbert"] = bool(t["gilbert"])
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


def buffer(action, vid):
    """Ordres qui passent par Buffer. L'appel à Buffer est fait UNE fois, avant l'enregistrement (qui peut se répéter)."""
    R = reglages()
    try:
        if action == "buffer_test":
            comptes = publier.comptes_tiktok()
            choisi = publier.compte(R)["nom"] if comptes else None

            def ok():
                R2 = reglages()
                R2.setdefault("publication", {"mode": "manuel", "compte": ""})["buffer_ok"] = bool(comptes)
                ecrire("reglages.json", R2)
                noter(f"🔗 Buffer répond. Comptes TikTok reliés : {', '.join(c['nom'] for c in comptes) or 'aucun'}"
                      + (f". Compte utilisé : {choisi}." if choisi else "."))
            depot.enregistrer(ok, "Site : vérification de Buffer")
            return 0
        v = _video(publier.mettre_a_jour(lire("file.json") or {"videos": []}), vid)
        if action in ("tiktok_maintenant", "tiktok_programmer"):
            quand = None
            if action == "tiktok_programmer":
                quand = v.get("publier_le") or planning.creneau(R, lire("file.json") or {"videos": []}, v["format"])
            b = publier.envoyer(v, R, quand)

            def ranger():
                f = lire("file.json") or {"videos": []}
                w = _video(f, vid)
                w["buffer"] = b
                if b["quand"]:
                    w.update(statut="programmee", publier_le=quand)
                    noter(f"📅 « {w['titre']} » programmée sur TikTok ({b['compte']}) pour le {quand[8:10]}/{quand[5:7]} à {quand[11:16]}.")
                else:
                    w.update(statut="publiee", publiee_le=iso())
                    noter(f"🚀 « {w['titre']} » envoyée sur TikTok ({b['compte']}) : en ligne d'ici quelques minutes.")
                if not b["etiquette_ia"]:
                    noter("⚠️ Buffer a refusé l'étiquette IA : coche « Contenu généré par l'IA » dans l'appli TikTok.", "alerte")
                ecrire("file.json", f)
            depot.enregistrer(ranger, f"Site : {action} {vid}")
            return 0
        if v.get("statut") == "programmee" and (v.get("buffer") or {}).get("id"):   # annuler, écarter, supprimer
            publier.annuler(v["buffer"]["id"])
        suite = {"annuler_programmation": "a_publier"}.get(action, action)
        depot.enregistrer(lambda: appliquer(suite, vid, ""), f"Site : {action} {vid}")
        return 0
    except publier.ErreurBuffer as e:
        depot.enregistrer(lambda: noter(f"❌ Publication TikTok : {e}", "erreur"), "Site : erreur Buffer")
        return 1


def main():
    action, vid, texte = os.environ.get("ACTION", ""), os.environ.get("ID", ""), os.environ.get("TEXTE", "")
    if action == "portrait":
        return portrait()
    programmee = False
    if vid and action in ("ecarter", "supprimer"):
        try:
            programmee = _video(lire("file.json") or {"videos": []}, vid).get("statut") == "programmee"
        except ValueError:
            pass
    if action in ("buffer_test", "tiktok_maintenant", "tiktok_programmer", "annuler_programmation") or programmee:
        return buffer(action, vid)
    depot.enregistrer(lambda: appliquer(action, vid, texte), f"Site : {action} {vid}".strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
