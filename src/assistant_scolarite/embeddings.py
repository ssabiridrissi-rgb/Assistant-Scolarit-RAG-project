from langchain_huggingface import HuggingFaceEmbeddings


# Un seul modèle pour les questions et les fragments.
MODEL_NAME = "intfloat/multilingual-e5-small"


def get_embeddings(provider="huggingface"):
    """Crée le modèle d'embedding local."""

    if provider != "huggingface":
        raise ValueError("Le fournisseur configuré est huggingface.")

    return HuggingFaceEmbeddings(
        model_name=MODEL_NAME,

        # Fonctionne sur le processeur, sans nécessiter de carte graphique.
        model_kwargs={
            "device": "cpu",
        },

        # E5 demande le préfixe "passage: " pour les fragments.
        encode_kwargs={
            "prompt": "passage: ",
            "normalize_embeddings": True,
        },

        # E5 demande le préfixe "query: " pour les questions,
        # même lorsque le texte est en français.
        query_encode_kwargs={
            "prompt": "query: ",
            "normalize_embeddings": True,
        },
    )


if __name__ == "__main__":
    embeddings = get_embeddings()

    # Transforme une question en un vecteur.
    question = "Quand faut-il déposer la convention de stage ?"
    vecteur_question = embeddings.embed_query(question)

    # Transforme une liste de fragments en une liste de vecteurs.
    fragments = [
        "La convention signée doit être déposée sur le Portail Stages "
        "au moins 15 jours calendaires avant le début du stage."
    ]
    vecteurs_fragments = embeddings.embed_documents(fragments)

    # Vérifie les dimensions sans afficher les 384 nombres.
    print("Dimension question :", len(vecteur_question))
    print("Dimension fragment :", len(vecteurs_fragments[0]))