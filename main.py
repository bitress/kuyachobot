import os
import asyncio
import time
import logging
from datetime import datetime
import traceback

import gspread
from twitchio.ext import commands
from thefuzz import process, fuzz
from dotenv import load_dotenv

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TreasureBot")

# --- ENVIRONMENT SETUP ---
load_dotenv()

REQUIRED_VARS = ['TWITCH_TOKEN', 'TWITCH_CHANNEL', 'WORKBOOK_NAME']
MISSING = [var for var in REQUIRED_VARS if not os.getenv(var)]
if MISSING:
    logger.critical(f"Missing required environment variables: {', '.join(MISSING)}")
    raise ValueError(f"Missing required environment variables: {', '.join(MISSING)}")

TOKEN = os.getenv('TWITCH_TOKEN')
CHANNEL = os.getenv('TWITCH_CHANNEL')
WORKBOOK_NAME = os.getenv('WORKBOOK_NAME')
JSON_KEYFILE = 'service_account.json'
CACHE_REFRESH_HOURS = 1


class TreasureBot(commands.Bot):
    def __init__(self):
        super().__init__(token=TOKEN, prefix='!', initial_channels=[CHANNEL])
        self.cache = {}
        self.last_update = None
        self.gc = None
        self.cooldowns = {}
        self._refresh_task = None

        try:
            self.gc = gspread.service_account(filename=JSON_KEYFILE)
            logger.info("Google Sheets client initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")

    async def event_ready(self):
        logger.info(f"Logged in as: {self.nick}")
        logger.info(f"Monitoring channel: {CHANNEL}")
        await self.update_cache()

        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self.auto_refresh_cache())
            logger.info("Background cache refresh task started.")

    async def event_message(self, message):
        """Handles incoming messages and logs them."""
        if message.echo:
            return

        # --- CHAT LOGGING ---
        try:
            author = message.author.name if message.author else "Unknown"
            logger.info(f"[CHAT] {author}: {message.content}")
        except Exception as e:
            logger.error(f"Failed to log message: {e}")
        # --------------------

        await self.handle_commands(message)

    async def update_cache(self):
        logger.info("Updating cache from Google Sheets...")
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._sync_update)
            logger.info(f"Cache updated: {len(self.cache)} items loaded.")
        except Exception as e:
            logger.error(f"Sheet Update Failed: {e}", exc_info=True)

    def _sync_update(self):
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

            logger.info(f"Found {len(worksheets)} sheets. Scanning...")

            for sheet in worksheets:
                if sheet.title == "ACNH_Items":
                    logger.debug("Skipping 'ACNH_Items'.")
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
                                # Store locations as comma-separated string initially
                                if key in temp_cache:
                                    current_locations = temp_cache[key].split(", ")
                                    if location_name not in current_locations:
                                        temp_cache[key] += f", {location_name}"
                                else:
                                    temp_cache[key] = location_name

                    sheets_scanned += 1
                    logger.info(f"Indexed: {location_name}")
                    time.sleep(1.0)  # Rate limit

                except Exception as e:
                    logger.error(f"Error reading '{sheet.title}': {e}")

            self.cache = temp_cache
            self.last_update = datetime.now()
            logger.info(f"Scan complete. {sheets_scanned} sheets processed.")

        except Exception as e:
            logger.error(f"Workbook fetch failed: {e}")

    async def auto_refresh_cache(self):
        try:
            while True:
                await asyncio.sleep(3600 * CACHE_REFRESH_HOURS)
                await self.update_cache()
        except asyncio.CancelledError:
            logger.info("Refresh task cancelled.")
        except Exception as e:
            logger.error(f"Auto-refresh failed: {e}")

    def check_cooldown(self, user_id: str, cooldown_sec: int = 3) -> bool:
        now = time.time()
        if user_id in self.cooldowns:
            if now - self.cooldowns[user_id] < cooldown_sec:
                return True
        self.cooldowns[user_id] = now
        return False

    @commands.command(aliases=['locate', 'where'])
    async def find(self, ctx: commands.Context, *, item: str = ""):
        if not item:
            await ctx.send(f"Usage: !find <item name>")
            return

        if self.check_cooldown(str(ctx.author.id)):
            return

        if not self.cache:
            await ctx.send("Database loading...")
            return

        search_term = item.lower().strip()

        # 1. Exact Match
        if search_term in self.cache:
            # Format: Found LUCKY CAT on: MATAHOM | PARALUMAN
            raw_locations = self.cache[search_term]
            formatted_locations = raw_locations.upper().replace(", ", " | ")

            await ctx.send(f"Found {search_term.upper()} on: {formatted_locations}")
            logger.info(f"Found {search_term.upper()} on: {formatted_locations}")
            return

        # 2. Fuzzy Match & Suggestions
        matches = process.extract(
            search_term,
            self.cache.keys(),
            limit=5,
            scorer=fuzz.token_set_ratio
        )

        # Filter matches (Threshold > 75)
        valid_suggestions = [m[0] for m in matches if m[1] > 75]

        if valid_suggestions:
            suggestions_str = ", ".join(valid_suggestions)
            await ctx.send(
                f"Couldn't find \"{search_term}\" - Did you mean: {suggestions_str}?"
            )
            logger.info(
                f"Couldn't find \"{search_term}\" - Did you mean: {suggestions_str}?"
            )
        else:
            await ctx.send(
                f"I couldn't find \"{search_term}\" or anything similar. Check your spelling!")
            logger.info(f"I couldn't find \"{search_term}\" or anything similar. Check your spelling!")

    @commands.command()
    async def help(self, ctx: commands.Context):
        await ctx.send("Commands: !find <item> | !status | Mods: !refresh")

    @commands.command()
    async def status(self, ctx: commands.Context):
        if self.last_update:
            time_str = self.last_update.strftime("%H:%M:%S")
            await ctx.send(f"Items: {len(self.cache)} | Last Update: {time_str}")
        else:
            await ctx.send("Database loading...")


if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        logger.info("Bot starting...")
        bot = TreasureBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"Critical Error: {e}", exc_info=True)