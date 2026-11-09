"""Consultation des sept PDF originaux, indépendante de Chroma et du LLM."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

# Ce fichier doit être placé dans src/assistant_scolarite/.
# Le chemin ne dépend pas du dossier depuis lequel uvicorn est lancé.
CORPUS_DIR = Path(__file__).resolve().parents[2] / "data" / "corpus"

# Liste fermée de fichiers autorisés : aucune règle métier n'est codée ici.
ALLOWED_FILES = (
    "01_Reglement_des_etudes_2026-2027.pdf",
    "02_Guide_stages_PFE_2026.pdf",
    "03_Charte_mobilite_internationale.pdf",
    "04_Calendrier_academique_2026-2027.pdf",
    "05_Guide_vie_etudiante.pdf",
    "06_FAQ_Scolarite.pdf",
    "07_Note_de_service_2026-14.pdf",
)


def create_pdf_router(corpus_dir: Path) -> APIRouter:
    """La factory permet de tester un dossier temporaire sans toucher au corpus."""
    router = APIRouter(prefix="/api", tags=["PDF"])
    root = corpus_dir.resolve()

    def resolve_pdf(filename: str) -> Path:
        if filename not in ALLOWED_FILES:
            raise HTTPException(status_code=404, detail="Document non autorisé.")
        path = (root / filename).resolve()
        # Empêche aussi de suivre un lien symbolique vers un fichier extérieur.
        if path.parent != root or not path.is_file():
            raise HTTPException(status_code=404, detail="PDF introuvable.")
        return path

    @router.get("/files", responses={503: {"description": "Corpus absent"}})
    def list_files():
        if not root.is_dir():
            raise HTTPException(status_code=503, detail="Dossier corpus indisponible.")
        files = []
        for filename in ALLOWED_FILES:
            try:
                resolve_pdf(filename)
                files.append(filename)
            except HTTPException:
                continue
        return {"files": files}

    @router.get("/files/{filename}", response_class=FileResponse,
                responses={404: {"description": "PDF absent ou non autorisé"}})
    def get_pdf(filename: str, download: bool = False):
        path = resolve_pdf(filename)
        return FileResponse(
            path=path,
            media_type="application/pdf",
            filename=filename,
            content_disposition_type="attachment" if download else "inline",
            headers={"X-Content-Type-Options": "nosniff"},
        )

    return router


router = create_pdf_router(CORPUS_DIR)
