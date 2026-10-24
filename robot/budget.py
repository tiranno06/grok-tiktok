"""Garde-fou du budget : le robot ne lance jamais une dépense qui ferait passer le mois au-dessus du plafond."""
from .commun import lire, ecrire, maintenant, simulation


def estimation(format_, R):
    """Coût prévu d'une vidéo, en dollars, au plus long : secondes de vidéo, images de départ (environ un plan sur deux
    change de personne), scénario + relecture du producteur, contrôle du scripte à chaque plan et jury. Sans les reprises."""
    f, p = R["formats"][format_], R["prix"]
    plans = f["plans_max"]
    return round(f["duree_max"] * p["video_seconde"] + (plans + 1) // 2 * p["image"] + 2 * p["scenario"]
                 + (plans + 2) * p.get("verification", 0.01), 2)


def charger(R):
    """Budget du mois en cours (remis à zéro le 1er du mois, l'ancien total est gardé dans l'historique)."""
    mois = maintenant().strftime("%Y-%m")
    b = lire("budget.json") or {"mois": mois, "depense_usd": 0.0, "lignes": [], "historique": {}}
    if b.get("mois") != mois:
        b.setdefault("historique", {})[b.get("mois", "?")] = round(b.get("depense_usd", 0.0), 2)
        b.update(mois=mois, depense_usd=0.0, lignes=[])
    b["plafond_usd"] = R["budget"]["plafond_mensuel_usd"]
    return b


def reste(R):
    b = charger(R)
    return round(b["plafond_usd"] - b["depense_usd"], 4)


def ajouter(R, lignes):
    """Enregistre des dépenses [{date, usd, quoi, video}] (appelé au moment d'enregistrer dans le dépôt)."""
    b = charger(R)
    for l in lignes:
        if l.get("usd", 0) > 0:
            b["lignes"].append(l)
            b["depense_usd"] = round(b["depense_usd"] + l["usd"], 4)
    del b["lignes"][:-300]
    ecrire("budget.json", b)
    return b


class Caisse:
    """Compte les dépenses d'une fabrication en cours et refuse celle qui dépasserait le plafond."""

    def __init__(self, R, video=""):
        self.R, self.video, self.lignes = R, video, []
        self.dispo = float("inf") if simulation() else reste(R)      # le test gratuit ne coûte rien

    @property
    def depense(self):
        return round(sum(l["usd"] for l in self.lignes), 4)

    def autoriser(self, montant, quoi):
        if self.depense + montant > self.dispo + 1e-9:
            raise PlafondAtteint(f"plafond du mois atteint : il resterait {self.dispo - self.depense:.2f} $, "
                                 f"il faudrait {montant:.2f} $ pour « {quoi} »")

    def payer(self, usd, quoi):
        self.lignes.append({"date": maintenant().isoformat(timespec="seconds"), "usd": round(usd, 4),
                            "quoi": quoi, "video": self.video})


class PlafondAtteint(Exception):
    pass
