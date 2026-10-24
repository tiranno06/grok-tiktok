"""Publication sur TikTok par Buffer (comme jt-auto), au choix dans Réglages → Publication sur TikTok.

- Manuelle (par défaut) : rien n'est envoyé, tu publies toi-même depuis le site.
- Automatique : chaque nouvelle vidéo est programmée sur Buffer à l'heure conseillée ; Buffer la met en ligne avec
  l'étiquette « Contenu généré par l'IA ». Tant que l'heure n'est pas passée, « Annuler la programmation » l'efface de Buffer.
Le site peut aussi envoyer une vidéo tout de suite (« Publier maintenant sur TikTok »).

Clé : secret GitHub BUFFER_API_KEY (la même que pour jt-auto convient). Si plusieurs comptes TikTok sont reliés à Buffer,
le nom du compte à utiliser se règle sur le site (reglages.publication.compte).
"""
import datetime
import json
import os
import urllib.error
import urllib.request

from .commun import maintenant

BUFFER = "https://api.buffer.com"


class ErreurBuffer(Exception):
    pass


def cle():
    c = os.environ.get("BUFFER_API_KEY", "").strip()
    if not c:
        raise ErreurBuffer("clé Buffer absente : ajoute le secret BUFFER_API_KEY dans GitHub (Settings → Secrets and "
                           "variables → Actions)")
    return c


def _gql(requete):
    req = urllib.request.Request(BUFFER, data=json.dumps({"query": requete}).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {cle()}", "Content-Type": "application/json"})
    try:
        rep = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
    except urllib.error.HTTPError as e:
        raise ErreurBuffer(f"Buffer a répondu {e.code} : {e.read().decode(errors='replace')[:200]}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise ErreurBuffer(f"Buffer injoignable : {e}")
    if rep.get("errors"):
        raise ErreurBuffer(f"Buffer : {str(rep['errors'])[:300]}")
    return rep["data"]


def comptes_tiktok():
    """Comptes TikTok reliés à Buffer : [{id, nom}]."""
    out = []
    for o in _gql("query { account { organizations { id } } }")["account"]["organizations"]:
        q = "query { channels(input: { organizationId: %s }) { id name displayName service isDisconnected } }"
        for c in _gql(q % json.dumps(o["id"]))["channels"]:
            if str(c.get("service", "")).lower() == "tiktok" and not c.get("isDisconnected"):
                out.append({"id": c["id"], "nom": c.get("displayName") or c.get("name") or c["id"]})
    return out


def compte(R):
    voulu = str((R.get("publication") or {}).get("compte") or "").strip().lstrip("@").lower()
    liste = comptes_tiktok()
    if not liste:
        raise ErreurBuffer("aucun compte TikTok relié à Buffer (publish.buffer.com → Channels → Connect → TikTok)")
    if voulu:
        for c in liste:
            if voulu in (c["id"].lower(), c["nom"].lower().lstrip("@")):
                return c
        raise ErreurBuffer(f"compte « {voulu} » introuvable dans Buffer. Comptes TikTok reliés : "
                           + ", ".join(c["nom"] for c in liste))
    if len(liste) > 1:
        raise ErreurBuffer("plusieurs comptes TikTok dans Buffer : écris lequel utiliser dans Réglages → Publication "
                           "(" + ", ".join(c["nom"] for c in liste) + ")")
    return liste[0]


def texte(v):
    return f"{v.get('legende', '')} {' '.join(v.get('hashtags') or [])}".strip()[:2200]


def _quand_utc(iso):
    """Heure conseillée → UTC pour Buffer ; None si elle est passée ou trop proche (publication tout de suite)."""
    if not iso:
        return None
    d = datetime.datetime.fromisoformat(iso)
    if d <= maintenant() + datetime.timedelta(minutes=10):
        return None
    return d.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envoyer(v, R, quand_iso=None):
    """Programme (ou publie tout de suite si quand_iso est vide ou passé) la vidéo sur TikTok. Renvoie l'id Buffer."""
    if not str(v.get("url", "")).startswith("https://"):
        raise ErreurBuffer("la vidéo n'a pas d'adresse publique (vidéo de test ?)")
    c, quand = compte(R), _quand_utc(quand_iso)
    planif = f'mode: customScheduled\n      dueAt: "{quand}"' if quand else "mode: shareNow"
    derniere = None
    for ia in (True, False):                                  # étiquette IA d'abord ; si Buffer la refuse, on prévient
        meta = "metadata: { tiktok: { isAiGenerated: true } }" if ia else ""
        req = f"""mutation {{
  createPost(input: {{
      text: {json.dumps(texte(v), ensure_ascii=False)}
      channelId: {json.dumps(c["id"])}
      schedulingType: automatic
      {planif}
      {meta}
      assets: [{{ video: {{ url: {json.dumps(v["url"])}, metadata: {{ thumbnailOffset: 1500 }} }} }}]
  }}) {{
    ... on PostActionSuccess {{ post {{ id }} }}
    ... on MutationError {{ message }}
  }}
}}"""
        try:
            rep = _gql(req)["createPost"]
        except ErreurBuffer as e:
            derniere = str(e)
            continue
        if rep.get("post"):
            return {"id": rep["post"]["id"], "compte": c["nom"], "quand": quand, "etiquette_ia": ia}
        derniere = rep.get("message")
    raise ErreurBuffer(f"Buffer a refusé la vidéo : {derniere}")


def annuler(post_id):
    """Efface une publication programmée sur Buffer."""
    rep = _gql('mutation { deletePost(input: { id: %s }) { __typename ... on MutationError { message } } }'
               % json.dumps(post_id))["deletePost"]
    if rep.get("message"):
        raise ErreurBuffer(f"Buffer n'a pas pu annuler : {rep['message']}")


def mettre_a_jour(file):
    """Les vidéos programmées dont l'heure est passée sont comptées comme publiées."""
    now = maintenant()
    for v in file.get("videos", []):
        if v.get("statut") == "programmee" and v.get("publier_le") and datetime.datetime.fromisoformat(v["publier_le"]) <= now:
            v.update(statut="publiee", publiee_le=v["publier_le"])
    return file
