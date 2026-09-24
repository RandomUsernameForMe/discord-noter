import json
import re
from pathlib import Path
from typing import TypedDict

PROJECTS_FILE = Path(__file__).parent / "projects.json"


class Project(TypedDict):
    folder_id: str
    style_folder: str | None


def _load() -> dict[str, Project]:
    if not PROJECTS_FILE.exists():
        return {}
    data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    # Starý formát: {name: folder_id}
    return {
        name: {"folder_id": v, "style_folder": None} if isinstance(v, str) else v
        for name, v in data.items()
    }


def _save(data: dict[str, Project]) -> None:
    PROJECTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_projects() -> dict[str, Project]:
    return _load()


def add_project(name: str, drive_url: str, style_folder: str | None = None) -> str:
    """Add project, return extracted folder ID."""
    folder_id = _extract_folder_id(drive_url)
    if not folder_id:
        raise ValueError(f"Nepodařilo se extrahovat ID složky z URL: {drive_url}")
    if style_folder and not Path(style_folder).is_dir():
        raise ValueError(f"Složka se vzory neexistuje: {style_folder}")
    data = _load()
    data[name] = {"folder_id": folder_id, "style_folder": style_folder or None}
    _save(data)
    return folder_id


def remove_project(name: str) -> bool:
    data = _load()
    if name not in data:
        return False
    del data[name]
    _save(data)
    return True


def get_project(name: str) -> Project | None:
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
