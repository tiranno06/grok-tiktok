"""Icônes de l'application (écran d'accueil Android / iPhone) : un « G » blanc et un éclair, sur fond nuit avec le voyant rouge.
    python outils/icones.py   → docs/logo-192.png, logo-512.png, versions « maskable » et logo-apple.png"""
import os

from PIL import Image, ImageDraw, ImageFont

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOND, ROUGE, BLANC, JAUNE = (21, 32, 43), (210, 59, 45), (245, 247, 250), (255, 196, 40)


def icone(taille, marge=0.0):
    im = Image.new("RGB", (taille, taille), FOND)
    d = ImageDraw.Draw(im)
    z = taille * (1 - 2 * marge)                       # zone utile (les icônes « maskable » sont rognées en rond)
    o = taille * marge
    police = ImageFont.truetype(os.path.join(RACINE, "polices", "Poppins-Bold.ttf"), int(z * 0.62))
    d.text((o + z * 0.46, o + z * 0.54), "G", font=police, fill=BLANC, anchor="mm")
    eclair = [(0.70, 0.16), (0.56, 0.47), (0.66, 0.47), (0.52, 0.80), (0.80, 0.40), (0.69, 0.40), (0.80, 0.16)]
    d.polygon([(o + z * x, o + z * y) for x, y in eclair], fill=JAUNE)
    r = z * 0.075
    d.ellipse([o + z * 0.80 - r, o + z * 0.80 - r, o + z * 0.80 + r, o + z * 0.80 + r], fill=ROUGE)
    return im


if __name__ == "__main__":
    docs = os.path.join(RACINE, "docs")
    for t in (192, 512):
        icone(t).save(os.path.join(docs, f"logo-{t}.png"))
        icone(t, 0.12).save(os.path.join(docs, f"logo-{t}-maskable.png"))
    icone(180).save(os.path.join(docs, "logo-apple.png"))
