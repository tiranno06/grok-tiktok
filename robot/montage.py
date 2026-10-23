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


def sous_titres(plans, durees, chemin):
    """Fichier ASS : chaque réplique est découpée en courts morceaux répartis sur la durée de son plan
    (au prorata du nombre de lettres), en gros texte blanc bordé de noir au tiers bas de l'image."""
    lignes = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {L}", f"PlayResY: {H}", "WrapStyle: 0", "",
              "[V4+ Styles]",
              "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
              "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
              "MarginR, MarginV, Encoding",
              "Style: Base,Poppins,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,1,2,60,60,330,1",
              "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    debut = 0.0
    for plan, d in zip(plans, durees):
        bouts = morceaux(plan.get("dialogue", ""))
        if bouts:
            t0, t1 = debut + 0.3, debut + d - 0.3            # la réplique tient dans le plan, marges de 0,3 s
            total = sum(len(b) for b in bouts)
            t = t0
            for b in bouts:
                fin = t + (t1 - t0) * len(b) / total
                texte = b.replace("{", "(").replace("}", ")").replace("\\", "/")
                lignes.append(f"Dialogue: 0,{_ts(t)},{_ts(fin)},Base,,0,0,0,,{texte}")
                t = fin
        debut += d
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")
    return chemin


def monter(clips, plans, dest, avec_sous_titres=True):
    """Assemble les clips. Renvoie la durée finale en secondes."""
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
    if avec_sous_titres and any(p.get("dialogue") for p in plans):
        ass = sous_titres(plans, durees, os.path.splitext(dest)[0] + ".ass")
        fin_v += f",ass='{_echapper(ass)}':fontsdir='{_echapper(POLICES)}'"
    filtres.append(fin_v + "[vf]")
    filtres.append(f"[ac]loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=out:st={max(0, total - 0.4):.2f}:d=0.4[af]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *entrees, "-filter_complex", ";".join(filtres),
                    "-map", "[vf]", "-map", "[af]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
                    "-movflags", "+faststart", dest], check=True)
    return round(duree(dest), 1)


def miniature(video, dest, instant=1.5):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(instant), "-i", video, "-frames:v", "1",
                    "-vf", "scale=360:640", "-q:v", "4", dest], check=True)
    return dest


def _echapper(chemin):
    return chemin.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
