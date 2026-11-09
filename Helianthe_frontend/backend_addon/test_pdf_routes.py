"""Copier dans tests/ ; pytest.ini existant ajoute src/assistant_scolarite."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from pdf_routes import ALLOWED_FILES, create_pdf_router


@pytest.fixture
def pdf_client(tmp_path):
    name = ALLOWED_FILES[0]
    content = b"%PDF-1.4\n% fixture test\n%%EOF"
    (tmp_path / name).write_bytes(content)
    (tmp_path / "hors_corpus.pdf").write_bytes(content)
    (tmp_path / ".env").write_text("SECRET=ne_pas_servir")
    app = FastAPI()
    app.include_router(create_pdf_router(tmp_path))
    return TestClient(app), name, content


def test_catalogue_limite_au_corpus(pdf_client):
    client, name, _ = pdf_client
    assert client.get("/api/files").json() == {"files": [name]}


def test_pdf_inline_octets_inchanges(pdf_client):
    client, name, content = pdf_client
    response = client.get(f"/api/files/{name}")
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")


def test_pdf_telechargement(pdf_client):
    client, name, _ = pdf_client
    response = client.get(f"/api/files/{name}?download=true")
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")


@pytest.mark.parametrize("filename", ["hors_corpus.pdf", ".env", ALLOWED_FILES[-1], "..%2F.env"])
def test_pdf_non_autorise_ou_absent(pdf_client, filename):
    client, _, _ = pdf_client
    assert client.get(f"/api/files/{filename}").status_code == 404


def test_corpus_absent(tmp_path):
    app = FastAPI()
    app.include_router(create_pdf_router(tmp_path / "absent"))
    assert TestClient(app).get("/api/files").status_code == 503


def test_parametre_download_invalide(pdf_client):
    client, name, _ = pdf_client
    assert client.get(f"/api/files/{name}?download=invalide").status_code == 422


def test_lien_symbolique_exterieur_refuse(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(b"secret")
    try:
        (root / ALLOWED_FILES[0]).symlink_to(secret)
    except OSError:
        pytest.skip("Création de liens symboliques non autorisée sur ce système.")
    app = FastAPI()
    app.include_router(create_pdf_router(root))
    response = TestClient(app).get(f"/api/files/{ALLOWED_FILES[0]}")
    assert response.status_code == 404
