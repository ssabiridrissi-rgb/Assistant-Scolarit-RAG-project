from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    indexed_chunks: int = Field(ge=0)


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str | None = None


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    top_k: StrictInt = Field(default=5, ge=1)
    filters: SearchFilters = Field(default_factory=SearchFilters)

    @field_validator("question")
    @classmethod
    def nettoyer_question(cls, valeur):
        # Refuse les questions vides, y compris les espaces seuls.
        valeur = valeur.strip()
        if not valeur:
            raise ValueError("La question ne doit pas être vide.")
        return valeur


class AskRequest(SearchRequest):
    # Borne les passages initiaux pour le contexte du LLM local.
    top_k: StrictInt = Field(default=5, ge=1, le=10)


class Source(BaseModel):
    id: int = Field(ge=1)
    chunk_id: str
    file: str
    reference: str
    date: str
    page: int = Field(ge=1)
    pages: list[int]
    section: str | None = None
    type: str
    version: str
    status: str
    kind: Literal["paragraph", "table"]
    excerpt: str
    score: float = Field(ge=0, le=1)
    distance: float


class SearchResponse(BaseModel):
    results: list[Source]
    latency_ms: float = Field(ge=0)


class AskResponse(BaseModel):
    answer: str
    found: bool
    sources: list[Source]
    invalid_citations: list[int]
    latency_ms: float = Field(ge=0)


class IndexedDocument(BaseModel):
    file: str
    reference: str
    type: str
    date: str
    version: str
    status: str
    chunks_count: int = Field(ge=1)


class DocumentsResponse(BaseModel):
    documents: list[IndexedDocument]


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["fixed", "structural"] = "structural"
    chunk_size: StrictInt = Field(default=500, ge=1)
    chunk_overlap: StrictInt = Field(default=0, ge=0)

    @model_validator(mode="after")
    def verifier_parametres(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                "Le chevauchement doit être inférieur à la taille."
            )

        if self.strategy == "structural" and self.chunk_overlap != 0:
            raise ValueError(
                "Notre stratégie structurelle utilise "
                "un chevauchement de 0."
            )

        return self


class IngestResponse(BaseModel):
    documents_count: int = Field(ge=0)
    chunks_count: int = Field(ge=0)
    collection: str
    upserted: int = Field(ge=0)
    deleted: int = Field(ge=0)