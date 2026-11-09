import json
from pathlib import Path
import pdfplumber


def nettoyer_cellule(cellule):
    """Réunit le texte d'une cellule sur une seule ligne."""
    return " ".join((cellule or "").split())


# Contiendra les lignes de tableau avec leur provenance.
lignes_tableaux = []

for fichier in sorted(Path("data/corpus").glob("*.pdf")):
    with pdfplumber.open(fichier) as pdf:
        for page in pdf.pages:
            for numero, tableau in enumerate(page.extract_tables(), start=1):

                # Ignore les tableaux de métadonnées déjà traités.
                if any(ligne[0] == "Référence" for ligne in tableau):
                    continue

                # La première ligne contient les noms des colonnes.
                en_tetes = [
                    nettoyer_cellule(cellule) for cellule in tableau[0]
                ]

                # Les lignes suivantes contiennent les données.
                for numero_ligne, ligne in enumerate(tableau[1:], start=1):
                    valeurs = [
                        nettoyer_cellule(cellule) for cellule in ligne
                    ]

                    # Associe chaque en-tête à la valeur correspondante.
                    # strict=True signale un nombre de colonnes incohérent.
                    texte = " — ".join(
                        f"{entete} : {valeur}"
                        for entete, valeur in zip(
                            en_tetes, valeurs, strict=True
                        )
                    )

                    # Conserve l'emplacement précis de la ligne.
                    lignes_tableaux.append({
                        "file": fichier.name,
                        "page": page.page_number,
                        "table": numero,
                        "row": numero_ligne,
                        "text": texte,
                    })

# Enregistre les lignes structurées dans un fichier distinct.
sortie = Path("data/processed/tableaux.json")
sortie.parent.mkdir(parents=True, exist_ok=True)
sortie.write_text(
    json.dumps(lignes_tableaux, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"{len(lignes_tableaux)} lignes de tableau enregistrées.")