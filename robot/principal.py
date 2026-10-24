"""Le robot : écrit un épisode, fait filmer chaque plan par Grok Imagine, monte la vidéo et la range dans la file.

    python -m robot.principal --format auto        (réveil programmé : fabrique ce que le planning prévoit)
    python -m robot.principal --format courte --idee "…"
    SIMULATION=1 python -m robot.principal --format longue     (test gratuit : aucune IA appelée)
"""
import argparse
import os
import shutil
import sys
import traceback

from . import budget, depot, grok, montage, planning, scenario
from .commun import MINIATURES, SORTIE, DONNEES, ecrire, iso, lire, maintenant, noter, personnage, reglages, simulation


def portrait_present():
    return os.path.exists(os.path.join(DONNEES, "portrait.jpg"))


def fabriquer_portrait(R, P, caisse, dest):
    """Portrait de référence du personnage : il sert de point de départ à chaque plan (même visage partout)."""
    caisse.autoriser(R["prix"]["image"], "portrait")
    prompt = (f"Photorealistic vertical portrait photo of a fictional man: {P['apparence']}. "
              f"Looking at the camera, neutral background, soft daylight, sharp face, upper body visible, no text.")
    _, cout = grok.creer_image(R["modeles"]["image"], prompt, dest, R["prix"]["image"])
    caisse.payer(cout, "portrait du personnage")
    return dest


def fabriquer(format_, idee="", remplace="", auto=False):
    """Fabrique une vidéo. Renvoie toujours un « résultat » à enregistrer (même en cas d'échec : les dépenses comptent)."""
    R, P = reglages(), personnage()
    now = maintenant()
    vid = now.strftime("%Y%m%d-%H%M%S") + "-" + format_[0]
    dossier = os.path.join(SORTIE, vid)
    os.makedirs(dossier, exist_ok=True)
    caisse = budget.Caisse(R, vid)
    res = {"id": vid, "format": format_, "auto": auto, "remplace": remplace, "caisse": caisse,
           "evenements": [], "entree": None, "portrait": None}
    try:
        prevu = budget.estimation(format_, R)
        caisse.autoriser(prevu, f"vidéo {format_}")          # on ne commence pas une vidéo qu'on ne pourra pas finir
        # 1. le portrait de référence
        portrait = os.path.join(DONNEES, "portrait.jpg")
        if not portrait_present():
            portrait = fabriquer_portrait(R, P, caisse, os.path.join(dossier, "portrait.jpg"))
            res["portrait"] = None if simulation() else portrait    # un faux portrait de test n'est jamais gardé
        # 2. le scénario
        deja = [v.get("titre", "") for v in (lire("file.json") or {}).get("videos", [])]
        caisse.autoriser(R["prix"]["scenario"], "scénario")
        ep, cout = scenario.ecrire(format_, P, R, idee, deja)
        caisse.payer(cout, "scénario")
        print(f"Épisode : {ep['titre']}", flush=True)
        # 3. chaque plan : une image de départ (le personnage dans le décor) puis le clip filmé
        secondes = R["formats"][format_]["secondes_par_clip"]
        clips = []
        for i, plan in enumerate(ep["plans"], 1):
            clips.append(filmer_plan(R, P, plan, i, secondes, portrait, dossier, caisse))
            print(f"  plan {i}/{len(ep['plans'])} filmé ({caisse.depense:.2f} $ jusqu'ici)", flush=True)
        # 4. montage, miniature, rangement dans une Release
        video = os.path.join(dossier, f"{vid}.mp4")
        duree = montage.monter(clips, ep["plans"], video, R["montage"].get("sous_titres", True))
        mini = montage.miniature(video, os.path.join(dossier, f"{vid}.jpg"))
        url = depot.publier_release(f"v-{vid}", ep["titre"], [video])
        res["miniature"] = mini
        res["entree"] = {
            "id": vid, "format": format_, "titre": ep["titre"], "legende": ep["legende"], "hashtags": ep["hashtags"],
            "duree": duree, "cout_usd": caisse.depense, "cree_le": iso(now), "statut": "a_publier",
            "url": url, "tag": f"v-{vid}", "miniature": f"miniatures/{vid}.jpg", "auto": auto,
            "simulation": simulation(), "idee": idee, "plans": ep["plans"]}
        res["evenements"].append(("info", f"✅ « {ep['titre']} » prête ({format_}, {duree:.0f} s, {caisse.depense:.2f} $)"
                                          + (" — test gratuit" if simulation() else "")))
    except budget.PlafondAtteint as e:
        res["evenements"].append(("alerte", f"⏸️ Vidéo {format_} pas fabriquée : {e}. Reprise le 1er du mois "
                                            f"(ou monte le plafond dans Réglages)."))
    except grok.ErreurGrok as e:
        res["evenements"].append(("erreur", f"❌ Vidéo {format_} ratée : {e}"))
    except Exception as e:                                   # erreur imprévue : on garde la trace et les dépenses
        traceback.print_exc()
        res["evenements"].append(("erreur", f"❌ Vidéo {format_} ratée (erreur du robot) : {type(e).__name__}: {e}"))
    return res


def filmer_plan(R, P, plan, i, secondes, portrait, dossier, caisse):
    m, prix = R["modeles"], R["prix"]
    image = os.path.join(dossier, f"depart_{i}.jpg")
    caisse.autoriser(prix["image"], f"image du plan {i}")
    _, cout = grok.modifier_image(m["image"], scenario.prompt_image(plan, P), portrait, image, prix["image"])
    caisse.payer(cout, f"image du plan {i}")
    dest = os.path.join(dossier, f"clip_{i}.mp4")
    for essai in (1, 2):
        caisse.autoriser(secondes * prix["video_seconde"], f"clip du plan {i}")
        try:
            _, cout = grok.creer_video(m["video"], scenario.prompt_video(plan, P), image, secondes, dest,
                                       prix["video_seconde"], R["montage"].get("resolution", "720p"))
            caisse.payer(cout, f"clip {secondes} s (plan {i})")
            return dest
        except grok.RefusModeration as e:
            caisse.payer(e.cout, f"clip refusé par la modération (plan {i})")
            if essai == 2:
                raise
            plan = dict(plan, action="looks at the camera and talks calmly, deadpan expression",
                        camera="static selfie framing")
            print(f"  plan {i} refusé par la modération : nouvel essai plus sobre", flush=True)


def ranger(res):
    """Écrit le résultat dans les données du site (appelé sur la dernière version du dépôt)."""
    R = reglages()
    budget.ajouter(R, res["caisse"].lignes)
    if res.get("portrait"):
        shutil.copy(res["portrait"], os.path.join(DONNEES, "portrait.jpg"))
    file = lire("file.json") or {"videos": []}
    if res["entree"]:
        e = res["entree"]
        e["publier_le"] = planning.creneau(R, file, e["format"])
        os.makedirs(MINIATURES, exist_ok=True)
        shutil.copy(res["miniature"], os.path.join(MINIATURES, f"{e['id']}.jpg"))
        for v in file["videos"]:
            if v["id"] == res["remplace"] and v["statut"] == "a_publier":
                v["statut"] = "remplacee"
        file["videos"].insert(0, e)
        ecrire("file.json", file)
    elif res["auto"]:                                        # échec du réveil automatique : compté pour ne pas boucler
        et = planning.etat()
        jour = maintenant().date().isoformat()
        et["essais"] = {jour: et.get("essais", {}).get(jour, {})}
        et["essais"][jour][res["format"]] = et["essais"][jour].get(res["format"], 0) + 1
        ecrire("etat.json", et)
    for niveau, texte in res["evenements"]:
        noter(texte, niveau)


def main(argv=None):
    a = argparse.ArgumentParser()
    a.add_argument("--format", default="auto", choices=["auto", "courte", "longue"])
    a.add_argument("--idee", default="")
    a.add_argument("--remplace", default="")
    args = a.parse_args(argv)
    R = reglages()
    if args.format == "auto":
        if R["planning"].get("pause"):
            print("Mode manuel (Réglages du site) : aucune création automatique.")
            return 0
        formats = planning.a_faire(R, lire("file.json") or {"videos": []}, planning.etat())
        if not formats:
            print("Rien à fabriquer pour l'instant (déjà fait aujourd'hui, ou jour sans vidéo).")
            return 0
    else:
        formats = [args.format]
    echecs = 0
    for f in formats:
        res = fabriquer(f, args.idee, args.remplace, auto=args.format == "auto")
        depot.enregistrer(lambda: ranger(res), f"Robot : {res['entree']['titre'] if res['entree'] else 'essai ' + f}")
        echecs += res["entree"] is None
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
