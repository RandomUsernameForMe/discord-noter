import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path

import discord

from config import load_settings
from transcriber import load_model, transcribe_recording, format_transcript
from notes_generator import generate_notes
from drive_uploader import upload_file
from projects import list_projects, add_project, remove_project, get_project

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

settings = load_settings()

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)


@bot.event
async def on_ready():
    await bot.sync_commands()
    log.info(f"Bot přihlášen jako {bot.user}, příkazy synchronizovány.")


log.info(f"Načítám Whisper model '{settings.whisper_model}'...")
whisper_model = load_model(settings.whisper_model)
log.info("Whisper připraven.")

# guild_id -> voice_client; None = slot rezervován / probíhá zastavování
active_sessions: dict[int, discord.VoiceClient | None] = {}

# guild_id -> ID toho, kdo zavolal /note-stop (None = automatické zastavení)
pending_stop: dict[int, int | None] = {}

SKIP = "__skip__"


@bot.check
async def _is_allowed(ctx: discord.ApplicationContext) -> bool:
    """Prázdný whitelist = bez omezení."""
    return not settings.allowed_user_ids or ctx.author.id in settings.allowed_user_ids


@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: discord.DiscordException):
    if isinstance(error, discord.CheckFailure):
        await ctx.respond("Nemáš oprávnění používat tento příkaz.", ephemeral=True)
        return
    log.error(f"Příkaz /{ctx.command} selhal: {error}", exc_info=error)
    try:
        await ctx.respond("Příkaz selhal, detail je v logu bota.", ephemeral=True)
    except discord.DiscordException:
        pass


# ── Project management ────────────────────────────────────────────────────────

project_group = bot.create_group("project", "Správa projektů pro ukládání zápisů")


async def _project_names(ctx: discord.AutocompleteContext) -> list[str]:
    return [n for n in list_projects() if ctx.value.lower() in n.lower()][:25]


@project_group.command(name="add", description="Přidej projekt s Google Drive složkou")
async def project_add(
    ctx: discord.ApplicationContext,
    name: discord.Option(str, "Název projektu"),
    drive_url: discord.Option(str, "URL Google Drive složky (nebo jen ID)"),
    style_folder: discord.Option(str, "Lokální složka s dřívějšími zápisy (vzor stylu)", required=False, default=None),
):
    try:
        folder_id = add_project(name, drive_url, style_folder)
        await ctx.respond(f"Projekt **{name}** přidán (folder ID: `{folder_id}`).", ephemeral=True)
    except ValueError as e:
        await ctx.respond(str(e), ephemeral=True)


@project_group.command(name="list", description="Vypíše uložené projekty")
async def project_list(ctx: discord.ApplicationContext):
    projects = list_projects()
    if not projects:
        await ctx.respond("Žádné projekty. Přidej je pomocí `/project add`.", ephemeral=True)
        return
    lines = [
        f"• **{name}** — `{p['folder_id']}`" + (f" · vzory: `{p['style_folder']}`" if p["style_folder"] else "")
        for name, p in projects.items()
    ]
    await ctx.respond("\n".join(lines), ephemeral=True)


@project_group.command(name="remove", description="Odstraní projekt")
async def project_remove(
    ctx: discord.ApplicationContext,
    name: discord.Option(str, "Název projektu", autocomplete=_project_names),
):
    if remove_project(name):
        await ctx.respond(f"Projekt **{name}** odstraněn.", ephemeral=True)
    else:
        await ctx.respond(f"Projekt **{name}** nenalezen.", ephemeral=True)


# ── Recording ─────────────────────────────────────────────────────────────────

@bot.slash_command(name="note-start", description="Bot se připojí do tvého voice kanálu a začne nahrávat.")
async def join(ctx: discord.ApplicationContext):
    if not ctx.author.voice:
        await ctx.respond("Nejsi ve voice kanálu.", ephemeral=True)
        return
    if ctx.guild_id in active_sessions:
        await ctx.respond("Nahrávání už probíhá.", ephemeral=True)
        return

    # Rezervuj slot před await, aby souběžné /note-start neprošlo kontrolou výše
    active_sessions[ctx.guild_id] = None
    try:
        channel = ctx.author.voice.channel
        voice_client = await channel.connect()
    except Exception:
        active_sessions.pop(ctx.guild_id, None)
        raise

    # sync_start: stopy všech uživatelů začínají ve stejný čas → sedí časové značky
    voice_client.start_recording(discord.sinks.WaveSink(), _recording_finished_callback, ctx.channel, sync_start=True)

    active_sessions[ctx.guild_id] = voice_client
    await ctx.respond(f"Připojeno do **{channel.name}** — nahrávám. Zastav pomocí `/note-stop`.")


def _stop_recording(guild_id: int, invoker_id: int | None) -> bool:
    voice_client = active_sessions.get(guild_id)
    if voice_client is None:
        return False
    active_sessions[guild_id] = None
    pending_stop[guild_id] = invoker_id
    voice_client.stop_recording()
    return True


@bot.slash_command(name="note-stop", description="Zastaví nahrávání a vygeneruje zápis.")
async def stop(ctx: discord.ApplicationContext):
    if not _stop_recording(ctx.guild_id, ctx.author.id):
        await ctx.respond("Žádné aktivní nahrávání.", ephemeral=True)
        return
    await ctx.respond("Zastavuji nahrávání, čekej...")


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    voice_client = active_sessions.get(member.guild.id)
    if voice_client is None or before.channel != voice_client.channel:
        return
    if any(not m.bot for m in voice_client.channel.members):
        return
    log.info(f"Kanál {voice_client.channel} je prázdný, zastavuji nahrávání.")
    _stop_recording(member.guild.id, None)


# ── Post-recording flow ───────────────────────────────────────────────────────

class ProjectSelectView(discord.ui.View):
    def __init__(self, projects: list[str], invoker_id: int | None):
        super().__init__(timeout=120)
        self.invoker_id = invoker_id
        self.chosen: str | None = None  # název projektu, SKIP, nebo None po timeoutu

        # ponytail: Discord select má max 25 možností, projekty nad 24 se nezobrazí
        options = [discord.SelectOption(label=name, value=name) for name in projects[:24]]
        options.append(discord.SelectOption(label="— Neuložit na Drive —", value=SKIP))

        select = discord.ui.Select(placeholder="Vyber projekt…", options=options)
        select.callback = self._on_select
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.invoker_id is None or interaction.user.id == self.invoker_id:
            return True
        await interaction.response.send_message("Projekt vybírá ten, kdo zastavil nahrávání.", ephemeral=True)
        return False

    async def _on_select(self, interaction: discord.Interaction):
        self.chosen = interaction.data["values"][0]
        await interaction.response.defer()
        self.stop()


async def _ask_project(channel: discord.TextChannel, invoker_id: int | None) -> str | None:
    projects = list(list_projects())
    if not projects:
        return None
    view = ProjectSelectView(projects, invoker_id)
    msg = await channel.send("Ke kterému projektu zápis patří? (přepis mezitím běží)", view=view)
    await view.wait()
    await msg.delete()
    if view.chosen is None:
        await channel.send("Projekt nevybrán včas — zápis uložím jen lokálně.")
        return None
    return None if view.chosen == SKIP else view.chosen


def _output_base(project_name: str | None) -> Path:
    output_dir = Path(settings.notes_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    name = datetime.now().strftime("%Y-%m-%d_%H-%M")
    if project_name:
        name += "_" + re.sub(r"[^\w-]+", "_", project_name).strip("_")
    return output_dir / name


async def _recording_finished_callback(sink: discord.sinks.WaveSink, channel: discord.TextChannel, *args):
    guild = channel.guild
    invoker_id = pending_stop.pop(guild.id, None)
    active_sessions.pop(guild.id, None)

    try:
        await sink.vc.disconnect()
        if invoker_id is None:
            await channel.send("Všichni opustili voice kanál — nahrávání ukončeno.")
        await channel.send("Přepisuji audio (může to chvíli trvat)...")

        loop = asyncio.get_running_loop()
        transcription = loop.run_in_executor(None, transcribe_recording, sink, guild, whisper_model)
        project_name = await _ask_project(channel, invoker_id)
        segments = await transcription

        if not segments:
            await channel.send("Nepodařilo se přepsat žádné audio. Zápis nebyl vytvořen.")
            return

        project = get_project(project_name) if project_name else None
        transcript = format_transcript(segments)

        await channel.send("Generuji zápis pomocí Claude...")
        meeting_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        notes_md = await loop.run_in_executor(
            None,
            generate_notes,
            transcript,
            meeting_date,
            project["style_folder"] if project else None,
            settings.anthropic_api_key,
            settings.claude_model,
        )

        base = _output_base(project_name)
        notes_path = base.with_name(base.name + ".md")
        transcript_path = base.with_name(base.name + "_prepis.md")
        notes_path.write_text(notes_md, encoding="utf-8")
        transcript_path.write_text(transcript, encoding="utf-8")

        drive_url = None
        if project:
            try:
                drive_url = await loop.run_in_executor(
                    None, upload_file, str(notes_path), project["folder_id"], settings.google_service_account_json
                )
            except Exception as e:
                log.error(f"Drive upload selhal: {e}")
                await channel.send("Upload na Drive selhal. Zápis je uložen lokálně.")

        header = f"**Zápis uložen:** `{notes_path}`"
        if drive_url:
            header += f"\n**Google Drive:** {drive_url}"
        await channel.send(header, files=[discord.File(notes_path), discord.File(transcript_path)])

    except Exception as e:
        log.error(f"Chyba v _recording_finished_callback: {e}", exc_info=True)
        try:
            await channel.send(f"Při zpracování záznamu nastala chyba ({type(e).__name__}). Detail je v logu.")
        except Exception:
            pass


bot.run(settings.discord_token)
