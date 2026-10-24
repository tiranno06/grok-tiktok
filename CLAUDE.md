# Régie Gilbert (grok-tiktok)

Robot de vidéos TikTok réalistes faites avec Grok Imagine (xAI), et site de gestion. Projet frère de `jt-auto`
(dessins animés, @petitsdramas). Le propriétaire est débutant : tout en français (code, commentaires, commits, textes du site),
explications simples. Ne jamais écrire une clé en clair (secret GitHub `XAI_API_KEY` uniquement).

## Choix du propriétaire (23/10/2026)
- Images réalistes, personnage récurrent **Gilbert Mouchon** (fiche modifiable depuis le site, `docs/donnees/personnage.json`).
- **Publication toujours à la main** depuis le site (bouton Publier → Télécharger, Copier la légende, C'est publié) : pas d'API TikTok, pas de Buffer.
- **Création automatique ou manuelle** (24/10, Réglages → Création des vidéos) : manuel = `planning.pause` vrai (actions `pause` /
  `reprise`), les réveils programmés ne créent plus rien ; seul le bouton Créer (`--format courte|longue`) fabrique.
- **Son intégré de Grok Imagine** (voix comprise), pas d'ElevenLabs.
- Budget : 30 €/mois au plus → plafond 30 $ (≈ 26 €) dans `reglages.json`. Une courte (20 s) par jour, une longue (84 s,
  > 1 min pour la rémunération TikTok) le samedi ≈ 23 $/mois.

## Fonctionnement
- `robot/principal.py` (workflow `robot.yml`, réveils 4 h 17, 7 h 17, 10 h 17 UTC + bouton Créer du site) :
  `planning.a_faire` → `scenario.ecrire` (Grok texte, JSON) → pour chaque plan : `grok.modifier_image` (portrait de référence
  → image de départ du plan, même visage) puis `grok.creer_video` (image-to-video, 9:16, 720p, avec son) → `montage.monter`
  (ffmpeg, sous-titres ASS en Poppins) → Release `v-<id>` → `ranger` écrit `docs/donnees/*.json` + `docs/miniatures/`.
- API xAI : `POST /v1/videos/generations` puis `GET /v1/videos/{id}` (status done/failed/expired, `video.url`,
  `usage.cost_in_usd_ticks` : 1e10 ticks = 1 $, coût réel compté). Lite (`grok-imagine-video-1.5-lite`) : pas de
  `reference_images`, d'où l'image de départ tirée du portrait (`/v1/images/edits`).
- **Budget** (`budget.py`) : `Caisse.autoriser` avant chaque appel payant ; refus = rien n'est lancé. Les dépenses d'une vidéo
  ratée sont quand même comptées. Remise à zéro le 1er du mois (`historique`).
- **Écritures concurrentes** : `depot.enregistrer(fonction)` repart toujours de la dernière version en ligne
  (fetch + reset), applique, pousse, recommence si quelqu'un est passé entre-temps. Toute écriture de données passe par là.
- Site `docs/index.html` (GitHub Pages, branche main, dossier /docs) : lit `docs/donnees/` (ou l'API GitHub avec la clé,
  plus à jour), envoie les ordres par `workflow_dispatch` (`robot.yml`, `commande.yml`) avec la clé fine-grained du
  navigateur (`gt_jeton`, droit Actions). Démo automatique si les données sont introuvables.
- Simulation (`SIMULATION=1`, case « Test gratuit ») : fausses images et vidéos ffmpeg, aucun appel, faux portrait jamais gardé.

## Avant d'envoyer
`python -m unittest discover -s tests` (aucun appel payant ; workflow `tests.yml`). Pour tester le site : servir `docs/`
et l'ouvrir à 400 px de large.
