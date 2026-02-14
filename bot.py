import os
import re
import time
import discord
from dotenv import load_dotenv
from discord.ext import commands

# Load environment variables
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "0"))
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", "0"))
ACTION_ON_APPROVAL = os.getenv("ACTION_ON_APPROVAL", "kick").lower().strip()

if ACTION_ON_APPROVAL not in {"kick", "ban"}:
    ACTION_ON_APPROVAL = "kick"

# ----------------------------
# CUSTOM MODERATION SETTINGS
# ----------------------------

BANNED_WORDS = {"badword1", "badword2"}  # Auto-delete immediately
SEVERE_TRIGGERS = {"free nitro", "send password", "scam"}  # Ask owner approval
LINK_REGEX = re.compile(r"(https?://\S+)", re.IGNORECASE)

# ----------------------------
# BOT INTENTS
# ----------------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

pending_actions = {}


# ----------------------------
# OWNER CHECK
# ----------------------------

def only_owner(ctx):
    return ctx.guild is not None and ctx.author.id == ctx.guild.owner_id


async def get_modlog_channel(guild):
    if MOD_LOG_CHANNEL_ID == 0:
        return None
    return guild.get_channel(MOD_LOG_CHANNEL_ID)


# ----------------------------
# APPROVAL BUTTON SYSTEM
# ----------------------------

class ApprovalView(discord.ui.View):
    def __init__(self, key: str, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.key = key

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild and interaction.user.id == interaction.guild.owner_id:
            return True
        await interaction.response.send_message(
            "❌ Only the server owner can approve/decline.",
            ephemeral=True
        )
        return False

    @discord.ui.button(label="Approve ✅", style=discord.ButtonStyle.danger)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        payload = pending_actions.get(self.key)

        if not payload:
            return await interaction.response.send_message(
                "Request expired or already handled.",
                ephemeral=True
            )

        guild = interaction.guild
        action = payload["action"]
        target_id = payload["target_id"]
        reason = payload["reason"]

        try:
            if action == "kick":
                member = guild.get_member(target_id)
                if member:
                    await member.kick(reason=reason)

            elif action == "ban":
                await guild.ban(discord.Object(id=target_id), reason=reason)

            pending_actions.pop(self.key, None)

            await interaction.response.edit_message(
                content=f"✅ Approved. {action.upper()} executed for <@{target_id}>.\nReason: {reason}",
                view=None
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to kick/ban.",
                ephemeral=True
            )

    @discord.ui.button(label="Decline ❌", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        pending_actions.pop(self.key, None)

        await interaction.response.edit_message(
            content="❌ Declined. No action taken.",
            view=None
        )


async def request_owner_approval(message, reason):
    guild = message.guild
    modlog = await get_modlog_channel(guild)

    if not modlog:
        return

    key = f"{guild.id}:{message.author.id}:{int(time.time())}"

    pending_actions[key] = {
        "action": ACTION_ON_APPROVAL,
        "target_id": message.author.id,
        "reason": reason
    }

    preview = message.content[:300]

    text = (
        f"⚠️ **Approval Required**\n"
        f"User: {message.author.mention}\n"
        f"Action Requested: **{ACTION_ON_APPROVAL.upper()}**\n"
        f"Reason: {reason}\n"
        f"Channel: {message.channel.mention}\n"
        f"Message: ```{preview}```"
    )

    await modlog.send(text, view=ApprovalView(key))


# ----------------------------
# BOT EVENTS
# ----------------------------

@bot.event
async def on_ready():
    print(f"✅ FarazBot is ONLINE as {bot.user}")


@bot.event
async def on_member_join(member):
    print("JOIN EVENT:", member.name)

    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)

    if channel:
        await channel.send(
            f"🌌 Welcome {member.mention} to **The Stellar Boardroom**!\n"
            f"Please check 📢 announcements and enjoy your stay 🚀"
        )


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()

    # Auto-delete banned words
    for word in BANNED_WORDS:
        if word in content:
            await message.delete()
            await message.channel.send(
                f"⚠️ {message.author.mention}, your message contained a banned word.",
                delete_after=5
            )
            return

    # Severe triggers or links → approval request
    severe_hit = any(trigger in content for trigger in SEVERE_TRIGGERS)
    has_link = bool(LINK_REGEX.search(content))

    if severe_hit or has_link:
        await message.delete()
        reason = "Severe trigger detected" if severe_hit else "Link detected"
        await request_owner_approval(message, reason)

    await bot.process_commands(message)


# ----------------------------
# COMMANDS
# ----------------------------

@bot.command()
async def ping(ctx):
    await ctx.send("✅ FarazBot is working perfectly!")


@bot.command()
async def testwelcome(ctx):
    if not only_owner(ctx):
        return await ctx.send("❌ Only server owner can test this.")

    channel = ctx.guild.get_channel(WELCOME_CHANNEL_ID)

    if channel:
        await channel.send(f"🌌 Test welcome message for {ctx.author.mention}!")


# ----------------------------
# START BOT
# ----------------------------

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing in Railway Variables!")

bot.run(TOKEN)
