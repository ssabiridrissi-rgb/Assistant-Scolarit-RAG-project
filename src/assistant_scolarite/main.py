import json
from pathlib import Path
import pdfplumber

# Récupère les sept PDF dans l'ordre de leurs noms.
fichiers = sorted(Path("data/corpus").glob("*.pdf"))
pages = []

for fichier in fichiers:
    with pdfplumber.open(fichier) as pdf:
        for page in pdf.pages:
            # Conserve tout le texte et sa provenance.
            pages.append({
                "file": fichier.name,
                "page": page.page_number,
                "text": page.extract_text() or "",
            })

    print(f"Lu : {fichier.name}")

# Enregistre l'extraction complète.
sortie = Path("data/processed/pages_brutes.json")
sortie.parent.mkdir(parents=True, exist_ok=True)
sortie.write_text(
    json.dumps(pages, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"{len(fichiers)} PDF lus, {len(pages)} pages enregistrées.")