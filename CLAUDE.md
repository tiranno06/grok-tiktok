# Régie Gilbert (grok-tiktok)

Robot de vidéos TikTok réalistes faites avec Grok Imagine (xAI), et site de gestion. Projet frère de `jt-auto`
(dessins animés, @petitsdramas). Le propriétaire est débutant : tout en français (code, commentaires, commits, textes du site),
explications simples. Ne jamais écrire une clé en clair (secret GitHub `XAI_API_KEY` uniquement).

## Choix du propriétaire (23/10/2026)
- Images réalistes, personnage récurrent **Gilbert Mouchon** (fiche modifiable depuis le site, `docs/donnees/personnage.json`).
  Depuis le 24/10 : **inventeur fou** inspiré du savant excentrique de Retour vers le futur (sans jamais citer le film ni ses
  éléments) : inventions ubuesques qui merdouillent à chaque fois, de façon drôle. Cheveux blancs en bataille, blouse, lunettes
  de soudeur. Portrait à refaire après tout changement d'apparence (supprimé le 24/10 : recréé à la vidéo suivante).
- **Publication manuelle ou automatique** (24/10, comme jt-auto, `robot/publier.py`, `reglages.publication` : mode, compte) :
  manuelle = bouton Publier (Télécharger, Copier la légende, C'est publié) ; automatique = `principal.programmer` programme
  chaque vidéo sur Buffer (GraphQL `createPost`, `isAiGenerated`, `dueAt` = heure conseillée) → statut `programmee`
  (`buffer.id`), `annuler_programmation` / écarter = `deletePost`. Secret `BUFFER_API_KEY`. Les appels Buffer sont faits
  une seule fois AVANT `depot.enregistrer` (qui peut se répéter). Heure passée → `publiee` (`publier.mettre_a_jour`).
- **Création automatique ou manuelle** (24/10, Réglages → Création des vidéos) : manuel = `planning.pause` vrai (actions `pause` /
  `reprise`), les réveils programmés ne créent plus rien ; seul le bouton Créer (`--format courte|longue`) fabrique.
- **Son intégré de Grok Imagine** (voix comprise), pas d'ElevenLabs.
- Budget : 30 €/mois au plus (plafond réglable dans `reglages.json`, 5 $ choisi par le propriétaire le 24/10). Coûts réels
  du 24/10 en 720p : courte 20 s ≈ 0,77 $, longue 84 s ≈ 3,03 $ (clip 0,031 $/s, image de départ 0,07 $).

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

- **Épisodes de Gilbert** (24/10, après la 1re vraie vidéo jugée pas assez drôle et trop figée) : Grok (`grok-4.7`) propose
  5 idées et garde la plus drôle (consignes d'écriture TikTok dans `scenario.CONSIGNES`) ; jeu naturel (`scenario.JEU`),
  cadrages variés, `objets` identiques dans tous les plans, plan au même lieu = départ de la dernière image du plan précédent ;
  chaque clip est transcrit (`grok.transcrire`, POST /v1/stt) : sous-titres mot à mot calés sur la vraie voix, blancs coupés
  avec un léger zoom un morceau sur deux (`principal.rythmer`, une longue reste ≥ 62 s).
- **Sons TikTok** (24/10, `robot/sons_tiktok.py`, `--format tiktok --lien …`, onglet « Sons TikTok » du site, réglages
  `reglages.tiktok` : profils, auto + jours, duree_max) : yt-dlp (imitation navigateur) puis tikwm ; transcription
  avec voix séparées (`diarize`) ; `decouper` (un plan par réplique, plan « écoute » au milieu des longues répliques, ≤ 14 s) ;
  Grok vision (`modeles.vision`) crée de toutes pièces, pour chaque son, personnages (jamais Gilbert, jamais les vraies
  personnes), lieu, décor et cadrages ; un portrait par personnage ; `caler` recale
  la parole du clip Grok sur la parole d'origine (vitesse ×0,75 à ×1,35) ; `assembler` remet le son d'origine. Pas de vraie
  synchronisation labiale chez xAI (pas d'entrée audio) : c'est un doublage.
- **Profils de sketchs** (24/10) : `reglages.tiktok.profils` pré-rempli avec les 9 profils connus de jt-auto
  (`sons_tiktok.PROFILS_CONNUS`) ; liste vide = `connus(file)` (ceux de jt-auto + comptes des vidéos déjà reprises, jamais
  @petitsdramas). Bouton du site « Ajouter les profils déjà connus ».

- **Appli Android** (24/10, comme jt-auto) : `docs/manifest.webmanifest`, `docs/sw.js` (page et données : réseau d'abord,
  copie si hors ligne ; jamais les .mp4), icônes `docs/logo-*.png` (`outils/icones.py`), bouton « 📲 Installer l'application »
  (`beforeinstallprompt`). Clé GitHub vers un autre appareil : QR code (Réglages → Connecter un autre appareil), la clé voyage
  dans le `#cle=…` du lien (jamais envoyé au serveur), lue puis effacée de l'adresse au chargement.
- **Gilbert = hommage à Doc** (24/10) : fiche complète dans `personnage.json`, champ `repliques` (phrases à la Doc, une ou
  deux par épisode). Clins d'œil permis ; jamais « Doc », « Marty », « DeLorean », « convecteur temporel », le titre du film,
  ni ressemblance avec l'acteur (visage de Gilbert : rond, moustache de morse, lunettes).
- **Personnages secondaires** (24/10) : vraie adaptation de Retour vers le futur sous d'autres noms (`personnage.secondaires` :
  mat = Marty, bouc = Biff, gerard = George, lola = Jennifer, laurence = Lorraine, maire = Strickland), chacun avec rôle,
  apparence, voix, `gestuelle` (gestes et mimiques, aussi pour Gilbert), personnalité, répliques. Plan = UNE personne
  (`plan.personnage`, `scenario.qui`), portrait de chacun dans `docs/donnees/portraits/<id>.jpg` (fait à la 1re apparition,
  refait si son apparence change). 0 à 2 secondaires par épisode, environ un épisode sur deux en solo.

## Avant d'envoyer
`python -m unittest discover -s tests` (aucun appel payant ; workflow `tests.yml`). Pour tester le site : servir `docs/`
et l'ouvrir à 400 px de large.
