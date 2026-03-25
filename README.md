# Discord Voice Noter

Bot nahrává hlasové hovory na Discordu, přepíše je pomocí Whisper a vygeneruje strukturovaný zápis z porady pomocí Claude. Zápis volitelně nahraje na Google Drive.

---

## Požadavky

- Python 3.11+
- GPU doporučeno pro Whisper (CPU funguje, ale je pomalé)
- Discord bot token
- Anthropic API klíč
- Google Cloud service account (volitelné — jen pro Drive upload)

---

## Instalace

```bash
pip install -r requirements.txt
```

Vytvoř `.env` soubor (viz sekce Konfigurace).

---

## Konfigurace

Soubor `.env` v kořeni projektu:

```env
# Povinné
DISCORD_TOKEN=tvůj_discord_bot_token
ANTHROPIC_API_KEY=tvůj_anthropic_klíč

# Kdo může používat bota (čárkou oddělená Discord User ID)
# Prázdné = kdokoliv na serveru
ALLOWED_USER_IDS=123456789012345678

# Volitelné
WHISPER_MODEL=large-v3          # výchozí: large-v3
NOTES_OUTPUT_DIR=./notes        # kam se ukládají zápisy lokálně
GOOGLE_SERVICE_ACCOUNT_JSON=./service_account.json   # pro Drive upload
```

### Jak zjistit Discord User ID

V Discordu: Nastavení → Pokročilé → zapnout **Vývojářský režim** → pravý klik na sebe → **Kopírovat ID uživatele**.

### Pozvání bota na server

1. Jdi na [discord.com/developers](https://discord.com/developers/applications) → vyber svou aplikaci
2. Vlevo **OAuth2 → URL Generator**
3. Zaškrtni Scopes: `bot` + `applications.commands`
4. Zaškrtni Bot Permissions: `Send Messages`, `Connect`, `Speak`, `Use Voice Activity`
5. Zkopíruj vygenerovanou URL → otevři v prohlížeči → vyber server → Autorizovat

### Potřebné intenty

V záložce **Bot** na developer portálu zapnout: **Message Content Intent**

---

## Spuštění

```bash
python bot.py
```

Nebo přes tray ikonu (Windows): spusť `tray.py` — bot běží na pozadí s ikonou v systémové liště.

> **Poznámka:** Při prvním spuštění se načítá Whisper model (může trvat 1–2 minuty a vyžaduje ~5 GB RAM/VRAM pro `large-v3`). Bot se připojí k Discordu až po načtení.

---

## Příkazy

### Nahrávání

| Příkaz | Popis |
|--------|-------|
| `/note-start` | Bot se připojí do tvého aktuálního voice kanálu a začne nahrávat |
| `/note-stop` | Zastaví nahrávání a spustí zpracování |

### Správa projektů (Drive složky)

| Příkaz | Popis |
|--------|-------|
| `/project add <název> <url>` | Přidá projekt — propojí název s Google Drive složkou |
| `/project list` | Vypíše uložené projekty |
| `/project remove <název>` | Odstraní projekt |

`<url>` může být:
- Plná URL: `https://drive.google.com/drive/folders/ABC123...`
- Samotné folder ID: `ABC123defGHI456`

---

## Typický průběh

1. Přijdi do voice kanálu s ostatními
2. Napiš `/join` v textovém kanálu — bot se připojí a začne nahrávat
3. Po skončení porady napiš `/stop`
4. Bot se zeptá na **složku se vzory zápisů** (pro styl) — napiš cestu nebo `přeskoč`
5. Probíhá přepis (Whisper) — může trvat minutu i déle podle délky záznamu
6. Probíhá generování zápisu (Claude)
7. Pokud máš nastavené projekty, vyber kam uložit na Drive (nebo přeskoč)
8. Bot pošle do kanálu preview zápisu a cestu k lokálně uloženému souboru

### Vzorové zápisy (styl)

Když bot poprosí o cestu ke složce, můžeš zadat adresář s existujícími `.md` zápisy. Bot přečte posledních 5 souborů a použije je jako ukázku stylu pro Claude — výsledný zápis pak bude strukturou odpovídat tvým předchozím zápisům.

Zadej cestu jako:
- `C:\Users\TGJ\notes` (Windows absolutní cesta)
- `./notes` (relativní k adresáři bota)
- `přeskoč` / `skip` / `-` — přeskočí, zápis bude ve výchozím formátu

---

## Uložené soubory

Zápisy se ukládají do `NOTES_OUTPUT_DIR` (výchozí: `./notes/`) ve formátu:

```
notes/
  2026-03-25_14-30.md
  2026-03-25_16-00.md
  ...
```

Projekty (Drive folder ID) jsou uloženy v `projects.json` v adresáři bota.

---

## Google Drive (volitelné)

Pro upload zápisů na Drive potřebuješ **service account**:

1. V [Google Cloud Console](https://console.cloud.google.com) vytvoř projekt
2. Zapni **Google Drive API**
3. Vytvoř Service Account → stáhni JSON klíč → ulož jako `service_account.json`
4. Ve své Drive složce klikni **Sdílet** a přidej e-mail service accountu (formát `name@project.iam.gserviceaccount.com`) s oprávněním **Editor**

Nahraný soubor není automaticky veřejný — sdílení spravuješ ručně v Drive.

---

## Whisper modely

| Model | Velikost | Rychlost | Přesnost |
|-------|----------|----------|----------|
| `tiny` | ~75 MB | nejrychlejší | nízká |
| `base` | ~150 MB | rychlý | dobrá |
| `small` | ~500 MB | střední | dobrá |
| `medium` | ~1.5 GB | pomalý | velmi dobrá |
| `large-v3` | ~3 GB | nejpomalejší | nejlepší (výchozí) |

Nastav v `.env`: `WHISPER_MODEL=medium`
