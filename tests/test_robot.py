"""Tests du robot, sans aucun appel payant : Grok est simulé (SIMULATION=1) ou remplacé par de faux appels."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="grok-tiktok-")
os.environ.update(ROBOT_DOCS=os.path.join(TMP, "docs"), ROBOT_SORTIE=os.path.join(TMP, "sortie"),
                  GITHUB_ACTIONS="false", XAI_API_KEY="")
sys.path.insert(0, RACINE)

from robot import budget, commande, depot, grok, montage, planning, principal, publier, scenario, sons_tiktok  # noqa: E402
from robot.commun import lire, ecrire  # noqa: E402


def env(**kw):
    return mock.patch.dict(os.environ, {k: str(v) for k, v in kw.items()})


class Base(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(os.path.join(TMP, "docs"), ignore_errors=True)
        shutil.copytree(os.path.join(RACINE, "docs", "donnees"), os.path.join(TMP, "docs", "donnees"))
        os.makedirs(os.path.join(TMP, "docs", "miniatures"))
        for nom, vide in (("file.json", {"videos": []}), ("journal.json", {"evenements": []}), ("etat.json", {"essais": {}})):
            ecrire(nom, vide)                                       # repart de zéro, quelles que soient les vraies données
        R = lire("reglages.json")                                   # réglages fixes : les tests ne dépendent pas des vrais
        R["prix"].update(video_seconde=0.02, image=0.04, scenario=0.01)
        R["budget"]["plafond_mensuel_usd"] = 30
        R["planning"].update(courte_chaque_jour=True, jours_longue=["samedi"], heures_publication=[12, 19], pause=False)
        R["montage"]["sous_titres"] = True
        R["montage"]["couper_blancs"] = False
        R["formats"] = {"courte": {"plans_min": 3, "plans_max": 5, "duree_min": 24, "duree_max": 40},
                        "longue": {"plans_min": 7, "plans_max": 10, "duree_min": 66, "duree_max": 95}}
        R["qualite"] = {"producteur": True, "scripte": True, "reprises_max": 1, "jury": True, "note_min": 65}
        R["prix"]["verification"] = 0.01
        R["tiktok"] = {"profils": [], "auto": False, "jours": ["mercredi"], "duree_max": 45, "gilbert": True}
        R["publication"] = {"mode": "manuel", "compte": ""}
        ecrire("reglages.json", R)
        shutil.rmtree(os.path.join(TMP, "docs", "donnees", "portraits"), ignore_errors=True)
        for nom in ("budget.json", "portrait.jpg", "memoire.json"):
            if os.path.exists(os.path.join(TMP, "docs", "donnees", nom)):
                os.remove(os.path.join(TMP, "docs", "donnees", nom))
        os.environ["SIMULATION"] = "1"
        os.environ["ROBOT_MAINTENANT"] = "2026-10-24T06:17:00"          # un samedi

    def file(self):
        return lire("file.json")["videos"]


class Simulation(Base):
    def test_courte_puis_longue_le_samedi(self):
        self.assertEqual(principal.main(["--format", "auto"]), 0)
        vids = self.file()
        self.assertEqual(sorted(v["format"] for v in vids), ["courte", "longue"])
        d = {v["format"]: v for v in vids}
        self.assertTrue(23 <= d["courte"]["duree"] <= 41, d["courte"]["duree"])  # durée adaptée à l'idée
        self.assertGreaterEqual(d["longue"]["duree"], 61)               # plus d'une minute : monétisable
        for v in vids:
            self.assertEqual(v["statut"], "a_publier")
            self.assertTrue(v["simulation"])
            self.assertIn("#ia", v["hashtags"])
            self.assertTrue(os.path.exists(os.path.join(TMP, "docs", v["miniature"])))
        self.assertTrue(d["longue"]["publier_le"].endswith("19:00:00+02:00"))      # la longue vise le soir
        self.assertNotEqual(d["courte"]["publier_le"], d["longue"]["publier_le"])
        # deuxième réveil le même jour : rien de plus
        self.assertEqual(principal.main(["--format", "auto"]), 0)
        self.assertEqual(len(self.file()), 2)
        # le faux portrait de test n'est jamais gardé
        self.assertFalse(os.path.exists(os.path.join(TMP, "docs", "donnees", "portrait.jpg")))

    def test_video_a_le_son_et_le_bon_format(self):
        res = principal.fabriquer("courte")
        mp4 = res["entree"]["url"].replace("file://", "")
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json",
                            mp4], capture_output=True, text=True, check=True)
        flux = json.loads(r.stdout)["streams"]
        self.assertIn({"codec_type": "video", "width": 720, "height": 1280}, flux)
        self.assertTrue(any(s["codec_type"] == "audio" for s in flux))

    def test_avancement(self):
        from robot import avancement
        vus = []
        vrai = avancement._envoyer
        with mock.patch.object(avancement, "_envoyer", lambda force=False: (vus.append(dict(avancement.contenu())), vrai(force))):
            self.assertEqual(principal.main(["--format", "courte"]), 0)
        etapes = [v["etape"] for v in vus]
        self.assertIn("Le scénariste écrit l'épisode", etapes)
        self.assertTrue(any(e.startswith("Tournage du plan 1") for e in etapes))
        pourcents = [v["pourcent"] for v in vus]
        self.assertEqual(pourcents, sorted(pourcents))                      # la barre n'avance que dans un sens
        self.assertEqual((vus[-1]["etat"], vus[-1]["pourcent"], vus[-1]["reste_s"]), ("fini", 100, 0))
        self.assertTrue(vus[-1]["titre"].startswith("[Test]"))
        fichier = json.load(open(os.path.join(TMP, "sortie", "avancement.json"), encoding="utf-8"))
        self.assertEqual(fichier["etat"], "fini")

    def test_jour_sans_longue(self):
        with env(ROBOT_MAINTENANT="2026-10-26T06:17:00"):                # lundi
            self.assertEqual(planning.a_faire(lire("reglages.json"), {"videos": []}, {}), ["courte"])

    def test_pause(self):
        commande.appliquer("pause", "", "")
        self.assertEqual(principal.main(["--format", "auto"]), 0)
        self.assertEqual(self.file(), [])
        principal.main(["--format", "courte"])                       # mode manuel : le bouton Créer marche toujours
        self.assertEqual(len(self.file()), 1)


class AvecFauxGrok(Base):
    """Le vrai chemin payant, avec Grok remplacé par de faux appels qui « coûtent » le prix réel."""

    def setUp(self):
        super().setUp()
        os.environ["SIMULATION"] = "0"
        self.appels = []

        self.scripte_ok, self.note_jury, self.departs, self.prompts = [True], 80, [], []

        def texte(modele, consignes, demande, prix, images=()):
            if "producteur exigeant" in consignes:
                self.appels.append("producteur")
                return {"note": 70, "problemes": ["La fin du plan 1 ne colle pas au début du plan 2."], "scenario": None}, 0.01
            if "scripte d'un tournage" in consignes:
                self.appels.append("scripte")
                ok = self.scripte_ok.pop(0) if len(self.scripte_ok) > 1 else self.scripte_ok[0]
                return {"ok": ok, "ecarts": [] if ok else ["la machine n'a pas explosé"], "correction": "" if ok else
                        "the machine must visibly explode"}, 0.01
            if "jury de critiques" in consignes:
                self.appels.append("jury")
                return {"notes": {"humour": 70, "continuite": 80, "image": 85, "son": 75}, "note": self.note_jury,
                        "points_forts": ["l'effet"], "remarques": ["chute un peu molle"],
                        "lecons": ["Toujours montrer l'expérience en entier."]}, 0.02
            self.appels.append("texte")
            return {"titre": "La 2CV sur la mairie", "legende": "Elle y est encore.", "hashtags": ["humour"],
                    "bible": {"lieu": "garage", "lumiere": "warm", "objets": [{"nom": "2CV", "description": "blue car"}]},
                    "plans": [{"personnage": "gilbert", "duree": 10, "enchaine": k > 0, "cadrage": "medium",
                               "debut": f"etat {k}", "deroule": ["0-5s: action"], "fin": f"etat {k + 1}",
                               "dialogue": "mot " * 60} for k in range(7)]}, 0.01

        def image(modele, prompt, *a):
            self.appels.append("image")
            dest = a[-2]
            return grok._fausse_image(dest, "img"), 0.04

        def video(modele, prompt, image, duree, dest, prix, resolution="720p", suivi=None):
            if suivi:
                suivi(40)
            self.appels.append("video")
            self.departs.append(image)
            self.prompts.append(prompt)
            return grok._faux_clip(dest, duree, prompt), round(duree * prix, 4)

        self.p = [mock.patch.object(grok, "transcrire", lambda c, *a, **k: (grok._fausse_transcription(c), 0.0)),
                  mock.patch.object(grok, "ecrire_json", texte), mock.patch.object(grok, "creer_image", image),
                  mock.patch.object(grok, "modifier_image", image), mock.patch.object(grok, "creer_video", video)]
        for p in self.p:
            p.start()

    def tearDown(self):
        for p in self.p:
            p.stop()



class FauxGrok(AvecFauxGrok):
    # courte : 7 plans de 10 s proposés → 5 plans ramenés à 40 s au plus. Coût : portrait 0,04 + scénario 0,01
    # + producteur 0,01 + 1 image de départ 0,04 (les autres plans s'enchaînent) + 40 s × 0,02 + scripte 5 × 0,01 + jury 0,02
    COURTE = 0.04 + 0.01 + 0.01 + 0.04 + 0.8 + 0.05 + 0.02

    def test_couts_continuite_et_portrait(self):
        self.assertEqual(principal.main(["--format", "courte"]), 0)
        v = self.file()[0]
        self.assertAlmostEqual(v["cout_usd"], self.COURTE, places=4)
        self.assertAlmostEqual(lire("budget.json")["depense_usd"], v["cout_usd"], places=4)
        self.assertTrue(os.path.exists(os.path.join(TMP, "docs", "donnees", "portrait.jpg")))
        self.assertEqual((len(v["plans"]), sum(p["duree"] for p in v["plans"])), (5, 40))
        self.assertLessEqual(len(v["plans"][0]["dialogue"].split()), 21)          # 8 s × 2,5 mots
        for k in range(1, 5):                                                     # chaque plan démarre sur la fin du précédent
            self.assertTrue(self.departs[k].endswith(f"fin_{k}.jpg"), self.departs[k])
        self.assertIn("START OF THE SHOT", self.prompts[1])
        self.assertIn("etat 1", self.prompts[1])
        self.assertEqual(v["qualite"]["producteur"]["note"], 70)
        self.assertEqual(v["qualite"]["jury"]["note"], 80)
        self.assertFalse(v["a_revoir"])
        self.assertEqual(self.appels.count("scripte"), 5)
        self.assertIn("Toujours montrer l'expérience en entier.", lire("memoire.json")["lecons"][0]["texte"])
        # deuxième vidéo : le portrait existe déjà ; le scénariste reçoit les leçons du jury
        self.appels.clear()
        principal.main(["--format", "courte"])
        self.assertEqual(self.appels.count("image"), 1)

    def test_scripte_fait_refaire_un_plan(self):
        self.scripte_ok = [False, True]
        self.assertEqual(principal.main(["--format", "courte"]), 0)
        v = self.file()[0]
        self.assertEqual(self.appels.count("video"), 6)                         # 5 plans + 1 reprise
        self.assertIn("FIX THESE PROBLEMS", self.prompts[1])
        self.assertTrue(v["qualite"]["scripte"][0]["reprise"])
        self.assertAlmostEqual(v["cout_usd"], self.COURTE + 0.16, places=4)     # reprise du plan 1 (8 s × 0,02)

    def test_jury_a_revoir(self):
        self.note_jury = 40
        commande.appliquer("reglages", "", json.dumps({"publication": {"mode": "auto"}}))
        self.assertEqual(principal.main(["--format", "courte"]), 0)
        v = self.file()[0]
        self.assertTrue(v["a_revoir"])
        self.assertEqual(v["statut"], "a_publier")                              # jamais publiée automatiquement
        textes = " ".join(e["texte"] for e in lire("journal.json")["evenements"])
        self.assertIn("à revoir", textes)

    def test_un_seul_secondaire(self):
        P = lire("personnage.json")
        f = {"plans_min": 3, "plans_max": 5, "duree_min": 24, "duree_max": 40}
        ep = scenario.nettoyer({"plans": [
            {"personnage": "gilbert", "visibles": ["gilbert", "mat", "newton"], "duree": 8},
            {"personnage": "bouc", "visibles": ["bouc", "gilbert"], "duree": 8},
            {"personnage": "mat", "visibles": ["mat", "lola"], "duree": 8}]}, f, P)
        self.assertEqual([p["personnage"] for p in ep["plans"]], ["gilbert", "gilbert", "mat"])
        self.assertEqual([p["visibles"] for p in ep["plans"]], [["gilbert", "mat", "newton"], ["gilbert"], ["mat"]])

    def test_avis_de_l_auteur(self):
        principal.main(["--format", "courte"])
        vid = self.file()[0]["id"]
        commande.appliquer("avis", vid, json.dumps({"pouce": -1, "remarque": "On ne voit pas l'explosion"}))
        self.assertEqual(self.file()[0]["avis_auteur"]["pouce"], -1)
        self.assertIn("On ne voit pas l'explosion", lire("memoire.json")["lecons"][0]["texte"])
        from robot import production
        self.assertIn("On ne voit pas l'explosion", production.memoire_texte())

    def test_personnage_secondaire(self):
        vrai = grok.ecrire_json

        def avec_mat(modele, consignes, *a, **k):
            ep, c = self_texte(modele, consignes, *a, **k)
            if "plans" in ep:
                ep["plans"][1]["personnage"] = "mat"
                ep["plans"][0]["personnage"] = "inconnu"                  # id inconnu : c'est Gilbert
            return ep, c
        self_texte = grok.ecrire_json
        with mock.patch.object(grok, "ecrire_json", avec_mat):
            self.assertEqual(principal.main(["--format", "courte"]), 0)
        v = self.file()[0]
        self.assertEqual([p["personnage"] for p in v["plans"]], ["gilbert", "mat", "gilbert", "gilbert", "gilbert"])
        self.assertEqual([p["enchaine"] for p in v["plans"]], [False, False, False, True, True])
        self.assertTrue(os.path.exists(os.path.join(TMP, "docs", "donnees", "portraits", "mat.jpg")))
        self.assertEqual(self.appels.count("image"), 5)                 # 2 portraits + 3 images de départ
        self.assertIs(grok.ecrire_json, vrai)

    def test_plafond_respecte(self):
        R = lire("reglages.json")
        ecrire("budget.json", {"mois": "2026-10", "depense_usd": R["budget"]["plafond_mensuel_usd"] - 0.3,
                               "lignes": [], "historique": {}})
        self.assertEqual(principal.main(["--format", "courte"]), 1)
        self.assertEqual(self.appels, [])                            # aucune dépense lancée
        self.assertEqual(self.file(), [])
        self.assertIn("plafond", lire("journal.json")["evenements"][0]["texte"])

    def test_nouveau_mois(self):
        ecrire("budget.json", {"mois": "2026-09", "depense_usd": 29.5, "lignes": [{"usd": 29.5}], "historique": {}})
        b = budget.charger(lire("reglages.json"))
        self.assertEqual((b["mois"], b["depense_usd"], b["historique"]["2026-09"]), ("2026-10", 0.0, 29.5))

    def test_moderation_un_nouvel_essai(self):
        vrai = grok.creer_video
        n = {"refus": 0}

        def parfois(*a, **k):
            if n["refus"] == 0:
                n["refus"] += 1
                raise grok.RefusModeration("refusé", 0.2)
            return vrai(*a, **k)
        with mock.patch.object(grok, "creer_video", parfois):
            self.assertEqual(principal.main(["--format", "courte"]), 0)
        self.assertAlmostEqual(self.file()[0]["cout_usd"], self.COURTE + 0.2, places=4)

    def test_echec_auto_compte(self):
        with mock.patch.object(grok, "creer_video", side_effect=grok.ErreurGrok("panne")):
            principal.main(["--format", "auto"])
            principal.main(["--format", "auto"])
            self.assertEqual(principal.main(["--format", "auto"]), 0)     # 2 essais par format, puis on arrête
        self.assertEqual(lire("etat.json")["essais"]["2026-10-24"], {"courte": 2, "longue": 2})
        self.assertGreater(lire("budget.json")["depense_usd"], 0)        # les images payées restent comptées


class Buffer(AvecFauxGrok):
    """Publication par Buffer, avec Buffer remplacé par de faux appels."""

    def setUp(self):
        super().setUp()
        self.envois = []

        def gql(requete):
            self.envois.append(requete)
            if "createPost" in requete:
                return {"createPost": {"post": {"id": f"p{len(self.envois)}"}}}
            if "deletePost" in requete:
                return {"deletePost": {"__typename": "DeletePostSuccess"}}
            raise AssertionError(requete)
        for p in (mock.patch.object(publier, "_gql", gql),
                  mock.patch.object(publier, "comptes_tiktok", lambda: [{"id": "c1", "nom": "gilbert"}]),
                  mock.patch.object(depot, "publier_release", lambda tag, t, f: f"https://exemple.org/{tag}.mp4"),
                  mock.patch.dict(os.environ, {"BUFFER_API_KEY": "faux"})):
            p.start()
            self.p.append(p)

    def test_publication_automatique_puis_annulation(self):
        commande.appliquer("reglages", "", json.dumps({"publication": {"mode": "auto"}}))
        self.assertEqual(principal.main(["--format", "courte"]), 0)
        v = self.file()[0]
        self.assertEqual((v["statut"], v["buffer"]["id"]), ("programmee", "p1"))
        self.assertIn("isAiGenerated: true", self.envois[0])              # étiquette IA demandée
        self.assertIn("customScheduled", self.envois[0])
        with mock.patch.dict(os.environ, {"ACTION": "annuler_programmation", "ID": v["id"], "TEXTE": ""}):
            self.assertEqual(commande.main(), 0)
        self.assertIn("deletePost", self.envois[-1])
        v = self.file()[0]
        self.assertEqual(v["statut"], "a_publier")
        self.assertNotIn("buffer", v)

    def test_manuel_rien_n_est_envoye(self):
        self.assertEqual(principal.main(["--format", "courte"]), 0)
        self.assertEqual(self.file()[0]["statut"], "a_publier")
        self.assertFalse(any("createPost" in e for e in self.envois))
        with mock.patch.dict(os.environ, {"ACTION": "tiktok_maintenant", "ID": self.file()[0]["id"], "TEXTE": ""}):
            self.assertEqual(commande.main(), 0)                            # bouton « Envoyer par Buffer → Maintenant »
        self.assertIn("shareNow", self.envois[-1])
        self.assertEqual(self.file()[0]["statut"], "publiee")

    def test_programmee_passee_devient_publiee(self):
        f = {"videos": [{"id": "x", "statut": "programmee", "publier_le": "2026-10-24T05:00:00+02:00"}]}
        self.assertEqual(publier.mettre_a_jour(f)["videos"][0]["statut"], "publiee")


class Commandes(Base):
    def test_cycle_de_vie(self):
        principal.main(["--format", "courte"])
        vid = self.file()[0]["id"]
        commande.appliquer("legende", vid, "  Nouvelle légende  ")
        commande.appliquer("publiee", vid, "https://www.tiktok.com/@x/video/1")
        v = self.file()[0]
        self.assertEqual((v["statut"], v["legende"], v["lien_tiktok"][:5]), ("publiee", "Nouvelle légende", "https"))
        commande.appliquer("supprimer", vid, "")
        self.assertEqual(self.file(), [])

    def test_reglages_bornes(self):
        commande.appliquer("reglages", "", json.dumps({"plafond_mensuel_usd": 5000, "jours_longue": ["samedi", "xx"],
                                                        "heures_publication": [19, 12, 99], "courte_chaque_jour": False}))
        R = lire("reglages.json")
        self.assertEqual(R["budget"]["plafond_mensuel_usd"], 200)
        self.assertEqual(R["planning"]["jours_longue"], ["samedi"])
        self.assertEqual(R["planning"]["heures_publication"], [12, 19])

    def test_secondaires(self):
        commande.appliquer("personnage", "", json.dumps({"secondaires": [
            {"id": "mat", "nom": "Mat", "age": "19", "apparence": "young man", "repliques": ["Sérieux ?", ""]},
            {"nom": "Nouvelle Voisine !", "apparence": "woman"}, {"nom": ""}]}))
        S = lire("personnage.json")["secondaires"]
        self.assertEqual([c["id"] for c in S], ["mat", "nouvellevoisine"])
        self.assertEqual((S[0]["age"], S[0]["repliques"]), (19, ["Sérieux ?"]))
        self.assertEqual(scenario.qui({"personnage": "mat"}, lire("personnage.json"))["nom"], "Mat")

    def test_personnage(self):
        commande.appliquer("personnage", "", json.dumps({"nom": "Gaston", "age": "61", "gags_recurrents": ["a", "", "b"]}))
        P = lire("personnage.json")
        self.assertEqual((P["nom"], P["age"], P["gags_recurrents"]), ("Gaston", 61, ["a", "b"]))
        self.assertTrue(P["apparence"])                                  # champ absent = inchangé


class SonsTikTok(Base):
    def test_video_sur_un_son(self):
        self.assertEqual(principal.main(["--format", "tiktok", "--lien", "https://www.tiktok.com/@drole/video/42"]), 0)
        v = self.file()[0]
        self.assertEqual((v["format"], v["source"]), ("tiktok", "https://www.tiktok.com/@drole/video/42"))
        self.assertAlmostEqual(v["duree"], 24, delta=0.5)               # exactement la durée du son d'origine
        self.assertIn("🎧", v["legende"])
        mp4 = v["url"].replace("file://", "")
        self.assertAlmostEqual(montage.duree(mp4), 24, delta=0.5)

    def test_liste_vide_profils_connus(self):
        self.assertEqual(principal.main(["--format", "tiktok"]), 0)          # liste vide : profils déjà connus
        self.assertIn("yan_animation0", sons_tiktok.connus())
        f = {"videos": [{"source": "https://www.tiktok.com/@nouveau.compte/video/9"},
                        {"source": "https://www.tiktok.com/@petitsdramas/video/8"}]}
        self.assertEqual(sons_tiktok.connus(f)[-1], "nouveau.compte")       # un lien collé fait connaître son compte
        self.assertNotIn("petitsdramas", sons_tiktok.connus(f))             # jamais notre propre chaîne
        self.assertEqual(len(lire("reglages.json")["tiktok"]["profils"]), 0)

    def test_mauvais_lien(self):
        self.assertEqual(principal.main(["--format", "tiktok", "--lien", "https://youtube.com/x"]), 1)

    def test_planning_et_reglages(self):
        commande.appliquer("reglages", "", json.dumps({"tiktok": {"profils": "@aa\nhttps://www.tiktok.com/@b.c?x=1\n@aa",
                                                                   "auto": True, "jours": ["samedi"], "duree_max": 500}}))
        T = lire("reglages.json")["tiktok"]
        self.assertEqual((T["profils"], T["duree_max"]), (["aa", "b.c"], 90))
        self.assertIn("tiktok", planning.a_faire(lire("reglages.json"), {"videos": []}, {}))

    def test_decoupage(self):
        mots = [{"w": f"m{k}", "s": k * 0.4, "e": k * 0.4 + 0.3, "voix": 0} for k in range(25)]       # 10 s d'une voix
        mots += [{"w": "quoi", "s": 11.0, "e": 11.4, "voix": 1}]
        plans = sons_tiktok.decouper(sons_tiktok.repliques(mots), 12.5, True)
        self.assertEqual([p["role"] for p in plans], ["parle", "ecoute", "parle"])   # longue réplique : on voit l'autre écouter
        self.assertEqual(plans[0]["debut"], 0)
        self.assertEqual(plans[-1]["fin"], 12.5)
        for a, b in zip(plans, plans[1:]):
            self.assertEqual(a["fin"], b["debut"])                      # aucun trou, aucun chevauchement
        self.assertTrue(all(p["fin"] - p["debut"] <= 14 for p in plans))

    def test_calage(self):
        clip = grok._faux_clip(os.path.join(TMP, "c.mp4"), 6, "x")
        plan = {"debut": 10.0, "fin": 13.0, "mots": [{"w": "a", "s": 10.5, "e": 11.0}, {"w": "b", "s": 11.2, "e": 12.5}]}
        mots_clip = [{"w": "a", "s": 1.0, "e": 1.5}, {"w": "b", "s": 1.8, "e": 3.0}]
        dest, facteur, _ = sons_tiktok.caler(clip, mots_clip, plan, True, os.path.join(TMP, "cale.mp4"))
        self.assertAlmostEqual(facteur, 1.0, places=1)
        self.assertAlmostEqual(montage.duree(dest), 3.0, delta=0.1)


class Divers(Base):
    def test_estimations(self):
        R = lire("reglages.json")
        # courte : 40 s × 0,02 + 3 images × 0,04 + scénario et producteur 2 × 0,01 + 7 contrôles × 0,01
        self.assertAlmostEqual(budget.estimation("courte", R), 1.01, places=2)
        self.assertAlmostEqual(budget.estimation("longue", R), 2.24, places=2)

    def test_creneaux(self):
        R = lire("reglages.json")
        with env(ROBOT_MAINTENANT="2026-10-24T18:30:00"):
            self.assertTrue(planning.creneau(R, {"videos": []}, "courte").startswith("2026-10-25T12"))

    def test_sous_titres(self):
        chemin = os.path.join(TMP, "t.ass")
        from robot import montage
        montage.sous_titres([{"dialogue": "Bon. On va pas se mentir, c'est {un} succès."}, {"dialogue": ""}], [10, 10],
                            chemin)
        lignes = [l for l in open(chemin, encoding="utf-8") if l.startswith("Dialogue")]
        self.assertEqual(len(lignes), 2)
        self.assertNotIn("{un}", "".join(lignes))

    def test_javascript_du_site(self):
        if not shutil.which("node"):
            self.skipTest("node absent")
        html = open(os.path.join(RACINE, "docs", "index.html"), encoding="utf-8").read()
        js = "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))
        f = os.path.join(TMP, "site.js")
        open(f, "w").write(js)
        subprocess.run(["node", "--check", f], check=True)


if __name__ == "__main__":
    unittest.main()
