import discord
from discord.ext import commands
import json
import os

# Path to the JSON data file
DATA_FILE = "data.json"

class QuotaManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self.load_data()

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
                    "reset_time": "00:00"  # Default reset time
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
        # Check if the user already has a quota entry
        if str(user.id) not in self.data["quotas"]:
            # Assign normal quota for existing staff
            self.data["quotas"][str(user.id)] = self.data["settings"]["normal_quota"]
            await ctx.send(f"{user.mention} has been added to the quota system with a normal quota.")
        else:
            await ctx.send(f"{user.mention} is already in the quota system.")

        # Save the updated data to JSON
        self.save_data()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def new_staff(self, ctx, user: discord.User):
        """Assign a smaller quota to a new staff member."""
        # Assign the new staff quota
        self.data["quotas"][str(user.id)] = self.data["settings"]["new_staff_quota"]
        await ctx.send(f"{user.mention} has been assigned the new staff quota.")

        # Save the updated data to JSON
        self.save_data()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_reset_time(self, ctx, time: str):
        """Set the quota reset time."""
        # Update reset time in settings
        self.data["settings"]["reset_time"] = time
        await ctx.send(f"Quota reset time has been set to {time}.")

        # Save the updated data to JSON
        self.save_data()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_enable(self, ctx):
        """Enable the quota system for the server."""
        await ctx.send("Quota system has been enabled.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_disable(self, ctx):
        """Disable the quota system for the server."""
        await ctx.send("Quota system has been disabled.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_exemption(self, ctx, user: discord.User):
        """Exempt a user from the quota system for this week."""
        if str(user.id) not in self.data["exemptions"]:
            self.data["exemptions"].append(str(user.id))
            await ctx.send(f"{user.mention} has been exempted from this week's quota.")
        else:
            await ctx.send(f"{user.mention} is already exempted from this week's quota.")
        
        # Save the updated data to JSON
        self.save_data()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def strikes_until_demotion(self, ctx, num_strikes: int):
        """Set the number of strikes until a user is demoted."""
        self.data["settings"]["strikes_until_demotion"] = num_strikes
        await ctx.send(f"Users will be demoted after {num_strikes} strikes.")

        # Save the updated data to JSON
        self.save_data()

    @commands.Cog.listener()
    async def on_message(self, message):
        """Track user messages and update their quota."""
        if message.author.bot:
            return

        # Ensure user is in the quotas system
        if str(message.author.id) not in self.data["quotas"]:
            return  # No action if user is not in the quotas system

        # Increment the user's message count
        self.data["quotas"][str(message.author.id)] -= 1

        # Check if the user has completed their quota
        if self.data["quotas"][str(message.author.id)] <= 0:
            self.data["quotas"][str(message.author.id)] = 0  # Prevent negative quota
            await message.author.send("You have completed your weekly message quota!")

        # Save the updated data to JSON
        self.save_data()

    @commands.command()
    async def quota_status(self, ctx):
        """Check the status of your current quota."""
        if str(ctx.author.id) in self.data["quotas"]:
            remaining = self.data["quotas"][str(ctx.author.id)]
            await ctx.send(f"You have {remaining} messages remaining to complete your weekly quota.")
        else:
            await ctx.send("You are not currently assigned a quota.")

# Add the cog to the bot
def setup(bot):
    bot.add_cog(QuotaManager(bot))
