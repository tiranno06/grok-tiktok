# Régie Gilbert : vidéos TikTok réalistes avec Grok Imagine

Chaque matin, le robot :
1. **écrit un épisode** avec Grok (titre, légende, hashtags, découpage en plans) autour du personnage récurrent
   **Gilbert Mouchon**, vlogueur pince-sans-rire d'un village imaginaire, sa voisine invisible Monique et son pigeon Napoléon ;
2. **fait filmer chaque plan** par **Grok Imagine** (modèle *Video 1.5 Lite*, avec le son et la voix). Chaque plan part
   d'une image de Gilbert tirée de son **portrait de référence** : il garde le même visage d'une vidéo à l'autre ;
3. **monte la vidéo** : format vertical 720×1280, son égalisé, sous-titres incrustés ;
4. la range dans les **Releases** du dépôt et l'affiche sur le **site**, avec l'heure conseillée pour la publier.

**Publication sur TikTok**, au choix dans **Réglages → Publication sur TikTok** (comme jt-auto) :
- *Manuelle* : bouton **Publier** → Télécharger → Copier la légende → C'est publié.
- *Automatique* : chaque nouvelle vidéo est programmée sur **Buffer** à l'heure conseillée, avec l'étiquette « Contenu généré
  par l'IA ». Jusqu'à l'heure prévue, **Annuler la programmation** la retire de Buffer.
- Dans les deux cas, **Envoyer par Buffer** sur une vidéo l'envoie tout de suite ou à l'heure conseillée.

Pour Buffer : ta clé API Buffer (la même que jt-auto) dans le secret GitHub `BUFFER_API_KEY`, et le compte TikTok de
Gilbert relié à Buffer (publish.buffer.com → Channels → Connect → TikTok ; le plan gratuit accepte 3 comptes). Si plusieurs
comptes TikTok sont reliés, écris le nom de celui de Gilbert dans Réglages, puis **Vérifier Buffer** : le Journal affiche
les comptes trouvés.

**Automatique ou manuel**, au choix dans **Réglages → Création des vidéos** :
- *Automatique* : le robot crée chaque matin les vidéos du planning (courte chaque jour, longue le samedi ; les deux se règlent).
- *Manuelle* : rien ne se crée tout seul, ni le matin ni le samedi. Tu crées chaque vidéo avec le bouton **Créer**.

| Vidéo | Durée | Coût prévu |
|---|---|---|
| Courte, chaque jour | 20 s (2 plans de 10 s) | ~0,77 $ |
| Longue, le samedi | 84 s (6 plans de 14 s), plus d'une minute pour la rémunération TikTok | ~3,03 $ |

En automatique complet (courte chaque jour + longue le samedi), il faudrait **environ 37 $ par mois**, plus que 30 € :
le plafond (réglable dans Réglages) arrête le robot avant de le dépasser, et il reprend le 1er du mois.
Coûts réels constatés le 24/10/2026 (720p) : vidéo 0,031 $/s, image de départ 0,07 $, scénario ~0,01 $. Le coût réel
renvoyé par Grok est celui qui est compté.

## Sons TikTok (onglet du site)
Le robot prend une vidéo TikTok drôle (lien collé, ou au hasard de tes profils, jamais deux fois la même), **garde seulement
son son**, puis tourne une nouvelle vidéo réaliste autour :
1. xAI transcrit le son et sépare les voix (qui dit quoi, et quand) ;
2. Grok regarde quelques images de la vidéo d'origine pour comprendre la situation, puis invente les personnages
   (fictifs, jamais les vraies personnes de la vidéo ; Gilbert peut jouer le rôle principal), les lieux et les gestes ;
3. chaque réplique est filmée par Grok Imagine ; on voit aussi celui qui écoute réagir pendant les longues répliques ;
4. au montage, chaque plan est recalé (et un peu accéléré ou ralenti) pour que la bouche tombe sur la parole d'origine,
   puis le son d'origine est remis tel quel. C'est un doublage : la synchronisation des lèvres est bonne mais pas parfaite.

Coût : environ 1 $ pour un son de 15 s, 1,80 $ pour 30 s, 2,60 $ pour 45 s. Durée maximale réglable (45 s par défaut).
Le compte d'origine est cité dans la légende (🎧 Son : @compte).

---

## Installation (une seule fois, environ 20 minutes)

### 1. Le site
Dans le dépôt : **Settings → Pages** → *Source* : **Deploy from a branch** → branche **main**, dossier **/docs** → *Save*.
Une minute plus tard, le site est en ligne à l'adresse **https://<ton-pseudo>.github.io/grok-tiktok/**.
Sur Android, ouvre-la dans Chrome, puis menu ⋮ → *Ajouter à l'écran d'accueil*.

### 2. La clé Grok (xAI)
1. Va sur **console.x.ai** et crée un compte.
2. **Billing** : ajoute du crédit (25 à 30 $ pour un mois). Si la console propose une limite de dépense mensuelle, mets 30 $ :
   ça fait une deuxième sécurité en plus de celle du robot.
3. **API Keys → Create API Key**, puis copie la clé (`xai-…`).
4. Dans le dépôt GitHub : **Settings → Secrets and variables → Actions → New repository secret**.
   Nom : `XAI_API_KEY`, valeur : la clé. **Ne la colle jamais ailleurs** (ni dans un chat, ni dans un message).

### 3. La clé GitHub du site (pour que les boutons agissent)
1. Ouvre **github.com/settings/personal-access-tokens/new**.
2. Nom : `regie-gilbert`. *Repository access* : **Only select repositories** → `grok-tiktok`.
3. *Permissions* → **Actions** : *Read and write*. Rien d'autre.
4. *Generate token*, copie la clé, puis colle-la sur le site dans **Réglages → Clé GitHub de ce téléphone**.
   Elle reste seulement dans ton navigateur.

### 4. Test gratuit
Sur le site : **Créer** → coche **Test gratuit** → *Lancer la création*.
Au bout de 3 à 5 minutes, une fausse vidéo (mire de couleurs, marquée TEST) arrive dans **À publier**.
Aucune IA n'est appelée et rien n'est dépensé. Ce test vérifie que le site, le robot, le montage et les Releases marchent.
Tu peux ensuite la supprimer : **Écarter**, puis **Supprimer**.

### 5. Première vraie vidéo
**Créer → Courte → Lancer la création**, sans cocher le test. Le robot crée d'abord le portrait de Gilbert
(onglet **Personnage**), puis la vidéo. Regarde-la, et vérifie son coût dans **Budget**.
Si la voix ou le visage ne te plaisent pas : **Personnage** → modifie l'apparence ou la voix → **Refaire le portrait**.

Ensuite, en mode automatique : une courte chaque jour, une longue le samedi. En mode manuel : seulement quand tu appuies sur **Créer**.

---

## Au quotidien
- **À publier** : les vidéos prêtes, avec l'heure conseillée (12 h, et 19 h pour les longues). **Refaire** commande une
  autre version, **Écarter** la met de côté.
- Sur TikTok, active toujours **« Contenu généré par l'IA »** (Plus d'options) : c'est obligatoire pour ces vidéos.
- **Réglages** : création automatique ou manuelle, plafond, jours des longues, heures, sous-titres.
- **Journal** : ce que fait le robot, et pourquoi une vidéo a raté.

## Si quelque chose ne va pas
- « clé refusée par xAI » dans le Journal : vérifie le secret `XAI_API_KEY` et ton crédit sur console.x.ai.
- « plafond du mois atteint » : normal, le robot reprend le 1er. Tu peux aussi monter le plafond dans Réglages.
- « plan refusé par la modération » : le robot réessaie une fois avec un plan plus sobre. Le plan refusé est quand même facturé.
- Un réveil raté est retenté deux fois dans la matinée (vers 6 h, 9 h et 12 h), pas plus.

À savoir : le dépôt est public, comme celui de jt-auto (minutes du robot gratuites). Les titres des vidéos et le budget
sont donc visibles. Tes clés restent secrètes.
