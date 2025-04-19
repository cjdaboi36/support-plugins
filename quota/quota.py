import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime

# Path to the JSON data file
DATA_FILE = "data.json"

class QuotaManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self.load_data()
        self.quota_system_enabled = self.data.get("settings", {}).get("enabled", True)
        self.reset_quotas.start()

    def load_data(self):
        """Load data from the JSON file."""
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as file:
                return json.load(file)
        else:
            # If no data file exists, initialize with default values
            return {
                "settings": {
                    "normal_quota": 10,  # Default quota for normal staff
                    "new_staff_quota": 5,  # Default quota for new staff
                    "reset_time": "00:00",  # Default reset time
                    "enabled": True,  # Whether the quota system is enabled
                    "strikes_until_demotion": 3  # Default number of strikes until demotion
                },
                "quotas": {},  # Holds user quota data
                "strikes": {},  # Holds user strike data
                "exemptions": []  # List of exempted users
            }

    def save_data(self):
        """Save data to the JSON file."""
        with open(DATA_FILE, 'w') as file:
            json.dump(self.data, file, indent=4)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def add_existing_staff(self, ctx, user: discord.User):
        """Assign a quota to an existing staff member."""
        if str(user.id) not in self.data["quotas"]:
            self.data["quotas"][str(user.id)] = self.data["settings"]["normal_quota"]
            await ctx.send(f"{user.mention} has been added to the quota system with a normal quota.")
        else:
            await ctx.send(f"{user.mention} is already in the quota system.")

        self.save_data()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def new_staff(self, ctx, user: discord.User):
        """Assign a smaller quota to a new staff member."""
        self.data["quotas"][str(user.id)] = self.data["settings"]["new_staff_quota"]
        await ctx.send(f"{user.mention} has been assigned the new staff quota.")
        self.save_data()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_reset_time(self, ctx, time: str):
        """Set the quota reset time."""
        self.data["settings"]["reset_time"] = time
        await ctx.send(f"Quota reset time has been set to {time}.")
        self.save_data()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_enable(self, ctx):
        """Enable the quota system for the server."""
        self.data["settings"]["enabled"] = True
        self.quota_system_enabled = True
        await ctx.send("Quota system has been enabled.")
        self.save_data()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_disable(self, ctx):
        """Disable the quota system for the server."""
        self.data["settings"]["enabled"] = False
        self.quota_system_enabled = False
        await ctx.send("Quota system has been disabled.")
        self.save_data()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_exemption(self, ctx, user: discord.User):
        """Exempt a user from the quota system for this week."""
        if str(user.id) not in self.data["exemptions"]:
            self.data["exemptions"].append(str(user.id))
            await ctx.send(f"{user.mention} has been exempted from this week's quota.")
        else:
            await ctx.send(f"{user.mention} is already exempted from this week's quota.")
        self.save_data()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def strikes_until_demotion(self, ctx, num_strikes: int):
        """Set the number of strikes until a user is demoted."""
        self.data["settings"]["strikes_until_demotion"] = num_strikes
        await ctx.send(f"Users will be demoted after {num_strikes} strikes.")
        self.save_data()

    @commands.Cog.listener()
    async def on_message(self, message):
        """Track user messages and update their quota."""
        if message.author.bot:
            return

        if not self.quota_system_enabled:
            return  # No action if the quota system is disabled

        # Ensure user is in the quotas system
        if str(message.author.id) not in self.data["quotas"]:
            return  # No action if user is not in the quotas system

        # Check if user is exempted
        if str(message.author.id) in self.data["exemptions"]:
            return  # No action if user is exempted

        # Increment the user's message count
        self.data["quotas"][str(message.author.id)] -= 1

        # Check if the user has completed their quota
        if self.data["quotas"][str(message.author.id)] <= 0:
            self.data["quotas"][str(message.author.id)] = 0  # Prevent negative quota
            await message.author.send("You have completed your weekly message quota!")

        self.save_data()

    @commands.command()
    async def quota_status(self, ctx):
        """Check the status of your current quota."""
        if str(ctx.author.id) in self.data["quotas"]:
            remaining = self.data["quotas"][str(ctx.author.id)]
            await ctx.send(f"You have {remaining} messages remaining to complete your weekly quota.")
        else:
            await ctx.send("You are not currently assigned a quota.")

    @tasks.loop(minutes=1)
    async def reset_quotas(self):
        """Reset quotas at the specified reset time."""
        reset_time = self.data["settings"]["reset_time"]
        current_time = datetime.now().strftime("%H:%M")
        
        if current_time == reset_time:
            for user_id in self.data["quotas"]:
                if user_id not in self.data["exemptions"]:
                    self.data["quotas"][user_id] = self.data["settings"]["normal_quota"]
            self.save_data()

# Add the cog to the bot
def setup(bot):
    bot.add_cog(QuotaManager(bot))
