"""
File storage abstraction for generated report artifacts (FR-18.2: "the
file itself lives in Cloudinary" -- `Report`'s own model docstring).

Every other module that stores a URL on a model (`Plant.photo_urls`,
`DiseaseReport.photo_url`, `Passport.pdf_url`, ...) accepts a caller-
supplied string and never uploads anything itself -- those are always
client-side direct uploads (the browser/mobile app uploads straight to
Cloudinary and only hands the resulting URL to the API), which is why no
`FileStorage`-shaped abstraction exists anywhere in this codebase before
this module. Reports are different: nothing on the client produces this
artifact -- `ReportGenerationService` builds the PDF/Excel/CSV/JSON bytes
itself (server-side, in a background task), so *something* server-side has
to persist them and hand back a URL, or a generated report would have
nowhere to live.

`CLOUDINARY_CLOUD_NAME`/`API_KEY`/`API_SECRET` (app/core/config.py) have
been declared since Phase 5 but never read by any code -- this module is
the first to actually use them. Following the exact "real implementation +
local graceful-degradation fallback when unset" shape `SmtpEmailSender`
(Module 2) and `SmsProvider`/`PushProvider` (Module 11) already
established for this codebase's disclosed "no vendor credentials in this
environment" situation: `get_file_storage()` returns a real
`CloudinaryFileStorage` when credentials are configured, otherwise a
`LocalFileStorage` that writes to disk and serves the file back through
`GET /reports/{id}/download` (app/api/routes/reports.py) -- unlike the
email/SMS/push no-ops, a report genuinely has to be downloadable even
absent real credentials, so the fallback here is a fully working
substitute store (legitimate for a self-hosted/on-prem deployment), not a
no-op.
"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class FileStorage(Protocol):
    async def upload(self, *, content: bytes, filename: str, content_type: str) -> str:
        """Persists `content` and returns a URL the caller can hand back to a client for download."""
        ...


class CloudinaryFileStorage:
    """
    Uploads as Cloudinary's `raw` resource type (PDFs/Excel/CSV/JSON are
    not images) via the official `cloudinary` SDK, which is itself a
    synchronous, blocking HTTP client -- run in a worker thread via
    `asyncio.to_thread` so it doesn't block the event loop, the same
    reasoning `AssistantOrchestrator`'s Anthropic SDK call would need if
    that SDK weren't already async-native.
    """

    def __init__(self, *, cloud_name: str, api_key: str, api_secret: str) -> None:
        import cloudinary

        cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True)

    async def upload(self, *, content: bytes, filename: str, content_type: str) -> str:
        import cloudinary.uploader

        def _do_upload() -> str:
            result = cloudinary.uploader.upload(
                content,
                resource_type="raw",
                public_id=f"reports/{filename}",
                overwrite=True,
            )
            return result["secure_url"]

        url = await asyncio.to_thread(_do_upload)
        logger.info("report_file_uploaded", backend="cloudinary", filename=filename)
        return url


class LocalFileStorage:
    """
    Writes to `settings.REPORTS_LOCAL_STORAGE_PATH` on the API server's
    own filesystem. Returns a relative URL (`/reports/files/{filename}`)
    that `GET /reports/files/{filename}` (app/api/routes/reports.py)
    streams back -- authorization for that download route is the same
    `reports:read` permission check + tenant-ownership check every other
    report-download path uses, not a public/unauthenticated file server.
    """

    def __init__(self, *, base_path: str) -> None:
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    async def upload(self, *, content: bytes, filename: str, content_type: str) -> str:
        target = self._base_path / filename

        def _write() -> None:
            target.write_bytes(content)

        await asyncio.to_thread(_write)
        logger.info("report_file_uploaded", backend="local", filename=filename, path=str(target))
        return f"/reports/files/{filename}"

    def resolve(self, filename: str) -> Path | None:
        """
        Used only by the download route to map a previously-issued
        `/reports/files/{filename}` URL back to a real path -- validates
        the resolved path stays inside `_base_path` (rejects `filename`
        values containing `..`/path separators from a malformed or
        tampered URL) before returning it.
        """
        candidate = (self._base_path / filename).resolve()
        if self._base_path.resolve() not in candidate.parents and candidate != self._base_path.resolve():
            return None
        return candidate if candidate.is_file() else None


def build_report_filename(*, report_id: uuid.UUID, extension: str) -> str:
    """Shared by every export format so `ReportGenerationService` and the download route agree on one naming scheme."""
    return f"{report_id}.{extension}"


def get_file_storage(settings: Settings) -> FileStorage:
    if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
        return CloudinaryFileStorage(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
        )
    return LocalFileStorage(base_path=settings.REPORTS_LOCAL_STORAGE_PATH)
