import re
from pathlib import Path
import pdfplumber


def identifier_titre(ligne):
    """Reconnaît un titre à partir de son texte et de sa présentation."""

    texte = ligne["text"].strip()

    # Examine les caractères visibles, sans les espaces.
    caracteres = [
        caractere
        for caractere in ligne["chars"]
        if caractere["text"].strip()
    ]

    # Les titres du corpus sont entièrement en gras.
    # Cela évite de prendre les listes ordinaires pour des sections.
    if not caracteres:
        return None

    if not all(
        "bold" in caractere["fontname"].lower()
        for caractere in caracteres
    ):
        return None

    # Reconnaît "Article 1", "Article 2", etc.
    if re.match(r"^Article\s+\d+\b", texte):
        return "article"

    # Reconnaît "Q1.", "Q2.", etc.
    if re.match(r"^Q\d+\.", texte):
        return "question"

    # Reconnaît les grandes parties : "Titre I", "Titre II"...
    if re.match(r"^Titre\s+[IVXLCDM]+\b", texte):
        return "groupe"

    # Reconnaît les sections : "1.", "2.2", "5.3"...
    if re.match(r"^\d+(?:\.\d+)*\.?\s+\S", texte):
        return "section"

    return None


if __name__ == "__main__":
    compteurs = {
        "article": 0,
        "question": 0,
        "section": 0,
        "groupe": 0,
    }

    # Examine les titres dans les sept PDF.
    for fichier in sorted(Path("data/corpus").glob("*.pdf")):
        with pdfplumber.open(fichier) as pdf:
            for page in pdf.pages:
                # Conserve les caractères pour connaître leur police.
                lignes = page.extract_text_lines(return_chars=True)

                for ligne in lignes:
                    nature = identifier_titre(ligne)

                    if nature:
                        compteurs[nature] += 1

    # Affiche le bilan sans créer ou modifier de JSON.
    for nature, nombre in compteurs.items():
        print(f"{nature} : {nombre}")

    print(f"TOTAL : {sum(compteurs.values())} repères")