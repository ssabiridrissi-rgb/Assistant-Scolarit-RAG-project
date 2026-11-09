import json
from pathlib import Path
import pdfplumber

# Liste qui contiendra la fiche d'identité de chaque PDF.
documents = []

for fichier in sorted(Path("data/corpus").glob("*.pdf")):
    with pdfplumber.open(fichier) as pdf:
        # Le bloc de métadonnées se trouve sur la première page.
        tableaux = pdf.pages[0].extract_tables()
        metadonnees = {}

        for tableau in tableaux:
            # Reconnaît le tableau contenant l'étiquette "Référence".
            if not any(ligne[0] == "Référence" for ligne in tableau):
                continue

            for ligne in tableau:
                # Vérifie que la ligne contient une étiquette et une valeur.
                if len(ligne) == 2 and ligne[0] and ligne[1]:
                    etiquette = ligne[0].strip()

                    # Réunit les valeurs réparties sur plusieurs lignes.
                    valeur = " ".join(ligne[1].split())

                    metadonnees[etiquette] = valeur

            break  # Le tableau recherché est trouvé.

        # Signale une extraction manquante au lieu de l'ignorer.
        if not metadonnees:
            raise ValueError(f"Métadonnées introuvables : {fichier.name}")

        documents.append({
            "file": fichier.name,
            "metadata": metadonnees,
        })

# Enregistre les fiches dans un fichier distinct.
sortie = Path("data/processed/metadonnees.json")
sortie.parent.mkdir(parents=True, exist_ok=True)
sortie.write_text(
    json.dumps(documents, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"{len(documents)} fiches enregistrées dans {sortie}")