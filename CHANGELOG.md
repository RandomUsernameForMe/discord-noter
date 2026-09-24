## [2026-09-24] - faster-whisper turbo, zjednodušený flow po nahrávání

- Whisper → `faster-whisper` (`large-v3-turbo`, int8, VAD); odpadá torch/openai-whisper a pydub
- Oprava: WAV konstanty `WaveSink.AUDIO_*` v py-cord 2.7 neexistují → přepis padal; nyní `discord.opus.Decoder`
- Časování stop přes `sync_start=True`; smazán `recorder.py` (vlastní offsety)
- Složka se vzory je volitelná vlastnost projektu (`/project add ... style_folder`); zrušen dotaz v chatu → není potřeba Message Content Intent
- Projekt se vybírá hned po zastavení (paralelně s přepisem), jen autor `/note-stop`, timeout 2 min s hláškou
- Zápis + přepis ukládány lokálně a posílány jako přílohy; název souboru obsahuje projekt
- Auto-stop nahrávání, když voice kanál opustí všichni lidé
- Autocomplete v `/project remove`, globální kontrola oprávnění (`@bot.check`)
- `CLAUDE_MODEL` v env, `max_tokens` 8192 + upozornění na zkrácený zápis
- Srozumitelná chyba při chybějící povinné env proměnné
- Tray: bot startuje automaticky, položka „Otevřít log", kill fallback, log handle už neleakuje
- `bot.log` v `.gitignore`, `ALLOWED_USER_IDS` a `CLAUDE_MODEL` v `.env.example`

## [2026-03-25] - Security & reliability fixes

- Přidána autorizace přes `ALLOWED_USER_IDS` env var (všechny slash příkazy)
- `msg_check` v callbacku nyní přijímá odpověď jen od toho, kdo zavolal `/stop`
- Validace cesty ke složce vzorových zápisů (musí být existující adresář)
- Race condition na `/join` — slot se rezervuje před `await channel.connect()`
- `asyncio.get_event_loop()` → `get_running_loop()` (Python 3.12+ kompatibilita)
- Top-level `try/except` v `_recording_finished_callback` — chyby se reportují do kanálu
- Discord zpráva s preview nepřekročí 2000 znaků
- Drive upload error — detail do logu, generická zpráva do Discordu
- Drive upload odstraněn automatický `anyone/reader` permission

## [2026-03-25] - Přidány testy

48 testů pro `projects.py`, `transcriber.py`, `notes_generator.py`. Pytest konfigurace v `pytest.ini`.
