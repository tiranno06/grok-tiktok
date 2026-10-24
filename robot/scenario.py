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

DURÉE (elle dépend de l'idée)
- Choisis le nombre de plans ({plans_min} à {plans_max}) et la durée de chaque plan ("duree", de 5 à 12 secondes) pour que
  toute l'histoire tienne SANS TROU. Durée totale entre {duree_min} et {duree_max} secondes.
- La réplique d'un plan fait au plus 2,5 mots par seconde de plan. Les moments d'action peuvent être sans parole.

RÈGLES
- Personnages fictifs. Jamais de vraie personne, de marque, de politique, de violence, d'enfant ni de sujet choquant.
- Hommage à Retour vers le futur : énergie, tics, relations, inventions et clins d'œil (horloges, éclairs, 88 km/h,
  gigawatts, voyage dans le temps raté, la brute qui finit dans le fumier) sont bienvenus. Mais on ne dit jamais « Doc »,
  « Marty », « McFly », « Biff », « DeLorean », « convecteur temporel » ni le titre du film, et personne ne ressemble aux
  acteurs du film.
- Seuls {nom} et les personnages secondaires existent. 0, 1 ou 2 secondaires selon l'idée. Chacun garde ses phrases
  fétiches, sa gestuelle, ses mimiques et sa personnalité.
- "visibles" = les ids des personnes à l'image dans ce plan (1 à 3, le chien compris). "personnage" = l'id de celle qui dit
  "dialogue" (elle est dans "visibles"). Une seule réplique par plan. Les autres peuvent être hors champ : on les entend
  (écris leur réplique en français entre guillemets dans "deroule").
- N'écris JAMAIS l'apparence des personnages (âge, visage, cheveux, habits) dans "debut", "deroule" ou "fin" : seulement
  leur NOM et leur position (« Gilbert au centre, Mat à gauche »). Leur apparence vient toujours de leur fiche.
- Positions stables : chacun garde sa place d'un plan à l'autre, sauf si on le voit se déplacer.
{memoire}
Réponds uniquement en JSON :
{{"idees": ["5 idées d'expérience en une phrase chacune"], "choix": "l'idée retenue (la plus drôle et spectaculaire) et pourquoi",
 "titre": "...", "legende": "légende TikTok drôle, 1 ou 2 phrases, sans hashtag", "hashtags": ["#...", "..."],
 "bible": {{"lieu": "...", "lumiere": "...", "objets": [{{"nom": "...", "description": "...", "etat_initial": "..."}}]}},
 "plans": [{{"personnage": "gilbert", "duree": 8, "enchaine": false, "cadrage": "...", "emotion": "...",
            "visibles": ["gilbert"], "debut": "...", "deroule": ["0-3s: ...", "3-8s: ..."], "fin": "...", "dialogue": "..."}}]}}
4 à 6 hashtags en français, dont #humour."""

DEMANDE = """Écris l'épisode {genre}.
{idee}
Ne refais pas ces épisodes déjà diffusés : {deja}."""


def fiche(p, f, memoire=""):
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
                            duree_max=f["duree_max"], memoire=memoire)


def ecrire(format_, perso, reglages, idee="", deja=(), memoire=""):
    """Renvoie (episode, coût)."""
    f = reglages["formats"][format_]
    genre = ("COURT (une grande expérience, montrée en entier, et sa chute)" if format_ == "courte"
             else "LONG (une vraie petite histoire avec une grande expérience, des rebondissements et une chute)")
    demande = DEMANDE.format(genre=genre, idee=f"Idée imposée : {idee}" if idee else "Invente une idée originale.",
                             deja="; ".join(list(deja)[-30:]) or "aucun")
    if os.environ.get("SIMULATION") == "1":
        ep, cout = _episode_simulation(perso, f, idee), 0.0
    else:
        ep, cout = grok.ecrire_json(reglages["modeles"]["texte"], fiche(perso, f, memoire), demande,
                                    reglages["prix"]["scenario"])
    return nettoyer(ep, f, perso), cout


def qui(plan, perso):
    """Fiche de la personne filmée dans le plan (Gilbert si l'id est inconnu)."""
    for c in perso.get("secondaires", []):
        if c.get("id") and c["id"] == plan.get("personnage"):
            return c
    return dict(perso, id="gilbert")


def _texte(x):
    return str(x or "").strip()


def nettoyer(ep, f, perso):
    """Remet l'épisode d'aplomb quoi que Grok ait répondu : nombre de plans, durées, répliques, champs manquants."""
    plans = [p for p in (ep.get("plans") or []) if isinstance(p, dict)][:f["plans_max"]]
    if not plans:
        raise grok.ErreurGrok("scénario sans aucun plan")
    avant = None
    for k, p in enumerate(plans):
        try:
            p["duree"] = max(5, min(12, int(round(float(p.get("duree") or 8)))))
        except (TypeError, ValueError):
            p["duree"] = 8
        for cle in ("cadrage", "emotion", "debut", "fin", "dialogue"):
            p[cle] = _texte(p.get(cle))
        p["cadrage"] = p["cadrage"] or "medium shot, handheld phone"
        der = p.get("deroule")
        p["deroule"] = [_texte(x) for x in (der if isinstance(der, list) else [der]) if _texte(x)] or ["the action continues"]
        p["personnage"] = qui(p, perso)["id"]
        connus_ = {"gilbert"} | {c["id"] for c in perso.get("secondaires", [])}
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
    for p in plans:                                         # la réplique tient dans le plan (2,5 mots par seconde)
        mots = p["dialogue"].split()
        if len(mots) > int(p["duree"] * 2.5):
            p["dialogue"] = " ".join(mots[:int(p["duree"] * 2.5)]).rstrip(",;:") + "…"
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
            "hashtags": tags, "bible": bible, "plans": plans, "choix": _texte(ep.get("choix"))[:400]}


def _episode_simulation(perso, f, idee):
    sujets = ["la 2CV téléportée sur la mairie", "le clocher invisible", "la machine à arrêter le temps"]
    sujet = idee or random.choice(sujets)
    sec = perso["secondaires"][0]["id"] if perso.get("secondaires") else "gilbert"
    n = f["plans_min"]
    return {"titre": f"[Test] {sujet[:60]}", "legende": "Vidéo de test : aucune IA n'a été appelée.",
            "hashtags": ["#test", "#humour"],
            "bible": {"lieu": "garage laboratory", "lumiere": "warm light",
                      "objets": [{"nom": "machine", "description": "big copper machine with a red lever", "etat_initial": "intact"}]},
            "plans": [{"personnage": "gilbert" if i % 2 == 0 else sec, "duree": 8, "enchaine": i > 1,
                       "visibles": ["gilbert", sec],
                       "cadrage": "medium shot", "emotion": "excited", "debut": f"state {i}",
                       "deroule": ["0-4s: he explains", "4-8s: he pulls the lever"], "fin": f"state {i + 1}",
                       "dialogue": f"Plan {i + 1}. {perso['phrase_fetiche']} Ça, c'est la vérité vraie."}
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


def prompt_video(plan, gens, parleur, bible, correction=""):
    """Consigne de tournage complète d'un plan : une prise continue, sans coupe, de l'état de départ à l'état de fin."""
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
         f"CAMERA: {plan['cadrage']}, handheld phone with slight natural movement.",
         f"EMOTION: {plan.get('emotion') or 'natural'}. {JEU}"]
    if plan["dialogue"]:
        t.append(f'DIALOGUE: only {parleur["nom"]} speaks, in French, at a lively natural pace, and says exactly: '
                 f'"{plan["dialogue"]}". Voice: {parleur.get("voix") or "natural French voice"}. Accurate lip sync.')
    else:
        t.append("Nobody on screen speaks.")
    t.append("RULES: everything not mentioned stays exactly as in the input image (same faces, clothes, positions, place, "
             "props); props only change state when the timeline says so; no new person appears; no on-screen text, no "
             "subtitles, no music; realistic physics; the special effect is clearly visible.")
    if correction:
        t.append(f"IMPORTANT, FIX THESE PROBLEMS FROM THE PREVIOUS TAKE: {correction}")
    return " ".join(x for x in t if x)
