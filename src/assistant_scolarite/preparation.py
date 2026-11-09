import json
from datetime import date
from pathlib import Path

import pdfplumber

# Réutilise la fonction de découpage déjà vérifiée.
from chunking import decouper_fixe


MOIS = {
    "janvier": 1, "février": 2, "mars": 3,
    "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12,
}


def date_iso(texte):
    """Convertit une date française au format AAAA-MM-JJ."""
    jour, mois, annee = texte.split()

    return date(
        int(annee),
        MOIS[mois],
        int(jour.removesuffix("er")),
    ).isoformat()


def charger_metadonnees(dossier):
    """Retrouve l'identité de chaque document par son fichier."""

    documents = json.loads(
        (dossier / "metadonnees.json").read_text(encoding="utf-8")
    )

    resultat = {}

    for document in documents:
        meta = document["metadata"]

        # Prépare les champs communs à tous les fragments du document.
        resultat[document["file"]] = {
            "reference": meta["Référence"],
            "type": meta["Type de document"],
            "date": date_iso(meta["Date de publication"]),
            "version": meta["Version"],
            "status": meta["Statut"],
        }

    return resultat


def extraire_paragraphes(page):
    """Récupère le texte nettoyé situé hors des tableaux."""

    # Repère les rectangles des tableaux, y compris celui des métadonnées.
    tableaux = page.find_tables()

    def garder_element(element):
        # Calcule la position centrale de l'élément.
        x = (element["x0"] + element["x1"]) / 2
        y = (element["top"] + element["bottom"]) / 2

        for tableau in tableaux:
            gauche, haut, droite, bas = tableau.bbox

            if gauche <= x <= droite and haut <= y <= bas:
                return False

        return True

    # Filtre la page en mémoire : aucun PDF n'est modifié.
    texte = page.filter(garder_element).extract_text() or ""

    prefixes_a_supprimer = (
        "École d'Ingénieurs Hélianthe (EIH) — établissement fictif",
        "Document fictif – usage pédagogique uniquement",
    )

    lignes_propres = []

    # Applique le même nettoyage des lignes répétées et des puces.
    for ligne in texte.splitlines():
        ligne = ligne.strip()

        if ligne.startswith(prefixes_a_supprimer):
            continue

        lignes_propres.append(ligne.replace("(cid:127)", "-"))

    return "\n".join(lignes_propres)


def preparer_paragraphes(metadonnees, taille=500, chevauchement=100):
    """Découpe les paragraphes et leur associe les métadonnées."""

    fragments = []

    # Parcourt les documents présents dans les fiches de métadonnées.
    for nom_fichier in sorted(metadonnees):
        fichier = Path("data/corpus") / nom_fichier
        meta = metadonnees[nom_fichier]

        with pdfplumber.open(fichier) as pdf:
            for page in pdf.pages:
                texte = extraire_paragraphes(page)

                morceaux = decouper_fixe(
                    texte,
                    taille=taille,
                    chevauchement=chevauchement,
                )

                for numero, morceau in enumerate(morceaux, start=1):
                    fragments.append({
                        # Inclut les paramètres pour identifier la configuration.
                        "chunk_id": (
                            f"{meta['reference']}-p{page.page_number}"
                            f"-fixe-{taille}-{chevauchement}-c{numero}"
                        ),
                        "text": morceau,
                        "file": nom_fichier,
                        "page": page.page_number,

                        # Le titre de section n'est pas encore identifié.
                        "section": None,
                        "kind": "paragraph",

                        # Ajoute référence, type, date, version et statut.
                        **meta,
                    })

    return fragments


def preparer_lignes(lignes, metadonnees):
    """Associe les lignes de tableaux aux métadonnées."""

    fragments = []

    for ligne in lignes:
        meta = metadonnees[ligne["file"]]

        fragments.append({
            "chunk_id": (
                f"{meta['reference']}-p{ligne['page']}"
                f"-t{ligne['table']}-r{ligne['row']}"
            ),
            "text": ligne["text"],
            "file": ligne["file"],
            "page": ligne["page"],
            "section": (
                f"Tableau {ligne['table']}, ligne {ligne['row']}"
            ),
            "kind": "table",
            **meta,
        })

    return fragments


if __name__ == "__main__":
    dossier = Path("data/processed")

    # 1. Charge les identités des documents.
    metadonnees = charger_metadonnees(dossier)

    # 2. Prépare les fragments de paragraphes.
    paragraphes = preparer_paragraphes(metadonnees)

    # 3. Charge et prépare les fragments de tableaux.
    lignes = json.loads(
        (dossier / "tableaux.json").read_text(encoding="utf-8")
    )
    tableaux = preparer_lignes(lignes, metadonnees)

    # 4. Réunit les deux groupes dans une liste en mémoire.
    fragments = paragraphes + tableaux

    print(f"{len(paragraphes)} fragments de paragraphes préparés.")
    print(f"{len(tableaux)} fragments de tableaux préparés.")
    print(f"TOTAL : {len(fragments)} fragments.")

    # Affiche un fragment de paragraphe avec sa provenance.
    if paragraphes:
        print(json.dumps(paragraphes[0], ensure_ascii=False, indent=2))