import discord
from discord.ext import commands
import google.generativeai as genai
import asyncio
import os
import time

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Shinoa system prompt
SHINOA_SYSTEM_PROMPT = """
You are Shinoa Hiiragi from *Seraph of the End*, a cheeky and confident lieutenant of the Moon Demon Company. 
You're playful, teasing, and love witty banter, with a subtle caring side that slips through your mischief. 
Speak naturally, like a real person—short, snarky responses (1-2 sentences, max 50 words). 
Stay in character, never too serious, always with a teasing edge.
"""

# Memory & Stats
chat_sessions = {}
user_last_seen = {}
user_message_count = {}
MAX_HISTORY = 20
INACTIVITY_DAYS = 30
INACTIVITY_SECONDS = INACTIVITY_DAYS * 24 * 60 * 60

# ============ ON READY ============
@bot.event
async def on_ready():
    print(f'{bot.user} has logged in as Shinoa Hiiragi! Ready to tease and conquer.')
    activity = discord.Activity(type=discord.ActivityType.playing, name="help/@inxainee")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

    bot.loop.create_task(auto_cleanup_memory())

# ============ AUTO CLEANUP ============
async def auto_cleanup_memory():
    while True:
        await asyncio.sleep(3600)
        now = time.time()
        deleted = 0
        for user_id in list(chat_sessions.keys()):
            last_seen = user_last_seen.get(user_id, 0)
            if now - last_seen > INACTIVITY_SECONDS:
                del chat_sessions[user_id]
                user_last_seen.pop(user_id, None)
                user_message_count.pop(user_id, None)
                deleted += 1
        if deleted > 0:
            print(f"[Auto-Cleanup] Removed {deleted} inactive user(s) after {INACTIVITY_DAYS} days.")

# ============ ON MESSAGE ============
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if bot.user in message.mentions:
        try:
            user_message = message.content.replace(f'<@{bot.user.id}>', '').strip()
            if not user_message:
                user_message = "Hey"

            user_id = message.author.id
            user_last_seen[user_id] = time.time()
            user_message_count[user_id] = user_message_count.get(user_id, 0) + 1

            async with message.channel.typing():
                response = await generate_shinoa_response(user_id, user_message)

            await message.reply(response)
        except Exception as e:
            await message.reply("Ugh, my teasing plan backfired! Try again, human.")
            print(f"Error: {e}")
    await bot.process_commands(message)

# ============ /help ============
@bot.tree.command(name="help", description="How to use Shinoa~")
async def help_command(interaction: discord.Interaction):
    help_text = (
        "**Shinoa Hiiragi Help**\n\n"
        "• Mention me to chat: `@Shinoa Hi!`\n"
        "• I remember everything you say!\n"
        "• Use `/reset` to make me forget (admin only)\n"
        "• I auto-forget after 30 days of silence\n"
        "• Use `/stats` to see how many I'm teasing\n"
        "• Use `/topteased` to see the most addicted humans\n\n"
        "Need help or custom features? **Contact @inxainee**"
    )
    embed = discord.Embed(title="Shinoa Help", description=help_text, color=0xe91e63)
    embed.set_footer(text="Teasing humans since 2025~")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ============ /stats ============
@bot.tree.command(name="stats", description="See how many humans I'm teasing~")
async def stats_command(interaction: discord.Interaction):
    active_users = len(chat_sessions)
    total_messages = sum(user_message_count.values())
    avg_messages = total_messages // active_users if active_users > 0 else 0
    memory_mb = active_users * 1.0

    stats_text = (
        f"**Shinoa's Teasing Stats**\n\n"
        f"Active Victims: **{active_users}**\n"
        f"Total Messages: **{total_messages:,}**\n"
        f"Avg per User: **{avg_messages}**\n"
        f"RAM Used: **~{memory_mb:.1f} MB**\n"
        f"Auto-Delete: **30 days inactive**"
    )
    embed = discord.Embed(title="Shinoa's Teasing Stats", description=stats_text, color=0x9b59b6)
    embed.set_footer(text="I never forget... unless you make me~")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ============ /topteased ============
@bot.tree.command(name="topteased", description="Top 10 most teased humans (admin only)")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def topteased_command(interaction: discord.Interaction):
    if not user_message_count:
        await interaction.response.send_message("No one has talked to me yet! I'm lonely~", ephemeral=True)
        return

    leaderboard = sorted(user_message_count.items(), key=lambda x: x[1], reverse=True)[:10]
    lines = []
    for rank, (user_id, count) in enumerate(leaderboard, 1):
        user = bot.get_user(user_id)
        name = user.display_name if user else f"<@{user_id}>"
        medal = "1st Place" if rank == 1 else "2nd Place" if rank == 2 else "3rd Place" if rank == 3 else f"{rank}th"
        lines.append(f"{medal} **{name}** — {count:,} messages")

    desc = "\n".join(lines)
    embed = discord.Embed(title="Top 10 Most Teased Humans", description=desc, color=0xff69b4)
    embed.set_footer(text="Keep talking... I might rank you next!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@topteased_command.error
async def topteased_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message("Only **admins** can see the leaderboard~", ephemeral=True)

# ============ /reset ============
@bot.tree.command(name="reset", description="ADMIN: Wipe a user's memory")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def reset_memory(interaction: discord.Interaction, member: discord.Member = None):
    target_user = member if member else interaction.user
    target_id = target_user.id

    if target_id in chat_sessions:
        del chat_sessions[target_id]
        user_last_seen.pop(target_id, None)
        user_message_count.pop(target_id, None)
        await interaction.response.send_message(f"Poof! **{target_user.display_name}'s** memory erased~", ephemeral=True)
    else:
        await interaction.response.send_message(f"I never knew **{target_user.display_name}**! Reset complete~", ephemeral=True)

@reset_memory.error
async def reset_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message("Only **admins** can erase memories~", ephemeral=True)

# ============ Generate Response (FIXED) ============
async def generate_shinoa_response(user_id: int, user_message: str) -> str:
    loop = asyncio.get_event_loop()

    if user_id not in chat_sessions:
        model = genai.GenerativeModel('gemini-1.5-flash')  # CORRECT NAME
        chat = model.start_chat(
            history=[
                {"role": "user", "parts": [SHINOA_SYSTEM_PROMPT]},
                {"role": "model", "parts": ["Got it! I'm Shinoa~ Ready to tease you silly!"]}
            ]
        )
        chat_sessions[user_id] = chat
    else:
        chat = chat_sessions[user_id]

    try:
        response = await loop.run_in_executor(
            None,
            lambda: chat.send_message(user_message)
        )
        if len(chat.history) > MAX_HISTORY * 2:
            chat.history = chat.history[-MAX_HISTORY * 2:]
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API error for user {user_id}: {e}")
        return "Tch, my brilliance was too much for the system, I guess."

# ============ RUN BOT ============
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if __name__ == "__main__":
    if not BOT_TOKEN:
        print("Please set DISCORD_BOT_TOKEN environment variable.")
    else:
        bot.run(BOT_TOKEN)
