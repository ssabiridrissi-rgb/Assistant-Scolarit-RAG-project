import json
import re
import unicodedata
from time import perf_counter

from indexation import DB_DIR, ouvrir_base


# Nombre minimal de candidats demandés à Chroma avant le reclassement.
CANDIDATS_MIN = 20

# Poids du bonus lexical : il départage des scores E5 très proches
# (souvent entre 0,91 et 0,94) sans écraser la recherche sémantique.
POIDS_LEXICAL = 0.05

# Mots trop courants pour indiquer le sujet d'une question.
MOTS_VIDES = frozenset("""
les des une est qui que quoi par sur aux ces son ses pas pour dans avec sans sous
entre apres avant plus moins tout tous toute toutes leur leurs elle elles nous vous
quand quel quelle quels quelles combien comment pourquoi faut doit doivent dois peut
peuvent etre avoir faire cette cet sont mais donc ont the and
""".split())


def distance_vers_score(distance):
    """Convertit la distance cosinus [0, 2] en score [0, 1]."""

    # Le bornage absorbe les petits écarts des calculs numériques.
    return max(0.0, min(1.0, 1.0 - float(distance) / 2.0))


def mots_significatifs(texte):
    """Mots en minuscules, sans accents, hors mots vides et très courts."""

    sans_accents = (
        unicodedata.normalize("NFKD", texte.casefold())
        .encode("ascii", "ignore")
        .decode()
    )

    return {
        mot
        for mot in re.findall(r"[a-z0-9]+", sans_accents)
        if len(mot) >= 3 and mot not in MOTS_VIDES
    }


def racines(texte):
    """Garde les 5 premières lettres : « places » et « place » se rejoignent."""

    return {mot[:5] for mot in mots_significatifs(texte)}


def couverture_lexicale(question, texte):
    """Part des mots importants de la question présents dans le texte (0 à 1)."""

    racines_question = racines(question)

    if not racines_question:
        return 0.0

    return len(racines_question & racines(texte)) / len(racines_question)


def rechercher(base, question, top_k=5, type_document=None):
    """Recherche hybride : sémantique (E5), puis reclassement lexical léger.

    1. Chroma renvoie des candidats proches du sens de la question.
    2. Un petit bonus favorise ceux qui contiennent ses mots importants.
    Le champ "score" reste le score sémantique, utilisé pour le seuil de refus.
    """

    question = question.strip()

    if not question:
        raise ValueError("La question ne doit pas être vide.")

    if (
        isinstance(top_k, bool)
        or not isinstance(top_k, int)
        or top_k <= 0
    ):
        raise ValueError(
            "top_k doit être un entier strictement positif."
        )

    debut = perf_counter()

    # Aucun filtre par défaut : recherche dans les sept documents.
    filtre = {"type": type_document} if type_document else None

    resultats = base.similarity_search_with_score(
        question,
        k=max(top_k * 4, CANDIDATS_MIN),
        filter=filtre,
    )

    candidats = []

    for document, distance in resultats:
        meta = document.metadata
        score = distance_vers_score(distance)
        texte = f"{meta.get('section') or ''} {document.page_content}"
        classement = score + POIDS_LEXICAL * couverture_lexicale(question, texte)
        candidats.append((classement, document, distance, score))

    # Tri stable : à égalité, l'ordre sémantique de Chroma est conservé.
    candidats.sort(key=lambda candidat: candidat[0], reverse=True)

    sources = []

    for rang, (_, document, distance, score) in enumerate(
        candidats[:top_k],
        start=1,
    ):
        meta = document.metadata

        sources.append({
            # Numéro local : servira ensuite aux citations [1], [2]...
            "id": rang,

            # Identité et emplacement du fragment.
            "chunk_id": meta["chunk_id"],
            "file": meta["file"],
            "reference": meta["reference"],
            "date": meta["date"],
            "page": meta["page"],
            "pages": json.loads(meta["pages_json"]),
            "section": meta.get("section"),

            # Informations utiles aux filtres et aux règles de version.
            "type": meta["type"],
            "version": meta["version"],
            "status": meta["status"],
            "kind": meta["kind"],

            # Texte retrouvé et mesure de proximité sémantique.
            "excerpt": document.page_content,
            "score": score,
            "distance": float(distance),
        })

    return {
        "results": sources,
        "latency_ms": round(
            (perf_counter() - debut) * 1000,
            2,
        ),
    }


if __name__ == "__main__":
    if not DB_DIR.is_dir():
        raise RuntimeError(
            "Base absente : exécute d'abord indexation.py."
        )

    question = (
        "Combien de jours avant le début du stage "
        "faut-il déposer la convention ?"
    )

    print("Ouverture de Chroma...", flush=True)
    base = ouvrir_base()

    reponse = rechercher(base, question, top_k=5)

    print(f"\nQUESTION : {question}")
    print(f"Résultats : {len(reponse['results'])}")
    print(f"Durée : {reponse['latency_ms']} ms")

    for source in reponse["results"]:
        print(f"\n[{source['id']}] SCORE : {source['score']:.4f}")
        print(f"Distance cosinus : {source['distance']:.4f}")
        print(f"Document : {source['file']}")
        print(f"Référence : {source['reference']}")
        print(f"Pages : {source['pages']}")
        print(f"Section : {source['section']}")
        print(source["excerpt"])