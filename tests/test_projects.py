import json
import pytest
from pathlib import Path
from unittest.mock import patch

import projects
from projects import _extract_folder_id, add_project, remove_project, get_folder_id, list_projects


# ---------------------------------------------------------------------------
# _extract_folder_id
# ---------------------------------------------------------------------------

class TestExtractFolderId:
    def test_standard_drive_url(self):
        url = "https://drive.google.com/drive/folders/1abc123XYZ_-abcdef1234"
        assert _extract_folder_id(url) == "1abc123XYZ_-abcdef1234"

    def test_url_with_trailing_slash(self):
        assert _extract_folder_id("https://drive.google.com/drive/folders/ABC123defGHI/") == "ABC123defGHI"

    def test_url_with_query_params(self):
        url = "https://drive.google.com/drive/folders/ABC123defGHI?usp=sharing"
        assert _extract_folder_id(url) == "ABC123defGHI"

    def test_bare_id_exact_10_chars(self):
        # Minimální délka bare ID je 10 znaků
        assert _extract_folder_id("1234567890") == "1234567890"

    def test_bare_id_longer(self):
        bare = "1a2b3c4d5e6f7g8h"
        assert _extract_folder_id(bare) == bare

    def test_bare_id_too_short(self):
        # 9 znaků → None
        assert _extract_folder_id("123456789") is None

    def test_url_without_folders_segment(self):
        assert _extract_folder_id("https://drive.google.com/file/d/someId") is None

    def test_empty_string(self):
        assert _extract_folder_id("") is None

    def test_bare_id_with_hyphens_and_underscores(self):
        bare = "abc-def_ghi123"
        assert _extract_folder_id(bare) == bare

    def test_bare_id_with_spaces(self):
        # Mezery nejsou v [a-zA-Z0-9_-] → None
        assert _extract_folder_id("abc def ghij") is None


# ---------------------------------------------------------------------------
# add_project / remove_project / get_folder_id — s tmp souborem
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_projects(tmp_path, monkeypatch):
    """Přesměruje PROJECTS_FILE na dočasný soubor."""
    tmp_file = tmp_path / "projects.json"
    monkeypatch.setattr(projects, "PROJECTS_FILE", tmp_file)
    return tmp_file


class TestAddProject:
    def test_adds_project_from_url(self, tmp_projects):
        folder_id = add_project("MyProject", "https://drive.google.com/drive/folders/ABC123defGHI")
        assert folder_id == "ABC123defGHI"
        assert list_projects()["MyProject"] == "ABC123defGHI"

    def test_adds_project_from_bare_id(self, tmp_projects):
        folder_id = add_project("BarProject", "1234567890abc")
        assert folder_id == "1234567890abc"

    def test_raises_on_invalid_url(self, tmp_projects):
        # URL s neplatnými znaky (`:`, `/`) která nematchuje ani /folders/ ani bare ID
        with pytest.raises(ValueError, match="Nepodařilo se extrahovat"):
            add_project("Bad", "https://example.com/no-folders-here")

    def test_overwrites_existing_project(self, tmp_projects):
        add_project("Proj", "1234567890aaa")
        add_project("Proj", "1234567890bbb")
        assert list_projects()["Proj"] == "1234567890bbb"

    def test_persists_to_file(self, tmp_projects):
        add_project("Persist", "1234567890abc")
        # Přečti přímo ze souboru — ověří že se opravdu uložilo
        data = json.loads(tmp_projects.read_text(encoding="utf-8"))
        assert data["Persist"] == "1234567890abc"


class TestRemoveProject:
    def test_removes_existing_project(self, tmp_projects):
        add_project("ToRemove", "1234567890abc")
        assert remove_project("ToRemove") is True
        assert "ToRemove" not in list_projects()

    def test_returns_false_for_nonexistent(self, tmp_projects):
        assert remove_project("DoesNotExist") is False

    def test_does_not_affect_other_projects(self, tmp_projects):
        add_project("Keep", "1234567890abc")
        add_project("Remove", "1234567890xyz")
        remove_project("Remove")
        assert "Keep" in list_projects()


class TestGetFolderId:
    def test_returns_folder_id(self, tmp_projects):
        add_project("Proj", "1234567890abc")
        assert get_folder_id("Proj") == "1234567890abc"

    def test_returns_none_for_missing(self, tmp_projects):
        assert get_folder_id("Missing") is None


class TestListProjects:
    def test_empty_when_no_file(self, tmp_projects):
        # tmp_projects soubor ještě neexistuje
        assert list_projects() == {}

    def test_returns_all_projects(self, tmp_projects):
        add_project("A", "1234567890aaa")
        add_project("B", "1234567890bbb")
        result = list_projects()
        assert result == {"A": "1234567890aaa", "B": "1234567890bbb"}
