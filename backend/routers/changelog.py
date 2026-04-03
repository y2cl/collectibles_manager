"""
Changelog endpoints.
Serves markdown files from the changelogs/ directory at the project root.
GET /api/changelog        — list all changelog files
GET /api/changelog/{name} — return the content of a specific file
"""
import os
import re
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/changelog", tags=["changelog"])

# changelogs/ sits two levels up from backend/routers/
_CHANGELOGS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "changelogs")
)

_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(v[\w.]+)-ChangeLog\.md$", re.IGNORECASE)


class ChangelogEntry(BaseModel):
    filename: str
    date: str
    version: str
    title: str


def _parse_name(filename: str):
    m = _FILENAME_RE.match(filename)
    if m:
        return m.group(1), m.group(2)
    return "", ""


@router.get("", response_model=List[ChangelogEntry])
def list_changelogs():
    """List all changelog files, newest first."""
    if not os.path.isdir(_CHANGELOGS_DIR):
        return []
    entries = []
    for f in os.listdir(_CHANGELOGS_DIR):
        if not f.lower().endswith(".md"):
            continue
        date, version = _parse_name(f)
        entries.append(ChangelogEntry(
            filename=f,
            date=date,
            version=version,
            title=f"{version} — {date}" if version and date else f.replace(".md", ""),
        ))
    return sorted(entries, key=lambda e: e.date, reverse=True)


@router.get("/{filename}")
def get_changelog(filename: str):
    """Return the raw markdown content of a changelog file."""
    # Safety: only allow safe filenames
    if not _FILENAME_RE.match(filename) or ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    path = os.path.join(_CHANGELOGS_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Changelog not found.")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    date, version = _parse_name(filename)
    return {"filename": filename, "date": date, "version": version, "content": content}
