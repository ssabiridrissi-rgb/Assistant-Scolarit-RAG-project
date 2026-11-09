import json
import re
from pathlib import Path

import pdfplumber

# Réutilise les fonctions déjà vérifiées.
from chunking import decouper_fixe
from preparation import (
    charger_metadonnees,
    extraire_paragraphes,
    preparer_lignes,
)
from structure import identifier_titre


def lire_lignes(fichier):
    """Récupère le texte, la page et le type de titre de chaque ligne."""

    resultat = []

    with pdfplumber.open(fichier) as pdf:
        for page in pdf.pages:
            # Identifie les titres grâce au texte et à la police en gras.
            titres = {
                ligne["text"].strip(): identifier_titre(ligne)
                for ligne in page.extract_text_lines(return_chars=True)
            }

            # Récupère le texte nettoyé, sans les tableaux.
            texte = extraire_paragraphes(page)

            for ligne in texte.splitlines():
                if ligne.strip():
                    resultat.append({
                        "text": ligne,
                        "page": page.page_number,
                        "nature": titres.get(ligne),
                    })

    return resultat


def regrouper_sections(lignes):
    """Regroupe les contenus selon les articles, sections et questions."""

    blocs = []
    corps = []
    section = "Préambule"
    groupe = ""
    parents = {}

    # Dans les documents organisés en articles,
    # les sous-sections restent dans leur article.
    mode_articles = any(
        ligne["nature"] == "article"
        for ligne in lignes
    )

    def terminer_bloc():
        # Conserve le bloc précédent s'il possède du contenu.
        if corps:
            blocs.append({
                "section": section,
                "lignes": list(corps),
            })

    for ligne in lignes:
        nature = ligne["nature"]

        # Repère les frontières entre les blocs.
        nouvelle_section = (
            nature in ("article", "question", "groupe")
            or (nature == "section" and not mode_articles)
        )

        if not nouvelle_section:
            corps.append(ligne)
            continue

        # Ferme le bloc précédent et prépare le suivant.
        terminer_bloc()
        corps = []
        titre = ligne["text"]

        if nature == "groupe":
            # Exemple : "Titre I — Dispositions générales".
            groupe = titre
            section = titre
            parents = {}

        elif nature in ("article", "question"):
            # Conserve le grand titre parent lorsqu'il existe.
            section = " > ".join(
                partie
                for partie in (groupe, titre)
                if partie
            )

        else:
            # Récupère le numéro : "5", "5.1", etc.
            numero = re.match(
                r"^\d+(?:\.\d+)*", titre
            ).group()

            profondeur = len(numero.split("."))

            # Une nouvelle section remplace celles du même niveau
            # et leurs éventuelles sous-sections.
            parents = {
                niveau: texte
                for niveau, texte in parents.items()
                if niveau < profondeur
            }

            parents[profondeur] = titre

            # Exemple : "5. PFE > 5.3 Durée et période".
            section = " > ".join(
                parents[niveau]
                for niveau in sorted(parents)
            )

    # Enregistre également le dernier bloc du document.
    terminer_bloc()

    return blocs


def fragmenter_blocs(blocs, nom_fichier, meta, taille=500):
    """Crée des fragments bornés en taille, avec leur section et leurs pages."""

    fragments = []

    for numero_bloc, bloc in enumerate(blocs, start=1):
        # Répète le titre au début de chaque fragment du bloc.
        prefixe = bloc["section"] + "\n"
        capacite = taille - len(prefixe)

        if capacite <= 0:
            raise ValueError(
                "La taille doit dépasser la longueur du titre de section."
            )

        # Associe les positions du texte aux pages d'origine.
        positions = []
        debut_ligne = 0

        for ligne in bloc["lignes"]:
            fin_ligne = debut_ligne + len(ligne["text"])

            positions.append((
                debut_ligne,
                fin_ligne,
                ligne["page"],
            ))

            # Le caractère supplémentaire correspond au retour à la ligne.
            debut_ligne = fin_ligne + 1

        texte = "\n".join(
            ligne["text"]
            for ligne in bloc["lignes"]
        )

        # Un bloc court reste entier.
        # Un bloc long est subdivisé sans chevauchement du corps.
        morceaux = decouper_fixe(
            texte,
            taille=capacite,
            chevauchement=0,
        )

        for numero, morceau in enumerate(morceaux, start=1):
            debut = (numero - 1) * capacite
            fin = debut + len(morceau)

            # Identifie les pages qui contiennent ce morceau.
            pages = sorted({
                page
                for gauche, droite, page in positions
                if gauche < fin and droite > debut
            })

            if not pages:
                continue

            fragments.append({
                # Identifiant stable pour cette configuration.
                "chunk_id": (
                    f"{meta['reference']}-structurel-{taille}"
                    f"-b{numero_bloc}-c{numero}"
                ),
                "text": prefixe + morceau,
                "file": nom_fichier,
                "page": pages[0],
                "pages": pages,
                "section": bloc["section"],
                "kind": "paragraph",

                # Ajoute référence, type, date, version et statut.
                **meta,
            })

    return fragments


def preparer_structurel(metadonnees, taille=500):
    """Applique le découpage structurel aux sept documents."""

    fragments = []

    for nom_fichier in sorted(metadonnees):
        fichier = Path("data/corpus") / nom_fichier

        # 1. Lit les lignes et reconnaît les titres.
        lignes = lire_lignes(fichier)

        # 2. Regroupe les lignes par unité structurelle.
        blocs = regrouper_sections(lignes)

        # 3. Prépare les fragments avec leurs métadonnées.
        fragments.extend(
            fragmenter_blocs(
                blocs,
                nom_fichier,
                metadonnees[nom_fichier],
                taille,
            )
        )

    return fragments


if __name__ == "__main__":
    dossier = Path("data/processed")

    # Charge les métadonnées des documents.
    metadonnees = charger_metadonnees(dossier)

    # Prépare les paragraphes avec la stratégie structurelle.
    paragraphes = preparer_structurel(
        metadonnees,
        taille=500,
    )

    # Réutilise les lignes de tableaux déjà structurées.
    lignes = json.loads(
        (dossier / "tableaux.json").read_text(encoding="utf-8")
    )
    tableaux = preparer_lignes(lignes, metadonnees)

    # Réunit les fragments uniquement en mémoire.
    fragments = paragraphes + tableaux

    print(
        f"{len(paragraphes)} fragments de paragraphes structurels."
    )
    print(f"{len(tableaux)} fragments de tableaux.")
    print(f"TOTAL : {len(fragments)} fragments.")

    # Affiche un exemple d'article avec sa provenance.
    if paragraphes:
        exemple = next(
            (
                fragment
                for fragment in paragraphes
                if "Article 1 — Objet" in fragment["section"]
            ),
            paragraphes[0],
        )

        print(json.dumps(
            exemple,
            ensure_ascii=False,
            indent=2,
        ))