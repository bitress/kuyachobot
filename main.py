import os
import asyncio
import time
import logging
from datetime import datetime
import traceback
import re
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
VILLAGERS_DIR = os.getenv('VILLAGERS_DIR')


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
        """Fetches ITEMS from Google Sheets only. Villagers are fetched live."""
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
                    logger.info(f"Indexed: {location_name}")
                    time.sleep(1.0)

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

    def get_villagers(self):
        data = {}
        villagers_root = VILLAGERS_DIR

        if not villagers_root or not os.path.exists(villagers_root):
            return data

        try:
            for root, dirs, files in os.walk(villagers_root):
                if "Villagers.txt" in files:
                    location_name = os.path.basename(root)
                    file_path = os.path.join(root, "Villagers.txt")

                    with open(file_path, 'rb') as file:
                        raw_content = file.read().decode('utf-8', errors='ignore')

                        names_list = re.split(r'[,\n\r]+', raw_content)

                        for name in names_list:
                            clean_name = name.strip()

                            if clean_name:
                                key = clean_name.lower()

                                if len(key) > 30: continue

                                if key in data:
                                    current_locs = data[key].split(", ")
                                    if location_name not in current_locs:
                                        data[key] += f", {location_name}"
                                else:
                                    data[key] = location_name
            return data

        except Exception as e:
            logger.error(f"Villager scan failed: {e}")
            return data

    @commands.command(aliases=['locate', 'where', 'villager'])
    async def find(self, ctx: commands.Context, *, item: str = ""):
        if not item:
            await ctx.send(f"Usage: !find <item name>")
            return

        if self.check_cooldown(str(ctx.author.id)):
            return

        search_term = item.lower().strip()

        item_hits = self.cache.get(search_term, "")

        villager_map = self.get_villagers()
        villager_hits = villager_map.get(search_term, "")

        found_locations = []
        if item_hits:
            found_locations.append(item_hits)
        if villager_hits:
            found_locations.append(villager_hits)

        if found_locations:
            all_locations = ", ".join(found_locations)
            unique_locations = list(set(all_locations.split(", ")))
            formatted = " | ".join(unique_locations).upper()

            map_word = "this map" if len(unique_locations) == 1 else "these maps"

            await ctx.send(f"Hey @{ctx.author.name}, I found {search_term.upper()} on {map_word}: {formatted}")
            logger.info(f"Hey @{ctx.author.name}, I found {search_term.upper()} on {map_word}: {formatted}")
            return

        all_keys = list(self.cache.keys()) + list(villager_map.keys())

        matches = process.extract(
            search_term,
            all_keys,
            limit=5,
            scorer=fuzz.token_set_ratio
        )

        valid_suggestions = list(set([m[0] for m in matches if m[1] > 75]))

        if valid_suggestions:
            suggestions_str = ", ".join(valid_suggestions)
            await ctx.send(
                f"Hey @{ctx.author.name}, I couldn't find \"{search_term}\" - Did you mean: {suggestions_str}?"
            )
            logger.info(
                f"Hey @{ctx.author.name}, I couldn't find \"{search_term}\" - Did you mean: {suggestions_str}?"
            )
        else:
            await ctx.send(
                f"Hey @{ctx.author.name}, I couldn't find \"{search_term}\" or anything similar. Please check your spelling.")
            logger.info(
                f"Hey @{ctx.author.name}, I couldn't find \"{search_term}\" or anything similar. Please check your spelling.")

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