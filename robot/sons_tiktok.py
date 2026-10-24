"""Filière « Sons TikTok » : une vidéo réaliste construite autour du son d'une vidéo TikTok drôle.

1. on prend une vidéo (lien collé sur le site, ou au hasard d'un des profils choisis, jamais deux fois la même) ;
2. on garde seulement son audio, transcrit par xAI avec qui parle et quand (voix séparées) ;
3. Grok regarde quelques images de la vidéo d'origine et le texte, puis invente la mise en scène : personnages FICTIFS
   (jamais les vraies personnes de la vidéo), lieux, émotions, cadrages. Gilbert peut jouer le rôle principal ;
4. chaque réplique devient un plan filmé par Grok Imagine (la personne qui parle dit la même phrase) ;
5. au montage, chaque plan est recalé et légèrement accéléré ou ralenti pour que la bouche tombe sur la parole
   d'origine, puis on remet le son d'origine tel quel sur toute la vidéo.
"""
import json
import math
import os
import random
import re
import subprocess
import sys
import urllib.parse
import urllib.request

from . import grok, montage
from .commun import simulation

DUREE_MIN, DUREE_PLAN_MAX = 5, 14            # secondes ; Grok Imagine filme au plus 15 s par plan
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36"}
VARIANTES = (["--impersonate", "chrome"], ["--extractor-args", "tiktok:api_hostname=api16-normal-c-useast1a.tiktokv.com"], [])


def journal(m):
    print(m, flush=True)


# ---------------------------------------------------------------- profils et choix de la vidéo
def lire_profils(texte):
    """Pseudos (sans @) d'une liste : « @pseudo », « pseudo » ou lien https://www.tiktok.com/@pseudo…"""
    out = []
    for morceau in re.split(r"[\n,;]+", texte if isinstance(texte, str) else "\n".join(texte or [])):
        m = morceau.strip()
        r = re.search(r"tiktok\.com/@([\w.\-]+)", m) or re.match(r"^@?([\w.\-]{2,40})$", m)
        if r and r.group(1).lower() not in [x.lower() for x in out]:
            out.append(r.group(1))
    return out[:30]


def lien_valide(url):
    return bool(re.match(r"^https?://([a-z0-9-]+\.)*tiktok\.com/\S+$", (url or "").strip(), re.I))


def id_video(url):
    m = re.search(r"/video/(\d+)", url or "")
    return m.group(1) if m else ""


def _ytdlp_liste(pseudo, n=40):
    for v in VARIANTES:
        try:
            r = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "--no-warnings", "--socket-timeout", "30",
                                *v, "--playlist-end", str(n), "-J", f"https://www.tiktok.com/@{pseudo}"],
                               capture_output=True, text=True, timeout=180)
            d = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
        except (subprocess.TimeoutExpired, ValueError, OSError):
            continue
        out = [{"id": str(e.get("id")), "url": f"https://www.tiktok.com/@{pseudo}/video/{e.get('id')}",
                "duree": e.get("duration")} for e in d.get("entries") or [] if e.get("id")]
        if out:
            return out
    return []


def _tikwm_liste(pseudo, n=35):
    req = urllib.request.Request("https://www.tikwm.com/api/user/posts?" + urllib.parse.urlencode(
        {"unique_id": pseudo, "count": n, "cursor": 0}), headers=UA)
    d = (json.loads(urllib.request.urlopen(req, timeout=60).read()) or {}).get("data") or {}
    return [{"id": str(v["video_id"]), "url": f"https://www.tiktok.com/@{pseudo}/video/{v['video_id']}",
             "duree": v.get("duration")} for v in d.get("videos") or [] if v.get("video_id")]


def videos_du_profil(pseudo):
    try:
        v = _ytdlp_liste(pseudo)
        if v:
            return v
    except Exception as e:
        journal(f"  profil : yt-dlp en échec ({str(e)[:100]})")
    try:
        return _tikwm_liste(pseudo)
    except Exception as e:
        journal(f"  profil : liste impossible ({str(e)[:100]})")
    return []


def choisir(profils, deja, duree_max, essais=4):
    """Liens à essayer, au hasard des profils, jamais déjà utilisés, d'une durée raisonnable."""
    profils = list(profils)
    random.shuffle(profils)
    out = []
    for p in profils[:6]:
        vs = [v for v in videos_du_profil(p) if v["id"] not in deja
              and (v.get("duree") is None or DUREE_MIN <= float(v["duree"]) <= duree_max)]
        journal(f"  un profil : {len(vs)} vidéo(s) jamais utilisée(s) de la bonne durée")
        random.shuffle(vs)
        out += [v["url"] for v in vs[:2]]
        if len(out) >= essais:
            break
    return out[:essais]


# ---------------------------------------------------------------- téléchargement
def telecharger(url, dossier):
    """Vidéo d'origine (image + son) et ses infos. yt-dlp en imitant un navigateur, sinon le service public tikwm."""
    if simulation():
        return {"uploader": "compte_de_test", "webpage_url": url}, _fausse_source(os.path.join(dossier, "source.mp4"))
    err = ""
    for v in VARIANTES:
        for f in os.listdir(dossier):
            if f.startswith("source."):
                os.remove(os.path.join(dossier, f))
        try:
            r = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-warnings", "--socket-timeout", "30", *v,
                                "-f", "best[acodec!=none][height<=1080]/best", "-o", f"{dossier}/source.%(ext)s", "-j",
                                "--no-simulate", url], capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            continue
        src = next((os.path.join(dossier, f) for f in os.listdir(dossier) if f.startswith("source.") and not f.endswith(".part")), None)
        if r.returncode == 0 and src:
            return json.loads(r.stdout.strip().splitlines()[-1]), src
        err = (r.stderr or "").strip()[-160:]
    try:                                                     # dernier recours
        req = urllib.request.Request("https://www.tikwm.com/api/?" + urllib.parse.urlencode({"url": url, "hd": "0"}), headers=UA)
        d = (json.loads(urllib.request.urlopen(req, timeout=60).read()) or {}).get("data") or {}
        lien = d.get("play") or d.get("wmplay")
        if lien:
            lien = "https://www.tikwm.com" + lien if lien.startswith("/") else lien
            dest = os.path.join(dossier, "source.mp4")
            open(dest, "wb").write(urllib.request.urlopen(urllib.request.Request(lien, headers=UA), timeout=300).read())
            return {"uploader": (d.get("author") or {}).get("unique_id", ""), "webpage_url": url}, dest
    except Exception as e:
        err += f" / tikwm : {str(e)[:100]}"
    raise grok.ErreurGrok(f"vidéo TikTok impossible à récupérer ({err or 'aucune réponse'})")


def _fausse_source(dest):
    """Test gratuit : une fausse vidéo TikTok de 24 s avec du son."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=576x1024:r=30:d=24",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=24", "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", dest], check=True)
    return dest


def extraire_son(video, dest):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vn", "-ac", "2", "-ar", "44100", dest], check=True)
    return dest


def images_cles(video, duree, dossier, n=6):
    out = []
    for k in range(n):
        t = duree * (k + 0.5) / n
        dest = os.path.join(dossier, f"cle_{k}.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                        "-vf", "scale=360:-2", "-q:v", "5", dest])
        if os.path.exists(dest):
            out.append(dest)
    return out


# ---------------------------------------------------------------- répliques et plans
def repliques(mots, blanc=0.8):
    """Mots regroupés en répliques : même voix, sans grand blanc."""
    out = []
    for m in mots:
        if out and out[-1]["voix"] == m["voix"] and m["s"] - out[-1]["fin"] <= blanc:
            out[-1]["mots"].append(m)
            out[-1]["fin"] = m["e"]
        else:
            out.append({"voix": m["voix"], "deb": m["s"], "fin": m["e"], "mots": [m]})
    for r in out:
        r["texte"] = " ".join(x["w"] for x in r["mots"])
    return out


def decouper(reps, duree, plusieurs_personnages):
    """Plans de la vidéo, bout à bout de 0 à la fin du son. Chaque plan montre une personne : celle qui parle
    (« parle ») ou, pour couper une longue réplique, celle qui écoute (« ecoute »). Aucun plan de plus de 14 s."""
    if not reps:                                              # aucune parole : des plans d'ambiance
        n = max(1, math.ceil(duree / 10))
        return [{"voix": 0, "role": "parle", "mots": [], "texte": "", "i": k, "debut": round(duree * k / n, 3),
                 "fin": round(duree * (k + 1) / n, 3)} for k in range(n)]
    morceaux = []
    for i, r in enumerate(reps):
        m = r["mots"]
        if r["fin"] - r["deb"] > 7 and len(m) >= 6:            # longue réplique : la personne parle, puis on voit l'autre réagir
            coupe = max(range(1, len(m)), key=lambda k: -abs(m[k]["s"] - (r["deb"] + min(6.0, (r["fin"] - r["deb"]) / 2))))
            morceaux.append(dict(r, i=i, mots=m[:coupe], fin=m[coupe - 1]["e"], role="parle"))
            morceaux.append(dict(r, i=i, mots=m[coupe:], deb=m[coupe]["s"], role="ecoute" if plusieurs_personnages else "parle"))
        else:
            morceaux.append(dict(r, i=i, role="parle"))
    plans = []
    for k, mc in enumerate(morceaux):
        debut = 0.0 if k == 0 else plans[-1]["fin"]
        fin = duree if k == len(morceaux) - 1 else (mc["fin"] + morceaux[k + 1]["deb"]) / 2
        plans.append(dict(mc, debut=round(debut, 3), fin=round(max(fin, debut + 0.8), 3),
                          texte=" ".join(x["w"] for x in mc["mots"])))
    # un plan trop long (blanc, musique) est coupé en deux plans du même personnage
    out = []
    for p in plans:
        while p["fin"] - p["debut"] > DUREE_PLAN_MAX:
            milieu = p["debut"] + DUREE_PLAN_MAX * 0.8
            out.append(dict(p, fin=milieu, mots=[m for m in p["mots"] if m["s"] < milieu]))
            p = dict(p, debut=milieu, mots=[m for m in p["mots"] if m["s"] >= milieu])
        out.append(p)
    for p in out:
        p["texte"] = " ".join(x["w"] for x in p["mots"])
    return out


# ---------------------------------------------------------------- mise en scène par Grok
CONSIGNES = """Tu es réalisateur. On reprend uniquement le SON d'une vidéo TikTok drôle et on tourne une toute nouvelle vidéo
réaliste autour de ce son, comme un vrai sketch filmé au téléphone. Tu reçois la transcription (avec le numéro de la voix
qui parle) et quelques images de la vidéo d'origine pour comprendre la situation.

RÈGLES
- Les personnages sont FICTIFS : ils ne doivent pas ressembler aux personnes de la vidéo d'origine (autre visage, autre
  coiffure, autres habits). Tous adultes. Jamais de marque, de célébrité ni de logo.
- Âge, genre et allure de chaque personnage collent à sa voix et à ce qu'il dit.
- {gilbert}
- Une personne qu'on entend au téléphone ou hors champ peut être « hors_champ » : on ne la montre pas.
- Lieux, accessoires, émotions et gestes servent la blague. Jeu naturel et expressif, jamais figé.
- "description", "lieu", "action", "ecoute" et "cadrage" sont en ANGLAIS, précis et visuels.

Réponds uniquement en JSON :
{{"contexte": "ce qui se passe, en une phrase", "titre": "...", "legende": "légende TikTok drôle, sans hashtag",
 "hashtags": ["#..."],
 "personnages": [{{"voix": 0, "nom": "prénom", "gilbert": false, "hors_champ": false,
                  "description": "age, gender, face, hair, clothes", "voix_desc": "voice in English"}}],
 "lieux": [{{"id": "A", "description": "..."}}],
 "plans": [{{"plan": 0, "lieu": "A", "cadrage": "close-up | medium shot | over-the-shoulder | selfie ...",
            "action": "gestures and facial expression while speaking", "ecoute": "how the listener reacts (for listening shots)",
            "emotion": "..."}}]}}"""


def mettre_en_scene(R, P, plans, voix, cles, info, gilbert):
    """Décisions de Grok (personnages, lieux, cadrages). Renvoie (mise_en_scene, coût)."""
    lignes = "\n".join(f"plan {k} ({p['debut']:.1f}–{p['fin']:.1f} s) voix {p['voix']} "
                       f"{'[on voit la personne qui écoute]' if p['role'] == 'ecoute' else ''} : {p['texte'] or '(pas de parole)'}"
                       for k, p in enumerate(plans))
    g = (f"Le personnage récurrent de la chaîne, {P['nom']} ({P['apparence']}), joue la voix principale si c'est un homme "
         f"adulte (mets alors \"gilbert\": true pour cette voix)." if gilbert else "Aucun personnage récurrent imposé.")
    demande = (f"Voix entendues : {', '.join(str(v) for v in voix)}.\nCompte d'origine : @{info.get('uploader', '?')}.\n"
               f"Transcription découpée en plans :\n{lignes}")
    if simulation():
        return _scene_simulation(plans, voix), 0.0
    ms, cout = grok.ecrire_json(R["modeles"].get("vision", R["modeles"]["texte"]), CONSIGNES.format(gilbert=g), demande,
                                R["prix"]["scenario"] * 2, images=cles)
    return ms, cout


def _scene_simulation(plans, voix):
    return {"contexte": "test", "titre": "[Test] Son TikTok", "legende": "Vidéo de test.", "hashtags": ["#test"],
            "personnages": [{"voix": v, "nom": f"Perso {v}", "gilbert": v == 0, "hors_champ": False,
                             "description": "adult person, casual clothes", "voix_desc": "neutral"} for v in voix],
            "lieux": [{"id": "A", "description": "kitchen"}],
            "plans": [{"plan": k, "lieu": "A", "cadrage": "medium shot", "action": "talks", "ecoute": "listens",
                       "emotion": "neutral"} for k in range(len(plans))]}


def distribution(ms, voix, P, gilbert):
    """Personnage de chaque voix (toujours quelqu'un, même si Grok en a oublié)."""
    persos = {}
    for c in ms.get("personnages") or []:
        try:
            v = int(c.get("voix"))
        except (TypeError, ValueError):
            continue
        if v in voix and v not in persos:
            persos[v] = c
    for v in voix:
        persos.setdefault(v, {"voix": v, "nom": f"Personne {v + 1}", "description": "adult person, casual clothes"})
    if not gilbert:
        for c in persos.values():
            c["gilbert"] = False
    elif sum(bool(c.get("gilbert")) for c in persos.values()) > 1:     # un seul Gilbert
        premier = next(v for v, c in persos.items() if c.get("gilbert"))
        for v, c in persos.items():
            c["gilbert"] = v == premier
    for c in persos.values():
        if c.get("gilbert"):
            c.update(nom=P["nom"], description=P["apparence"], voix_desc=P.get("voix", ""))
    return persos


# ---------------------------------------------------------------- prompts
def qui_voit_on(p, plans, persos):
    """Personnage à l'image : celui qui parle, ou celui qui écoute (l'autre voix la plus proche dans le temps)."""
    if p["role"] == "ecoute":
        autres = [q["voix"] for q in plans if q["voix"] != p["voix"] and not persos[q["voix"]].get("hors_champ")]
        if autres:
            return autres[0], False
    if persos[p["voix"]].get("hors_champ"):
        visibles = [v for v, c in persos.items() if not c.get("hors_champ")]
        return (visibles[0], False) if visibles else (p["voix"], True)
    return p["voix"], True


def prompt_image(c, lieu, d):
    return (f"The same person as in the reference photo, keep exactly the same face, hair and clothes ({c['description']}). "
            f"Scene: {lieu}. Framing: {d.get('cadrage') or 'medium shot'}. Expression: {d.get('emotion') or 'natural'}. "
            "Vertical 9:16 photorealistic smartphone photo, natural light, realistic skin, no text, no logo.")


def prompt_video(c, lieu, d, parle, texte):
    base = (f"Photorealistic vertical smartphone video, like a real TikTok sketch. The person ({c['description']}). "
            f"Setting: {lieu}. Framing: {d.get('cadrage') or 'medium shot'}, handheld with slight natural movement. "
            "Natural, spontaneous acting: expressive face, micro-expressions, natural hand gestures, blinks, small head "
            "movements. Never stiff or robotic. ")
    if parle and texte:
        return base + (f"Action: {d.get('action') or 'talks'}. Emotion: {d.get('emotion') or 'natural'}. "
                       f'The person speaks and says exactly: "{texte}". Voice: {c.get("voix_desc") or "natural"}. '
                       "Accurate lip sync. No music, no on-screen text, no subtitles.")
    return base + (f"The person does not speak: listens to someone off-camera and reacts: {d.get('ecoute') or 'reacts'}. "
                   "No music, no on-screen text, no subtitles.")


# ---------------------------------------------------------------- calage sur le son d'origine
def caler(clip, mots_clip, plan, parle, dest):
    """Prend dans le clip de Grok le morceau qui colle au plan : la parole de Grok est déplacée et accélérée ou
    ralentie (entre ×0,75 et ×1,35) pour tomber sur la parole d'origine. Renvoie le fichier, sans son."""
    duree_plan = plan["fin"] - plan["debut"]
    d_clip = montage.duree(clip)
    facteur, debut_src = 1.0, 0.0
    if parle and mots_clip and plan["mots"]:
        g0, g1 = mots_clip[0]["s"], mots_clip[-1]["e"]
        o0, o1 = plan["mots"][0]["s"] - plan["debut"], plan["mots"][-1]["e"] - plan["debut"]
        if g1 - g0 > 0.3 and o1 - o0 > 0.3:
            facteur = min(1.35, max(0.75, (o1 - o0) / (g1 - g0)))
        debut_src = g0 - o0 / facteur                        # instant du clip qui doit tomber au début du plan
    if debut_src > d_clip - 0.5:
        debut_src = 0.0
    avance = max(0.0, -debut_src) * facteur                  # le clip commence trop tard : on fige sa première image
    debut_src = max(0.0, debut_src)
    filtre = (f"trim=start={debut_src:.3f},setpts=(PTS-STARTPTS)*{facteur:.4f},"
              f"scale={montage.L}:{montage.H}:force_original_aspect_ratio=increase,crop={montage.L}:{montage.H},setsar=1,fps=30,"
              f"tpad=start_duration={avance:.3f}:start_mode=clone:stop_duration={duree_plan + 2:.3f}:stop_mode=clone,"
              f"trim=duration={duree_plan:.3f},setpts=PTS-STARTPTS,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-vf", filtre, "-an", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "16", dest], check=True)
    return dest, round(facteur, 2), d_clip


def assembler(plans_video, son, dest, mots, sous_titres=True):
    """Plans mis bout à bout, son d'origine par-dessus, sous-titres calés sur la parole d'origine."""
    liste = dest + ".txt"
    with open(liste, "w") as f:
        f.writelines(f"file '{p}'\n" for p in plans_video)
    video_seule = dest + ".video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", liste, "-c", "copy", video_seule],
                   check=True)
    vf = "fade=t=in:st=0:d=0.2"
    if sous_titres and mots:
        ass = montage.sous_titres_mots(mots, os.path.splitext(dest)[0] + ".ass")
        vf += f",ass='{montage._echapper(ass)}':fontsdir='{montage._echapper(montage.POLICES)}'"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video_seule, "-i", son, "-vf", vf, "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                    "-shortest", "-movflags", "+faststart", dest], check=True)
    return round(montage.duree(dest), 1)


def estimation(duree_son, R, nb_voix=2):
    """Coût prévu : environ un plan toutes les 5 s, chaque plan filmé 1,5 s plus long que nécessaire."""
    p = R["prix"]
    nb_plans = max(1, math.ceil(duree_son / 5))
    return round((duree_son + 1.5 * nb_plans) * p["video_seconde"] + nb_plans * p["image"] + nb_voix * p["image"]
                 + 3 * p["scenario"], 2)


# ---------------------------------------------------------------- tout le tournage
def filmer(R, prompt, image, secondes, dest, caisse, quoi, sobre):
    """Un clip Grok Imagine ; refus de la modération : un seul nouvel essai avec un prompt plus sobre."""
    m, prix = R["modeles"], R["prix"]
    for essai in (1, 2):
        caisse.autoriser(secondes * prix["video_seconde"], quoi)
        try:
            _, cout = grok.creer_video(m["video"], prompt if essai == 1 else sobre, image, secondes, dest,
                                       prix["video_seconde"], R["montage"].get("resolution", "720p"))
            caisse.payer(cout, f"{quoi} ({secondes} s)")
            return dest
        except grok.RefusModeration as e:
            caisse.payer(e.cout, f"{quoi} refusé par la modération")
            if essai == 2:
                raise
            journal(f"  {quoi} refusé par la modération : nouvel essai plus sobre")


def fabriquer(R, P, caisse, dossier, lien, deja, portrait_gilbert):
    """Fabrique la vidéo. Renvoie un dict : titre, legende, hashtags, video, duree, source, auteur, plans."""
    T = R.get("tiktok") or {}
    duree_max = float(T.get("duree_max", 60))
    au_hasard = not lien or lien == "hasard"
    if not au_hasard:
        if not lien_valide(lien):
            raise grok.ErreurGrok("il faut un lien de vidéo TikTok (https://www.tiktok.com/@compte/video/… ou https://vm.tiktok.com/…)")
        candidats = [lien]
    else:
        profils = lire_profils(T.get("profils") or [])
        if not profils:
            raise grok.ErreurGrok("aucun profil TikTok réglé : ajoute des profils dans l'onglet TikTok du site")
        candidats = ["https://www.tiktok.com/@test/video/1"] if simulation() else choisir(profils, deja, duree_max)
        if not candidats:
            raise grok.ErreurGrok("aucune vidéo utilisable dans les profils cette fois (déjà toutes prises, trop longues, "
                                  "ou TikTok n'a pas répondu)")
    info = source = None
    for url in candidats:
        try:
            info, source = telecharger(url, dossier)
        except grok.ErreurGrok as e:
            journal(f"  {e}")
            continue
        d = montage.duree(source)
        if d > duree_max + 1 and au_hasard:
            journal(f"  vidéo trop longue ({d:.0f} s, maximum {duree_max:.0f} s) : on en essaie une autre")
            info = source = None
            continue
        if d > duree_max + 1:
            raise grok.ErreurGrok(f"vidéo trop longue ({d:.0f} s) : le maximum réglé est {duree_max:.0f} s (onglet TikTok)")
        info["webpage_url"] = info.get("webpage_url") or url
        break
    if not source:
        raise grok.ErreurGrok("aucune des vidéos TikTok essayées n'a pu être récupérée")
    url = info["webpage_url"]
    auteur = info.get("uploader") or info.get("uploader_id") or info.get("channel") or ""
    son = extraire_son(source, os.path.join(dossier, "son.wav"))
    duree = montage.duree(son)
    journal(f"Son TikTok : {duree:.1f} s")
    caisse.autoriser(estimation(duree, R), "vidéo depuis TikTok")            # on ne commence pas ce qu'on ne pourra pas finir
    # qui dit quoi
    mots, cout = grok.transcrire(son, R["prix"].get("transcription_heure", 0.10), langue=T.get("langue", "fr"), voix_separees=True)
    caisse.payer(cout, "transcription du son TikTok")
    reps = repliques(mots)
    voix = sorted({r["voix"] for r in reps}) or [0]
    plans = decouper(reps, duree, len(voix) > 1)
    journal(f"  {len(reps)} répliques, {len(voix)} voix, {len(plans)} plans")
    # la mise en scène
    cles = images_cles(source, duree, dossier)
    gilbert = bool(T.get("gilbert", True)) and bool(portrait_gilbert)
    caisse.autoriser(R["prix"]["scenario"] * 2, "mise en scène")
    ms, cout = mettre_en_scene(R, P, plans, voix, cles, info, gilbert)
    caisse.payer(cout, "mise en scène (Grok regarde la vidéo)")
    persos = distribution(ms, voix, P, gilbert)
    lieux = {str(l.get("id")): str(l.get("description") or "") for l in ms.get("lieux") or [] if isinstance(l, dict)}
    lieu_defaut = next(iter(lieux.values()), "") or "an ordinary French apartment"
    dplans = {}
    for d in ms.get("plans") or []:
        try:
            dplans[int(d.get("plan"))] = d
        except (TypeError, ValueError, AttributeError):
            pass
    journal("  scène : " + str(ms.get("contexte", ""))[:200])
    # un portrait par personnage visible : il garde le même visage dans tous ses plans
    portraits = {}
    for v, c in persos.items():
        if c.get("hors_champ") and len(persos) > 1:
            continue
        if c.get("gilbert"):
            portraits[v] = portrait_gilbert
            continue
        caisse.autoriser(R["prix"]["image"], f"portrait de {c['nom']}")
        dest = os.path.join(dossier, f"portrait_{v}.jpg")
        _, cout = grok.creer_image(R["modeles"]["image"], f"Photorealistic vertical portrait photo of a fictional adult: "
                                   f"{c['description']}. Looking at the camera, neutral background, soft daylight, no text.",
                                   dest, R["prix"]["image"])
        caisse.payer(cout, f"portrait de {c['nom']}")
        portraits[v] = dest
    # chaque plan
    sorties = []
    for k, p in enumerate(plans):
        d = dplans.get(k, {})
        v, parle = qui_voit_on(p, plans, persos)
        v = v if v in portraits else next(iter(portraits))
        c, lieu = persos[v], lieux.get(str(d.get("lieu")), lieu_defaut)
        depart = os.path.join(dossier, f"depart_{k}.jpg")
        caisse.autoriser(R["prix"]["image"], f"image du plan {k + 1}")
        _, cout = grok.modifier_image(R["modeles"]["image"], prompt_image(c, lieu, d), portraits[v], depart, R["prix"]["image"])
        caisse.payer(cout, f"image du plan {k + 1}")
        secondes = int(min(15, math.ceil(p["fin"] - p["debut"] + 1.5)))
        clip = filmer(R, prompt_video(c, lieu, d, parle, p["texte"]), depart, secondes, os.path.join(dossier, f"clip_{k}.mp4"),
                      caisse, f"plan {k + 1}", prompt_video(c, lieu, {"cadrage": "medium shot"}, parle, p["texte"]))
        mots_clip = []
        if parle and p["texte"]:
            try:
                mots_clip, cout = grok.transcrire(clip, R["prix"].get("transcription_heure", 0.10), langue=T.get("langue", "fr"))
                caisse.payer(cout, f"transcription du plan {k + 1}")
            except grok.ErreurGrok as e:
                journal(f"  plan {k + 1} : transcription impossible ({e}), calage approximatif")
        cale, facteur, _ = caler(clip, mots_clip, p, parle, os.path.join(dossier, f"cale_{k}.mp4"))
        sorties.append(cale)
        journal(f"  plan {k + 1}/{len(plans)} : {c['nom']} {'parle' if parle else 'écoute'} ({p['fin'] - p['debut']:.1f} s, "
                f"vitesse ×{facteur}) — {caisse.depense:.2f} $ jusqu'ici")
    video = os.path.join(dossier, "video.mp4")
    duree_v = assembler(sorties, son, video, mots, R["montage"].get("sous_titres", True))
    credit = f"🎧 Son : @{auteur}" if auteur else "🎧 Son d'origine sur TikTok"
    legende = (str(ms.get("legende") or "").strip() + " " + credit).strip()[:300]
    tags = [t if str(t).startswith("#") else "#" + str(t) for t in ms.get("hashtags") or [] if str(t).strip()][:5]
    tags = [t.replace(" ", "") for t in tags] + ([] if "#ia" in tags else ["#ia"])
    return {"titre": str(ms.get("titre") or "Sketch sur un son TikTok").strip()[:90], "legende": legende, "hashtags": tags,
            "video": video, "duree": duree_v, "source": url, "auteur": auteur,
            "plans": [{"debut": p["debut"], "fin": p["fin"], "voix": p["voix"], "texte": p["texte"]} for p in plans],
            "personnages": {str(v): c.get("nom") for v, c in persos.items()}}
