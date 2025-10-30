import discord
from discord.ext import commands
import google.generativeai as genai
import asyncio
import os
from flask import Flask
from threading import Thread

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Roleplay prompt for Shinoa Hiiragi
SHINOA_PROMPT = """
You are Shinoa Hiiragi from *Seraph of the End*, a cheeky and confident lieutenant of the Moon Demon Company. You're playful, teasing, and love witty banter, with a subtle caring side that slips through your mischief. Speak naturally, like a real person—short, snarky responses (1-2 sentences, max 50 words) that feel like casual conversation. Stay in character, never too serious, always with a teasing edge.

User message: {user_message}

Your response:
"""

@bot.event
async def on_ready():
    print(f'{bot.user} has logged in as Shinoa Hiiragi! Ready to tease and conquer.')
    # Set custom presence to "Playing help/@inxainee"
    activity = discord.Activity(type=discord.ActivityType.playing, name="help/@inxainee")
    await bot.change_presence(status=discord.Status.online, activity=activity)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if bot.user in message.mentions:  # Safe mention check
        try:
            user_message = message.content.replace(f'<@{bot.user.id}>', '').strip() if bot.user else ''
            if not user_message:
                user_message = "Hey"

            # Start typing indicator while generating response
            async with message.channel.typing():
                response = await generate_shinoa_response(user_message)

            await message.reply(response)
        except Exception as e:
            await message.reply("Ugh, my teasing plan backfired! Try again, human.")
            print(f"Error: {e}")
    await bot.process_commands(message)

async def generate_shinoa_response(user_message):
    loop = asyncio.get_event_loop()
    full_prompt = SHINOA_PROMPT.format(user_message=user_message)
    model = genai.GenerativeModel(model_name='models/gemini-2.5-flash')
    try:
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(full_prompt)
        )
        return response.text.strip() if hasattr(response, 'text') else str(response)
    except Exception as e:
        print(f"Gemini API error: {e}")
        return "Tch, my brilliance was too much for the system, I guess."

# Flask web server for UptimeRobot pings
app = Flask('')

@app.route('/')
def main():
    return "Your Bot Is Alive! (Shinoa says hi~)"

def run_flask():
    app.run(host='0.0.0.0', port=8080)  # Replit uses port 8080

def keep_alive():
    server_thread = Thread(target=run_flask)
    server_thread.start()

# Start the keep-alive server before running the bot
keep_alive()

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if __name__ == "__main__":
    if not BOT_TOKEN:
        print("Please set DISCORD_BOT_TOKEN environment variable or hardcode it.")
    else:
        bot.run(BOT_TOKEN)