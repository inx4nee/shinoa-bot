import discord
from discord.ext import commands
import google.generativeai as genai
import asyncio
import os
import time

# === CONFIG ===
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

SHINOA_SYSTEM_PROMPT = """
You are Shinoa Hiiragi from *Seraph of the End*, a cheeky and confident lieutenant. 
You're playful, teasing, and love witty banter. Speak naturally, short, snarky (1-2 sentences, max 50 words). 
Stay in character, never too serious, always with a teasing edge.
"""

chat_sessions = {}
user_last_seen = {}
user_message_count = {}
MAX_HISTORY = 20
INACTIVITY_SECONDS = 30 * 24 * 60 * 60  # 30 days

# === ON READY ===
@bot.event
async def on_ready():
    print(f"[SUCCESS] {bot.user} is online as Shinoa!")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="help/@inxainee"))
    try:
        synced = await bot.tree.sync()
        print(f"[COMMANDS] Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"[ERROR] Sync failed: {e}")
    bot.loop.create_task(auto_cleanup())

# === AUTO CLEANUP ===
async def auto_cleanup():
    while True:
        await asyncio.sleep(3600)
        now = time.time()
        for uid in list(chat_sessions.keys()):
            if now - user_last_seen.get(uid, 0) > INACTIVITY_SECONDS:
                chat_sessions.pop(uid, None)
                user_last_seen.pop(uid, None)
                user_message_count.pop(uid, None)

# === ON MESSAGE ===
@bot.event
async def on_message(message):
    if message.author == bot.user or bot.user not in message.mentions:
        return

    user_msg = message.content.replace(f'<@{bot.user.id}>', '').strip() or "Hey"
    uid = message.author.id
    user_last_seen[uid] = time.time()
    user_message_count[uid] = user_message_count.get(uid, 0) + 1

    async with message.channel.typing():
        reply = await generate_response(uid, user_msg)
    await message.reply(reply)
    await bot.process_commands(message)

# === /help ===
@bot.tree.command(name="help", description="Shinoa Help")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="Shinoa Help", color=0xe91e63)
    embed.description = (
        "**Shinoa Hiiragi**\n\n"
        "• Mention me to chat\n"
        "• I remember everything\n"
        "• `/reset` (admin only)\n"
        "• Auto-forget after 30 days\n"
        "• `/stats` • `/topteased`\n\n"
        "Need help? **@inxainee**"
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# === /stats ===
@bot.tree.command(name="stats", description="Bot stats")
async def stats(interaction: discord.Interaction):
    users = len(chat_sessions)
    msgs = sum(user_message_count.values())
    avg = msgs // users if users else 0
    embed = discord.Embed(title="Shinoa Stats", color=0x9b59b6)
    embed.add_field(name="Active Users", value=users, inline=True)
    embed.add_field(name="Total Messages", value=f"{msgs:,}", inline=True)
    embed.add_field(name="Avg per User", value=avg, inline=True)
    embed.set_footer(text="Auto-delete: 30 days")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# === /topteased ===
@bot.tree.command(name="topteased", description="Top 10 most active (admin only)")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def topteased(interaction: discord.Interaction):
    if not user_message_count:
        return await interaction.response.send_message("No data yet!", ephemeral=True)
    top = sorted(user_message_count.items(), key=lambda x
