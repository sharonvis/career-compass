"""Temporary local attachments with real SQLite ownership and neutrality."""
from contextlib import ExitStack
from io import BytesIO
import json

from PIL import Image
import pytest
from sqlalchemy import select

from database import db, models as m
from services import evidence_service as evidence, evidence_storage_service as storage
from services import career_service, roadmap_service
from services.errors import EvidenceNotFoundError
from test_evidence_settings_ui import store


def pdf_bytes():
    data = b"%PDF-1.4\n"
    offsets = []
    for obj in (b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
                b"2 0 obj\n<< /Type /Pages /Count 0 /Kids [] >>\nendobj\n"):
        offsets.append(len(data))
        data += obj
    xref = len(data)
    data += b"xref\n0 3\n0000000000 65535 f \n"
    data += b"".join(f"{o:010} 00000 n \n".encode() for o in offsets)
    return data + f"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


def image_bytes(kind="PNG"):
    out = BytesIO()
    Image.new("RGB", (8, 8), "white").save(out, format=kind)
    return out.getvalue()


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_ROOT", tmp_path / "uploads")


def attach(store, filename="certificate.pdf", data=None, mime="application/pdf"):
    with ExitStack() as cleanup:
        with db.session_scope() as session:
            row = evidence.add_evidence(session, store["uid"], store["sid"], "Certificate")
            cleanup.enter_context(storage.stage_attachment(session, store["uid"], row["evidence_id"], filename, data if data is not None else pdf_bytes(), mime))
    return row


@pytest.mark.parametrize("name,data,mime", [
    ("certificate.pdf", pdf_bytes(), "application/pdf"),
    ("certificate.png", image_bytes(), "image/png"),
    ("certificate.jpg", image_bytes("JPEG"), "image/jpeg"),
    ("certificate.JPEG", image_bytes("JPEG"), "image/jpeg"),
], ids=["pdf", "png", "jpg", "jpeg"])
def test_supported_uploads_roundtrip(store, name, data, mime):
    row = attach(store, name, data, mime)
    with store["factory"]() as session:
        result = storage.get_attachment(session, store["uid"], row["evidence_id"])
    assert result["data"] == data and result["original_filename"] == name
    assert result["mime_type"] == mime and result["size"] == len(data)
    directory = storage.STORAGE_ROOT / str(store["uid"]) / str(row["evidence_id"])
    metadata = json.loads((directory / "attachment.json").read_text())
    assert set(metadata) == {"original_filename", "generated_filename", "mime_type", "size", "extension"}
    assert result["generated_filename"] != name
    assert row["url"] is None


@pytest.mark.parametrize("name,data,mime", [
    ("file.exe", b"abc", "application/octet-stream"),
    ("file.pdf", b"", "application/pdf"),
    ("file.pdf", b"x" * (storage.MAX_FILE_SIZE + 1), "application/pdf"),
    ("file.pdf", b"%PDF-1.4\nnot a PDF\n%%EOF", "application/pdf"),
    ("file.png", b"not an image", "image/png"),
    ("file.jpg", image_bytes(), "image/jpeg"),
    ("file.png", image_bytes(), "application/pdf"),
], ids=["unsupported", "empty", "oversize", "invalid-pdf", "invalid-image", "content-mismatch", "mime-mismatch"])
def test_invalid_upload_rolls_back_metadata(store, name, data, mime):
    with pytest.raises(ValueError):
        attach(store, name, data, mime)
    with store["factory"]() as session:
        assert not evidence.list_user_evidence(session, store["uid"])
    assert not list(storage.STORAGE_ROOT.rglob("attachment.json"))


def test_duplicate_does_not_overwrite(store):
    row = attach(store)
    with pytest.raises(ValueError, match="already has an attachment"):
        attach(store, "new.png", image_bytes(), "image/png")
    with store["factory"]() as session:
        assert len(evidence.list_user_evidence(session, store["uid"])) == 1
        assert storage.get_attachment(session, store["uid"], row["evidence_id"])["data"] == pdf_bytes()


def test_ownership_and_safe_names(store):
    row = attach(store, "../../certificate.pdf")
    eid = row["evidence_id"]
    with store["factory"]() as session:
        assert storage.get_attachment(session, store["uid"], eid)["original_filename"] == "certificate.pdf"
        for method in (storage.get_attachment,):
            with pytest.raises(EvidenceNotFoundError):
                method(session, store["other"], eid)
        with pytest.raises(EvidenceNotFoundError):
            with storage.stage_attachment(session, store["other"], eid, "x.pdf", pdf_bytes()):
                pass
        with pytest.raises(EvidenceNotFoundError):
            with storage.delete_attachment_after_commit(session, store["other"], eid):
                pass
        directory = storage.STORAGE_ROOT / str(store["uid"]) / str(eid)
        manifest = directory / "attachment.json"
        metadata = json.loads(manifest.read_text())
        metadata["generated_filename"] = "../../outside.pdf"
        manifest.write_text(json.dumps(metadata))
        with pytest.raises(ValueError, match="metadata"):
            storage.get_attachment(session, store["uid"], eid)


def test_commit_failure_removes_new_attachment(store, monkeypatch):
    with pytest.raises(RuntimeError, match="commit failed"):
        with ExitStack() as cleanup:
            with db.session_scope() as session:
                row = evidence.add_evidence(session, store["uid"], store["sid"], "Certificate")
                cleanup.enter_context(storage.stage_attachment(session, store["uid"], row["evidence_id"], "x.pdf", pdf_bytes()))
                monkeypatch.setattr(session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("commit failed")))
    assert not list(storage.STORAGE_ROOT.rglob("attachment.json"))
    with store["factory"]() as session:
        assert not evidence.list_user_evidence(session, store["uid"])


def test_storage_failure_cleans_partial_directory(store, monkeypatch):
    from pathlib import Path
    original = Path.write_text
    def fail_manifest(path, *args, **kwargs):
        if path.name == "attachment.json":
            raise OSError("disk full")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", fail_manifest)
    with pytest.raises(OSError):
        attach(store)
    assert not list(storage.STORAGE_ROOT.rglob("*.pdf"))


def test_delete_only_after_commit_and_failure_preserves_file(store):
    row = attach(store)
    eid = row["evidence_id"]
    directory = storage.STORAGE_ROOT / str(store["uid"]) / str(eid)
    with pytest.raises(RuntimeError):
        with ExitStack() as cleanup:
            with db.session_scope() as session:
                cleanup.enter_context(storage.delete_attachment_after_commit(session, store["uid"], eid))
                evidence.delete_evidence(session, store["uid"], eid)
                raise RuntimeError("rollback")
    assert directory.exists()
    with ExitStack() as cleanup:
        with db.session_scope() as session:
            cleanup.enter_context(storage.delete_attachment_after_commit(session, store["uid"], eid))
            evidence.delete_evidence(session, store["uid"], eid)
            assert directory.exists()
    assert not directory.exists()


def test_upload_scoring_and_roadmap_neutrality(store):
    def snapshot():
        with store["factory"]() as session:
            return dict(summary=career_service.get_user_career_summary(session, store["uid"], store["cid"]),
                        roadmap=roadmap_service.get_user_roadmap(session, store["uid"], store["cid"]),
                        claims=[(r.skill_id, r.claimed_level) for r in session.scalars(select(m.UserSkillClaim).where(m.UserSkillClaim.user_id == store["uid"]))],
                        attempts=[(r.id, r.status, r.resulting_level) for r in session.scalars(select(m.AssessmentAttempt).where(m.AssessmentAttempt.user_id == store["uid"]))])
    before = snapshot()
    row = attach(store)
    assert snapshot() == before
    with ExitStack() as cleanup:
        with db.session_scope() as session:
            cleanup.enter_context(storage.delete_attachment_after_commit(session, store["uid"], row["evidence_id"]))
            evidence.delete_evidence(session, store["uid"], row["evidence_id"])
    assert snapshot() == before
