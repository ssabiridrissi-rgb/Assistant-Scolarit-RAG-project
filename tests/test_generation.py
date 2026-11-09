"""Tests de generation.py sans Chroma ni Ollama : base et LLM sont simulés."""
import pytest
from langchain_core.documents import Document

import generation
from generation import REFUS, Brouillon, normaliser_citations, repondre


def metadonnees(**autres):
    """Métadonnées minimales d'un fragment, au format de Chroma."""
    meta = {
        "chunk_id": "DOC-REF-structurel-500-b1-c1",
        "file": "doc.pdf",
        "reference": "DOC-REF",
        "date": "2026-01-01",
        "page": 1,
        "pages_json": "[1]",
        "section": "Section de test",
        "type": "Guide",
        "version": "1.0",
        "status": "En vigueur",
        "kind": "paragraph",
    }
    meta.update(autres)
    return meta


class FausseBase:
    """Remplace Chroma : renvoie un seul passage, à la distance choisie."""

    def __init__(self, distance):
        self.distance = distance
        self.meta = metadonnees()

    def similarity_search_with_score(self, question, k, filter=None):
        document = Document(
            page_content="Le délai est de 15 jours.",
            metadata=self.meta,
        )
        return [(document, self.distance)]

    def get(self, include=None, where=None):
        # Aucun texte modificatif, aucun tableau : rien à compléter.
        return {"metadatas": [self.meta]}


class FauxLLM:
    """Remplace Ollama : compte les appels et renvoie un brouillon fixé."""

    def __init__(self, answer="", found=True):
        self.brouillon = Brouillon(answer=answer, found=found)
        self.appels = 0

    def invoke(self, systeme, message):
        self.appels += 1
        return self.brouillon


@pytest.fixture
def llm(monkeypatch):
    """Installe un faux LLM ; chaque test choisit sa réponse."""
    monkeypatch.setenv("RAG_SCORE_THRESHOLD", "0.90")
    faux = FauxLLM()
    monkeypatch.setattr(generation, "get_llm", lambda provider="ollama": faux)
    return faux


def test_refus_hors_corpus_avant_appel_au_llm(llm):
    # Distance 0.6 -> score 0.70, sous le seuil 0.90.
    resultat = repondre(FausseBase(0.6), None, "Qui a gagné la Coupe du monde ?")

    assert resultat["answer"] == REFUS
    assert resultat["found"] is False
    assert resultat["sources"] == []
    assert llm.appels == 0


def test_reponse_valide_garde_la_source_citee(llm):
    llm.brouillon = Brouillon(answer="Le délai est de 15 jours [1].", found=True)

    resultat = repondre(FausseBase(0.1), None, "Quel délai ?")

    assert resultat["found"] is True
    assert [s["id"] for s in resultat["sources"]] == [1]
    assert llm.appels == 1


def test_citation_inventee_refusee(llm):
    llm.brouillon = Brouillon(answer="Le délai est de 15 jours [7].", found=True)

    resultat = repondre(FausseBase(0.1), None, "Quel délai ?")

    assert resultat["answer"] == REFUS
    assert resultat["found"] is False
    assert resultat["invalid_citations"] == [7]


def test_reponse_sans_citation_refusee(llm):
    llm.brouillon = Brouillon(answer="Le délai est de 15 jours.", found=True)

    resultat = repondre(FausseBase(0.1), None, "Quel délai ?")

    assert resultat["answer"] == REFUS
    assert resultat["found"] is False


def test_refus_du_modele_remplace_par_la_phrase_exacte(llm):
    llm.brouillon = Brouillon(answer="Pas d'information.", found=False)

    resultat = repondre(FausseBase(0.1), None, "Quel délai ?")

    assert resultat["answer"] == REFUS
    assert resultat["found"] is False


def test_citations_groupees_normalisees():
    assert normaliser_citations("A [1, 2] et B [3;4] puis C [5]") == (
        "A [1] [2] et B [3] [4] puis C [5]"
    )


def test_citations_ajoutees_depuis_les_preuves():
    from generation import citer_depuis_preuves

    # Le texte n'a aucune citation : on reprend les preuves valides.
    assert citer_depuis_preuves("16 places.", [1, 9], {1, 2}) == "16 places. [1]"
    # Le texte a déjà ses citations : rien ne change.
    assert citer_depuis_preuves("16 places [2].", [1], {1, 2}) == "16 places [2]."


def test_reponse_hors_sujet_refusee(llm):
    # Le modèle répond, cite [1], mais l'extrait ne parle pas du sujet demandé.
    llm.brouillon = Brouillon(
        answer="La journée d'intégration a lieu en septembre [1].",
        found=True,
    )

    resultat = repondre(FausseBase(0.1), None, "journée d'intégration")

    assert resultat["answer"] == REFUS
    assert resultat["found"] is False


def test_question_ancree_dans_les_sources():
    from generation import question_ancree

    source = {"section": "2.2 Convention de stage",
              "excerpt": "La convention doit être déposée 15 jours avant le stage."}

    assert question_ancree("Quand faut-il déposer la convention de stage ?", [source])
    assert not question_ancree("Qui a gagné la Coupe du monde de football ?", [source])


def test_refus_deguise_remplace_par_la_phrase_exacte(llm):
    llm.brouillon = Brouillon(
        answer="Le délai n'est pas mentionné dans les extraits fournis [1].",
        found=True,
    )

    resultat = repondre(FausseBase(0.1), None, "Quel délai ?")

    assert resultat["answer"] == REFUS
    assert resultat["found"] is False