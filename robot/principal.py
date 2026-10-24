"""Le robot : écrit un épisode, fait filmer chaque plan par Grok Imagine, monte la vidéo et la range dans la file.

    python -m robot.principal --format auto        (réveil programmé : fabrique ce que le planning prévoit)
    python -m robot.principal --format courte --idee "…"
    SIMULATION=1 python -m robot.principal --format longue     (test gratuit : aucune IA appelée)
"""
import argparse
import os
import shutil
import sys
import time
import traceback

from . import avancement, budget, depot, grok, montage, planning, production, publier, scenario, sons_tiktok
from .commun import MINIATURES, SORTIE, DONNEES, ecrire, iso, lire, maintenant, noter, personnage, reglages, simulation


def chemin_portrait(ident="gilbert"):
    """Portrait de référence : Gilbert dans donnees/portrait.jpg, chaque personnage secondaire dans donnees/portraits/."""
    return os.path.join(DONNEES, "portrait.jpg") if ident in ("", "gilbert") else os.path.join(DONNEES, "portraits", f"{ident}.jpg")


def portrait_present(ident="gilbert"):
    return os.path.exists(chemin_portrait(ident))


def fabriquer_portrait(R, c, caisse, dest):
    """Portrait de référence d'un personnage : il sert de point de départ à chacun de ses plans (même visage partout)."""
    caisse.autoriser(R["prix"]["image"], f"portrait de {c['nom']}")
    prompt = (f"Photorealistic vertical portrait photo of a fictional person: {c['apparence']}. "
              f"Looking at the camera, neutral background, soft daylight, sharp face, upper body visible, no text.")
    _, cout = grok.creer_image(R["modeles"]["image"], prompt, dest, R["prix"]["image"])
    caisse.payer(cout, f"portrait de {c['nom']}")
    return dest


def fabriquer(format_, idee="", remplace="", auto=False, lien=""):
    """Fabrique une vidéo. Renvoie toujours un « résultat » à enregistrer (même en cas d'échec : les dépenses comptent)."""
    R, P = reglages(), personnage()
    now = maintenant()
    vid = now.strftime("%Y%m%d-%H%M%S") + "-" + format_[0]
    dossier = os.path.join(SORTIE, vid)
    os.makedirs(dossier, exist_ok=True)
    caisse = budget.Caisse(R, vid)
    avancement.demarrer(vid, format_)
    res = {"id": vid, "format": format_, "auto": auto, "remplace": remplace, "caisse": caisse,
           "evenements": [], "entree": None, "portraits": {}}
    try:
        if format_ != "tiktok":                              # (vidéo TikTok : estimée une fois la durée du son connue)
            caisse.autoriser(budget.estimation(format_, R), f"vidéo {format_}")   # on ne commence pas ce qu'on ne finira pas
        # 1. le portrait de référence
        portrait = os.path.join(DONNEES, "portrait.jpg")
        if not portrait_present() and format_ != "tiktok":       # (vidéos TikTok : personnages inventés, pas Gilbert)
            portrait = fabriquer_portrait(R, P, caisse, os.path.join(dossier, "portrait.jpg"))
            if not simulation():                             # un faux portrait de test n'est jamais gardé
                res["portraits"]["gilbert"] = portrait
        if format_ == "tiktok":
            return video_tiktok(res, R, caisse, dossier, lien)
        # 2. le scénariste écrit, le producteur relit et fait corriger AVANT de payer le tournage
        deja = [v.get("titre", "") for v in (lire("file.json") or {}).get("videos", [])]
        Q = R.get("qualite") or {}
        caisse.autoriser(R["prix"]["scenario"], "scénario")
        avancement.etape("Le scénariste écrit l'épisode", 4, "5 idées, il garde la plus drôle")
        t0 = time.time()
        ep, cout = scenario.ecrire(format_, P, R, idee, deja, production.memoire_texte())
        caisse.payer(cout, "scénario")
        print(f"  scénario écrit en {time.time() - t0:.0f} s", flush=True)
        avis_prod = None
        if Q.get("producteur", True):
            avancement.etape("Le producteur relit le scénario", 9, "continuité, logique, drôlerie", titre=ep["titre"])
            caisse.autoriser(R["prix"]["scenario"], "relecture du producteur")
            t0 = time.time()
            ep, avis_prod, cout = production.relire(R, ep, format_, P, scenario.nettoyer)
            caisse.payer(cout, "relecture du producteur")
            print(f"  relecture faite en {time.time() - t0:.0f} s", flush=True)
            print(f"  producteur : {avis_prod.get('note')}/100, {len(avis_prod['problemes'])} correction(s)", flush=True)
        print(f"Épisode : {ep['titre']} ({len(ep['plans'])} plans, {sum(p['duree'] for p in ep['plans'])} s)", flush=True)
        # 3. le tournage, plan par plan. Un plan qui prolonge le précédent démarre sur SA dernière image (scène continue) ;
        #    sinon il démarre sur une image faite à partir du portrait (ou de la dernière image de cette personne).
        avancement.etape("Préparation du tournage", 14, f"{len(ep['plans'])} plans, {sum(p['duree'] for p in ep['plans'])} s",
                         titre=ep["titre"])
        portraits = {"gilbert": portrait}
        for ident in sorted({v for p in ep["plans"] for v in p["visibles"]} - {"gilbert"}):   # secondaires à l'image
            c = scenario.qui({"personnage": ident}, P)
            portraits[ident] = chemin_portrait(ident)
            if not portrait_present(ident):
                portraits[ident] = fabriquer_portrait(R, c, caisse, os.path.join(dossier, f"portrait_{ident}.jpg"))
                if not simulation():
                    res["portraits"][ident] = portraits[ident]
        clips, scene, controles = [], None, []
        total_s, fait_s = sum(p["duree"] for p in ep["plans"]), 0
        prix = R["prix"]
        for i, plan in enumerate(ep["plans"], 1):
            gens, parleur = scenario.fiches_visibles(plan, P), scenario.qui(plan, P)
            base, part = 15 + 73 * fait_s / total_s, 73 * plan["duree"] / total_s       # le tournage = 15 à 88 %
            fait_s += plan["duree"]
            avancement.etape(f"Tournage du plan {i} sur {len(ep['plans'])}", base,
                             f"{', '.join(g['nom'].split(' (')[0] for g in gens)} · {plan['duree']} s")
            if plan["enchaine"] and scene:
                depart = scene                                       # la scène continue exactement
            else:                                                    # mêmes visages (portraits) et même lieu (scène)
                depart = os.path.join(dossier, f"depart_{i}.jpg")
                refs = ([scene] if scene else []) + [portraits[g["id"]] for g in gens]
                caisse.autoriser(prix["image"], f"image du plan {i}")
                _, cout = grok.modifier_image(R["modeles"]["image"], scenario.prompt_image(plan, gens, ep["bible"], bool(scene)),
                                              refs, depart, prix["image"])
                caisse.payer(cout, f"image du plan {i}")
            reserve = sum(q["duree"] * prix["video_seconde"] + (0 if q["enchaine"] else prix["image"])
                          + prix.get("verification", 0.01) for q in ep["plans"][i:]) + 0.05     # pour finir l'épisode
            clip, controle = tourner(R, Q, plan, gens, parleur, ep["bible"], depart, i, dossier, caisse, (base, part), reserve)
            clips.append(clip)
            controles.append(controle)
            scene = montage.derniere_image(clip, os.path.join(dossier, f"fin_{i}.jpg"))
            print(f"  plan {i}/{len(ep['plans'])} filmé ({caisse.depense:.2f} $ jusqu'ici)", flush=True)
        # 4. sous-titres calés sur la vraie voix (plus de coupe dans les blancs : l'action continue pendant les silences)
        avancement.etape("Sous-titres calés sur la voix", 89)
        clips, mots = rythmer(R, format_, clips, dossier, caisse)
        avancement.etape("Montage de la vidéo", 92)
        video = os.path.join(dossier, f"{vid}.mp4")
        duree = montage.monter(clips, ep["plans"], video, R["montage"].get("sous_titres", True), mots)
        # 5. le jury regarde la vidéo finie
        jury = None
        if Q.get("jury", True):
            avancement.etape("Le jury regarde la vidéo", 95)
            dit = " ".join(m["w"] for m_ in (mots or []) for m in m_)
            caisse.autoriser(R["prix"].get("verification", 0.01) * 2, "jury")
            jury, cout = production.juger(R, video, ep, dit, dossier)
            caisse.payer(cout, "avis du jury")
            print(f"  jury : {jury['note']}/100", flush=True)
        a_revoir = bool(jury and jury["note"] < int(Q.get("note_min", 65)))
        avancement.etape("Envoi de la vidéo sur le site", 97)
        mini = montage.miniature(video, os.path.join(dossier, f"{vid}.jpg"))
        url = depot.publier_release(f"v-{vid}", ep["titre"], [video])
        res["miniature"] = mini
        res["lecons"] = (jury or {}).get("lecons", [])
        res["entree"] = {
            "id": vid, "format": format_, "titre": ep["titre"], "legende": ep["legende"], "hashtags": ep["hashtags"],
            "duree": duree, "cout_usd": caisse.depense, "cree_le": iso(now), "statut": "a_publier",
            "url": url, "tag": f"v-{vid}", "miniature": f"miniatures/{vid}.jpg", "auto": auto,
            "simulation": simulation(), "idee": idee, "plans": ep["plans"], "bible": ep["bible"],
            "qualite": {"producteur": avis_prod, "scripte": controles, "jury": jury}, "a_revoir": a_revoir}
        res["evenements"].append(("alerte" if a_revoir else "info",
                                  f"{'🔎' if a_revoir else '✅'} « {ep['titre']} » prête ({format_}, {duree:.0f} s, "
                                  f"{caisse.depense:.2f} $)" + (f", note du jury {jury['note']}/100" if jury else "")
                                  + (" : à revoir avant de publier" if a_revoir else "")
                                  + (" — test gratuit" if simulation() else "")))
    except budget.PlafondAtteint as e:
        res["budget_bloque"] = True
        res["evenements"].append(("alerte", f"⏸️ Vidéo {format_} pas fabriquée : {e}. Reprise le 1er du mois "
                                            f"(ou monte le plafond dans Réglages)."))
    except grok.ErreurGrok as e:
        res["evenements"].append(("erreur", f"❌ Vidéo {format_} ratée : {e}"))
    except Exception as e:                                   # erreur imprévue : on garde la trace et les dépenses
        traceback.print_exc()
        res["evenements"].append(("erreur", f"❌ Vidéo {format_} ratée (erreur du robot) : {type(e).__name__}: {e}"))
    return res


def video_tiktok(res, R, caisse, dossier, lien):
    """Filière « Sons TikTok » (voir sons_tiktok.py)."""
    vid, now = res["id"], maintenant()
    file = lire("file.json") or {"videos": []}
    deja = {sons_tiktok.id_video(v.get("source", "")) for v in file.get("videos", [])} - {""}
    t = sons_tiktok.fabriquer(R, caisse, dossier, lien, deja, file)
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


def tourner(R, Q, plan, gens, parleur, bible, depart, i, dossier, caisse, zone=(0, 0), reserve=0.0):
    """Filme un plan, le fait vérifier par le scripte et le refait s'il a un défaut GRAVE (mauvaise personne, action ou effet
    absent, objet dans le mauvais état), seulement si le budget permet encore de finir l'épisode (`reserve`).
    Refus de la modération : un nouvel essai plus sobre. Renvoie (clip, contrôle)."""
    m, prix = R["modeles"], R["prix"]
    correction, controle, reprises = "", {"ok": None, "ecarts": [], "reprise": False}, int(Q.get("reprises_max", 1))
    base, part = zone

    def suivi(pc):                                               # pourcentage de Grok pendant qu'il filme
        avancement.progres(base + part * 0.85 * pc / 100,
                           f"Grok filme{' (reprise)' if controle['reprise'] else ''} : {int(pc)} %")
    for essai in range(1, 3 + reprises):
        dest = os.path.join(dossier, f"clip_{i}_{essai}.mp4")
        caisse.autoriser(plan["duree"] * prix["video_seconde"], f"clip du plan {i}")
        try:
            _, cout = grok.creer_video(m["video"], scenario.prompt_video(plan, gens, parleur, bible, correction), depart, plan["duree"],
                                       dest, prix["video_seconde"], R["montage"].get("resolution", "720p"), suivi=suivi)
            caisse.payer(cout, f"clip {plan['duree']} s (plan {i}{', reprise' if controle['reprise'] else ''})")
        except grok.RefusModeration as e:
            caisse.payer(e.cout, f"clip refusé par la modération (plan {i})")
            if essai >= 2:
                raise
            correction = "Keep it gentle and cartoonish-safe: no danger, nobody hurt, softer special effect."
            print(f"  plan {i} refusé par la modération : nouvel essai plus sobre", flush=True)
            continue
        if not Q.get("scripte", True) or controle["reprise"]:
            return dest, controle
        try:
            avancement.progres(base + part * 0.9, "Le scripte vérifie le plan")
            caisse.autoriser(prix.get("verification", 0.01), f"scripte du plan {i}")
            avis, cout = production.verifier_plan(R, dest, plan, gens, bible, dossier, i)
            caisse.payer(cout, f"scripte du plan {i}")
        except grok.ErreurGrok as e:
            print(f"  scripte indisponible ({e}) : plan gardé", flush=True)
            return dest, controle
        controle.update(ok=avis["ok"], ecarts=avis["ecarts"], grave=avis["grave"])
        if avis["ok"] or not avis["grave"] or reprises <= 0:      # défaut mineur : on garde le plan
            return dest, controle
        try:                                                     # le plan est refait, si le budget permet de finir quand même
            caisse.autoriser(plan["duree"] * prix["video_seconde"] + reserve, f"reprise du plan {i}")
        except budget.PlafondAtteint:
            print(f"  plan {i} imparfait, pas de reprise (le budget doit d'abord permettre de finir l'épisode)", flush=True)
            controle["sans_reprise_budget"] = True
            return dest, controle
        print(f"  plan {i} refait (scripte : {'; '.join(avis['ecarts'])[:200]})", flush=True)
        avancement.progres(base, "Plan refait (le scripte a vu un problème)")
        correction, controle["reprise"] = avis["correction"] or "; ".join(avis["ecarts"]), True
    return dest, controle


DUREE_MIN_LONGUE = 62          # TikTok ne rémunère que les vidéos de plus d'une minute : on garde de la marge


def rythmer(R, format_, clips, dossier, caisse):
    """Transcrit chaque clip (les sous-titres suivent alors la vraie voix) et coupe les blancs, comme un vlogueur qui
    monte sa vidéo. Une longue reste au-dessus d'une minute : on coupe moins si besoin. Renvoie (clips, mots par clip)."""
    if not R["montage"].get("couper_blancs", False) and not R["montage"].get("sous_titres", True):
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
    if not R["montage"].get("couper_blancs", False):
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
    for ident, chemin in (res.get("portraits") or {}).items():
        os.makedirs(os.path.dirname(chemin_portrait(ident)), exist_ok=True)
        shutil.copy(chemin, chemin_portrait(ident))
    if res.get("lecons"):
        production.ajouter_lecons(res["lecons"], "jury")
    file = publier.mettre_a_jour(lire("file.json") or {"videos": []})
    if res["entree"]:
        e = res["entree"]
        e["publier_le"] = e.get("publier_le") or planning.creneau(R, file, e["format"])
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


def programmer(res, R):
    """Publication automatique (Réglages) : la vidéo est programmée sur Buffer à l'heure conseillée."""
    e = res["entree"]
    if not e or simulation() or (R.get("publication") or {}).get("mode") != "auto":
        return
    if e.get("a_revoir"):
        res["evenements"].append(("alerte", f"🔎 « {e['titre']} » pas programmée sur TikTok : le jury la juge à revoir."))
        return
    quand = planning.creneau(R, lire("file.json") or {"videos": []}, e["format"])
    try:
        b = publier.envoyer(e, R, quand)
    except publier.ErreurBuffer as err:
        res["evenements"].append(("alerte", f"⚠️ « {e['titre']} » pas programmée sur TikTok : {err}. Elle t'attend dans « À publier »."))
        return
    e.update(buffer=b, publier_le=quand, statut="programmee" if b["quand"] else "publiee")
    if not b["quand"]:
        e["publiee_le"] = iso()
    res["evenements"].append(("info", f"📅 « {e['titre']} » programmée sur TikTok ({b['compte']}) pour le "
                                      f"{quand[8:10]}/{quand[5:7]} à {quand[11:16]}. Tu peux encore l'annuler sur le site."))
    if not b["etiquette_ia"]:
        res["evenements"].append(("alerte", "⚠️ Buffer a refusé l'étiquette IA : coche « Contenu généré par l'IA » dans TikTok."))


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
        programmer(res, R)
        avancement.etape("Rangement dans « À publier »", 98)
        depot.enregistrer(lambda: ranger(res), f"Robot : {res['entree']['titre'] if res['entree'] else 'essai ' + f}")
        avancement.finir(res["entree"] is not None, (f"« {res['entree']['titre']} » est prête" if res["entree"] else
                         "Création ratée : regarde le Journal") if not res.get("budget_bloque") else "Plafond du mois atteint")
        echecs += res["entree"] is None
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
