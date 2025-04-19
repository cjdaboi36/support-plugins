import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import json
import os
from datetime import datetime, timedelta
import pytz

DATA_FILE = "quota_data.json"
LOG_FILE = "quota_logs.json"
WEB_SERVER_URL = "https://quota.cjscommmissions.xyz"  # Update this if needed

TIMEZONE = pytz.timezone("Europe/London")


def now_uk():
    return datetime.now(TIMEZONE)


class QuotaManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self.load_json(DATA_FILE)
        self.logs = self.load_json(LOG_FILE)
        self.web_online = True
        self.last_heartbeat_sent = None
        self.heartbeat_loop.start()
        self.weekly_reset_loop.start()

    def load_json(self, file):
        if not os.path.exists(file):
            return {}
        with open(file, "r") as f:
            return json.load(f)

    def save_json(self, file, data):
        with open(file, "w") as f:
            json.dump(data, f, indent=4)

    def log_event(self, event):
        timestamp = now_uk().isoformat()
        self.logs[timestamp] = event
        self.save_json(LOG_FILE, self.logs)

    @commands.Cog.listener()
    async def on_ready(self):
        print("Quota Manager loaded.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        user_id = str(message.author.id)

        if self.data.get("quota_disabled", False):
            return
        if user_id in self.data.get("exempt", []):
            return

        self.data.setdefault("message_counts", {})
        self.data["message_counts"][user_id] = self.data["message_counts"].get(user_id, 0) + 1
        self.save_json(DATA_FILE, self.data)

    @tasks.loop(minutes=15)
    async def heartbeat_loop(self):
        async with aiohttp.ClientSession() as session:
            try:
                payload = {
                    "timestamp": now_uk().isoformat(),
                    "bot_status": "online"
                }
                async with session.post(f"{WEB_SERVER_URL}/status", json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        if not self.web_online:
                            self.log_event("Bot back online and synced.")
                        self.web_online = True
                        await self.sync_with_web(session)
            except Exception:
                if self.web_online:
                    self.log_event("Web server offline. Saving to JSON.")
                self.web_online = False

    async def sync_with_web(self, session):
        payload = {
            "data": self.data,
            "logs": self.logs
        }
        await session.post(f"{WEB_SERVER_URL}/data", json=payload)

    @tasks.loop(hours=1)
    async def weekly_reset_loop(self):
        now = now_uk()
        reset_time_str = self.data.get("reset_time", "23:59")
        reset_hour, reset_minute = map(int, reset_time_str.split(":"))
        scheduled = now.replace(hour=reset_hour, minute=reset_minute, second=0, microsecond=0)

        if now > scheduled:
            scheduled += timedelta(days=7)

        wait_seconds = (scheduled - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        await self.perform_weekly_reset()

    async def perform_weekly_reset(self):
        message_counts = self.data.get("message_counts", {})
        quotas = self.data.get("quotas", {"normal": 100, "new": 50})
        strikes = self.data.setdefault("strikes", {})
        exempt = self.data.get("exempt", [])
        new_staff = self.data.get("new_staff", [])
        channel_id = self.data.get("log_channel")

        results = []
        for user_id, count in message_counts.items():
            if user_id in exempt:
                results.append((user_id, True, "Exempt"))
                continue

            required = quotas["new"] if user_id in new_staff else quotas["normal"]
            if count >= required:
                results.append((user_id, True, None))
            else:
                results.append((user_id, False, None))
                strikes[user_id] = strikes.get(user_id, 0) + 1

        self.data["message_counts"] = {}
        self.data["exempt"] = []
        self.save_json(DATA_FILE, self.data)
        self.save_json(LOG_FILE, self.logs)

        if self.web_online:
            async with aiohttp.ClientSession() as session:
                await self.sync_with_web(session)

        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send("@everyone\n**Quota Reset**\nGreetings, Moderation Team. The weekly quota has reset...")
                for user_id, passed, reason in results:
                    user = await self.bot.fetch_user(int(user_id))
                    if reason == "Exempt":
                        msg = f"{user.mention} - ✅ (Exempt)"
                    elif passed:
                        msg = f"{user.mention} - ✅"
                    else:
                        msg = f"{user.mention} - ❌"
                        await user.send(embed=self.create_strike_embed())
                    await channel.send(msg)

    def create_strike_embed(self):
        embed = discord.Embed(
            title="Quota Strike",
            description="You did not meet your quota this week. A strike has been added.",
            color=0xFF0000
        )
        embed.set_footer(text=f"Powered by Cj’s Commissions {now_uk().strftime('%H:%M')}")
        return embed

    # Add commands (e.g. quota_exemption, set quota, etc) here...

async def setup(bot):
    await bot.add_cog(QuotaManager(bot))
