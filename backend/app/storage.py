from pathlib import Path

from app.config import get_settings

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".txt": "text/plain",
}


def storage_dir() -> Path:
    path = Path(get_settings().file_storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path
