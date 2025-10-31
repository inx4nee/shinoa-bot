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
INACTIVITY_SECONDS = 30 * 24 * 60 * 60

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
    top = sorted(user_message_count.items(), key=lambda x: x[1], reverse=True)[:10]
    lines = [f"**{i+1}** {bot.get_user(uid).display_name if bot.get_user(uid) else '??'} — {count:,} msgs" 
             for i, (uid, count) in enumerate(top)]
    embed = discord.Embed(title="Top 10 Most Teased", description="\n".join(lines), color=0xff69b4)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# === /reset ===
@bot.tree.command(name="reset", description="ADMIN: Reset user memory")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def reset(interaction: discord.Interaction, member: discord.Member = None):
    uid = (member or interaction.user).id
    if uid in chat_sessions:
        del chat_sessions[uid]
        user_last_seen.pop(uid, None)
        user_message_count.pop(uid, None)
        await interaction.response.send_message(f"Memory erased for **{(member or interaction.user).display_name}**!", ephemeral=True)
    else:
        await interaction.response.send_message("No memory to erase!", ephemeral=True)

# === GENERATE RESPONSE (CORRECT MODEL NAME) ===
async def generate_response(uid: int, msg: str) -> str:
    loop = asyncio.get_event_loop()
    if uid not in chat_sessions:
        try:
            # CORRECT: gemini-pro (NO "models/" prefix)
            model = genai.GenerativeModel('gemini-pro')
            chat = model.start_chat(history=[
                {"role": "user", "parts": [SHINOA_SYSTEM_PROMPT]},
                {"role": "model", "parts": ["Got it! I'm Shinoa~ Ready to tease!"]}
            ])
            chat_sessions[uid] = chat
            print(f"[MODEL] Created session for user {uid} using gemini-pro")
        except Exception as e:
            print(f"[FATAL] Model init failed: {e}")
            return "My AI core is down! Blame @inxainee~"
    else:
        chat = chat_sessions[uid]

    try:
        resp = await loop.run_in_executor(None, lambda: chat.send_message(msg))
        if len(chat.history) > MAX_HISTORY * 2:
            chat.history = chat.history[-MAX_HISTORY * 2:]
        return resp.text.strip()
    except Exception as e:
        print(f"[GEMINI ERROR] {e}")
        return "Tch, my brilliance was too much for the system, I guess."

# === RUN ===
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN missing!")
    else:
        bot.run(token)
