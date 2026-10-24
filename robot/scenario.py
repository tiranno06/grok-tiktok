"""Le scénariste : écrit un épisode de Gilbert sous forme de découpage précis, prêt à filmer.

Chaque épisode a une « bible » (lieu, lumière, objets avec leur état) et des plans qui s'enchaînent sans trou :
pour chaque plan, l'état de départ, ce qui se passe seconde par seconde, l'état de fin (qui est le départ du plan suivant)
et la réplique en français. La durée totale dépend de l'idée (assez longue pour tout montrer, jamais de trou).
"""
import os
import random

from . import grok

CONSIGNES = """Tu es le scénariste d'une mini-série TikTok qui cartonne en France, filmée en images totalement réalistes,
comme de vraies vidéos tournées au téléphone. Le héros revient dans chaque épisode.

FICHE DU HÉROS
- Nom : {nom}, {age} ans, {ville}
- Apparence (pour la caméra) : {apparence}
- Voix : {voix}
- Personnalité : {personnalite}
- Phrase fétiche : « {phrase} » (seulement quand elle tombe bien)
- Répliques typiques (une ou deux par épisode au plus, adaptées à la situation) : {repliques}
- Gestes et mimiques : {gestuelle}
- Gags récurrents : {gags}
- Ton : {ton}

PERSONNAGES SECONDAIRES (ils reviennent d'un épisode à l'autre ; "id" entre crochets)
{secondaires}

L'EXPÉRIENCE DE L'ÉPISODE (le cœur de chaque vidéo)
- Une GRANDE expérience par épisode, spectaculaire et complètement débile, avec un vrai effet « waouh » visible à l'écran
  et des conséquences pour le village : téléporter la 2CV de Mat sur le toit de la mairie, rendre le clocher invisible
  sauf ses cloches, arrêter le temps pour tout le monde sauf Le Bouc, faire pleuvoir des grenouilles en chocolat sur la
  fête du village, agrandir Newton à la taille d'un cheval, inverser la gravité dans la cuisine de Laurence… Jamais une
  petite expérience banale (pas de baguette, pas de grille-pain qui grille).
- L'expérience se voit EN ENTIER, dans l'ordre : 1) l'enjeu et la machine, 2) le lancement (compte à rebours, manette,
  bouton, éclairs), 3) l'effet spectaculaire pendant qu'il se produit, 4) ce qui foire (visible), 5) la chute. On ne saute
  jamais une étape : le spectateur voit chaque chose arriver, aucun résultat n'apparaît avant l'action qui le cause.
- Ça foire presque toujours, de façon drôle et sans blessé : fumée, étincelles, cheveux électrisés, effet inverse,
  conséquence absurde. Parfois ça marche… pour de mauvaises raisons.

{effets}
CE QUI REND LE SKETCH DRÔLE
- Accroche dans les 2 premières secondes : la première phrase pose l'enjeu avec un sérieux total. Jamais « Bonjour ».
- Escalade, décalage image / parole (il dit « tout est sous contrôle », derrière ça explose), chute vraiment inattendue.
- Langue parlée naturelle, phrases courtes. Jamais de morale, jamais expliquer la blague.

CONTINUITÉ (le plus important : la vidéo doit être une scène continue, sans trou ni incohérence)
- "bible" : le lieu exact, la lumière, et chaque objet important décrit précisément en ANGLAIS (couleur, matière, forme)
  avec son état au début de l'épisode. Le lieu et les objets ne changent JAMAIS d'apparence, seulement d'état quand
  l'histoire le dit (entier → cassé).
- Chaque plan dit en ANGLAIS : "debut" = ce qu'on voit à la première image (position des personnes, état de chaque objet),
  "deroule" = ce qui se passe seconde par seconde ("0-3s: …", "3-6s: …"), "fin" = ce qu'on voit à la dernière image.
- La "fin" d'un plan est EXACTEMENT le "debut" du plan suivant. Un objet garde son état d'un plan à l'autre tant que le
  "deroule" ne le change pas à l'écran.
- "enchaine" : true si le plan continue directement le plan précédent (mêmes personnes à l'image, même lieu, la caméra
  continue) ; false pour un changement de cadrage sur d'autres personnes (champ / contrechamp) ou de lieu.
- Tout ce qui est dit est vu ou entendu : si un personnage est nommé comme présent, il est à l'image ou on l'entend.

{style}
DURÉE (elle dépend de l'idée)
- Choisis le nombre de plans ({plans_min} à {plans_max}) et la durée de chaque plan ("duree", de 5 à 12 secondes) pour que
  toute l'histoire tienne SANS TROU. Durée totale entre {duree_min} et {duree_max} secondes.
- Les répliques d'un plan font en tout au plus 2,3 mots par seconde de plan. Les moments d'action peuvent être sans parole.

RÈGLES
- Personnages fictifs. Jamais de vraie personne, de marque, de politique, de violence, d'enfant ni de sujet choquant.
- Hommage à Retour vers le futur : énergie, tics, relations, inventions et clins d'œil (horloges, éclairs, 88 km/h,
  gigawatts, voyage dans le temps raté, la brute qui finit dans le fumier) sont bienvenus. Mais on ne dit jamais « Doc »,
  « Marty », « McFly », « Biff », « DeLorean », « convecteur temporel » ni le titre du film, et personne ne ressemble aux
  acteurs du film.
- Seuls {nom} et les personnages secondaires existent. AU PLUS UN personnage secondaire par épisode (souvent aucun) :
  on ne présente jamais toute la bande. Newton le chien peut s'ajouter s'il sert le gag. Chacun garde ses phrases
  fétiches, sa gestuelle, ses mimiques et sa personnalité.
- "visibles" = les ids des personnes à l'image dans ce plan (1 à 3, le chien compris).
- VRAIS ÉCHANGES : "repliques" = jusqu'à 3 répliques COURTES par plan (3 à 10 mots chacune), dans l'ordre, chacune avec
  "qui" (id de celui qui parle, à l'image ou hors champ) et "t" (le moment exact dans le plan, ex. "0-3s", "3-6s").
  Quand Gilbert et le personnage secondaire sont ensemble, ils se répondent du tac au tac (question → réponse → réaction),
  comme une vraie conversation. Chaque réplique est dite EN ENTIER dans son créneau : pas de phrase coupée, pas de tunnel.
  Le "deroule" suit les mêmes créneaux (ce qu'on voit pendant que chacun parle).
- N'écris JAMAIS l'apparence des personnages (âge, visage, cheveux, habits) dans "debut", "deroule" ou "fin" : seulement
  leur NOM et leur position (« Gilbert au centre, Mat à gauche »). Leur apparence vient toujours de leur fiche.
- Positions stables : chacun garde sa place d'un plan à l'autre, sauf si on le voit se déplacer.
{memoire}
SALLE DES AUTEURS : propose 5 idées, puis écris 3 VERSIONS COMPLÈTES et différentes (les 3 meilleures idées), classées de
la meilleure à la moins bonne. Pour chaque version, écris D'ABORD la chute et son "image_cle" (l'image finale drôle même
SANS le son), puis l'effet spectaculaire (pris dans la liste des effets qui marchent), puis remonte jusqu'à l'accroche.
Le producteur gardera la plus drôle ET la plus facile à filmer.
Réponds uniquement en JSON :
{{"idees": ["5 idées d'expérience en une phrase chacune"], "versions": [VERSION, VERSION, VERSION]}}
où chaque VERSION est :
{{"choix": "l'idée de cette version et pourquoi elle est drôle", "chute": "la chute en une phrase",
 "image_cle": "l'image finale drôle sans le son", "effet": "l'effet spectaculaire montré", "titre": "...", "legende": "légende TikTok drôle, 1 ou 2 phrases, sans hashtag", "hashtags": ["#...", "..."],
 "bible": {{"lieu": "...", "lumiere": "...", "objets": [{{"nom": "...", "description": "...", "etat_initial": "..."}}]}},
 "plans": [{{"personnage": "gilbert", "duree": 8, "enchaine": false, "cadrage": "...", "emotion": "...",
            "visibles": ["gilbert"], "debut": "...", "deroule": ["0-3s: ...", "3-8s: ..."], "fin": "...",
            "repliques": [{{"qui": "gilbert", "t": "0-3s", "texte": "..."}}]}}]}}
4 à 6 hashtags en français, dont #humour."""

DEMANDE = """Écris l'épisode {genre}.
{idee}
Ne refais pas ces épisodes déjà diffusés : {deja}."""


EFFETS = """CE QUE LA CAMÉRA IA SAIT FILMER (choisis l'effet spectaculaire dans la 1re liste)
- Marche très bien (soudain, gros, visible en une seconde) : jet ou gerbe d'eau, pluie d'étincelles, explosion de farine,
  de mousse ou de confettis, gros nuage de fumée qui jaillit d'un coup, objets qui s'envolent ou tombent, lumières qui
  clignotent ou grillent, cheveux qui se dressent, éclair électrique bleu, machine qui tremble et crache de la vapeur,
  personne couverte de suie, de mousse ou de farine.
- Marche mal (à éviter) : transformation lente d'un objet en un autre, objet ou personne invisible, téléportation,
  changement de taille progressif, temps arrêté, texte à l'écran, effet qui ne se voit qu'avec une explication. Une idée
  « impossible » se montre par un effet simple de la 1re liste et la réaction des personnages.
"""


STYLES = {
    "vlog": """STYLE : PLAN-SÉQUENCE FAÇON VLOG (obligatoire)
- Gilbert se filme lui-même, téléphone TENU À LA MAIN (selfie à bout de bras, ou il retourne le téléphone vers la machine) :
  il marche, se tourne, se rapproche de la machine, recule quand ça explose. Jamais un trépied fixe, jamais une image figée.
  C'est un vrai vlog TikTok, filmé en continu, dans UN SEUL lieu du début à la fin.
- Les gens bougent et réagissent : ils s'approchent, se penchent, sursautent, se regardent entre eux. Ils ne sont jamais
  alignés face à l'objectif comme pour une photo.
- Les plans s'enchaînent comme une seule prise : "enchaine": true dès le 2e plan. Pas de champ / contrechamp, pas de saut.
- Le personnage secondaire (s'il y en a un) est là dès le premier plan, ou entre dans le champ au début d'un plan
  (on le voit arriver). Il reste à la même place ensuite, sauf si on le voit bouger.
- Peu d'objets : la machine de l'expérience, l'objet ou la cible de l'expérience, au plus un ou deux accessoires.
""",
    "film": """STYLE : PETIT FILM
- Plusieurs angles possibles (plans larges et serrés, champ / contrechamp), dans un ou deux lieux voisins.
""",
}


def fiche(p, f, memoire="", style="vlog"):
    return CONSIGNES.format(nom=p["nom"], age=p["age"], ville=p["ville"], apparence=p["apparence"],
                            voix=p.get("voix", ""), personnalite=p["personnalite"], phrase=p["phrase_fetiche"],
                            gags="; ".join(p.get("gags_recurrents", [])), ton=p["ton"],
                            repliques=" / ".join(f"« {r} »" for r in p.get("repliques", [])) or "aucune",
                            gestuelle=p.get("gestuelle", ""),
                            secondaires="\n".join(
                                f"- [{c['id']}] {c['nom']}, {c.get('age', '?')} ans : {c.get('role', '')}. {c.get('personnalite', '')} "
                                f"Gestes et mimiques : {c.get('gestuelle', '')}. "
                                f"Répliques typiques : " + " / ".join(f"« {r} »" for r in c.get("repliques", []))
                                for c in p.get("secondaires", [])) or "aucun",
                            plans_min=f["plans_min"], plans_max=f["plans_max"], duree_min=f["duree_min"],
                            duree_max=f["duree_max"], memoire=memoire, style=STYLES.get(style, ""), effets=EFFETS)


def ecrire(format_, perso, reglages, idee="", deja=(), memoire=""):
    """Salle des auteurs : 3 versions complètes. Renvoie (meilleure version, coût) ; les deux autres sont dans
    episode["autres"] pour que le producteur puisse choisir."""
    f = reglages["formats"][format_]
    genre = ("COURT (une grande expérience, montrée en entier, et sa chute)" if format_ == "courte"
             else "LONG (une vraie petite histoire avec une grande expérience, des rebondissements et une chute)")
    demande = DEMANDE.format(genre=genre, idee=f"Idée imposée : {idee}" if idee else "Invente une idée originale.",
                             deja="; ".join(list(deja)[-30:]) or "aucun")
    if os.environ.get("SIMULATION") == "1":
        ep, cout = _episode_simulation(perso, f, idee), 0.0
    else:
        ep, cout = grok.ecrire_json(reglages["modeles"]["texte"], fiche(perso, f, memoire, (reglages.get("video") or {}).get("style", "vlog")), demande,
                                    reglages["prix"]["scenario"])
    versions = [v for v in (ep.get("versions") or []) if isinstance(v, dict) and v.get("plans")] or [ep]
    propres = []
    for v in versions[:3]:
        try:
            propres.append(nettoyer(v, f, perso))
        except grok.ErreurGrok:
            pass
    if not propres:
        raise grok.ErreurGrok("scénario sans aucun plan")
    propres[0]["autres"] = propres[1:]
    return propres[0], cout


def voix_du_plan(plan, perso):
    """Fiches des personnes qui parlent dans le plan, par id."""
    return {r["qui"]: qui({"personnage": r["qui"]}, perso) for r in plan.get("repliques") or []}


def qui(plan, perso):
    """Fiche de la personne filmée dans le plan (Gilbert si l'id est inconnu)."""
    for c in perso.get("secondaires", []):
        if c.get("id") and c["id"] == plan.get("personnage"):
            return c
    return dict(perso, id="gilbert")


def _secondaire_autorise(plans, perso):
    """Ids permis dans l'épisode : Gilbert, le chien, et UN seul autre personnage secondaire (le premier qui parle)."""
    ids = {c["id"] for c in perso.get("secondaires", [])}
    ordre = [i for p in plans for i in [p.get("personnage")] + list(p.get("visibles") or [])     # dans l'ordre d'apparition
             + [r.get("qui") for r in (p.get("repliques") or []) if isinstance(r, dict)]]
    premier = next((i for i in ordre if i in ids and i != "newton"), None)
    return {"gilbert", "newton"} & ({"gilbert"} | ids) | ({premier} if premier else set())


def _texte(x):
    return str(x or "").strip()


def nettoyer(ep, f, perso):
    """Remet l'épisode d'aplomb quoi que Grok ait répondu : nombre de plans, durées, répliques, champs manquants."""
    plans = [p for p in (ep.get("plans") or []) if isinstance(p, dict)][:f["plans_max"]]
    if not plans:
        raise grok.ErreurGrok("scénario sans aucun plan")
    autorise = _secondaire_autorise(plans, perso)
    avant = None
    for k, p in enumerate(plans):
        try:
            p["duree"] = max(5, min(12, int(round(float(p.get("duree") or 8)))))
        except (TypeError, ValueError):
            p["duree"] = 8
        for cle in ("cadrage", "emotion", "debut", "fin", "dialogue"):
            p[cle] = _texte(p.get(cle))
        reps = [r for r in (p.get("repliques") if isinstance(p.get("repliques"), list) else []) if isinstance(r, dict)]
        reps = [{"qui": r.get("qui") if r.get("qui") in autorise else "gilbert", "t": _texte(r.get("t")),
                 "texte": _texte(r.get("texte"))} for r in reps if _texte(r.get("texte"))][:3]
        if not reps and p["dialogue"]:                       # ancien format : une seule réplique
            reps = [{"qui": p.get("personnage") if p.get("personnage") in autorise else "gilbert", "t": "",
                     "texte": p["dialogue"]}]
        p["repliques"] = reps
        if reps:
            p["personnage"] = reps[0]["qui"]
        p["cadrage"] = p["cadrage"] or "medium shot, handheld phone"
        der = p.get("deroule")
        p["deroule"] = [_texte(x) for x in (der if isinstance(der, list) else [der]) if _texte(x)] or ["the action continues"]
        p["personnage"] = qui(p, perso)["id"]
        if p["personnage"] not in autorise:                  # un 2e secondaire : sa réplique revient à Gilbert
            p["personnage"] = "gilbert"
        connus_ = autorise
        vis = [v for v in (p.get("visibles") if isinstance(p.get("visibles"), list) else []) if v in connus_]
        p["visibles"] = list(dict.fromkeys([p["personnage"]] + vis))[:3]
        # on n'enchaîne que si ce sont les mêmes personnes à l'image (la caméra continue)
        p["enchaine"] = bool(p.get("enchaine")) and k > 0 and set(p["visibles"]) == set(avant or [])
        if k > 0 and not p["debut"]:
            p["debut"] = plans[k - 1]["fin"]
        avant = p["visibles"]
        for vieux in ("decor", "action", "meme_lieu", "camera"):
            p.pop(vieux, None)
    total = sum(p["duree"] for p in plans)                   # durée totale dans la fourchette du format
    k = 0
    while total < f["duree_min"] and any(p["duree"] < 12 for p in plans):
        if plans[k % len(plans)]["duree"] < 12:
            plans[k % len(plans)]["duree"] += 1
            total += 1
        k += 1
    while total > f["duree_max"] and any(p["duree"] > 5 for p in plans):
        if plans[k % len(plans)]["duree"] > 5:
            plans[k % len(plans)]["duree"] -= 1
            total -= 1
        k += 1
    for p in plans:                                         # les répliques tiennent dans le plan (2,3 mots par seconde)
        reste = int(p["duree"] * 2.3)
        for r in list(p["repliques"]):
            mots = r["texte"].split()
            if reste < 3:                                    # plus de place : la réplique saute (jamais à moitié dite)
                p["repliques"].remove(r)
                continue
            if len(mots) > reste:
                r["texte"] = " ".join(mots[:reste]).rstrip(",;:") + "…"
            reste -= min(len(mots), reste)
        p["dialogue"] = " ".join(r["texte"] for r in p["repliques"])
    b = ep.get("bible") if isinstance(ep.get("bible"), dict) else {}
    objets = [o for o in (b.get("objets") or []) if isinstance(o, dict) and _texte(o.get("nom"))][:6]
    bible = {"lieu": _texte(b.get("lieu")) or "Gilbert's cluttered garage laboratory full of clocks and cables",
             "lumiere": _texte(b.get("lumiere")) or "warm late-afternoon light through dusty windows",
             "objets": [{"nom": _texte(o["nom"]), "description": _texte(o.get("description")),
                         "etat_initial": _texte(o.get("etat_initial"))} for o in objets]}
    tags = [t if t.startswith("#") else "#" + t for t in (str(x).strip() for x in ep.get("hashtags") or []) if t]
    tags = [t.replace(" ", "") for t in tags][:6]
    if "#ia" not in [t.lower() for t in tags]:
        tags.append("#ia")
    return {"titre": _texte(ep.get("titre"))[:90] or "Épisode sans titre", "legende": _texte(ep.get("legende"))[:300],
            "hashtags": tags, "bible": bible, "plans": plans, "choix": _texte(ep.get("choix"))[:400],
            "chute": _texte(ep.get("chute"))[:300], "image_cle": _texte(ep.get("image_cle"))[:300],
            "effet": _texte(ep.get("effet"))[:300]}


def _episode_simulation(perso, f, idee):
    sujets = ["la 2CV téléportée sur la mairie", "le clocher invisible", "la machine à arrêter le temps"]
    sujet = idee or random.choice(sujets)
    sec = perso["secondaires"][0]["id"] if perso.get("secondaires") else "gilbert"
    n = f["plans_min"]
    return {"versions": [dict(_version_simulation(perso, sujet, sec, n), titre=f"[Test] {sujet[:60]}" + (f" ({k})" if k else ""))
                         for k in range(3)]}


def _version_simulation(perso, sujet, sec, n):
    return {"titre": f"[Test] {sujet[:60]}", "chute": "la machine crache de la farine", "effet": "explosion de farine", "legende": "Vidéo de test : aucune IA n'a été appelée.",
            "hashtags": ["#test", "#humour"],
            "bible": {"lieu": "garage laboratory", "lumiere": "warm light",
                      "objets": [{"nom": "machine", "description": "big copper machine with a red lever", "etat_initial": "intact"}]},
            "plans": [{"personnage": "gilbert" if i % 2 == 0 else sec, "duree": 8, "enchaine": i > 1,
                       "visibles": ["gilbert", sec],
                       "cadrage": "medium shot", "emotion": "excited", "debut": f"state {i}",
                       "deroule": ["0-4s: he explains", "4-8s: he pulls the lever"], "fin": f"state {i + 1}",
                       "repliques": [{"qui": "gilbert", "t": "0-3s", "texte": f"Plan {i + 1}. {perso['phrase_fetiche']}"},
                                     {"qui": sec, "t": "3-5s", "texte": "Vous êtes sûr de vous ?"},
                                     {"qui": "gilbert", "t": "5-8s", "texte": "Ça, c'est la vérité vraie."}]}
                      for i in range(n)]}


# ---------------------------------------------------------------- consignes de tournage pour Grok Imagine
JEU = ("Natural, spontaneous acting like a real person: expressive face, micro-expressions, raised eyebrows, quick "
       "glances, natural hand gestures that follow the words, small head movements, shifts weight, blinks. Never stiff, "
       "never robotic, never frozen.")


def _objets(bible):
    if not bible.get("objets"):
        return ""
    return "PROPS (they must look exactly like this in every shot): " + " ".join(
        f"- {o['nom']}: {o['description']}." for o in bible["objets"]) + " "


def fiches_visibles(plan, perso):
    return [qui({"personnage": v}, perso) for v in plan["visibles"]]


def prompt_image(plan, gens, bible, scene_ref=False):
    """Image de départ d'un plan qui ne prolonge pas directement le précédent. Les images de référence sont, dans l'ordre :
    la dernière image de la scène (si scene_ref), puis le portrait de chaque personne à l'image."""
    k0 = 1 if scene_ref else 0
    t = []
    if scene_ref:
        t.append(f"<IMAGE_0> is the scene a moment ago: keep exactly this place, these props, this lighting.")
    else:
        t.append(f"Place: {bible['lieu']}. Lighting: {bible['lumiere']}.")
    for j, c in enumerate(gens):
        t.append(f"The person from <IMAGE_{k0 + j}> is {c['nom']}: keep exactly the same face, hair, facial hair, glasses "
                 f"and clothes ({c['apparence']}).")
    t.append(f"New image showing exactly: {plan['debut']}. Framing: {plan['cadrage']}. Expression: "
             f"{plan.get('emotion') or 'natural'}. Only these people are visible: {', '.join(c['nom'] for c in gens)}.")
    return " ".join(t) + " " + _objets(bible) + ("Vertical 9:16 photorealistic smartphone photo, natural light, realistic "
                                                  "skin, no text, no logo.")


def prompt_video(plan, gens, voix, bible, correction=""):
    """Consigne de tournage complète d'un plan : une prise continue, sans coupe, de l'état de départ à l'état de fin.
    `voix` = {id: fiche} de chaque personne qui parle (à l'image ou hors champ)."""
    t = [f"Photorealistic vertical 9:16 smartphone video: ONE continuous shot of {plan['duree']} seconds, no cuts, filmed "
         f"like a real TikTok sketch.",
         "PEOPLE ON SCREEN (exactly as in the input image, same faces and clothes the whole time): " + " ".join(
             f"- {c['nom']}: {c['apparence']}." + (f" Mannerisms: {c['gestuelle']}." if c.get("gestuelle") else "")
             for c in gens),
         f"LOCATION (identical in every shot): {bible['lieu']}. LIGHTING: {bible['lumiere']}.",
         _objets(bible).strip(),
         f"START OF THE SHOT (first frame, as in the input image): {plan['debut']}",
         "WHAT HAPPENS, IN THIS EXACT ORDER: " + " ".join(f"[{x}]" for x in plan["deroule"]),
         f"END OF THE SHOT (last frame): {plan['fin']}",
         f"CAMERA: {plan['cadrage']}; the phone is held by hand, always moving a little (walks, turns, follows the "
         f"action), never a fixed tripod. People move and react naturally, never lined up facing the lens.",
         f"EMOTION: {plan.get('emotion') or 'natural'}. {JEU}"]
    reps = plan.get("repliques") or []
    if reps:
        noms = {k: c["nom"].split(" (")[0] for k, c in voix.items()}
        visibles = set(plan.get("visibles") or [])
        t.append("DIALOGUE in French, a real lively back-and-forth conversation, lines in this exact order and at these "
                 "moments, each line spoken COMPLETELY (never cut), nothing else is said: " + " ".join(
                     f'[{r["t"] + " " if r["t"] else ""}{noms.get(r["qui"], r["qui"])}'
                     f'{"" if r["qui"] in visibles else " (off-screen voice)"}: "{r["texte"]}"]' for r in reps)
                 + " VOICES: " + " ".join(f"- {noms[k]}: {c.get('voix') or 'natural French voice'}."
                                          for k, c in voix.items() if any(r["qui"] == k for r in reps))
                 + " Accurate lip sync; the others listen and react while someone speaks.")
    else:
        t.append("Nobody on screen speaks.")
    t.append("RULES: everything not mentioned stays exactly as in the input image (same faces, clothes, positions, place, "
             "props); props only change state when the timeline says so; no new person appears; no on-screen text, no "
             "subtitles, no music; realistic physics; the special effect is clearly visible.")
    if correction:
        t.append(f"IMPORTANT, FIX THESE PROBLEMS FROM THE PREVIOUS TAKE: {correction}")
    return " ".join(x for x in t if x)
