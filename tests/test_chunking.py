import pytest

from chunking import decouper_fixe
from chunking_structurel import fragmenter_blocs, regrouper_sections


def ligne(texte, page=1, nature=None):
    """Construit une ligne synthétique, sans lire de PDF."""
    return {
        "text": texte,
        "page": page,
        "nature": nature,
    }


def test_fixe_conserve_texte_et_chevauchement():
    texte = "La convention doit etre deposee quinze jours avant le stage."

    fragments = decouper_fixe(
        texte,
        taille=20,
        chevauchement=5,
    )

    # Chaque fragment respecte la taille maximale.
    assert all(0 < len(f) <= 20 for f in fragments)

    # Les fragments voisins partagent cinq caractères.
    for precedent, suivant in zip(fragments, fragments[1:]):
        assert precedent[-5:] == suivant[:5]

    # Retirer les répétitions doit permettre de retrouver tout le texte.
    reconstruit = fragments[0] + "".join(
        fragment[5:] for fragment in fragments[1:]
    )
    assert reconstruit == texte


def test_fixe_texte_vide():
    assert decouper_fixe("") == []


# Le même test sera exécuté avec trois paramètres invalides.
@pytest.mark.parametrize("taille,chevauchement", [
    (0, 0),
    (10, -1),
    (10, 10),
])
def test_fixe_refuse_parametres_invalides(taille, chevauchement):
    # Ces paramètres doivent être refusés avant de démarrer une boucle.
    with pytest.raises(ValueError):
        decouper_fixe("Un texte", taille, chevauchement)


def test_article_conserve_sous_section_et_pages():
    lignes = [
        ligne("Article 1 — Objet", nature="article"),
        ligne("Première partie."),
        ligne("1.1 Précision", nature="section"),
        ligne("Suite sur la deuxième page.", page=2),
        ligne("Article 2 — Inscription", page=2, nature="article"),
        ligne("Contenu du deuxième article.", page=2),
    ]

    blocs = regrouper_sections(lignes)

    # Les deux articles restent séparés.
    assert len(blocs) == 2
    assert blocs[0]["section"] == "Article 1 — Objet"

    # La sous-section reste dans le premier article.
    assert [l["text"] for l in blocs[0]["lignes"]] == [
        "Première partie.",
        "1.1 Précision",
        "Suite sur la deuxième page.",
    ]

    # La continuation sur la deuxième page est conservée.
    assert {l["page"] for l in blocs[0]["lignes"]} == {1, 2}

    assert blocs[1]["lignes"][0]["text"] == (
        "Contenu du deuxième article."
    )


def test_faq_garde_chaque_question_avec_sa_reponse():
    lignes = [
        ligne("Q1. Première question ?", nature="question"),
        ligne("Réponse à Q1."),
        ligne("Q2. Deuxième question ?", nature="question"),
        ligne("Réponse à Q2."),
    ]

    blocs = regrouper_sections(lignes)

    # Chaque réponse appartient à la bonne question.
    assert len(blocs) == 2

    assert blocs[0]["section"] == "Q1. Première question ?"
    assert [l["text"] for l in blocs[0]["lignes"]] == [
        "Réponse à Q1."
    ]

    assert blocs[1]["section"] == "Q2. Deuxième question ?"
    assert [l["text"] for l in blocs[1]["lignes"]] == [
        "Réponse à Q2."
    ]


def test_bloc_long_conserve_texte_pages_titre_et_source():
    # Un bloc synthétique qui traverse deux pages.
    bloc = {
        "section": "5. PFE > 5.4 Encadrement",
        "lignes": [
            ligne("A" * 70),
            ligne("B" * 70, page=2),
        ],
    }

    meta = {
        "reference": "TEST-REG",
        "date": "2026-07-10",
    }

    fragments = fragmenter_blocs(
        [bloc],
        "test.pdf",
        meta,
        taille=80,
    )

    prefixe = bloc["section"] + "\n"

    # Vérifie la taille et la présence du titre.
    assert all(len(f["text"]) <= 80 for f in fragments)
    assert all(f["text"].startswith(prefixe) for f in fragments)

    # Le corps doit être conservé sans perte ni répétition.
    reconstruit = "".join(
        f["text"][len(prefixe):] for f in fragments
    )
    assert reconstruit == "A" * 70 + "\n" + "B" * 70

    # Vérifie les pages, les sources et les identifiants.
    assert {p for f in fragments for p in f["pages"]} == {1, 2}
    assert any(f["pages"] == [1, 2] for f in fragments)
    assert all(f["page"] == min(f["pages"]) for f in fragments)
    assert all(f["reference"] == "TEST-REG" for f in fragments)

    identifiants = {f["chunk_id"] for f in fragments}
    assert len(identifiants) == len(fragments)