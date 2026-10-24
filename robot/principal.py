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

from . import budget, depot, grok, montage, planning, scenario, sons_tiktok
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


def fabriquer(format_, idee="", remplace="", auto=False, lien=""):
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
        if format_ != "tiktok":                              # (vidéo TikTok : estimée une fois la durée du son connue)
            caisse.autoriser(budget.estimation(format_, R), f"vidéo {format_}")   # on ne commence pas ce qu'on ne finira pas
        # 1. le portrait de référence
        portrait = os.path.join(DONNEES, "portrait.jpg")
        if not portrait_present() and (format_ != "tiktok" or (R.get("tiktok") or {}).get("gilbert", True)):
            portrait = fabriquer_portrait(R, P, caisse, os.path.join(dossier, "portrait.jpg"))
            res["portrait"] = None if simulation() else portrait    # un faux portrait de test n'est jamais gardé
        if format_ == "tiktok":
            return video_tiktok(res, R, P, caisse, dossier, lien, idee, portrait if os.path.exists(portrait) else None)
        # 2. le scénario
        deja = [v.get("titre", "") for v in (lire("file.json") or {}).get("videos", [])]
        caisse.autoriser(R["prix"]["scenario"], "scénario")
        ep, cout = scenario.ecrire(format_, P, R, idee, deja)
        caisse.payer(cout, "scénario")
        print(f"Épisode : {ep['titre']}", flush=True)
        # 3. chaque plan : une image de départ (le personnage dans le décor) puis le clip filmé.
        #    Même lieu que le plan d'avant : on repart de sa dernière image (mêmes objets, même lumière).
        secondes = R["formats"][format_]["secondes_par_clip"]
        clips, derniere = [], None
        for i, plan in enumerate(ep["plans"], 1):
            depart = derniere if plan.get("meme_lieu") and derniere else portrait
            clip = filmer_plan(R, P, plan, i, secondes, depart, dossier, caisse, ep.get("objets", []), depart is derniere)
            clips.append(clip)
            derniere = montage.derniere_image(clip, os.path.join(dossier, f"fin_{i}.jpg"))
            print(f"  plan {i}/{len(ep['plans'])} filmé ({caisse.depense:.2f} $ jusqu'ici)", flush=True)
        # 4. ce qui est vraiment dit dans chaque clip (sous-titres exacts), et coupe des blancs façon vlog
        clips, mots = rythmer(R, format_, clips, dossier, caisse)
        video = os.path.join(dossier, f"{vid}.mp4")
        duree = montage.monter(clips, ep["plans"], video, R["montage"].get("sous_titres", True), mots)
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


def video_tiktok(res, R, P, caisse, dossier, lien, idee, portrait):
    """Filière « Sons TikTok » (voir sons_tiktok.py)."""
    vid, now = res["id"], maintenant()
    deja = {sons_tiktok.id_video(v.get("source", "")) for v in (lire("file.json") or {}).get("videos", [])} - {""}
    t = sons_tiktok.fabriquer(R, P, caisse, dossier, lien, deja, portrait)
    video = os.path.join(dossier, f"{vid}.mp4")
    os.replace(t["video"], video)
    res["miniature"] = montage.miniature(video, os.path.join(dossier, f"{vid}.jpg"), min(1.5, t["duree"] / 2))
    url = depot.publier_release(f"v-{vid}", t["titre"], [video])
    res["entree"] = {
        "id": vid, "format": "tiktok", "titre": t["titre"], "legende": t["legende"], "hashtags": t["hashtags"],
        "duree": t["duree"], "cout_usd": caisse.depense, "cree_le": iso(now), "statut": "a_publier", "url": url,
        "tag": f"v-{vid}", "miniature": f"miniatures/{vid}.jpg", "auto": res["auto"], "simulation": simulation(),
        "idee": lien, "source": t["source"], "auteur": t["auteur"], "plans": t["plans"]}
    res["evenements"].append(("info", f"✅ « {t['titre']} » prête (son TikTok de @{t['auteur'] or '?'}, {t['duree']:.0f} s, "
                                      f"{caisse.depense:.2f} $)" + (" — test gratuit" if simulation() else "")))
    return res


def filmer_plan(R, P, plan, i, secondes, depart, dossier, caisse, objets=(), suite=False):
    m, prix = R["modeles"], R["prix"]
    image = os.path.join(dossier, f"depart_{i}.jpg")
    caisse.autoriser(prix["image"], f"image du plan {i}")
    _, cout = grok.modifier_image(m["image"], scenario.prompt_image(plan, P, objets, suite), depart, image, prix["image"])
    caisse.payer(cout, f"image du plan {i}")
    dest = os.path.join(dossier, f"clip_{i}.mp4")
    for essai in (1, 2):
        caisse.autoriser(secondes * prix["video_seconde"], f"clip du plan {i}")
        try:
            _, cout = grok.creer_video(m["video"], scenario.prompt_video(plan, P, objets), image, secondes, dest,
                                       prix["video_seconde"], R["montage"].get("resolution", "720p"))
            caisse.payer(cout, f"clip {secondes} s (plan {i})")
            return dest
        except grok.RefusModeration as e:
            caisse.payer(e.cout, f"clip refusé par la modération (plan {i})")
            if essai == 2:
                raise
            plan = dict(plan, action="looks at the camera and talks calmly, deadpan expression",
                        cadrage="selfie, medium close-up")
            print(f"  plan {i} refusé par la modération : nouvel essai plus sobre", flush=True)


DUREE_MIN_LONGUE = 62          # TikTok ne rémunère que les vidéos de plus d'une minute : on garde de la marge


def rythmer(R, format_, clips, dossier, caisse):
    """Transcrit chaque clip (les sous-titres suivent alors la vraie voix) et coupe les blancs, comme un vlogueur qui
    monte sa vidéo. Une longue reste au-dessus d'une minute : on coupe moins si besoin. Renvoie (clips, mots par clip)."""
    if not R["montage"].get("couper_blancs", True) and not R["montage"].get("sous_titres", True):
        return clips, None
    mots, durees = [], [montage.duree(c) for c in clips]
    for i, c in enumerate(clips, 1):
        try:
            caisse.autoriser(0.01, f"transcription du plan {i}")
            m_, cout = grok.transcrire(c, R["prix"].get("transcription_heure", 0.10))
            caisse.payer(cout, f"transcription du plan {i}")
        except grok.ErreurGrok as e:                       # sans transcription : sous-titres estimés, pas de coupe
            print(f"  transcription impossible ({e}) : sous-titres estimés", flush=True)
            return clips, None
        mots.append(m_)
    if not R["montage"].get("couper_blancs", True):
        return clips, mots
    for blanc_max in (0.45, 0.8, 1.5, None):
        if blanc_max is None:
            return clips, mots                             # même sans couper, trop court : on garde tout
        inter = [montage.intervalles_parole(m_, d, blanc_max, fin_en_plus=0.6 if k == len(clips) - 1 else 0.0)
                 for k, (m_, d) in enumerate(zip(mots, durees))]
        total = sum(b - a for iv in inter for a, b in iv)
        if format_ != "longue" or total >= DUREE_MIN_LONGUE:
            break
    out = [montage.couper(c, iv, os.path.join(dossier, f"coupe_{k}.mp4")) for k, (c, iv) in enumerate(zip(clips, inter), 1)]
    print(f"  blancs coupés : {sum(durees):.1f} s → {total:.1f} s", flush=True)
    return out, [montage.recaler(m_, iv) for m_, iv in zip(mots, inter)]


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
    a.add_argument("--format", default="auto", choices=["auto", "courte", "longue", "tiktok"])
    a.add_argument("--lien", default="", help="vidéo TikTok (format tiktok) ; vide ou « hasard » = au hasard des profils")
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
        res = fabriquer(f, args.idee, args.remplace, auto=args.format == "auto", lien=args.lien)
        depot.enregistrer(lambda: ranger(res), f"Robot : {res['entree']['titre'] if res['entree'] else 'essai ' + f}")
        echecs += res["entree"] is None
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
