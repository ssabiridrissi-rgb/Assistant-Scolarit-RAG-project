import json
from pathlib import Path


def decouper_fixe(
    texte: str,
    taille: int = 500,
    chevauchement: int = 100,
) -> list[str]:
    """Découpe un texte en fragments avec chevauchement."""

    # Vérifie que les paramètres permettent un découpage valide.
    if taille <= 0:
        raise ValueError("La taille doit être strictement positive.")

    if not 0 <= chevauchement < taille:
        raise ValueError(
            "Le chevauchement doit être positif ou nul "
            "et strictement inférieur à la taille."
        )

    fragments = []
    debut = 0

    # Parcourt le texte jusqu'à son dernier caractère.
    while debut < len(texte):
        # Limite la fin du fragment à la longueur du texte.
        fin = min(debut + taille, len(texte))

        # Ajoute la tranche sans modifier son contenu.
        fragments.append(texte[debut:fin])

        # Arrête lorsque la fin du texte est atteinte.
        if fin == len(texte):
            break

        # Reprend une partie du fragment précédent.
        debut = fin - chevauchement

    # Un texte vide produit une liste vide.
    return fragments


# Ce bloc s'exécute uniquement lorsqu'on lance ce fichier directement.
if __name__ == "__main__":

    # 1. Charge les pages nettoyées des sept PDF.
    chemin = Path("data/processed/pages_nettoyees.json")
    pages = json.loads(chemin.read_text(encoding="utf-8"))

    # 2. Définit les paramètres du découpage fixe, en caractères.
    taille = 500
    chevauchement = 100

    # Compteur du nombre total de fragments.
    total = 0

    # 3. Découpe chaque page indépendamment.
    for page in pages:
        fragments = decouper_fixe(
            page["text"],
            taille=taille,
            chevauchement=chevauchement,
        )

        total += len(fragments)

        # Affiche le document, la page et le nombre de fragments.
        print(
            f"{page['file']} | page {page['page']} "
            f"| {len(fragments)} fragments"
        )

    # 4. Affiche le bilan sans créer de fichier supplémentaire.
    print(f"TOTAL : {len(pages)} pages, {total} fragments.")