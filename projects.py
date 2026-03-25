import json
import re
from pathlib import Path

PROJECTS_FILE = Path(__file__).parent / "projects.json"


def _load() -> dict[str, str]:
    if not PROJECTS_FILE.exists():
        return {}
    return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))


def _save(data: dict[str, str]) -> None:
    PROJECTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_projects() -> dict[str, str]:
    return _load()


def add_project(name: str, drive_url: str) -> str:
    """Add project, return extracted folder ID."""
    folder_id = _extract_folder_id(drive_url)
    if not folder_id:
        raise ValueError(f"Nepodařilo se extrahovat ID složky z URL: {drive_url}")
    data = _load()
    data[name] = folder_id
    _save(data)
    return folder_id


def remove_project(name: str) -> bool:
    data = _load()
    if name not in data:
        return False
    del data[name]
    _save(data)
    return True


def get_folder_id(name: str) -> str | None:
    return _load().get(name)


def _extract_folder_id(url: str) -> str | None:
    # https://drive.google.com/drive/folders/<ID>
    m = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    # Bare ID (no slashes)
    if re.fullmatch(r"[a-zA-Z0-9_-]{10,}", url):
        return url
    return None
