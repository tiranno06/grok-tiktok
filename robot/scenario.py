"""Écriture d'un épisode par Grok : titre, légende TikTok, hashtags et découpage en plans.

Chaque plan donne à Grok Imagine le décor et l'action (en anglais, c'est ce qu'il comprend le mieux)
et la réplique que le personnage dit face caméra (en français).
"""
import os
import random

from . import grok

CONSIGNES = """Tu es l'auteur d'une mini-série humoristique pour TikTok, filmée comme un vrai vlog au téléphone,
avec des images totalement réalistes (pas de dessin animé). Le personnage principal revient dans chaque épisode.

FICHE DU PERSONNAGE
- Nom : {nom}, {age} ans, {ville}
- Apparence (pour la caméra) : {apparence}
- Voix : {voix}
- Personnalité : {personnalite}
- Phrase fétiche : « {phrase} »
- Gags récurrents : {gags}
- Ton : {ton}

RÈGLES
- Personnage fictif. Jamais de vraie personne, de marque, de politique, de violence, d'enfant ni de sujet choquant.
- Monique la voisine n'apparaît JAMAIS à l'image : on parle d'elle, on la montre du doigt hors champ.
- Seul {nom} parle. Il parle français, face caméra ou presque, comme un vlogueur.
- Chaque plan dure {secondes} secondes : sa réplique fait au plus {mots} mots (on doit pouvoir la dire sans se presser).
- Un épisode = une situation absurde traitée avec un sérieux total, et une chute surprenante dans le dernier plan.
- Les champs "decor", "action" et "camera" sont en ANGLAIS, courts et très visuels (ce que voit la caméra).
- Garde le même lieu ou des lieux voisins d'un plan à l'autre pour que l'histoire reste cohérente.

Réponds uniquement en JSON :
{{"titre": "...", "legende": "légende TikTok drôle, 1 ou 2 phrases, sans hashtag",
 "hashtags": ["#...", "..."],
 "plans": [{{"decor": "...", "action": "...", "camera": "...", "dialogue": "..."}}]}}
Exactement {nb} plans. 4 à 6 hashtags en français, dont #humour."""

DEMANDE = """Écris l'épisode {genre}.
{idee}
Ne refais pas ces épisodes déjà diffusés : {deja}."""


def _fiche(p, secondes, nb):
    return CONSIGNES.format(nom=p["nom"], age=p["age"], ville=p["ville"], apparence=p["apparence"],
                            voix=p.get("voix", ""), personnalite=p["personnalite"], phrase=p["phrase_fetiche"],
                            gags="; ".join(p.get("gags_recurrents", [])), ton=p["ton"],
                            secondes=secondes, mots=int(secondes * 2.3), nb=nb)


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


def nettoyer(ep, nb, secondes, perso):
    """Remet l'épisode d'aplomb quoi que Grok ait répondu (plans en trop ou manquants, répliques trop longues)."""
    plans = [p for p in (ep.get("plans") or []) if isinstance(p, dict)][:nb]
    if not plans:
        raise grok.ErreurGrok("scénario sans aucun plan")
    while len(plans) < nb:                                  # plan manquant : on prolonge le dernier lieu
        plans.append(dict(plans[-1], dialogue="", action="reacts silently to the camera, deadpan"))
    mots_max = int(secondes * 2.6)
    for p in plans:
        for k in ("decor", "action", "camera", "dialogue"):
            p[k] = str(p.get(k) or "").strip()
        mots = p["dialogue"].split()
        if len(mots) > mots_max:
            p["dialogue"] = " ".join(mots[:mots_max]).rstrip(",;:") + "…"
    tags = [t if t.startswith("#") else "#" + t for t in (ep.get("hashtags") or []) if str(t).strip()]
    tags = [t.replace(" ", "") for t in tags][:6]
    if "#ia" not in [t.lower() for t in tags]:
        tags.append("#ia")
    return {"titre": str(ep.get("titre") or "Épisode sans titre").strip()[:90],
            "legende": str(ep.get("legende") or "").strip()[:300],
            "hashtags": tags, "plans": plans}


def _episode_simulation(perso, nb, idee):
    sujets = ["la tondeuse qui a peur du noir", "Napoléon refuse de quitter la voiture", "un concours de soupe"]
    sujet = idee or random.choice(sujets)
    return {"titre": f"[Test] {sujet[:60]}", "legende": "Vidéo de test : aucune IA n'a été appelée.",
            "hashtags": ["#test", "#humour"],
            "plans": [{"decor": "village street in France", "action": f"{perso['nom']} talks to the camera",
                       "camera": "handheld selfie", "dialogue": f"Plan {i + 1}. {perso['phrase_fetiche']}"}
                      for i in range(nb)]}


def prompt_image(plan, perso):
    """Image de départ du plan, faite à partir du portrait : même visage, nouveau décor."""
    return (f"The same man as in the reference photo, keep exactly his face, moustache, glasses, hair and clothes "
            f"({perso['apparence']}). New scene: {plan['decor']}. Action: {plan['action']}. "
            f"Vertical 9:16 photorealistic smartphone vlog frame, natural light, realistic skin, no text.")


def prompt_video(plan, perso):
    texte = (f"Photorealistic vertical smartphone vlog, filmed like a real TikTok video. "
             f"The man ({perso['apparence']}) — {plan['action']}. Setting: {plan['decor']}. Camera: {plan['camera']}. ")
    if plan["dialogue"]:
        texte += (f'He speaks French directly to the camera and says exactly: "{plan["dialogue"]}". '
                  f"Voice: {perso.get('voix', 'calm French male voice')}. Natural lip sync. ")
    else:
        texte += "He does not speak. "
    return texte + "Ambient sound only, no music, no on-screen text, no subtitles, no other person visible."
