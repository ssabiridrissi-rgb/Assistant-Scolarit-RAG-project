"""Évaluation reproductible de l'Assistant Scolarité.

Compare les deux découpages (fixe 500/100 et structurel 500/0) avec
le même modèle d'embedding, le même LLM et le même top_k.

Lancement, depuis la racine du projet :
    uv run python eval/run_eval.py              # recherche + génération
    uv run python eval/run_eval.py --sans-llm   # recherche seule (rapide)
"""
import argparse
import csv
import hashlib
import json
import statistics
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from time import perf_counter

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src" / "assistant_scolarite"))

from dotenv import load_dotenv  # noqa: E402

# Charge .env avant les bibliothèques d'IA (HF_HUB_OFFLINE, LLM_PROVIDER...).
load_dotenv(RACINE / ".env")

from chromadb.config import Settings  # noqa: E402
from langchain_chroma import Chroma  # noqa: E402

from chunking_structurel import preparer_structurel  # noqa: E402
from embeddings import MODEL_NAME, get_embeddings  # noqa: E402
from generation import LLMError, repondre  # noqa: E402
from indexation import DB_DIR, synchroniser  # noqa: E402
from preparation import (  # noqa: E402
    charger_metadonnees,
    preparer_lignes,
    preparer_paragraphes,
)
from recherche import rechercher  # noqa: E402


# Les deux configurations comparées (mêmes règles de nommage que /api/ingest).
CONFIGURATIONS = {
    "structurel": {"strategie": "structural", "taille": 500, "chevauchement": 0},
    "fixe": {"strategie": "fixed", "taille": 500, "chevauchement": 100},
}


def nom_collection(config):
    """Reproduit le nom calculé par /api/ingest pour cette configuration."""

    if config["strategie"] == "structural":
        signature = f"{MODEL_NAME}|structurel|{config['taille']}|cosine|v1"
        etiquette = f"structurel_{config['taille']}"
    else:
        signature = (
            f"{MODEL_NAME}|fixe|{config['taille']}|"
            f"{config['chevauchement']}|cosine|v1"
        )
        etiquette = f"fixe_{config['taille']}_{config['chevauchement']}"

    empreinte = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:12]
    return f"eih_{etiquette}_{empreinte}"


def ouvrir_collection(config, embeddings):
    """Ouvre la collection et la synchronise (sans doublon si rien n'a changé)."""

    dossier = RACINE / "data" / "processed"
    metadonnees = charger_metadonnees(dossier)

    if config["strategie"] == "structural":
        paragraphes = preparer_structurel(metadonnees, taille=config["taille"])
    else:
        paragraphes = preparer_paragraphes(
            metadonnees,
            taille=config["taille"],
            chevauchement=config["chevauchement"],
        )

    lignes = json.loads((dossier / "tableaux.json").read_text(encoding="utf-8"))
    fragments = paragraphes + preparer_lignes(lignes, metadonnees)

    base = Chroma(
        collection_name=nom_collection(config),
        embedding_function=embeddings,
        persist_directory=str(DB_DIR),
        collection_configuration={"hnsw": {"space": "cosine"}},
        client_settings=Settings(anonymized_telemetry=False),
    )

    etat = synchroniser(base, fragments)
    return base, etat


def normaliser(texte):
    """Minuscules, sans accents ni espaces : « 15 000 » = « 15000 »."""

    sans_accents = (
        unicodedata.normalize("NFKD", texte.casefold())
        .encode("ascii", "ignore")
        .decode()
    )
    return "".join(sans_accents.split())


def contient(texte, element):
    return normaliser(element) in normaliser(texte)


def rang_pertinent(resultats, documents):
    """Rang (1, 2...) du premier passage issu d'un document attendu, sinon None."""

    for rang, source in enumerate(resultats, start=1):
        if source["reference"] in documents:
            return rang
    return None


def evaluer_question(base, embeddings, q, top_k, avec_llm):
    ligne = {
        "id": q["id"],
        "categorie": q["categorie"],
        "question": q["question"],
        "reponse_attendue": q["reponse_attendue"],
    }

    # 1. Recherche seule : Hit@k et rang réciproque (questions répondables).
    resultats = rechercher(base, q["question"], top_k)["results"]
    ligne["documents_trouves"] = [s["reference"] for s in resultats]

    if not q["refus_attendu"]:
        rang = rang_pertinent(resultats, q["documents"])
        ligne["rang_pertinent"] = rang
        ligne["hit"] = int(rang is not None)
        ligne["rr"] = 1 / rang if rang else 0.0

    if not avec_llm:
        return ligne

    # 2. Génération complète (recherche + seuil + LLM + contrôles).
    debut = perf_counter()
    try:
        reponse = repondre(base, embeddings, q["question"], top_k)
    except LLMError:
        # Une panne du LLM est comptée à part, sans arrêter l'évaluation.
        ligne.update(erreur_llm=1, found=None, latence_s=None, exactitude_auto=0)
        return ligne
    ligne["latence_s"] = round(perf_counter() - debut, 2)
    ligne["found"] = reponse["found"]
    ligne["reponse"] = reponse["answer"]
    ligne["sources_citees"] = [s["reference"] for s in reponse["sources"]]

    if q["refus_attendu"]:
        ligne["refus_correct"] = int(not reponse["found"])
        ligne["exactitude_auto"] = 2 if not reponse["found"] else 0
        return ligne

    ligne["refus_a_tort"] = int(not reponse["found"])

    # Exactitude automatique (indicateur, à confirmer à la main) :
    # 2 = tous les éléments clés présents, 1 = une partie, 0 = aucun ou refus.
    presents = [e for e in q["elements_cles"] if contient(reponse["answer"], e)]
    if not reponse["found"] or not presents:
        ligne["exactitude_auto"] = 0
    elif len(presents) == len(q["elements_cles"]):
        ligne["exactitude_auto"] = 2
    else:
        ligne["exactitude_auto"] = 1

    # Fidélité automatique : les éléments clés de la réponse
    # se retrouvent dans les passages qu'elle cite.
    texte_cite = " ".join(s["excerpt"] for s in reponse["sources"])
    ligne["fidelite_auto"] = int(
        reponse["found"]
        and bool(presents)
        and all(contient(texte_cite, e) for e in presents)
    )

    return ligne


def moyenne(valeurs):
    valeurs = list(valeurs)
    return round(sum(valeurs) / len(valeurs), 3) if valeurs else None


def resumer(nom, lignes, top_k, avec_llm, premiere_s):
    repondables = [l for l in lignes if "hit" in l]
    resume = {
        "configuration": nom,
        "questions": len(lignes),
        f"hit@{top_k}": moyenne(l["hit"] for l in repondables),
        "mrr": moyenne(l["rr"] for l in repondables),
    }

    if avec_llm:
        hors = [l for l in lignes if "refus_correct" in l]
        repondables = [l for l in repondables if not l.get("erreur_llm")]
        latences = [l["latence_s"] for l in lignes if l.get("latence_s") is not None]
        resume.update({
            "exactitude_moyenne_0_2": moyenne(l["exactitude_auto"] for l in lignes),
            "fidelite": moyenne(l["fidelite_auto"] for l in repondables),
            "refus_correct": f"{sum(l['refus_correct'] for l in hors)}/{len(hors)}",
            "refus_a_tort": f"{sum(l['refus_a_tort'] for l in repondables)}/{len(repondables)}",
            "erreurs_llm": sum(l.get("erreur_llm", 0) for l in lignes),
            "premiere_requete_s": premiere_s,
            "latence_mediane_s": round(statistics.median(latences), 2) if latences else None,
            "latence_moyenne_s": moyenne(latences),
        })

    return resume


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--questions", default=str(RACINE / "eval" / "questions.jsonl"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--sans-llm", action="store_true", help="recherche seule")
    parser.add_argument(
        "--configurations", nargs="+", default=list(CONFIGURATIONS),
        choices=list(CONFIGURATIONS),
    )
    args = parser.parse_args()

    avec_llm = not args.sans_llm
    questions = [
        json.loads(l)
        for l in Path(args.questions).read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]

    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    dossier = RACINE / "eval" / "resultats"
    dossier.mkdir(parents=True, exist_ok=True)

    print(f"{len(questions)} questions | top_k={args.top_k} | LLM={'oui' if avec_llm else 'non'}")
    embeddings = get_embeddings()
    resumes = []

    for nom in args.configurations:
        print(f"\n=== Configuration : {nom} ===", flush=True)
        base, etat = ouvrir_collection(CONFIGURATIONS[nom], embeddings)
        print(f"Collection {nom_collection(CONFIGURATIONS[nom])} : {etat['indexed']} fragments")

        # Chauffe : la première requête (chargements) est mesurée à part.
        premiere_s = None
        if avec_llm:
            debut = perf_counter()
            try:
                repondre(base, embeddings, questions[0]["question"], args.top_k)
            except LLMError:
                sys.exit(
                    "LLM indisponible : lance Ollama (ou configure l'API), "
                    "ou utilise --sans-llm pour la recherche seule."
                )
            premiere_s = round(perf_counter() - debut, 2)
            print(f"Première requête (chauffe) : {premiere_s} s")

        lignes = []
        for q in questions:
            ligne = evaluer_question(base, embeddings, q, args.top_k, avec_llm)
            lignes.append(ligne)
            detail = f"rang={ligne.get('rang_pertinent', '-')}"
            if avec_llm:
                detail += f" | found={ligne['found']} | {ligne['latence_s']} s | exact={ligne['exactitude_auto']}"
                if ligne.get("erreur_llm"):
                    detail += " | ERREUR LLM"
            print(f"  {q['id']} {detail}", flush=True)

        resume = resumer(nom, lignes, args.top_k, avec_llm, premiere_s)
        resumes.append(resume)

        (dossier / f"{nom}_{horodatage}.json").write_text(
            json.dumps({"resume": resume, "details": lignes}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # CSV pour la notation manuelle (exactitude 0-2 et fidélité 0/1).
        with open(dossier / f"{nom}_{horodatage}.csv", "w", newline="", encoding="utf-8-sig") as f:
            colonnes = [
                "id", "categorie", "question", "reponse_attendue", "reponse",
                "sources_citees", "exactitude_auto", "fidelite_auto",
                "exactitude_manuelle_0_2", "fidelite_manuelle_0_1",
            ]
            ecrivain = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore", delimiter=";")
            ecrivain.writeheader()
            for ligne in lignes:
                ecrivain.writerow({**ligne, "sources_citees": ", ".join(ligne.get("sources_citees", []))})

    print("\n=== Résumé ===")
    for resume in resumes:
        print(json.dumps(resume, ensure_ascii=False))

    (dossier / f"resume_{horodatage}.json").write_text(
        json.dumps(resumes, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(f"\nRésultats enregistrés dans {dossier}")


if __name__ == "__main__":
    main()