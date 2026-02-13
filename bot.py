import os
import re
import time
import discord
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "0"))
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", "0"))
ACTION_ON_APPROVAL = os.getenv("ACTION_ON_APPROVAL", "kick").lower().strip()

if ACTION_ON_APPROVAL not in {"kick", "ban"}:
    ACTION_ON_APPROVAL = "kick"

# --- Customize these ---
BANNED_WORDS = {"badword1", "badword2"}  # deleted immediately
SEVERE_TRIGGERS = {"free nitro", "send password", "scam"}  # approval request
LINK_REGEX = re.compile(r"(https?://\S+)", re.IGNORECASE)
# ----------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# key -> payload
pending_actions = {}


def only_owner(ctx: commands.Context) -> bool:
    return ctx.guild is not None and ctx.author.id == ctx.guild.owner_id


async def get_modlog_channel(guild: discord.Guild):
    if MOD_LOG_CHANNEL_ID == 0:
        return None
    return guild.get_channel(MOD_LOG_CHANNEL_ID)


class ApprovalView(discord.ui.View):
    def __init__(self, key: str, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.key = key

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # only server owner can click
        if interaction.guild and interaction.user and interaction.user.id == interaction.guild.owner_id:
            return True
        await interaction.response.send_message("Only the server owner can approve/decline.", ephemeral=True)
        return False

    @discord.ui.button(label="Approve ✅", style=discord.ButtonStyle.danger)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        payload = pending_actions.get(self.key)
        if not payload:
            return await interaction.response.send_message("This request expired or was already handled.", ephemeral=True)

        guild = interaction.guild
        action = payload["action"]
        target_id = payload["target_id"]
        reason = payload["reason"]

        try:
            if action == "kick":
                member = guild.get_member(target_id)
                if not member:
                    raise RuntimeError("Member not found (maybe left already).")
                await member.kick(reason=reason)
            else:
                await guild.ban(discord.Object(id=target_id), reason=reason, delete_message_days=0)

            pending_actions.pop(self.key, None)
            await interaction.response.edit_message(
                content=f"✅ Approved. **{action.upper()}** executed for <@{target_id}>.\nReason: {reason}",
                view=None
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don’t have permission (check my role is above members + kick/ban perms).",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"Failed: {e}", ephemeral=True)

    @discord.ui.button(label="Decline ❌", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        pending_actions.pop(self.key, None)
        await interaction.response.edit_message(content="❌ Declined. No action taken.", view=None)


async def request_owner_approval(message: discord.Message, reason: str):
    """Send approval request to mod-log."""
    guild = message.guild
    modlog = await get_modlog_channel(guild)
    if not modlog:
        return

    action = ACTION_ON_APPROVAL
    target = message.author
    key = f"{guild.id}:{target.id}:{action}:{int(time.time())}"

    pending_actions[key] = {
        "action": action,
        "target_id": target.id,
        "reason": reason,
    }

    preview = (message.content[:350] + "…") if len(message.content) > 350 else message.content

    text = (
        f"⚠️ **Approval Required**\n"
        f"Target: {target.mention} (`{target.id}`)\n"
        f"Requested action: **{action.upper()}**\n"
        f"Reason: {reason}\n"
        f"Channel: {message.channel.mention}\n"
        f"Message: ```{preview}```"
    )

    await modlog.send(content=text, view=ApprovalView(key))


@bot.event
async def on_ready():
    print(f"✅ FarazBot is online as {bot.user} | action_on_approval={ACTION_ON_APPROVAL}")


@bot.event
async def on_member_join(member: discord.Member):
    ch = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if ch:
        await ch.send(
            f"Welcome {member.mention} to **The Stellar Boardroom** 🌌\n"
            f"Please check **#announcements** and introduce yourself in **#general** 🚀"
        )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    content_lower = (message.content or "").lower()

    # 1) delete banned words immediately
    for w in BANNED_WORDS:
        if w in content_lower:
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} your message was removed (restricted word).",
                    delete_after=6
                )
            except discord.Forbidden:
                pass
            return

    # 2) severe triggers / link -> delete message + ask for owner approval
    severe_hit = any(t in content_lower for t in SEVERE_TRIGGERS)
    has_link = bool(LINK_REGEX.search(content_lower))

    if severe_hit or has_link:
        try:
            await message.delete()  # protect the server quickly
        except discord.Forbidden:
            pass

        reason = "Severe trigger detected" if severe_hit else "Link detected (requires approval)"
        await request_owner_approval(message, reason)

    await bot.process_commands(message)


# --- Owner commands to manage lists ---
@bot.command()
async def addword(ctx: commands.Context, *, word: str):
    if not only_owner(ctx):
        return await ctx.reply("Only the server owner can use this.")
    BANNED_WORDS.add(word.lower().strip())
    await ctx.reply(f"✅ Added banned word: `{word}`")

@bot.command()
async def delword(ctx: commands.Context, *, word: str):
    if not only_owner(ctx):
        return await ctx.reply("Only the server owner can use this.")
    BANNED_WORDS.discard(word.lower().strip())
    await ctx.reply(f"✅ Removed banned word: `{word}`")

@bot.command()
async def addtrigger(ctx: commands.Context, *, phrase: str):
    if not only_owner(ctx):
        return await ctx.reply("Only the server owner can use this.")
    SEVERE_TRIGGERS.add(phrase.lower().strip())
    await ctx.reply(f"✅ Added severe trigger: `{phrase}`")

@bot.command()
async def deltrigger(ctx: commands.Context, *, phrase: str):
    if not only_owner(ctx):
        return await ctx.reply("Only the server owner can use this.")
    SEVERE_TRIGGERS.discard(phrase.lower().strip())
    await ctx.reply(f"✅ Removed severe trigger: `{phrase}`")


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing. Put it in .env as DISCORD_TOKEN=...")

bot.run(TOKEN)
