"""Écriture d'un épisode par Grok : titre, légende TikTok, hashtags et découpage en plans.

Chaque plan donne à Grok Imagine le décor et l'action (en anglais, c'est ce qu'il comprend le mieux)
et la réplique que le personnage dit face caméra (en français).
"""
import os
import random

from . import grok

CONSIGNES = """Tu es un auteur de sketchs TikTok qui cartonnent en France. Mini-série filmée comme un vrai vlog au téléphone,
images totalement réalistes. Le personnage principal revient dans chaque épisode.

FICHE DU PERSONNAGE
- Nom : {nom}, {age} ans, {ville}
- Apparence (pour la caméra) : {apparence}
- Voix : {voix}
- Personnalité : {personnalite}
- Phrase fétiche : « {phrase} » (pas à chaque épisode : seulement quand elle tombe bien)
- Répliques typiques (une ou deux par épisode au plus, adaptées à la situation, jamais toutes) : {repliques}
- Gestes et mimiques : {gestuelle}
- Gags récurrents : {gags}
- Ton : {ton}

PERSONNAGES SECONDAIRES (ils reviennent d'un épisode à l'autre ; "id" entre crochets)
{secondaires}

CE QUI REND UN SKETCH TIKTOK DRÔLE
- Accroche dans les 2 premières secondes : la première phrase pose une situation absurde avec un sérieux total
  (« Aujourd'hui, j'ai inventé le grille-pain qui répond au téléphone. »). Jamais de « Bonjour tout le monde ».
- La personnalité du personnage guide chaque épisode : respecte-la à la lettre (ses inventions, ses ratés, ses gags).
- Partir d'un vrai petit problème du quotidien français (voisins, bricolage, supermarché, météo, administration,
  vacances, technologie) et le pousser jusqu'à l'absurde.
- Escalade : chaque plan est pire que le précédent. La règle de trois marche bien (deux choses normales, la troisième folle).
- Décalage image / parole : ce qu'on voit contredit ce qu'il affirme (il dit « tout est sous contrôle », derrière ça brûle).
- Chute vraiment inattendue dans le dernier plan, et si possible une dernière petite réplique ou un regard gêné à la caméra.
- Langue parlée naturelle, phrases courtes : « bon », « bah », « attends », « non mais », « voilà ». Jamais de phrase écrite,
  jamais de morale, jamais expliquer la blague.

RÈGLES
- Personnage fictif. Jamais de vraie personne, de marque, de politique, de violence, d'enfant ni de sujet choquant.
- Le personnage et ses proches sont un hommage à Retour vers le futur (le savant fou, son jeune acolyte, la brute, le
  voisin timide, la copine, le proviseur devenu maire) : énergie, tics, relations, inventions, ratés et clins d'œil
  (horloges, éclairs, 88 km/h, gigawatts, voyage dans le temps raté, la brute qui finit dans le fumier) sont bienvenus.
  Mais on ne dit jamais « Doc », « Marty », « McFly », « Biff », « DeLorean », « convecteur temporel » ni le titre du film,
  et personne ne ressemble aux acteurs du film.
- Les ratés restent drôles et sans blessé : fumée, étincelles, cheveux électrisés, effet inverse.
- Seuls Gilbert et les personnages secondaires ci-dessus existent (aucun autre personnage récurrent). Selon le gag, un
  personnage secondaire est à l'image, ou reste hors champ : on l'entend (écris sa réplique en français entre guillemets
  dans "action", ex. Mat yells from off-screen: « Gilbert, ça fume ! »), on le montre du doigt, on parle de lui.
- Un personnage qui ne parle pas (Newton le chien) peut être à l'image : "dialogue" vide, il réagit.
- {nom} est le héros de chaque épisode. Selon l'idée, 0, 1 ou 2 personnages secondaires peuvent venir (pas toujours les
  mêmes, et environ un épisode sur deux en solo). Tout le monde parle français.
- C'est une vraie adaptation du film : chacun garde ses phrases fétiches (adaptées à la situation), sa gestuelle, ses
  mimiques, sa personnalité et ses relations (l'acolyte qui panique, la brute qui finit dans le fumier, le voisin timide qui
  trouve enfin du courage…). Mets ses gestes typiques dans "action".
- Chaque plan montre UNE personne (champ / contrechamp) : "personnage" = l'id de celle qu'on voit et qui dit "dialogue"
  ("gilbert" ou un id secondaire). Les autres peuvent être hors champ (voir plus haut).
- Chaque plan dure {secondes} secondes : la réplique fait entre {mots_min} et {mots} mots (il parle presque tout le plan,
  pas de long blanc).
- "objets" : les accessoires importants (en ANGLAIS, décrits précisément : couleur, matière, forme). Ils doivent rester
  identiques dans tous les plans.
- "decor", "action" et "cadrage" sont en ANGLAIS, courts et très visuels. "action" décrit aussi les gestes naturels et
  l'expression du visage pendant que la personne parle. Varie les cadrages : selfie close-up, medium shot, wide shot, phone propped
  on a table, walking selfie, insert shot on an object.
- "meme_lieu" : true si le plan se passe exactement au même endroit que le plan précédent (sinon false).

Réponds uniquement en JSON :
{{"idees": ["5 idées d'épisode en une phrase chacune"], "choix": "l'idée retenue (la plus drôle) et pourquoi",
 "titre": "...", "legende": "légende TikTok drôle, 1 ou 2 phrases, sans hashtag",
 "hashtags": ["#...", "..."], "objets": ["..."],
 "plans": [{{"personnage": "gilbert", "decor": "...", "cadrage": "...", "action": "...", "emotion": "...", "meme_lieu": false,
            "dialogue": "..."}}]}}
Exactement {nb} plans. 4 à 6 hashtags en français, dont #humour."""

DEMANDE = """Écris l'épisode {genre}.
{idee}
Ne refais pas ces épisodes déjà diffusés : {deja}."""


def _fiche(p, secondes, nb):
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
                            secondes=secondes, mots=int(secondes * 2.6), mots_min=int(secondes * 1.8), nb=nb)


def ecrire(format_, perso, reglages, idee="", deja=()):
    """Renvoie (episode, coût). L'épisode a toujours le bon nombre de plans."""
    f = reglages["formats"][format_]
    nb, secondes = f["clips"], f["secondes_par_clip"]
    genre = ("COURT (gag éclair : mise en place, chute)" if format_ == "courte"
             else "LONG (une vraie petite histoire avec un début, des rebondissements et une chute)")
    demande = DEMANDE.format(genre=genre, idee=f"Idée imposée : {idee}" if idee else "Invente une idée originale.",
                             deja="; ".join(list(deja)[-30:]) or "aucun")
    if os.environ.get("SIMULATION") == "1":
        ep, cout = _episode_simulation(perso, nb, idee), 0.0
    else:
        m = reglages["modeles"]
        ep, cout = grok.ecrire_json(m["texte"], _fiche(perso, secondes, nb), demande, reglages["prix"]["scenario"])
    return nettoyer(ep, nb, secondes, perso), cout


def qui(plan, perso):
    """Fiche de la personne filmée dans le plan (Gilbert si l'id est inconnu)."""
    for c in perso.get("secondaires", []):
        if c.get("id") and c["id"] == plan.get("personnage"):
            return c
    return dict(perso, id="gilbert")


def nettoyer(ep, nb, secondes, perso):
    """Remet l'épisode d'aplomb quoi que Grok ait répondu (plans en trop ou manquants, répliques trop longues)."""
    plans = [p for p in (ep.get("plans") or []) if isinstance(p, dict)][:nb]
    if not plans:
        raise grok.ErreurGrok("scénario sans aucun plan")
    while len(plans) < nb:                                  # plan manquant : on prolonge le dernier lieu
        plans.append(dict(plans[-1], dialogue="", action="reacts silently to the camera, deadpan", meme_lieu=True))
    mots_max = int(secondes * 2.8)
    for k_, p in enumerate(plans):
        p["cadrage"] = p.get("cadrage") or p.get("camera") or "handheld selfie, medium close-up"
        for k in ("decor", "action", "cadrage", "emotion", "dialogue"):
            p[k] = str(p.get(k) or "").strip()
        p.pop("camera", None)
        p["personnage"] = qui(p, perso)["id"]
        p["meme_lieu"] = bool(p.get("meme_lieu")) and k_ > 0
        mots = p["dialogue"].split()
        if len(mots) > mots_max:
            p["dialogue"] = " ".join(mots[:mots_max]).rstrip(",;:") + "…"
    tags = [t if t.startswith("#") else "#" + t for t in (ep.get("hashtags") or []) if str(t).strip()]
    tags = [t.replace(" ", "") for t in tags][:6]
    if "#ia" not in [t.lower() for t in tags]:
        tags.append("#ia")
    return {"titre": str(ep.get("titre") or "Épisode sans titre").strip()[:90],
            "legende": str(ep.get("legende") or "").strip()[:300],
            "hashtags": tags, "plans": plans,
            "objets": [str(o).strip()[:200] for o in (ep.get("objets") or []) if str(o).strip()][:4]}


def _episode_simulation(perso, nb, idee):
    sujets = ["le grille-pain à téléportation", "le détecteur de lundi", "le robot qui plie les chaussettes"]
    sujet = idee or random.choice(sujets)
    return {"titre": f"[Test] {sujet[:60]}", "legende": "Vidéo de test : aucune IA n'a été appelée.",
            "hashtags": ["#test", "#humour"],
            "objets": ["a rusty red wheelbarrow"],
            "plans": [{"personnage": "gilbert" if i % 2 == 0 or not perso.get("secondaires") else perso["secondaires"][0]["id"],
                       "decor": "village street in France", "action": "talks to the camera",
                       "cadrage": "handheld selfie", "meme_lieu": i > 0,
                       "dialogue": f"Plan {i + 1}. {perso['phrase_fetiche']} Ça, c'est la vérité vraie."}
                      for i in range(nb)]}


JEU = ("Natural, spontaneous acting like a real person: expressive face, micro-expressions, raised eyebrows, quick "
       "glances away then back, natural hand gestures that follow the words, small head movements, shifts weight, blinks. "
       "Never stiff, never robotic, never frozen.")


def _objets(objets):
    return f" Props that must look exactly the same in every shot: {'; '.join(objets)}." if objets else ""


def prompt_image(plan, c, objets=(), depuis_plan_precedent=False):
    """Image de départ du plan : à partir du portrait (même visage), ou de la dernière image du plan précédent
    quand on reste au même endroit (mêmes objets, même lumière)."""
    if depuis_plan_precedent:
        debut = ("Same person, same place, same props, same lighting and clothes as in this image; change only the framing "
                 "and the pose for the next shot. ")
    else:
        debut = (f"The same person as in the reference photo, keep exactly the same face, hair, facial hair, glasses and "
                 f"clothes ({c['apparence']}). New scene: {plan['decor']}. ")
    return (debut + f"Framing: {plan['cadrage']}. Action: {plan['action']}. Expression: {plan.get('emotion') or 'deadpan'}."
            + _objets(objets) + " Vertical 9:16 photorealistic smartphone photo, natural light, realistic skin, no text.")


def prompt_video(plan, c, objets=()):
    texte = (f"Photorealistic vertical smartphone video, filmed like a real TikTok sketch. "
             f"The person ({c['apparence']}). Setting: {plan['decor']}. Framing: {plan['cadrage']}, handheld phone with "
             f"slight natural movement. Action: {plan['action']}. Emotion: {plan.get('emotion') or 'deadpan'}. "
             + (f"Typical mannerisms of this character: {c['gestuelle']}. " if c.get("gestuelle") else "") + f"{JEU}"
             + _objets(objets) + " ")
    if plan["dialogue"]:
        texte += (f'The person speaks French, at a lively natural pace, and says exactly: "{plan["dialogue"]}". '
                  f"Voice: {c.get('voix') or 'natural French voice'}. Accurate lip sync. ")
    else:
        texte += "The person does not speak; reacts silently. "
    return texte + "Ambient sound only, no music, no on-screen text, no subtitles, nobody else speaks."
