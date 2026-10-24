"""La salle de production de Gilbert : contrôle qualité du scénario jusqu'à la vidéo finie.

1. Le PRODUCTEUR relit le scénario AVANT le tournage (logique, continuité des objets et des personnes, expérience montrée en
   entier, drôlerie, durée) et le fait corriger : c'est là qu'on évite les incohérences, avant de payer la vidéo.
2. Le SCRIPTE regarde chaque plan juste après le tournage (première, milieu et dernière image) et vérifie qu'il correspond
   au découpage ; sinon le plan est retourné une fois avec des corrections, si le budget le permet.
3. Le JURY regarde la vidéo finie (images + texte réellement dit) : humour, continuité, image, son, une note sur 100 et des
   remarques. Sous la note minimale, la vidéo est marquée « à revoir » et n'est jamais publiée automatiquement.
4. La MÉMOIRE garde les leçons (remarques du jury et avis de l'auteur sur le site) ; le scénariste et le producteur les
   relisent avant chaque nouvel épisode.
"""
import json
import os
import subprocess

from . import grok, montage, scenario
from .commun import ecrire, iso, lire, simulation

# ---------------------------------------------------------------- mémoire des leçons
def memoire_texte(n=12):
    """Les dernières leçons, à glisser dans les consignes du scénariste et du producteur."""
    lecons = (lire("memoire.json") or {}).get("lecons", [])[:n]
    if not lecons:
        return ""
    return ("\nLEÇONS DES ÉPISODES PRÉCÉDENTS (à respecter absolument) :\n"
            + "\n".join(f"- ({l.get('source', '?')}) {l['texte']}" for l in lecons) + "\n")


def ajouter_lecons(textes, source):
    m = lire("memoire.json") or {"lecons": []}
    deja = {l["texte"] for l in m["lecons"]}
    for t in textes:
        t = str(t).strip()[:300]
        if t and t not in deja:
            m["lecons"].insert(0, {"date": iso(), "source": source, "texte": t})
    del m["lecons"][60:]
    ecrire("memoire.json", m)


# ---------------------------------------------------------------- 1. le producteur
PRODUCTEUR = """Tu es le producteur exigeant d'une mini-série TikTok réaliste. Les auteurs t'apportent une ou plusieurs
versions de l'épisode : garde celle qui est la plus drôle ET la plus facile à filmer (chute qui fait rire même sans le son,
effet spectaculaire que la caméra IA sait filmer). Avant le tournage (qui coûte cher), tu relis cette version et tu la
corriges pour qu'il n'y ait AUCUN problème une fois filmé. Le tournage se fait plan par plan avec
une IA vidéo qui ne voit que la consigne de chaque plan : tout doit y être écrit noir sur blanc.

Vérifie un par un :
1. L'expérience se voit en entier et dans l'ordre (enjeu, lancement, effet spectaculaire, ce qui foire, chute). Aucun
   résultat n'apparaît avant l'action qui le cause. L'effet est assez grand et « waouh ».
2. Continuité : la "fin" de chaque plan correspond exactement au "debut" du suivant ; chaque objet garde le même aspect et
   le même état d'un plan à l'autre tant qu'on ne voit pas ce qui le change ; personnes au bon endroit.
3. Tout ce qui est dit est vu ou entendu (un personnage nommé comme présent est à l'image ou on l'entend).
4. "deroule" est assez précis pour être filmé (gestes, effet, réactions) et tient dans la durée du plan.
5. Les répliques ("repliques" : qui, moment "t", texte) tiennent dans le plan (en tout au plus 2,3 mots par seconde),
   chacune dans son créneau, assez courtes pour être dites EN ENTIER. Quand deux personnages sont là, ils se répondent
   vraiment (question, réponse, réaction), pas deux monologues. La chute est vraiment drôle.
5 bis. L'effet est FILMABLE : s'il est dans la liste « marche mal », remplace-le par un effet de la liste « marche bien »
   qui garde le gag (voir ci-dessous).
6. "enchaine" n'est vrai que si le plan prolonge le précédent avec la même personne à l'image.
7. Personnages : leur apparence vient UNIQUEMENT de leurs fiches ci-dessous. Ne la réécris jamais dans les plans (seulement
   leur nom et leur position) et n'invente jamais une autre apparence. "visibles" liste les ids des personnes à l'image ;
   chacun garde sa place d'un plan à l'autre sauf si on le voit bouger.
   Au plus UN personnage secondaire dans l'épisode (Newton le chien en plus si utile) : retire les autres.
8. Règles : pas de « Doc », « Marty », « McFly », « Biff », « DeLorean », « convecteur temporel », pas de titre de film,
   pas de vraie personne, pas d'enfant.

{effets}
FICHES DES PERSONNAGES (id : nom, apparence)
{fiches}
{memoire}
Réponds uniquement en JSON :
{{"version": numéro de la version gardée (1 = première), "pourquoi": "pourquoi celle-là, en une phrase",
 "note": 0-100, "problemes": ["chaque problème trouvé, en français"],
 "scenario": {{la version gardée, complète et corrigée, même format}}}}
Si tout est parfait, renvoie quand même le scénario (inchangé)."""


def relire(R, ep, format_, perso, nettoyer):
    """Renvoie (episode corrigé, avis du producteur, coût)."""
    versions = [dict(ep, autres=None)] + list(ep.get("autres") or [])
    for v in versions:
        v.pop("autres", None)
    if simulation():
        return versions[0], {"note": 90, "problemes": [], "version": 1, "versions": len(versions)}, 0.0
    demande = "\n\n".join(f"VERSION {k + 1} :\n" + json.dumps(v, ensure_ascii=False) for k, v in enumerate(versions))
    fiches = "\n".join(f"- {c.get('id', 'gilbert')} : {c['nom']}, {c.get('age', '?')} ans, {c['apparence']}"
                       for c in [dict(perso, id="gilbert")] + perso.get("secondaires", []))
    rep, cout = grok.ecrire_json(R["modeles"].get("producteur", R["modeles"]["texte"]),
                                 PRODUCTEUR.format(memoire=memoire_texte(), fiches=fiches,
                                                   effets=scenario.EFFETS), demande, R["prix"]["scenario"])
    try:
        k = max(1, min(len(versions), int(rep.get("version") or 1)))
    except (TypeError, ValueError):
        k = 1
    choisie = versions[k - 1]
    avis = {"note": rep.get("note"), "problemes": [str(p)[:300] for p in rep.get("problemes") or []][:12],
            "version": k, "versions": len(versions), "pourquoi": str(rep.get("pourquoi") or "")[:300]}
    corrige = rep.get("scenario")
    if isinstance(corrige, dict) and corrige.get("plans"):
        try:
            ep2 = nettoyer(dict(choisie, **corrige), R["formats"][format_], perso)
            for cle in ("choix", "chute", "image_cle", "effet"):
                ep2[cle] = ep2.get(cle) or choisie.get(cle, "")
            return ep2, avis, cout
        except grok.ErreurGrok:
            pass
    return choisie, avis, cout


# ---------------------------------------------------------------- 2. le scripte
SCRIPTE = """Tu es le scripte d'un tournage. Tu reçois 3 images d'un plan qui vient d'être filmé (première, milieu, dernière),
la fiche des personnes qui doivent être à l'image (leur apparence officielle fait foi) et ce que le plan devait montrer.
Un défaut est GRAVE seulement s'il casse l'histoire ou la continuité pour un spectateur : mauvaise personne ou visage /
tenue différents de la fiche, personne en trop ou manquante, action ou effet spécial prévu absent, objet important dans le
mauvais état (déjà cassé, disparu), texte incrusté. Une pose de main, un regard, un détail de cadrage ou un petit objet
secondaire sont des défauts MINEURS : on garde le plan.
Si l'effet spécial prévu ne se voit pas, c'est sans doute que la caméra IA ne sait pas le faire : la correction le remplace
par un effet SIMPLE, GROS et SOUDAIN (gros nuage de fumée, pluie d'étincelles, jet d'eau, explosion de farine) qui garde
l'idée, au lieu de redemander le même effet.
Réponds uniquement en JSON : {"ok": true ou false, "grave": true ou false,
"type": "effet" | "personne" | "objet" | "continuite" | "texte" (le défaut grave principal), "ecarts": ["problèmes en français"],
"correction": "instructions précises en ANGLAIS pour refaire le plan (seulement les défauts graves), vide si ok"}"""


def images(video, dossier, nom, instants):
    out = []
    for k, t in enumerate(instants):
        dest = os.path.join(dossier, f"{nom}_{k}.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0.0, t):.2f}", "-i", video, "-frames:v", "1",
                        "-vf", "scale=360:-2", "-q:v", "5", dest])
        if os.path.exists(dest):
            out.append(dest)
    return out


def verifier_plan(R, clip, plan, gens, bible, dossier, i):
    """Avis du scripte sur un plan filmé : (avis, coût)."""
    if simulation():
        return {"ok": True, "grave": False, "type": "", "ecarts": [], "correction": ""}, 0.0
    d = montage.duree(clip)
    vues = images(clip, dossier, f"scripte_{i}", [0.1, d / 2, d - 0.15])
    demande = ("Personnes à l'image (fiches officielles) : " + " ; ".join(f"{c['nom']} : {c['apparence']}" for c in gens)
               + f".\nLieu : {bible['lieu']}.\n"
               f"Objets : {json.dumps(bible['objets'], ensure_ascii=False)}\nDébut prévu : {plan['debut']}\n"
               f"Déroulé prévu : {' '.join(plan['deroule'])}\nFin prévue : {plan['fin']}")
    rep, cout = grok.ecrire_json(R["modeles"].get("vision", R["modeles"]["texte"]), SCRIPTE, demande,
                                 R["prix"].get("verification", 0.01), images=vues)
    ok = bool(rep.get("ok", True))
    type_ = str(rep.get("type") or "autre").lower()
    return {"ok": ok, "grave": (not ok) and bool(rep.get("grave", True)),
            "type": type_ if type_ in ("effet", "personne", "objet", "continuite", "texte") else "autre",
            "ecarts": [str(e)[:200] for e in rep.get("ecarts") or []][:6],
            "correction": str(rep.get("correction") or "")[:600]}, cout


# ---------------------------------------------------------------- 1 bis. le storyboard, vérifié avant de filmer
STORYBOARD = """Tu es le producteur. Avant de payer le tournage, tu regardes le STORYBOARD : une image par plan (la première image
de chaque plan, dans l'ordre), avec le découpage et les fiches des personnages. Un spectateur doit voir UNE scène continue.
Vérifie d'une image à l'autre : mêmes visages et mêmes tenues que les fiches, même lieu, mêmes objets (même aspect), l'état
de chaque objet colle au moment de l'histoire (rien n'est déjà cassé ou disparu avant l'action qui le cause), chacun à sa
place, pas de personne en trop, pas de texte. Ignore les petits détails (pose des mains, regard).
Réponds uniquement en JSON : {"ok": true ou false, "problemes": [{"plan": numéro du plan (1 = premier), "probleme": "en
français", "correction": "instructions précises en ANGLAIS pour refaire cette image"}]}"""


def verifier_storyboard(R, images_plans, ep, perso):
    """Avis du producteur sur le storyboard : (avis, coût). avis["problemes"] = [{plan, probleme, correction}]."""
    if simulation():
        return {"ok": True, "problemes": []}, 0.0
    fiches = " ; ".join(f"{c['nom']} : {c['apparence']}" for c in [perso] + perso.get("secondaires", [])
                        if c is perso or any(c.get("id") in p["visibles"] for p in ep["plans"]))
    demande = (f"Fiches : {fiches}\nLieu : {ep['bible']['lieu']}\nObjets : {json.dumps(ep['bible']['objets'], ensure_ascii=False)}\n"
               + "\n".join(f"Plan {k + 1} (image {k + 1}) — début : {p['debut']}" for k, p in enumerate(ep["plans"])))
    rep, cout = grok.ecrire_json(R["modeles"].get("vision", R["modeles"]["texte"]), STORYBOARD, demande,
                                 R["prix"].get("verification", 0.01) * 2, images=images_plans)
    problemes = []
    for x in rep.get("problemes") or []:
        try:
            k = int(x.get("plan"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 1 <= k <= len(ep["plans"]):
            problemes.append({"plan": k, "probleme": str(x.get("probleme") or "")[:250],
                              "correction": str(x.get("correction") or "")[:500]})
    return {"ok": bool(rep.get("ok", not problemes)) and not problemes, "problemes": problemes[:6]}, cout


# ---------------------------------------------------------------- 3. le jury
JURY = """Tu es le jury de critiques d'une mini-série TikTok réaliste (un humoriste, un réalisateur, un scripte et un
spectateur de TikTok). Tu reçois des images de la vidéo finie, dans l'ordre (avec leur moment), le moment de chaque plan
et le texte réellement prononcé. Juge ce que VIT LE SPECTATEUR, pas l'écart avec le découpage prévu : une scène différente
du plan mais drôle et cohérente est réussie. Le texte prononcé est exactement ce qu'affichent les sous-titres : ne pénalise
pas une phrase parce qu'elle diffère du découpage, seulement si elle est coupée, incompréhensible ou pas drôle. Juge sans
complaisance : un spectateur de TikTok doit rire et ne rien remarquer de bizarre.
Notes sur 100 : "humour" (accroche, échanges, chute), "continuite" (aucun trou, objets et personnes cohérents d'une image à
l'autre, l'expérience se voit en entier), "image" (réalisme, visages, effets), "son" (voix, texte compréhensible).
Si un plan précis fait baisser la note (effet raté, trou, visage changé), indique-le dans "plan_a_refaire" (numéro, 0 si
aucun) avec une "correction" précise en ANGLAIS pour le refaire.
Réponds uniquement en JSON : {"notes": {"humour": 0, "continuite": 0, "image": 0, "son": 0}, "note": 0,
"points_forts": ["…"], "remarques": ["défauts précis, en français"], "plan_a_refaire": 0, "correction": "...",
"lecons": ["1 ou 2 règles générales à retenir pour les prochains épisodes, en français"]}"""


def juger(R, video, ep, texte_dit, dossier):
    """Avis du jury sur la vidéo finie : (avis, coût)."""
    if simulation():
        return {"notes": {}, "note": 80, "points_forts": [], "remarques": [], "lecons": [], "plan_a_refaire": 0,
                "correction": ""}, 0.0
    d = montage.duree(video)
    instants = [d * (k + 0.5) / 8 for k in range(8)]
    vues = images(video, dossier, "jury_" + os.path.splitext(os.path.basename(video))[0], instants)
    total = sum(p["duree"] for p in ep["plans"]) or 1
    debut, moments = 0.0, []
    for k, p in enumerate(ep["plans"]):                       # durées prévues ramenées à la durée réelle
        fin = debut + p["duree"] * d / total
        moments.append(f"plan {k + 1} de {debut:.0f} à {fin:.0f} s : {' '.join(p['deroule'])}")
        debut = fin
    demande = (f"Titre : {ep['titre']}\nIdée : {ep.get('choix', '')}\nChute voulue : {ep.get('chute', '')}\n"
               f"Texte réellement prononcé (= sous-titres) : {texte_dit or '(inconnu)'}\n"
               f"Images envoyées, dans l'ordre, aux moments : {', '.join(f'{t:.0f} s' for t in instants)}\n"
               f"Plans : " + " | ".join(moments))
    rep, cout = grok.ecrire_json(R["modeles"].get("vision", R["modeles"]["texte"]), JURY, demande,
                                 R["prix"].get("verification", 0.01) * 2, images=vues)
    notes = rep.get("notes") if isinstance(rep.get("notes"), dict) else {}
    try:
        note = int(rep.get("note"))
    except (TypeError, ValueError):
        vals = [v for v in notes.values() if isinstance(v, (int, float))]
        note = int(sum(vals) / len(vals)) if vals else 0
    return {"notes": {k: notes.get(k) for k in ("humour", "continuite", "image", "son")}, "note": note,
            "points_forts": [str(x)[:200] for x in rep.get("points_forts") or []][:4],
            "remarques": [str(x)[:250] for x in rep.get("remarques") or []][:6],
            "lecons": [str(x)[:250] for x in rep.get("lecons") or []][:2],
            "plan_a_refaire": _numero(rep.get("plan_a_refaire"), len(ep["plans"])),
            "correction": str(rep.get("correction") or "")[:600]}, cout


def _numero(x, n):
    try:
        k = int(x)
    except (TypeError, ValueError):
        return 0
    return k if 1 <= k <= n else 0
