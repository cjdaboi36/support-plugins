import discord
from discord.ext import commands, tasks
import asyncio
import aiohttp
import json
import datetime
import pytz
import os

QUOTA_FILE = "quota_data.json"
TIMEZONE = "Europe/London"
WEB_SERVER_URL = "https://quota.cjscommissions.xyz/status"
STATUS_SEND_INTERVAL = 900  # 15 minutes

def load_data():
    if not os.path.exists(QUOTA_FILE):
        with open(QUOTA_FILE, "w") as f:
            json.dump({
                "config": {
                    "message_requirements": {
                        "normal": 0,
                        "new": 0
                    },
                    "reset_time": "18:00",
                    "reset_day": "Sunday",
                    "enabled": True,
                    "strikes_until_demotion": 3,
                    "reset_channel": None
                },
                "staff": {},
                "log": []
            }, f, indent=4)
    with open(QUOTA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(QUOTA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class QuotaManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_data()
        self.status_task.start()
        self.reset_task.start()

    def cog_unload(self):
        self.status_task.cancel()
        self.reset_task.cancel()

    async def update_webserver(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(WEB_SERVER_URL, json=self.data, timeout=10) as resp:
                    if resp.status == 200:
                        return True
        except:
            return False
        return False

    @tasks.loop(seconds=STATUS_SEND_INTERVAL)
    async def status_task(self):
        await self.update_webserver()

    @tasks.loop(minutes=1)
    async def reset_task(self):
        now = datetime.datetime.now(pytz.timezone(TIMEZONE))
        day = self.data["config"]["reset_day"]
        time_str = self.data["config"]["reset_time"]
        target_time = datetime.datetime.strptime(time_str, "%H:%M").time()

        if now.strftime("%A") == day and now.time().hour == target_time.hour and now.time().minute == target_time.minute:
            await self.perform_reset()

    async def perform_reset(self):
        reset_channel_id = self.data["config"].get("reset_channel")
        if reset_channel_id:
            channel = self.bot.get_channel(reset_channel_id)
            if not channel:
                return
        else:
            return

        summary_lines = ["@everyone\n**Quota Reset**\nGreetings, Moderation Team. The weekly quota has reset. I hope you did your quota this week otherwise you will receive a strike. This strike is not avoidable as it is done automatically by our system.\n"]

        for user_id, info in self.data["staff"].items():
            user = self.bot.get_user(int(user_id))
            if not user:
                continue

            met_quota = info.get("messages", 0) >= self.data["config"]["message_requirements"]["normal"]
            tick_or_cross = "✅" if met_quota else "❌"
            summary_lines.append(f"{user.mention} {tick_or_cross}")

            if not met_quota:
                strikes = info.get("strikes", 0) + 1
                self.data["staff"][user_id]["strikes"] = strikes
                if strikes >= self.data["config"]["strikes_until_demotion"]:
                    await user.send("You have been demoted due to failing to meet your weekly message quota.")

        save_data(self.data)

        if channel:
            await channel.send("\n".join(summary_lines))

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_messages_required(self, ctx, type_of_staff: str, amount: int):
        if type_of_staff not in ["normal", "new"]:
            await ctx.send("Invalid staff type. Choose 'normal' or 'new'.")
            return
        
        self.data["config"]["message_requirements"][type_of_staff] = amount
        save_data(self.data)
        await ctx.send(f"Quota for {type_of_staff} staff has been set to {amount} messages per week.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def add_staff(self, ctx, user: discord.User):
        user_id = str(user.id)
        if user_id in self.data["staff"]:
            await ctx.send(f"{user.mention} is already a staff member.")
            return

        self.data["staff"][user_id] = {"messages": 0, "strikes": 0}
        save_data(self.data)
        await ctx.send(f"{user.mention} has been added to the staff system.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def new_staff(self, ctx, user: discord.User):
        """Add a user to the system as new staff without new message requirements."""
        user_id = str(user.id)
        if user_id in self.data["staff"]:
            await ctx.send(f"{user.mention} is already a staff member.")
            return

        self.data["staff"][user_id] = {"messages": 0, "strikes": 0}
        self.data["config"]["message_requirements"]["new"] = 0  # No message requirements for new staff
        save_data(self.data)
        await ctx.send(f"{user.mention} has been added as new staff without message requirements.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_reset(self, ctx):
        for user_id in self.data["staff"]:
            self.data["staff"][user_id]["messages"] = 0
        save_data(self.data)
        await ctx.send("Quotas have been reset for all staff members.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_enable(self, ctx):
        self.data["config"]["enabled"] = True
        save_data(self.data)
        await ctx.send("Quota tracking has been enabled.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_disable(self, ctx):
        self.data["config"]["enabled"] = False
        save_data(self.data)
        await ctx.send("Quota tracking has been disabled.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_reset_time(self, ctx, time: str):
        self.data["config"]["reset_time"] = time
        save_data(self.data)
        await ctx.send(f"Quota reset time has been set to {time}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_reset_day(self, ctx, day: str):
        self.data["config"]["reset_day"] = day
        save_data(self.data)
        await ctx.send(f"Quota reset day has been set to {day}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def strikes_until_demotion(self, ctx, strikes: int):
        self.data["config"]["strikes_until_demotion"] = strikes
        save_data(self.data)
        await ctx.send(f"The number of strikes before demotion has been set to {strikes}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_complete(self, ctx, user: discord.User):
        user_id = str(user.id)
        if user_id not in self.data["staff"]:
            await ctx.send(f"{user.mention} is not in the staff system.")
            return

        self.data["staff"][user_id]["messages"] = self.data["config"]["message_requirements"]["normal"]
        save_data(self.data)
        await ctx.send(f"{user.mention}'s quota has been marked as complete.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_exemption(self, ctx, user: discord.User):
        user_id = str(user.id)
        if user_id not in self.data["staff"]:
            await ctx.send(f"{user.mention} is not in the staff system.")
            return

        self.data["staff"][user_id]["strikes"] = 0
        save_data(self.data)
        await ctx.send(f"{user.mention} has been exempted from this week's quota.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_summary(self, ctx):
        summary = ["**Quota Summary**"]
        for user_id, info in self.data["staff"].items():
            user = self.bot.get_user(int(user_id))
            if user:
                summary.append(f"{user.name}: {info['messages']} messages, {info['strikes']} strikes")
        await ctx.send("\n".join(summary))

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_reset_channel(self, ctx, channel: discord.TextChannel):
        self.data["config"]["reset_channel"] = channel.id
        save_data(self.data)
        await ctx.send(f"Reset channel has been set to {channel.mention}.")

def setup(bot):
    bot.add_cog(QuotaManager(bot))
