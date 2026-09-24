# Discord Voice Noter

Bot nahrává hlasové hovory na Discordu, přepíše je pomocí Whisper a vygeneruje strukturovaný zápis z porady pomocí Claude. Zápis volitelně nahraje na Google Drive.

---

## Požadavky

- Python 3.11+
- Whisper běží lokálně přes `faster-whisper` (CPU stačí, GPU s CUDA se použije automaticky)
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
WHISPER_MODEL=large-v3-turbo    # výchozí: large-v3-turbo
CLAUDE_MODEL=claude-sonnet-4-6  # model pro generování zápisu
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

Žádné privilegované intenty nejsou potřeba.

---

## Spuštění

```bash
python bot.py
```

Nebo přes tray ikonu (Windows): spusť `start_bot.vbs` nebo `tray.py` — bot se spustí automaticky a běží na pozadí s ikonou v systémové liště. Výstup jde do `bot.log` (v menu **Otevřít log**).

> **Poznámka:** Při prvním spuštění se stahuje Whisper model (~1,6 GB pro `large-v3-turbo`). Bot se připojí k Discordu až po načtení modelu.

---

## Příkazy

### Nahrávání

| Příkaz | Popis |
|--------|-------|
| `/note-start` | Bot se připojí do tvého aktuálního voice kanálu a začne nahrávat |
| `/note-stop` | Zastaví nahrávání a spustí zpracování |

Nahrávání se zastaví i samo, když z voice kanálu odejdou všichni lidé.

### Správa projektů (Drive složky)

| Příkaz | Popis |
|--------|-------|
| `/project add <název> <url> [style_folder]` | Přidá projekt — propojí název s Google Drive složkou, volitelně se složkou vzorových zápisů |
| `/project list` | Vypíše uložené projekty |
| `/project remove <název>` | Odstraní projekt |

`<url>` může být:
- Plná URL: `https://drive.google.com/drive/folders/ABC123...`
- Samotné folder ID: `ABC123defGHI456`

---

## Typický průběh

1. Přijdi do voice kanálu s ostatními
2. Napiš `/note-start` v textovém kanálu — bot se připojí a začne nahrávat
3. Po skončení porady napiš `/note-stop` (nebo prostě všichni odejděte)
4. Pokud máš projekty, vyber ze seznamu, ke kterému zápis patří (nebo „Neuložit na Drive“) — přepis mezitím běží na pozadí. Vybírat může jen ten, kdo nahrávání zastavil; po 2 minutách se pokračuje bez projektu.
5. Probíhá přepis (Whisper) a generování zápisu (Claude)
6. Bot pošle do kanálu zápis a přepis jako přílohy `.md` (a odkaz na Drive, pokud byl vybrán projekt)

### Vzorové zápisy (styl)

Projekt může mít nastavenou `style_folder` — lokální adresář (na stroji, kde běží bot) s existujícími `.md` zápisy. Bot přečte posledních 5 souborů a použije je jako ukázku stylu pro Claude.

```
/project add name:Tým drive_url:https://drive.google.com/drive/folders/ABC... style_folder:D:/zapisy/tym
```

---

## Uložené soubory

Zápisy se ukládají do `NOTES_OUTPUT_DIR` (výchozí: `./notes/`) ve formátu:

```
notes/
  2026-03-25_14-30_Tym.md          # zápis
  2026-03-25_14-30_Tym_prepis.md   # přepis s časy a mluvčími
  ...
```

Projekty (Drive folder ID a složka se vzory) jsou uloženy v `projects.json` v adresáři bota.

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
| `large-v3-turbo` | ~1.6 GB | střední | velmi dobrá (výchozí) |
| `large-v3` | ~3 GB | nejpomalejší | nejlepší |

Nastav v `.env`: `WHISPER_MODEL=medium`
