import json
from pathlib import Path


def nettoyer_texte(texte: str) -> str:
    """Retire les lignes répétées et corrige les artefacts de puces."""

    # Débuts des lignes d'en-tête et de pied de page à supprimer.
    prefixes_a_supprimer = (
        "École d'Ingénieurs Hélianthe (EIH) — établissement fictif",
        "Document fictif – usage pédagogique uniquement",
    )

    lignes_propres = []

    # Examine chaque ligne du texte.
    for ligne in texte.splitlines():
        ligne = ligne.strip()

        # Si la ligne est un en-tête ou un pied de page, on l'ignore.
        if ligne.startswith(prefixes_a_supprimer):
            continue

        # Remplace les puces mal extraites par un tiret.
        ligne = ligne.replace("(cid:127)", "-")

        # Conserve la ligne utile.
        lignes_propres.append(ligne)

    # Réassemble le texte avec ses retours à la ligne.
    return "\n".join(lignes_propres)


# Lit les pages déjà extraites par main.py.
entree = Path("data/processed/pages_brutes.json")
pages = json.loads(entree.read_text(encoding="utf-8"))

# Nettoie uniquement le texte ; conserve le fichier et le numéro de page.
for page in pages:
    page["text"] = nettoyer_texte(page["text"])

# Enregistre dans un nouveau fichier : le JSON brut reste intact.
sortie = Path("data/processed/pages_nettoyees.json")
sortie.write_text(
    json.dumps(pages, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"{len(pages)} pages nettoyées.")
print(f"Résultat : {sortie}")