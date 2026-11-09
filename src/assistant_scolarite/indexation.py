import hashlib
import json
from pathlib import Path

from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from chunking_structurel import preparer_structurel
from embeddings import MODEL_NAME, get_embeddings
from preparation import charger_metadonnees, preparer_lignes


TAILLE = 500
MAX_TOKENS = 512
DB_DIR = Path("data/chroma")

# Une collection différente pour chaque modèle et configuration.
signature = f"{MODEL_NAME}|structurel|{TAILLE}|cosine|v1"
empreinte = hashlib.sha256(
    signature.encode("utf-8")
).hexdigest()[:12]

COLLECTION_NAME = f"eih_structurel_{TAILLE}_{empreinte}"


def charger_fragments():
    """Prépare les paragraphes structurels et les tableaux."""

    dossier = Path("data/processed")
    metadonnees = charger_metadonnees(dossier)

    paragraphes = preparer_structurel(
        metadonnees,
        taille=TAILLE,
    )

    lignes = json.loads(
        (dossier / "tableaux.json").read_text(encoding="utf-8")
    )

    tableaux = preparer_lignes(lignes, metadonnees)

    return paragraphes + tableaux


def verifier_longueurs(fragments):
    """Vérifie que le modèle pourra lire chaque fragment entièrement."""

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    maximum = 0

    for fragment in fragments:
        # Compte aussi le préfixe ajouté lors de la vectorisation.
        tokens = tokenizer.encode(
            "passage: " + fragment["text"],
            truncation=False,
        )

        maximum = max(maximum, len(tokens))

        if len(tokens) > MAX_TOKENS:
            raise ValueError(
                f"Fragment trop long : {fragment['chunk_id']} "
                f"({len(tokens)} tokens)"
            )

    print(
        f"Longueur maximale : {maximum} tokens / {MAX_TOKENS}",
        flush=True,
    )


def ouvrir_base():
    """Ouvre ou crée la collection persistante."""

    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(DB_DIR),

        # Fixe explicitement la métrique utilisée pour la recherche.
        collection_configuration={
            "hnsw": {"space": "cosine"}
        },

        client_settings=Settings(
            anonymized_telemetry=False
        ),
    )


def convertir_document(fragment):
    """Prépare un texte et ses métadonnées au format attendu par Chroma."""

    metadata = {
        cle: valeur
        for cle, valeur in fragment.items()
        if cle not in ("text", "pages") and valeur is not None
    }

    # Conserve les pages multiples dans une chaîne de métadonnée.
    # Cela ne crée aucun fichier JSON supplémentaire.
    metadata["pages_json"] = json.dumps(
        fragment.get("pages", [fragment["page"]])
    )

    return Document(
        page_content=fragment["text"],
        metadata=metadata,
    )


def synchroniser(base, fragments):
    """Ajoute les nouveautés, actualise les modifications et retire les obsolètes."""

    if not fragments:
        raise ValueError("Aucun fragment à indexer.")

    ids = [fragment["chunk_id"] for fragment in fragments]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Les identifiants de fragments doivent être uniques."
        )

    # Récupère les textes et métadonnées déjà enregistrés.
    etat = base.get(include=["documents", "metadatas"])

    existants = {
        identifiant: (texte, metadata)
        for identifiant, texte, metadata in zip(
            etat["ids"],
            etat["documents"],
            etat["metadatas"],
            strict=True,
        )
    }

    documents = []
    ids_a_indexer = []

    for fragment in fragments:
        document = convertir_document(fragment)
        identifiant = fragment["chunk_id"]

        # Ignore les fragments dont le contenu et les métadonnées sont inchangés.
        contenu = (document.page_content, document.metadata)

        if existants.get(identifiant) != contenu:
            documents.append(document)
            ids_a_indexer.append(identifiant)

    if documents:
        print(
            f"Vectorisation de {len(documents)} fragments...",
            flush=True,
        )

        # Les mêmes identifiants remplacent les entrées existantes.
        base.add_documents(
            documents=documents,
            ids=ids_a_indexer,
        )

    # Retire les anciens fragments absents de la préparation actuelle.
    # L'opération concerne uniquement cette collection.
    obsoletes = sorted(set(existants) - set(ids))

    if obsoletes:
        base.delete(ids=obsoletes)

    return {
        "prepared": len(fragments),
        "upserted": len(documents),
        "deleted": len(obsoletes),
        "indexed": len(base.get(include=[])["ids"]),
        "collection": COLLECTION_NAME,
    }


if __name__ == "__main__":
    print("Préparation des fragments...", flush=True)
    fragments = charger_fragments()

    verifier_longueurs(fragments)

    print("Ouverture du modèle et de Chroma...", flush=True)
    base = ouvrir_base()

    resultat = synchroniser(base, fragments)

    print(f"Fragments préparés : {resultat['prepared']}")
    print(f"Ajoutés ou mis à jour : {resultat['upserted']}")
    print(f"Obsolètes supprimés : {resultat['deleted']}")
    print(f"TOTAL INDEXÉ : {resultat['indexed']}")
    print(f"Collection : {resultat['collection']}")