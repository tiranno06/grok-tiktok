"""Montage final avec ffmpeg : clips mis bout à bout en 720×1280, son égalisé, sous-titres incrustés, miniature."""
import json
import os
import subprocess

from .commun import POLICES

L, H = 720, 1280


def duree(fichier):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", fichier],
                       capture_output=True, text=True, check=True)
    return float(json.loads(r.stdout)["format"]["duration"])


def a_du_son(fichier):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                        "-of", "csv=p=0", fichier], capture_output=True, text=True)
    return bool(r.stdout.strip())


def _ts(s):
    s = max(0.0, s)
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def morceaux(texte, mots_par_ligne=5):
    mots = texte.split()
    return [" ".join(mots[i:i + mots_par_ligne]) for i in range(0, len(mots), mots_par_ligne)]


def _entete():
    return ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {L}", f"PlayResY: {H}", "WrapStyle: 0", "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding",
            "Style: Base,Poppins,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,1,2,60,60,330,1",
            "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]


def _propre(t):
    return t.replace("{", "(").replace("}", ")").replace("\\", "/")


def sous_titres_mots(mots, chemin, par_ligne=4):
    """Sous-titres calés sur la vraie voix : lignes de quelques mots, le mot prononcé en jaune (style TikTok).
    mots = [{"w", "s", "e"}] en secondes depuis le début de la vidéo."""
    lignes, groupes, cur = _entete(), [], []
    for m in mots:
        coupe = cur and (len(cur) >= par_ligne or m["s"] - cur[-1]["e"] > 0.5 or cur[-1]["w"][-1:] in ".?!…")
        if coupe:
            groupes.append(cur)
            cur = []
        cur.append(m)
    if cur:
        groupes.append(cur)
    for k, g in enumerate(groupes):
        fin_ligne = g[-1]["e"] + 0.25
        if k + 1 < len(groupes):
            suivante = groupes[k + 1][0]["s"]
            fin_ligne = suivante if suivante - g[-1]["e"] < 0.6 else min(fin_ligne, suivante)   # pas de trou qui clignote
        for i, m in enumerate(g):
            t0 = g[0]["s"] if i == 0 else m["s"]
            t1 = g[i + 1]["s"] if i + 1 < len(g) else fin_ligne
            texte = " ".join(("{\\c&H00E6FF&}" + _propre(x["w"]) + "{\\c&HFFFFFF&}") if j == i else _propre(x["w"])
                             for j, x in enumerate(g))
            lignes.append(f"Dialogue: 0,{_ts(t0)},{_ts(max(t1, t0 + 0.05))},Base,,0,0,0,,{texte}")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")
    return chemin


def sous_titres(plans, durees, chemin):
    """Repli sans transcription : chaque réplique est découpée en courts morceaux répartis sur la durée de son plan
    (au prorata du nombre de lettres)."""
    lignes = _entete()
    debut = 0.0
    for plan, d in zip(plans, durees):
        bouts = morceaux(plan.get("dialogue", ""))
        if bouts:
            t0, t1 = debut + 0.3, debut + d - 0.3            # la réplique tient dans le plan, marges de 0,3 s
            total = sum(len(b) for b in bouts)
            t = t0
            for b in bouts:
                fin = t + (t1 - t0) * len(b) / total
                texte = _propre(b)
                lignes.append(f"Dialogue: 0,{_ts(t)},{_ts(fin)},Base,,0,0,0,,{texte}")
                t = fin
        debut += d
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")
    return chemin


def intervalles_parole(mots, duree_clip, blanc_max=0.45, marge=0.18, fin_en_plus=0.0):
    """Morceaux du clip à garder : la parole, sans les blancs de plus de `blanc_max` secondes (coupes « vlog »)."""
    if not mots:
        return [(0.0, duree_clip)]
    blocs = [[mots[0]["s"], mots[0]["e"]]]
    for m in mots[1:]:
        if m["s"] - blocs[-1][1] <= blanc_max:
            blocs[-1][1] = max(blocs[-1][1], m["e"])
        else:
            blocs.append([m["s"], m["e"]])
    out = []
    for k, (a, b) in enumerate(blocs):
        a = max(0.0, a - marge - (0.25 if k == 0 else 0))
        b = min(duree_clip, b + marge + (fin_en_plus if k == len(blocs) - 1 else 0))
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return [(round(a, 3), round(b, 3)) for a, b in out if b - a > 0.15]


def recaler(mots, intervalles):
    """Instants des mots une fois les blancs coupés."""
    out, decal = [], 0.0
    for a, b in intervalles:
        out += [dict(m, s=round(m["s"] - a + decal, 3), e=round(min(m["e"], b) - a + decal, 3))
                for m in mots if a <= m["s"] < b]
        decal += b - a
    return out


def couper(clip, intervalles, dest, zoom_alterne=True):
    """Garde seulement les morceaux donnés, avec un léger zoom un morceau sur deux (« jump cut » des vlogs)."""
    base = f"scale={L}:{H}:force_original_aspect_ratio=increase,crop={L}:{H},fps=30,setsar=1"
    filtres, chaine = [], ""
    for i, (a, b) in enumerate(intervalles):
        z = f",scale={int(L * 1.12) // 2 * 2}:{int(H * 1.12) // 2 * 2},crop={L}:{H},setsar=1" if zoom_alterne and i % 2 else ""
        filtres.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,{base}{z},format=yuv420p[v{i}]")
        filtres.append(f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,aresample=44100,aformat=channel_layouts=stereo[a{i}]")
        chaine += f"[v{i}][a{i}]"
    filtres.append(f"{chaine}concat=n={len(intervalles)}:v=1:a=1[v][a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-filter_complex", ";".join(filtres),
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                    "-c:a", "aac", "-b:a", "192k", dest], check=True)
    return dest


def monter(clips, plans, dest, avec_sous_titres=True, mots=None):
    """Assemble les clips. mots = mots réellement prononcés dans chaque clip (instants relatifs au clip) : les
    sous-titres sont alors calés sur la voix ; sinon ils sont répartis sur le plan. Renvoie la durée finale."""
    durees = [duree(c) for c in clips]
    entrees, filtres, chaine = [], [], ""
    for i, c in enumerate(clips):
        entrees += ["-i", c]
        filtres.append(f"[{i}:v]scale={L}:{H}:force_original_aspect_ratio=increase,crop={L}:{H},fps=30,"
                       f"setsar=1,format=yuv420p[v{i}]")
        if a_du_son(c):
            filtres.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,"
                           f"apad,atrim=0:{durees[i]:.3f},asetpts=PTS-STARTPTS[a{i}]")
        else:                                                 # clip muet : silence de la même durée
            filtres.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{durees[i]:.3f},asetpts=PTS-STARTPTS[a{i}]")
        chaine += f"[v{i}][a{i}]"
    total = sum(durees)
    filtres.append(f"{chaine}concat=n={len(clips)}:v=1:a=1[vc][ac]")
    fin_v = f"[vc]fade=t=in:st=0:d=0.3,fade=t=out:st={max(0, total - 0.4):.2f}:d=0.4"
    ass = None
    if avec_sous_titres and mots and any(mots):
        tous, decal = [], 0.0
        for m_clip, d in zip(mots, durees):
            tous += [dict(m, s=m["s"] + decal, e=m["e"] + decal) for m in m_clip]
            decal += d
        ass = sous_titres_mots(tous, os.path.splitext(dest)[0] + ".ass")
    elif avec_sous_titres and any(p.get("dialogue") for p in plans):
        ass = sous_titres(plans, durees, os.path.splitext(dest)[0] + ".ass")
    if ass:
        fin_v += f",ass='{_echapper(ass)}':fontsdir='{_echapper(POLICES)}'"
    filtres.append(fin_v + "[vf]")
    filtres.append(f"[ac]loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=out:st={max(0, total - 0.4):.2f}:d=0.4[af]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *entrees, "-filter_complex", ";".join(filtres),
                    "-map", "[vf]", "-map", "[af]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
                    "-movflags", "+faststart", dest], check=True)
    return round(duree(dest), 1)


def derniere_image(video, dest):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.15", "-i", video, "-frames:v", "1", "-q:v", "2",
                    "-update", "1", dest], check=True)
    return dest


def miniature(video, dest, instant=1.5):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(instant), "-i", video, "-frames:v", "1",
                    "-vf", "scale=360:640", "-q:v", "4", dest], check=True)
    return dest


def _echapper(chemin):
    return chemin.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
