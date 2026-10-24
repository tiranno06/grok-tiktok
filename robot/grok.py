"""Appels à l'API de xAI (Grok) : texte, images et vidéos (Grok Imagine).

Documentation : https://docs.x.ai  (vidéo : POST /v1/videos/generations puis GET /v1/videos/{id}).
La clé est lue dans la variable XAI_API_KEY (secret GitHub), jamais écrite ailleurs.
En mode simulation (SIMULATION=1), rien n'est envoyé : de fausses images et vidéos sont fabriquées avec ffmpeg.
"""
import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

API = "https://api.x.ai/v1"
TICKS_PAR_DOLLAR = 10_000_000_000          # l'API compte les coûts en « ticks » : 10 milliards = 1 $


class ErreurGrok(Exception):
    pass


class RefusModeration(ErreurGrok):
    """Grok a refusé de montrer le résultat (modération). Le plan est quand même facturé."""
    def __init__(self, message, cout=0.0):
        super().__init__(message)
        self.cout = cout


CLE_REFUSEE = ("clé xAI refusée (ancienne ou mal copiée) : sur console.x.ai → API Keys, copie ta clé actuelle, puis dans "
               "GitHub → dépôt grok-tiktok → Settings → Secrets and variables → Actions → XAI_API_KEY → Update secret, "
               "colle-la et enregistre. (La clé du site, elle, est la clé GitHub : rien à voir.)")


def _refus_de_cle(code, texte):
    return code in (401, 403) or (code == 400 and "api key" in texte.lower())


def _cle():
    cle = os.environ.get("XAI_API_KEY", "").strip()
    if not cle:
        raise ErreurGrok("clé XAI_API_KEY absente : ajoute-la dans Settings → Secrets and variables → Actions")
    return cle


def _appel(methode, chemin, corps=None, essais=4, delai=600):
    donnees = json.dumps(corps).encode() if corps is not None else None
    for n in range(essais):
        req = urllib.request.Request(API + chemin, data=donnees, method=methode,
                                     headers={"Authorization": f"Bearer {_cle()}", "Content-Type": "application/json",
                                              "User-Agent": "grok-tiktok-robot"})
        try:
            with urllib.request.urlopen(req, timeout=delai) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            texte = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 504) and n < essais - 1:
                time.sleep(10 * (n + 1))
                continue
            if _refus_de_cle(e.code, texte):
                raise ErreurGrok(CLE_REFUSEE)
            raise ErreurGrok(f"xAI a répondu {e.code} : {texte}")
        except (urllib.error.URLError, TimeoutError) as e:
            if n < essais - 1:
                time.sleep(10 * (n + 1))
                continue
            raise ErreurGrok(f"xAI injoignable : {e}")


def _cout(rep, estimation):
    """Coût réel donné par l'API s'il est présent, sinon l'estimation tirée des prix des réglages."""
    ticks = (rep.get("usage") or {}).get("cost_in_usd_ticks")
    return round(ticks / TICKS_PAR_DOLLAR, 4) if isinstance(ticks, (int, float)) and ticks > 0 else estimation


def _telecharger(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "grok-tiktok-robot"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def image_en_data_url(chemin):
    type_ = "image/png" if chemin.lower().endswith(".png") else "image/jpeg"
    return f"data:{type_};base64," + base64.b64encode(open(chemin, "rb").read()).decode()


# ---------------------------------------------------------------- texte
def ecrire_json(modele, consignes, demande, prix, images=()):
    """Demande à Grok une réponse JSON (en lui montrant des images si on en donne). Renvoie (objet, coût en $)."""
    contenu = demande
    if images:
        contenu = [{"type": "image_url", "image_url": {"url": image_en_data_url(i), "detail": "low"}} for i in images]
        contenu.append({"type": "text", "text": demande})
    rep = _appel("POST", "/chat/completions", {
        "model": modele,
        "messages": [{"role": "system", "content": consignes}, {"role": "user", "content": contenu}],
        "response_format": {"type": "json_object"},
        "temperature": 1.0,
    })
    texte = rep["choices"][0]["message"]["content"]
    debut, fin = texte.find("{"), texte.rfind("}")
    try:
        return json.loads(texte[debut:fin + 1]), _cout(rep, prix)
    except ValueError:
        raise ErreurGrok("Grok n'a pas renvoyé un scénario lisible")


# ---------------------------------------------------------------- transcription (qui dit quoi, et quand)
def transcrire(chemin, prix_heure, langue="fr", voix_separees=False):
    """Mots prononcés avec leurs instants : [{"w", "s", "e", "voix"}], coût. Service « Speech to Text » de xAI (POST /v1/stt).
    voix_separees : chaque mot reçoit le numéro de la personne qui parle."""
    if os.environ.get("SIMULATION") == "1":
        return _fausse_transcription(chemin), 0.0
    limite = "----grokTiktok" + str(int(time.time() * 1000))
    champs = {"model": "grok-voice-transcribe-2.0", "language": langue, "diarize": "true" if voix_separees else "false"}
    corps = b"".join(f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in champs.items())
    corps += (f'--{limite}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(chemin)}"\r\n'
              f"Content-Type: application/octet-stream\r\n\r\n").encode() + open(chemin, "rb").read() + f"\r\n--{limite}--\r\n".encode()
    for n in range(3):
        req = urllib.request.Request(API + "/stt", data=corps, method="POST", headers={
            "Authorization": f"Bearer {_cle()}", "Content-Type": f"multipart/form-data; boundary={limite}", "User-Agent": "grok-tiktok-robot"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                rep = json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and n < 2:
                time.sleep(10 * (n + 1))
                continue
            texte = e.read().decode(errors='replace')[:300]
            raise ErreurGrok(CLE_REFUSEE if _refus_de_cle(e.code, texte) else f"transcription refusée par xAI ({e.code}) : {texte}")
        except (urllib.error.URLError, TimeoutError) as e:
            if n < 2:
                time.sleep(10)
                continue
            raise ErreurGrok(f"transcription impossible : {e}")
    mots = [{"w": str(m.get("text", "")).strip(), "s": float(m["start"]), "e": float(m["end"]), "voix": int(m.get("speaker") or 0)}
            for m in rep.get("words") or [] if str(m.get("text", "")).strip()]
    duree = float(rep.get("duration") or (mots[-1]["e"] if mots else 0))
    return mots, _cout(rep, round(duree / 3600 * prix_heure, 5))


def _fausse_transcription(chemin):
    """Test gratuit : des mots réguliers, deux voix qui alternent, sur toute la durée du son."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", chemin],
                       capture_output=True, text=True)
    duree, mots, t, k = float(r.stdout.strip() or 0), [], 0.4, 0
    while t + 0.3 < duree - 0.3:
        mots.append({"w": f"mot{k}", "s": round(t, 2), "e": round(t + 0.3, 2), "voix": (k // 8) % 2})
        k += 1
        t += 0.42 if k % 8 else 1.2                       # un blanc toutes les 8 paroles
    return mots


# ---------------------------------------------------------------- images
def _image_reponse(rep, dest, prix):
    d = (rep.get("data") or [{}])[0]
    if d.get("b64_json"):
        open(dest, "wb").write(base64.b64decode(d["b64_json"]))
    elif d.get("url"):
        _telecharger(d["url"], dest)
    else:
        raise ErreurGrok("aucune image dans la réponse de Grok")
    return dest, _cout(rep, prix)


def creer_image(modele, prompt, dest, prix):
    """Image à partir d'un texte (portrait du personnage). Renvoie (chemin, coût)."""
    if os.environ.get("SIMULATION") == "1":
        return _fausse_image(dest, "PORTRAIT"), 0.0
    rep = _appel("POST", "/images/generations", {"model": modele, "prompt": prompt, "n": 1,
                                                 "aspect_ratio": "9:16", "response_format": "b64_json"})
    return _image_reponse(rep, dest, prix)


def modifier_image(modele, prompt, image, dest, prix):
    """Nouvelle image à partir d'images de référence (portraits, scène) : mêmes visages, autre moment. `image` est un
    chemin, ou une liste de chemins (jusqu'à 5) que la consigne désigne par <IMAGE_0>, <IMAGE_1>… Renvoie (chemin, coût)."""
    if os.environ.get("SIMULATION") == "1":
        return _fausse_image(dest, os.path.basename(dest)), 0.0
    corps = {"model": modele, "prompt": prompt, "n": 1, "response_format": "b64_json"}
    if isinstance(image, (list, tuple)) and len(image) > 1:
        corps.update(images=[{"url": image_en_data_url(i)} for i in image[:5]], aspect_ratio="9:16")
    else:
        i = image[0] if isinstance(image, (list, tuple)) else image
        corps["image"] = {"url": image_en_data_url(i), "type": "image_url"}
    rep = _appel("POST", "/images/edits", corps)
    return _image_reponse(rep, dest, prix)


# ---------------------------------------------------------------- vidéos
def creer_video(modele, prompt, image, duree, dest, prix_seconde, resolution="720p", attente_max=1200, suivi=None):
    """Clip vidéo (avec son) qui démarre sur l'image donnée. Renvoie (chemin, coût).
    suivi(pourcent) est appelé pendant que Grok filme (barre d'avancement du site)."""
    if os.environ.get("SIMULATION") == "1":
        if suivi:
            suivi(50)
        return _faux_clip(dest, duree, prompt), 0.0
    corps = {"model": modele, "prompt": prompt, "duration": int(duree), "aspect_ratio": "9:16", "resolution": resolution}
    if image:
        corps["image"] = {"url": image_en_data_url(image)}
    rep = _appel("POST", "/videos/generations", corps)
    rid = rep.get("request_id")
    if not rid:
        raise ErreurGrok(f"Grok n'a pas accepté la vidéo : {str(rep)[:300]}")
    estimation = round(duree * prix_seconde, 4)
    debut = time.time()
    while time.time() - debut < attente_max:
        time.sleep(8)
        etat = _appel("GET", f"/videos/{rid}")
        statut = etat.get("status")
        if suivi and isinstance(etat.get("progress"), (int, float)):
            suivi(etat["progress"])
        if statut == "done":
            v = etat.get("video") or {}
            cout = _cout(etat, estimation)
            if v.get("respect_moderation") is False or not v.get("url"):
                raise RefusModeration("plan refusé par la modération de Grok", cout)
            return _telecharger(v["url"], dest), cout
        if statut in ("failed", "expired"):
            err = etat.get("error") or {}
            raise ErreurGrok(f"vidéo ratée chez Grok ({err.get('code', statut)}) : {err.get('message', '')}")
    raise ErreurGrok("Grok n'a pas fini la vidéo à temps (20 min)")


# ---------------------------------------------------------------- simulation (test gratuit)
def _fausse_image(dest, texte):
    t = "".join(c for c in texte if c.isalnum() or c in " -_")[:30]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x6b7b8c:s=720x1280",
                    "-vf", f"drawtext=text='{t}':fontcolor=white:fontsize=44:x=(w-tw)/2:y=(h-th)/2",
                    "-frames:v", "1", dest], check=True)
    return dest


def _faux_clip(dest, duree, prompt):
    resume = "".join(c for c in prompt[:40] if c.isalnum() or c == " ")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", f"testsrc2=s=720x1280:r=24:d={duree}",
                    "-f", "lavfi", "-i", f"sine=frequency=330:duration={duree}",
                    "-vf", f"drawtext=text='SIMULATION':fontcolor=white:fontsize=60:x=(w-tw)/2:y=200,"
                           f"drawtext=text='{resume}':fontcolor=white:fontsize=26:x=(w-tw)/2:y=300",
                    "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", dest],
                   check=True)
    return dest
