import hashlib
import json
import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from threading import Lock
from time import perf_counter

from dotenv import load_dotenv

# Charge .env AVANT les bibliothèques d'IA :
# certaines lisent leurs réglages (ex. HF_HUB_OFFLINE) dès leur import.
load_dotenv(Path.cwd() / ".env")

import chromadb  # noqa: E402
from chromadb.config import Settings  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from langchain_chroma import Chroma  # noqa: E402

from chunking_structurel import preparer_structurel  # noqa: E402
from embeddings import MODEL_NAME, get_embeddings  # noqa: E402
from generation import LLMError, prechauffer_llm, repondre  # noqa: E402
from indexation import (  # noqa: E402
    COLLECTION_NAME,
    DB_DIR,
    MAX_TOKENS,
    synchroniser,
    verifier_longueurs,
)
from preparation import (  # noqa: E402
    charger_metadonnees,
    preparer_lignes,
    preparer_paragraphes,
)
from recherche import rechercher  # noqa: E402
from schemas import (  # noqa: E402
    AskRequest,
    AskResponse,
    DocumentsResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    SearchRequest,
    SearchResponse,
)


logger = logging.getLogger(__name__)

# Messages visibles dans le terminal uvicorn.
journal = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def cycle_de_vie(application):
    """Préchauffe les modèles au démarrage, avant la première question."""

    prechauffer()
    yield


app = FastAPI(
    title="Assistant Scolarité",
    version="0.4.0",
    lifespan=cycle_de_vie,
)

# Autorise le frontend React local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Sélection initiale : collection structurelle 500.
app.state.collection_active = COLLECTION_NAME

# Partage le même objet E5 entre les routes.
get_embeddings = lru_cache(maxsize=1)(get_embeddings)
ingest_lock = Lock()


def compter_fragments():
    """Vérifie Chroma et compte les fragments sans charger E5."""

    if not DB_DIR.is_dir():
        raise HTTPException(
            status_code=503,
            detail="Base absente : lance d'abord l'ingestion.",
        )

    try:
        client = chromadb.PersistentClient(
            path=str(DB_DIR),
            settings=Settings(anonymized_telemetry=False),
        )

        collection = client.get_collection(
            name=app.state.collection_active,
            embedding_function=None,
        )

        return collection.count()

    except Exception as erreur:
        logger.exception("Chroma est indisponible.")

        raise HTTPException(
            status_code=503,
            detail="Base vectorielle indisponible.",
        ) from erreur


@lru_cache(maxsize=1)
def obtenir_base():
    """Charge E5 une fois et ouvre la collection active."""

    return Chroma(
        collection_name=app.state.collection_active,
        embedding_function=get_embeddings(),
        persist_directory=str(DB_DIR),
        create_collection_if_not_exists=False,
        client_settings=Settings(
            anonymized_telemetry=False,
        ),
    )


@lru_cache(maxsize=1)
def obtenir_tokenizer():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(MODEL_NAME)


def verifier_question(question):
    """Vérifie la base et la longueur de la question."""

    compter_fragments()

    tokens = obtenir_tokenizer().encode(
        "query: " + question,
        truncation=False,
    )

    if len(tokens) > MAX_TOKENS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Question trop longue : maximum {MAX_TOKENS} "
                "tokens, préfixe compris."
            ),
        )


def prechauffer():
    """Charge E5, le tokenizer et le LLM une fois, au démarrage du serveur.

    Sans cela, la première question paie tous les chargements.
    Un échec n'empêche pas le serveur de démarrer : les routes
    renverront ensuite leurs erreurs 503 ou 502 habituelles.
    """

    debut = perf_counter()

    try:
        obtenir_tokenizer()
        obtenir_base()
        get_embeddings().embed_query("préchauffage")
        journal.info(
            "Préchauffage recherche (E5 + Chroma) : %.1f s",
            perf_counter() - debut,
        )
    except Exception:
        logger.exception("Préchauffage de la recherche impossible.")

    debut = perf_counter()

    try:
        prechauffer_llm()
        journal.info(
            "Préchauffage LLM (Ollama) : %.1f s",
            perf_counter() - debut,
        )
    except Exception:
        logger.warning(
            "Préchauffage Ollama impossible : "
            "vérifie qu'Ollama est lancé."
        )


# ─── 1. HEALTH ──────────────────────────────────────

@app.get(
    "/api/health",
    response_model=HealthResponse,
    responses={
        503: {"description": "Base indisponible"}
    },
)
def health():
    return HealthResponse(
        status="ok",
        indexed_chunks=compter_fragments(),
    )


# ─── 2. SEARCH ──────────────────────────────────────

@app.post(
    "/api/search",
    response_model=SearchResponse,
    responses={
        503: {"description": "Recherche indisponible"}
    },
)
def search(requete: SearchRequest):
    debut = perf_counter()

    try:
        verifier_question(requete.question)

        reponse = rechercher(
            obtenir_base(),
            requete.question,
            top_k=requete.top_k,
            type_document=requete.filters.type,
        )

        reponse["latency_ms"] = round(
            (perf_counter() - debut) * 1000,
            2,
        )

        return reponse

    except HTTPException:
        raise

    except Exception as erreur:
        logger.exception("La recherche est indisponible.")

        raise HTTPException(
            status_code=503,
            detail="Service de recherche indisponible.",
        ) from erreur


# ─── 3. DOCUMENTS ───────────────────────────────────

@app.get(
    "/api/documents",
    response_model=DocumentsResponse,
    responses={
        503: {"description": "Base indisponible"}
    },
)
def lister_documents():
    compter_fragments()

    try:
        client = chromadb.PersistentClient(
            path=str(DB_DIR),
            settings=Settings(anonymized_telemetry=False),
        )

        collection = client.get_collection(
            name=app.state.collection_active,
            embedding_function=None,
        )

        etat = collection.get(include=["metadatas"])
        documents = {}

        for meta in etat["metadatas"] or []:
            fichier = meta["file"]

            if fichier not in documents:
                documents[fichier] = {
                    "file": fichier,
                    "reference": meta["reference"],
                    "type": meta["type"],
                    "date": meta["date"],
                    "version": meta["version"],
                    "status": meta["status"],
                    "chunks_count": 0,
                }

            documents[fichier]["chunks_count"] += 1

        return {
            "documents": [
                documents[fichier]
                for fichier in sorted(documents)
            ]
        }

    except Exception as erreur:
        logger.exception(
            "Impossible de lister les documents."
        )

        raise HTTPException(
            status_code=503,
            detail="Documents indexés indisponibles.",
        ) from erreur


# ─── 4. INGEST ──────────────────────────────────────

@app.post(
    "/api/ingest",
    response_model=IngestResponse,
    responses={
        503: {"description": "Indexation indisponible"}
    },
)
def ingest(requete: IngestRequest):
    with ingest_lock:
        try:
            dossier = Path("data/processed")
            metadonnees = charger_metadonnees(dossier)

            if requete.strategy == "structural":
                paragraphes = preparer_structurel(
                    metadonnees,
                    taille=requete.chunk_size,
                )

                signature = (
                    f"{MODEL_NAME}|structurel|"
                    f"{requete.chunk_size}|cosine|v1"
                )
                etiquette = f"structurel_{requete.chunk_size}"

            else:
                paragraphes = preparer_paragraphes(
                    metadonnees,
                    taille=requete.chunk_size,
                    chevauchement=requete.chunk_overlap,
                )

                signature = (
                    f"{MODEL_NAME}|fixe|{requete.chunk_size}|"
                    f"{requete.chunk_overlap}|cosine|v1"
                )
                etiquette = (
                    f"fixe_{requete.chunk_size}_"
                    f"{requete.chunk_overlap}"
                )

            lignes = json.loads(
                (dossier / "tableaux.json").read_text(
                    encoding="utf-8"
                )
            )

            fragments = (
                paragraphes
                + preparer_lignes(lignes, metadonnees)
            )

            verifier_longueurs(fragments)

            empreinte = hashlib.sha256(
                signature.encode("utf-8")
            ).hexdigest()[:12]

            nom = f"eih_{etiquette}_{empreinte}"

            base = Chroma(
                collection_name=nom,
                embedding_function=get_embeddings(),
                persist_directory=str(DB_DIR),
                collection_configuration={
                    "hnsw": {"space": "cosine"}
                },
                client_settings=Settings(
                    anonymized_telemetry=False
                ),
            )

            resultat = synchroniser(base, fragments)

            # Active la collection après une ingestion réussie.
            app.state.collection_active = nom
            obtenir_base.cache_clear()

            return {
                "documents_count": len({
                    fragment["file"]
                    for fragment in fragments
                }),
                "chunks_count": resultat["indexed"],
                "collection": nom,
                "upserted": resultat["upserted"],
                "deleted": resultat["deleted"],
            }

        except ValueError as erreur:
            raise HTTPException(
                status_code=422,
                detail=str(erreur),
            ) from erreur

        except Exception as erreur:
            logger.exception("L'indexation est indisponible.")

            raise HTTPException(
                status_code=503,
                detail="Service d'indexation indisponible.",
            ) from erreur


# ─── 5. ASK ─────────────────────────────────────────

@app.post(
    "/api/ask",
    response_model=AskResponse,
    responses={
        502: {"description": "LLM indisponible ou réponse invalide"},
        503: {"description": "Service RAG indisponible"},
    },
)
def ask(requete: AskRequest):
    debut = perf_counter()

    try:
        verifier_question(requete.question)

        reponse = repondre(
            obtenir_base(),
            get_embeddings(),
            requete.question,
            top_k=requete.top_k,
            type_document=requete.filters.type,
        )

        reponse["latency_ms"] = round(
            (perf_counter() - debut) * 1000,
            2,
        )

        return reponse

    except HTTPException:
        raise

    except LLMError as erreur:
        logger.exception("Le LLM est indisponible.")

        raise HTTPException(
            status_code=502,
            detail=(
                "Ollama indisponible ou réponse invalide. "
                "Vérifie le modèle et le service Ollama."
            ),
        ) from erreur

    except Exception as erreur:
        logger.exception("Le service RAG est indisponible.")

        raise HTTPException(
            status_code=503,
            detail="Service RAG indisponible.",
        ) from erreur


# ─── 6. PDF (consultation et téléchargement) ───────
# Ces lignes sont au niveau du fichier, sans indentation :
# elles s'exécutent une fois, après la création de app.

from pdf_routes import router as pdf_router  # noqa: E402

app.include_router(pdf_router)