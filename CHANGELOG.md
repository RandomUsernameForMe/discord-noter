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
