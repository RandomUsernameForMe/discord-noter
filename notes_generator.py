import os
from pathlib import Path

import anthropic


def _read_existing_notes(folder: str, max_files: int = 5) -> str:
    """Read the most recent .md files from folder as style examples."""
    path = Path(folder)
    if not path.exists() or not path.is_dir():
        return ""

    md_files = sorted(path.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not md_files:
        return ""

    parts = []
    for f in md_files[:max_files]:
        content = f.read_text(encoding="utf-8")
        parts.append(f"--- {f.name} ---\n{content}")

    return "\n\n".join(parts)


def generate_notes(
    transcript: str,
    meeting_date: str,
    existing_notes_folder: str | None,
    api_key: str,
) -> str:
    """Generate meeting notes from transcript using Claude."""

    client = anthropic.Anthropic(api_key=api_key)

    style_section = ""
    if existing_notes_folder:
        existing = _read_existing_notes(existing_notes_folder)
        if existing:
            style_section = f"""
## Příklady existujících zápisů (použij stejný styl a úroveň detailu):

{existing}

---
"""

    prompt = f"""Jsi asistent pro tvorbu zápisů z porad. Vytvoř strukturovaný zápis z porady v češtině.
{style_section}
## Přepis porady ({meeting_date}):

{transcript}

---

Vytvoř zápis z porady ve formátu Markdown. Zápis musí obsahovat:
- Datum a čas
- Seznam účastníků (přesně ti, kteří mluví v přepisu)
- Hlavní témata diskuse
- Klíčová rozhodnutí
- Úkoly (kdo, co, do kdy pokud bylo zmíněno)
- Detailní shrnutí co kdo říkal — přiřaď výroky konkrétním osobám

Buď věcný a přesný. Nedomýšlej věci, které nebyly řečeny."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
