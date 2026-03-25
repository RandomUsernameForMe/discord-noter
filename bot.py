import asyncio
import logging
from datetime import datetime
from pathlib import Path

import discord
import whisper

from config import load_settings
from recorder import MeetingSink
from transcriber import transcribe_recording, format_transcript
from notes_generator import generate_notes
from drive_uploader import upload_file
from projects import list_projects, add_project, remove_project, get_folder_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

settings = load_settings()

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)

log.info(f"Načítám Whisper model '{settings.whisper_model}'...")
whisper_model = whisper.load_model(settings.whisper_model)
log.info("Whisper připraven.")

# guild_id -> (voice_client, sink, text_channel)
active_sessions: dict[int, tuple[discord.VoiceClient, MeetingSink, discord.TextChannel]] = {}


# ── Project management ────────────────────────────────────────────────────────

project_group = bot.create_group("project", "Správa projektů pro ukládání zápisů")


@project_group.command(name="add", description="Přidej projekt s Google Drive složkou")
async def project_add(
    ctx: discord.ApplicationContext,
    name: discord.Option(str, "Název projektu"),
    drive_url: discord.Option(str, "URL Google Drive složky (nebo jen ID)"),
):
    try:
        folder_id = add_project(name, drive_url)
        await ctx.respond(f"Projekt **{name}** přidán (folder ID: `{folder_id}`).", ephemeral=True)
    except ValueError as e:
        await ctx.respond(str(e), ephemeral=True)


@project_group.command(name="list", description="Vypíše uložené projekty")
async def project_list(ctx: discord.ApplicationContext):
    projects = list_projects()
    if not projects:
        await ctx.respond("Žádné projekty. Přidej je pomocí `/project add`.", ephemeral=True)
        return
    lines = [f"• **{name}** — `{fid}`" for name, fid in projects.items()]
    await ctx.respond("\n".join(lines), ephemeral=True)


@project_group.command(name="remove", description="Odstraní projekt")
async def project_remove(
    ctx: discord.ApplicationContext,
    name: discord.Option(str, "Název projektu"),
):
    if remove_project(name):
        await ctx.respond(f"Projekt **{name}** odstraněn.", ephemeral=True)
    else:
        await ctx.respond(f"Projekt **{name}** nenalezen.", ephemeral=True)


# ── Recording ─────────────────────────────────────────────────────────────────

@bot.slash_command(name="join", description="Bot se připojí do tvého voice kanálu a začne nahrávat.")
async def join(ctx: discord.ApplicationContext):
    if not ctx.author.voice:
        await ctx.respond("Nejsi ve voice kanálu.", ephemeral=True)
        return
    if ctx.guild_id in active_sessions:
        await ctx.respond("Nahrávání už probíhá.", ephemeral=True)
        return

    channel = ctx.author.voice.channel
    voice_client = await channel.connect()

    sink = MeetingSink()
    voice_client.start_recording(sink, _recording_finished_callback, ctx.channel)

    active_sessions[ctx.guild_id] = (voice_client, sink, ctx.channel)
    await ctx.respond(f"Připojeno do **{channel.name}** — nahrávám. Zastav pomocí `/stop`.")


@bot.slash_command(name="stop", description="Zastaví nahrávání a vygeneruje zápis.")
async def stop(ctx: discord.ApplicationContext):
    if ctx.guild_id not in active_sessions:
        await ctx.respond("Žádné aktivní nahrávání.", ephemeral=True)
        return

    await ctx.respond("Zastavuji nahrávání, čekej...")
    voice_client, sink, _ = active_sessions[ctx.guild_id]
    voice_client.stop_recording()


# ── Post-recording flow ───────────────────────────────────────────────────────

class ProjectSelectView(discord.ui.View):
    def __init__(self, projects: dict[str, str]):
        super().__init__(timeout=60)
        self.chosen: str | None = None  # folder_id or "" for skip

        options = [discord.SelectOption(label=name, value=fid) for name, fid in projects.items()]
        options.append(discord.SelectOption(label="— Neuložit na Drive —", value="__skip__"))

        select = discord.ui.Select(placeholder="Vyber projekt…", options=options)
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        self.chosen = interaction.data["values"][0]
        await interaction.response.defer()
        self.stop()


async def _recording_finished_callback(sink: MeetingSink, channel: discord.TextChannel, *args):
    guild = channel.guild
    session = active_sessions.pop(guild.id, None)
    if session:
        await session[0].disconnect()

    await channel.send("Přepisuji audio (může to chvíli trvat)...")

    loop = asyncio.get_event_loop()
    segments = await loop.run_in_executor(None, transcribe_recording, sink, guild, whisper_model)
    transcript = format_transcript(segments)

    if not segments:
        await channel.send("Nepodařilo se přepsat žádné audio. Zápis nebyl vytvořen.")
        return

    # Ask for notes style folder
    await channel.send("Zadej cestu ke složce s existujícími zápisy (pro styl) nebo napiš `přeskoč`:")

    def msg_check(m: discord.Message):
        return m.channel.id == channel.id and not m.author.bot

    notes_folder = None
    try:
        reply = await bot.wait_for("message", check=msg_check, timeout=60)
        text = reply.content.strip()
        if text.lower() not in ("přeskoč", "preskoc", "skip", "-"):
            notes_folder = text
    except asyncio.TimeoutError:
        await channel.send("Čas vypršel, pokračuji bez vzorových zápisů.")

    await channel.send("Generuji zápis pomocí Claude...")

    meeting_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    notes_md = await loop.run_in_executor(
        None, generate_notes, transcript, meeting_date, notes_folder, settings.anthropic_api_key
    )

    # Save locally
    output_dir = Path(settings.notes_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M") + ".md"
    local_path = output_dir / filename
    local_path.write_text(notes_md, encoding="utf-8")

    # Ask which project (Drive folder)
    projects = list_projects()
    drive_url = None

    if projects:
        view = ProjectSelectView(projects)
        msg = await channel.send("Kam uložit na Google Drive?", view=view)
        await view.wait()
        await msg.delete()

        folder_id = view.chosen
        if folder_id and folder_id != "__skip__":
            try:
                drive_url = await loop.run_in_executor(
                    None, upload_file, str(local_path), folder_id, settings.google_service_account_json
                )
            except Exception as e:
                log.error(f"Drive upload selhal: {e}")
                await channel.send(f"Upload na Drive selhal: {e}")

    # Preview
    preview_lines = notes_md.splitlines()[:25]
    preview = "\n".join(preview_lines)
    if len(notes_md.splitlines()) > 25:
        preview += "\n..."

    msg_text = f"**Zápis uložen:** `{local_path}`"
    if drive_url:
        msg_text += f"\n**Google Drive:** {drive_url}"
    msg_text += f"\n\n```markdown\n{preview[:1800]}\n```"

    await channel.send(msg_text)


bot.run(settings.discord_token)
