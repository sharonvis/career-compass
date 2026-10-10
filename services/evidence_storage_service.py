"""Local, ownership-checked supporting attachments; never scoring inputs.

Call the context managers from an ExitStack OUTSIDE the database transaction,
so their successful exit occurs only after session_scope commits.
"""
from contextlib import contextmanager
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import uuid
import warnings

from PIL import Image, UnidentifiedImageError

from services import evidence_service

STORAGE_ROOT = Path(__file__).resolve().parents[1] / "data" / "evidence_uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024
MIME_TYPES = {".pdf": "application/pdf", ".png": "image/png",
              ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def validate_attachment(filename, data, mime_type=None):
    if not isinstance(filename, str) or not filename.strip() or len(filename) > 255:
        raise ValueError("Choose a file with a valid filename (up to 255 characters).")
    extension = Path(filename).suffix.lower()
    if extension not in MIME_TYPES:
        raise ValueError("Only PDF, PNG, JPG and JPEG files are supported.")
    if not isinstance(data, bytes) or not data:
        raise ValueError("The attachment is empty.")
    if len(data) > MAX_FILE_SIZE:
        raise ValueError("The attachment must be 10 MB or smaller.")
    expected = MIME_TYPES[extension]
    supplied = (mime_type or "").split(";", 1)[0].strip().lower()
    if supplied not in {"", "application/octet-stream", expected}:
        raise ValueError("The file type does not match its extension.")
    if extension == ".pdf":
        # Conservative structural validation, not certificate verification or a
        # complete PDF parser. Files are downloaded, never rendered/executed.
        valid = (re.match(rb"%PDF-\d\.\d(?:\r|\n)", data) is not None
                 and data.rstrip().endswith(b"%%EOF")
                 and re.search(rb"\b\d+\s+\d+\s+obj\b", data) is not None
                 and re.search(rb"/Type\s*/Catalog\b", data) is not None)
        offsets = re.findall(rb"startxref\s+(\d+)\s+%%EOF", data)
        valid = valid and bool(offsets)
        if valid:
            offset = int(offsets[-1])
            valid = offset < len(data) and (data[offset:].startswith(b"xref")
                    or re.match(rb"\d+\s+\d+\s+obj\b", data[offset:]) is not None)
        if not valid:
            raise ValueError("The file does not appear to be a valid PDF.")
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    actual = image.format
                    image.verify()
                with Image.open(BytesIO(data)) as image:
                    image.load()
            if actual != ("PNG" if extension == ".png" else "JPEG"):
                raise ValueError("The image content does not match its extension.")
        except (UnidentifiedImageError, OSError, SyntaxError,
                Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
            raise ValueError("The attachment is not a valid supported image.") from error
    # This name is display/download metadata only, never a storage path.
    original = filename.replace("\\", "/").split("/")[-1]
    original = "".join(c for c in original if c.isprintable()).strip()
    if not original:
        raise ValueError("Choose a file with a valid filename.")
    return dict(original_filename=original, mime_type=expected, size=len(data), extension=extension)


def _directory(user_id, evidence_id):
    if any(type(value) is not int or value <= 0 for value in (user_id, evidence_id)):
        raise ValueError("Invalid evidence identity.")
    root = Path(STORAGE_ROOT).absolute()
    directory = root / str(user_id) / str(evidence_id)
    # Reject redirected paths, including Windows junctions resolved elsewhere.
    if root.resolve() != root or directory.resolve() != directory:
        raise ValueError("Invalid attachment storage path.")
    if any(p.is_symlink() for p in (root, directory.parent, directory)):
        raise ValueError("Invalid attachment storage path.")
    return directory


@contextmanager
def stage_attachment(session, user_id, evidence_id, filename, data, mime_type=None):
    """Create one attachment; remove it on file failure OR caller/commit failure."""
    evidence_service.get_evidence(session, user_id, evidence_id)
    metadata = validate_attachment(filename, data, mime_type)
    directory = _directory(user_id, evidence_id)
    directory.parent.mkdir(parents=True, exist_ok=True)
    try:
        directory.mkdir()  # Exclusive creation prevents duplicate overwrites.
    except FileExistsError as error:
        raise ValueError("This evidence already has an attachment. It was not replaced.") from error
    metadata["generated_filename"] = uuid.uuid4().hex + metadata["extension"]
    try:
        (directory / metadata["generated_filename"]).write_bytes(data)
        (directory / "attachment.json").write_text(json.dumps(metadata), encoding="utf-8")
        yield metadata
    except BaseException:
        shutil.rmtree(directory)
        raise


def get_attachment(session, user_id, evidence_id):
    """Return metadata and bytes only after checking evidence ownership."""
    evidence_service.get_evidence(session, user_id, evidence_id)
    directory = _directory(user_id, evidence_id)
    if not directory.exists():
        return None
    manifest = directory / "attachment.json"
    if manifest.is_symlink():
        raise ValueError("Invalid attachment metadata.")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    generated = metadata.get("generated_filename", "")
    if re.fullmatch(r"[0-9a-f]{32}\.(?:pdf|png|jpg|jpeg)", generated) is None:
        raise ValueError("Invalid attachment metadata.")
    path = directory / generated
    if path.is_symlink() or path.resolve().parent != directory:
        raise ValueError("Invalid attachment storage path.")
    if path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("Invalid attachment size.")
    data = path.read_bytes()
    validated = validate_attachment(metadata["original_filename"], data, metadata["mime_type"])
    if any(metadata.get(k) != v for k, v in validated.items()) or path.suffix != validated["extension"]:
        raise ValueError("Invalid attachment metadata.")
    return dict(metadata, data=data)


class AttachmentCleanupError(OSError):
    """The DB deletion committed but local cleanup could not finish."""


@contextmanager
def delete_attachment_after_commit(session, user_id, evidence_id):
    """Authorize before row deletion, remove files only on successful outer exit."""
    evidence_service.get_evidence(session, user_id, evidence_id)
    directory = _directory(user_id, evidence_id)
    yield
    try:
        directory = _directory(user_id, evidence_id)  # Recheck before deletion.
        if directory.exists():
            shutil.rmtree(directory)
    except (OSError, ValueError) as error:
        raise AttachmentCleanupError("Evidence deleted, but its local attachment could not be removed.") from error
