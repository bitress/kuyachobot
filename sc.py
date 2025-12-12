import os
import logging
import asyncio
from datetime import datetime
import traceback

import discord
from discord.ext import commands, tasks
import gspread
from thefuzz import process, fuzz
from dotenv import load_dotenv

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("discord_bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TreasureBot")

# --- ENVIRONMENT SETUP ---
load_dotenv()

# Note: Changed TWITCH_TOKEN to DISCORD_TOKEN
REQUIRED_VARS = ['DISCORD_TOKEN', 'WORKBOOK_NAME']
MISSING = [var for var in REQUIRED_VARS if not os.getenv(var)]
if MISSING:
    logger.critical(f"Missing required environment variables: {', '.join(MISSING)}")
    raise ValueError(f"Missing required environment variables: {', '.join(MISSING)}")

TOKEN = os.getenv('DISCORD_TOKEN')
WORKBOOK_NAME = os.getenv('WORKBOOK_NAME')
JSON_KEYFILE = 'service_account.json'
CACHE_REFRESH_HOURS = 1


class TreasureBot(commands.Bot):
    def __init__(self):
        # Discord requires Intents to read message content
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None  # Disabling default help to use our own
        )

        self.cache = {}
        self.last_update = None
        self.gc = None

    async def setup_hook(self):
        """Called once when the bot logs in."""
        # Initialize GSheets
        try:
            self.gc = gspread.service_account(filename=JSON_KEYFILE)
            logger.info("Google Sheets client initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")

        # Start background task
        self.background_cache_refresh.start()

    async def on_ready(self):
        logger.info(f"Logged in as: {self.user} (ID: {self.user.id})")
        logger.info("Bot is ready and listening.")
        # Set a status activity (e.g., "Playing !help")
        await self.change_presence(activity=discord.Game(name="!help | !find"))

    async def on_message(self, message):
        # Don't let the bot reply to itself
        if message.author == self.user:
            return

        # Log chat to console/file (Optional privacy note: be careful logging user messages)
        # logger.info(f"[CHAT] [{message.guild}] {message.author}: {message.content}")

        await self.process_commands(message)

    @tasks.loop(hours=CACHE_REFRESH_HOURS)
    async def background_cache_refresh(self):
        """Refreshes the cache periodically using Discord.py tasks."""
        logger.info("Updating cache from Google Sheets...")
        try:
            # Run blocking sync code in a separate thread to not freeze the bot
            await self.loop.run_in_executor(None, self._sync_update)
            logger.info(f"Cache updated: {len(self.cache)} items loaded.")
        except Exception as e:
            logger.error(f"Sheet Update Failed: {e}", exc_info=True)

    @background_cache_refresh.before_loop
    async def before_cache_refresh(self):
        await self.wait_until_ready()

    def _sync_update(self):
        """Synchronous method to read Google Sheets."""
        if not self.gc:
            try:
                self.gc = gspread.service_account(filename=JSON_KEYFILE)
            except Exception as e:
                logger.error(f"Failed to connect to Google Sheets: {e}")
                return

        try:
            wb = self.gc.open(WORKBOOK_NAME)
            worksheets = wb.worksheets()
            temp_cache = {}
            sheets_scanned = 0

            for sheet in worksheets:
                if sheet.title == "ACNH_Items":
                    continue

                try:
                    rows = sheet.get_all_values()
                    if not rows: continue

                    location_name = sheet.title

                    for row in rows[1:]:
                        for cell in row:
                            item_name = cell.strip()
                            if item_name:
                                key = item_name.lower()
                                if key in temp_cache:
                                    current_locations = temp_cache[key].split(", ")
                                    if location_name not in current_locations:
                                        temp_cache[key] += f", {location_name}"
                                else:
                                    temp_cache[key] = location_name

                    sheets_scanned += 1
                    # A small sleep is fine in executor, but generally gspread handles rate limits okay now
                    # time.sleep(0.5)

                except Exception as e:
                    logger.error(f"Error reading '{sheet.title}': {e}")

            self.cache = temp_cache
            self.last_update = datetime.now()
            logger.info(f"Scan complete. {sheets_scanned} sheets processed.")

        except Exception as e:
            logger.error(f"Workbook fetch failed: {e}")


bot = TreasureBot()


# --- COMMANDS ---

@bot.command(aliases=['locate', 'where'])
@commands.cooldown(1, 3, commands.BucketType.user)  # 1 use every 3 seconds per user
async def find(ctx, *, item: str = None):
    if not item:
        await ctx.send("Usage: `!find <item name>`")
        return

    if not bot.cache:
        await ctx.send("⚠️ Database is currently loading, please wait...")
        return

    search_term = item.lower().strip()

    # 1. Exact Match
    if search_term in bot.cache:
        raw_locations = bot.cache[search_term]
        # Use an Embed for cleaner Discord display
        embed = discord.Embed(
            title=f"Item Found: {search_term.upper()}",
            description=f"**Locations:**\n{raw_locations.upper().replace(', ', '\n')}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        logger.info(f"Found {search_term} for {ctx.author}")
        return

    # 2. Fuzzy Match & Suggestions
    matches = process.extract(
        search_term,
        bot.cache.keys(),
        limit=5,
        scorer=fuzz.token_set_ratio
    )

    valid_suggestions = [m[0] for m in matches if m[1] > 75]

    if valid_suggestions:
        suggestions_str = "\n".join([f"• {s}" for s in valid_suggestions])
        embed = discord.Embed(
            title="Item Not Found",
            description=f"Did you mean one of these?\n\n{suggestions_str}",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ I couldn't find \"{item}\" or anything similar. Check your spelling!")


@bot.command()
async def status(ctx):
    if bot.last_update:
        time_str = bot.last_update.strftime("%H:%M:%S")
        embed = discord.Embed(title="System Status", color=discord.Color.blue())
        embed.add_field(name="Total Items", value=str(len(bot.cache)), inline=True)
        embed.add_field(name="Last Update", value=time_str, inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Database is initializing...")


@bot.command()
async def help(ctx):
    embed = discord.Embed(title="TreasureBot Help", color=discord.Color.gold())
    embed.add_field(name="!find <item>", value="Search for an item location. Aliases: !locate, !where", inline=False)
    embed.add_field(name="!status", value="Check database status", inline=False)
    await ctx.send(embed=embed)


@bot.command()
@commands.is_owner()
async def refresh(ctx):
    """Manually triggers a cache refresh (Owner only)"""
    await ctx.send("🔄 Forcing manual cache refresh...")
    await bot.loop.run_in_executor(None, bot._sync_update)
    await ctx.send(f"✅ Refresh complete. {len(bot.cache)} items loaded.")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Please wait {error.retry_after:.1f}s before searching again.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing arguments. Check usage.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore invalid commands
    else:
        logger.error(f"Command Error: {error}")


if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        logger.critical("No DISCORD_TOKEN found in .env")