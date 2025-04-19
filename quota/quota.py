import discord
from discord.ext import commands, tasks
import json
import aiohttp
import os
from datetime import datetime, timedelta
import pytz

WEB_SERVER_URL = "http://yourdomain.com:8001"  # Set this to your web server domain or IP
DATA_FILE = "quota_data.json"
LOG_FILE = "quota_logs.json"
TIMEZONE = "Europe/London"

def save_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

def load_json(path, fallback):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    else:
        save_json(fallback, path)
        return fallback

class QuotaManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_json(DATA_FILE, {
            "quotas": {},
            "exempt": [],
            "messages": {},
            "strikes": {},
            "settings": {
                "normal_quota": 50,
                "new_staff_quota": 20,
                "reset_time": "18:00",
                "strikes_until_demotion": 3,
                "quota_disabled": False,
                "last_reset": None
            }
        })
        self.logs = load_json(LOG_FILE, [])
        self.reset_quota_check.start()

    def log(self, entry):
        timestamp = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        self.logs.append({"time": timestamp, "entry": entry})
        save_json(self.logs, LOG_FILE)

    def save(self):
        save_json(self.data, DATA_FILE)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_messages_required(self, ctx, type: str, amount: int):
        if type.lower() not in ["normal", "new"]:
            return await ctx.send("Type must be `normal` or `new`")
        if type.lower() == "normal":
            self.data["settings"]["normal_quota"] = amount
        else:
            self.data["settings"]["new_staff_quota"] = amount
        self.save()
        await ctx.send(f"{type.capitalize()} quota set to {amount} messages.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def new_staff(self, ctx, member: discord.Member):
        self.data["quotas"][str(member.id)] = {
            "quota": self.data["settings"]["new_staff_quota"],
            "joined": datetime.now().isoformat()
        }
        self.save()
        await ctx.send(f"{member.mention} has been set as new staff.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def strikes_until_demotion(self, ctx, count: int):
        self.data["settings"]["strikes_until_demotion"] = count
        self.save()
        await ctx.send(f"Strike limit set to {count} before demotion.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_exemption(self, ctx, member: discord.Member):
        self.data["exempt"].append(str(member.id))
        self.save()
        await ctx.send(f"{member.mention} has been exempted from this week's quota.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_reset_time(self, ctx, time_str: str):
        self.data["settings"]["reset_time"] = time_str
        self.save()
        await ctx.send(f"Quota reset time set to {time_str}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_disable(self, ctx):
        self.data["settings"]["quota_disabled"] = True
        self.save()
        await ctx.send("Quota has been disabled for this week.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_enable(self, ctx):
        now = datetime.now(pytz.timezone(TIMEZONE))
        reset_time_str = self.data["settings"]["reset_time"]
        reset_dt = datetime.strptime(reset_time_str, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )
        if reset_dt < now:
            reset_dt += timedelta(days=7)
        diff = reset_dt - now

        # Lower quota by 15% if within 23 hours
        if diff.total_seconds() < 82800:
            for uid in self.data["quotas"]:
                self.data["quotas"][uid]["quota"] = int(self.data["quotas"][uid]["quota"] * 0.85)
        self.data["settings"]["quota_disabled"] = False
        self.save()
        await ctx.send("Quota has been re-enabled.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_complete(self, ctx, member: discord.Member):
        self.data["messages"][str(member.id)] = self.data["quotas"].get(str(member.id), {}).get("quota", 0)
        self.save()
        await ctx.send(f"{member.mention}'s messages marked as complete.")

    @tasks.loop(minutes=1)
    async def reset_quota_check(self):
        now = datetime.now(pytz.timezone(TIMEZONE))
        reset_time = datetime.strptime(self.data["settings"]["reset_time"], "%H:%M")
        if now.strftime("%H:%M") == reset_time.strftime("%H:%M"):
            last_reset = self.data["settings"].get("last_reset")
            if last_reset == now.strftime("%Y-%m-%d"):
                return  # Already reset today

            await self.reset_quotas()

    async def reset_quotas(self):
        guild = self.bot.guilds[0]  # Replace with specific guild ID if needed
        results = []
        for uid in self.data["quotas"]:
            user = guild.get_member(int(uid))
            if not user:
                continue
            completed = self.data["messages"].get(uid, 0) >= self.data["quotas"][uid]["quota"]
            exempt = uid in self.data["exempt"]
            if not completed and not exempt and not self.data["settings"]["quota_disabled"]:
                self.data["strikes"][uid] = self.data["strikes"].get(uid, 0) + 1
                await user.send(embed=discord.Embed(
                    title="🚨 You received a strike",
                    description="You did not meet your message quota this week.",
                    color=0xFF0000
                ).set_footer(text=f"Powered by Cj’s Commissions | {datetime.now().strftime('%H:%M')}"))
                results.append(f"{user.mention} ❌")
            else:
                results.append(f"{user.mention} ✅")

        channel = discord.utils.get(guild.text_channels, name="quota-logs")  # Or use ID
        if channel:
            await channel.send("@everyone\n**Quota Reset**\nGreetings, Moderation Team. The weekly quota has reset. I hope you did your quota this week otherwise you will receive a strike. This strike is not avoidable as it is done automatically by our system.\n\n" + "\n".join(results))

        # Reset
        self.data["messages"] = {}
        self.data["exempt"] = []
        self.data["settings"]["last_reset"] = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
        self.save()

        # Try pushing to web
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(WEB_SERVER_URL + "/update", json=self.data)
        except:
            self.log("Web server not available during reset. Data stored locally.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        uid = str(message.author.id)
        if uid in self.data["quotas"]:
            self.data["messages"][uid] = self.data["messages"].get(uid, 0) + 1
            self.save()

async def setup(bot):
    await bot.add_cog(QuotaManager(bot))
