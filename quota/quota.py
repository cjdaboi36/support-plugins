import discord
from discord.ext import commands
import json

class QuotaManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quota_tracking_enabled = True  # Set to True by default
        self.quota_data_file = 'quota_data.json'
        self.load_data()

    def load_data(self):
        """Load the quota data from the JSON file."""
        try:
            with open(self.quota_data_file, 'r') as f:
                self.quota_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.quota_data = {}

    def save_data(self):
        """Save the quota data to the JSON file."""
        with open(self.quota_data_file, 'w') as f:
            json.dump(self.quota_data, f, indent=4)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_enable(self, ctx):
        """Enable quota tracking for the week."""
        self.quota_tracking_enabled = True
        await ctx.send("Quota tracking has been enabled for the week.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_disable(self, ctx):
        """Disable quota tracking for the week."""
        self.quota_tracking_enabled = False
        await ctx.send("Quota tracking has been disabled for the week.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_reset(self, ctx):
        """Reset quotas for all users for the week."""
        if not self.quota_tracking_enabled:
            await ctx.send("Quota tracking is currently disabled. Cannot reset quotas.")
            return
        
        self.quota_data = {}  # Reset the quota data
        self.save_data()
        await ctx.send("Quotas have been reset for the week.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_reset_time(self, ctx, time: str):
        """Set the time when quotas will reset (24-hour format)."""
        # Time should be in HH:MM format, example: 23:00 for 11 PM
        # You can add additional validation logic if needed
        self.reset_time = time
        await ctx.send(f"Quota reset time has been set to {time}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_reset_day(self, ctx, day: str):
        """Set the day of the week when quotas reset."""
        # Example: Monday, Tuesday, etc.
        self.reset_day = day
        await ctx.send(f"Quota reset day has been set to {day}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_summary(self, ctx):
        """Show a summary of the quota data."""
        if not self.quota_tracking_enabled:
            await ctx.send("Quota tracking is currently disabled.")
            return
        
        if not self.quota_data:
            await ctx.send("No quota data found for this week.")
            return
        
        summary = "Quota Summary:\n"
        for user_id, data in self.quota_data.items():
            status = "Complete" if data["messages_sent"] >= data["messages_required"] else "Not Complete"
            summary += f"{self.bot.get_user(int(user_id))}: {status}\n"
        
        await ctx.send(summary)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_messages_required(self, ctx, staff_type: str, amount: int):
        """Set the number of messages required for a staff type."""
        if staff_type not in self.quota_data:
            self.quota_data[staff_type] = {}
        
        self.quota_data[staff_type]["messages_required"] = amount
        self.save_data()
        await ctx.send(f"Messages required for {staff_type} has been set to {amount}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def add_staff(self, ctx, user: discord.User):
        """Add a user to the staff system without changing their message requirements."""
        if str(user.id) not in self.quota_data:
            self.quota_data[str(user.id)] = {"messages_sent": 0, "messages_required": 0}
        self.save_data()
        await ctx.send(f"{user} has been added to the staff system.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def new_staff(self, ctx, user: discord.User):
        """Add a user to the system as new staff without new message requirements."""
        if str(user.id) not in self.quota_data:
            self.quota_data[str(user.id)] = {"messages_sent": 0, "messages_required": 0}
        
        self.quota_data[str(user.id)]["messages_required"] = 0  # No new message requirements
        self.save_data()
        await ctx.send(f"{user} has been added as new staff without new message requirements.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def strikes_until_demotion(self, ctx, number: int):
        """Set the number of strikes before a staff member gets demoted."""
        self.strikes_until_demotion = number
        await ctx.send(f"Staff members will be demoted after {number} strikes.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_complete(self, ctx, user: discord.User):
        """Mark a user's quota as complete after they meet their message requirement."""
        if str(user.id) in self.quota_data:
            self.quota_data[str(user.id)]["messages_sent"] = self.quota_data[str(user.id)]["messages_required"]
            self.save_data()
            await ctx.send(f"{user}'s quota has been marked as complete.")
        else:
            await ctx.send(f"{user} does not have any quota data.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def quota_exemption(self, ctx, user: discord.User):
        """Exempt a user from the current week's quota."""
        if str(user.id) in self.quota_data:
            self.quota_data[str(user.id)]["messages_required"] = 0  # Exempt them from the quota
            self.save_data()
            await ctx.send(f"{user} has been exempted from the current week's quota.")
        else:
            await ctx.send(f"{user} does not have any quota data.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_reset_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel where the reset announcement will be sent."""
        self.reset_channel = channel.id
        await ctx.send(f"The reset announcement will be sent to {channel}.")

def setup(bot):
    bot.add_cog(QuotaManager(bot))
