import os
import datetime
import random
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# --- BOT SETUP ---
class Client(commands.Bot):
    def __init__(self):
        # Enable necessary intents
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Register persistent views (like the ticket close button)
        self.add_view(CloseTicketView())
        # Sync slash commands globally
        await self.tree.sync()
        print("Slash commands synced successfully!")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Game(name="/help | Serving the server!"))

bot = Client()

# --- GLOBAL SLASH COMMAND ERROR HANDLER ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
    else:
        print(f"Command Error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)

# --- TICKET SYSTEM VIEWS ---
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent view

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing ticket in 5 seconds...", ephemeral=True)
        await discord.utils.sleep_until(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=5))
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")

# --- COMMANDS ---

# ================================
# 1. TICKET SYSTEM
# ================================

@bot.tree.command(name="ticket", description="Create a private support ticket channel.")
async def ticket(interaction: discord.Interaction, reason: str = "No reason provided"):
    guild = interaction.guild
    user = interaction.user
    
    # Overwrites: Only the user, the bot, and admins can view the ticket
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }

    # Find or create a 'Tickets' category
    category = discord.utils.get(guild.categories, name="Tickets")
    if not category:
        category = await guild.create_category("Tickets")

    # Channel naming format: ticket-username
    channel_name = f"ticket-{user.name}".lower().replace(" ", "-")
    
    # Prevent duplicate tickets
    existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
    if existing_channel:
        return await interaction.response.send_message(f"You already have an open ticket: {existing_channel.mention}", ephemeral=True)

    channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)

    embed = discord.Embed(
        title="🎟️ Support Ticket Created",
        description=f"Hello {user.mention}, thank you for reaching out!\nAn admin will assist you shortly.",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    
    await channel.send(content=f"{user.mention}", embed=embed, view=CloseTicketView())
    await interaction.response.send_message(f"Your ticket has been created: {channel.mention}", ephemeral=True)

# ================================
# 2. MODERATION COMMANDS
# ================================

@bot.tree.command(name="kick", description="Kick a member from the server.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"✅ **{member}** was kicked. Reason: `{reason}`")

@bot.tree.command(name="ban", description="Ban a member from the server.")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"⛔ **{member}** was banned. Reason: `{reason}`")

@bot.tree.command(name="unban", description="Unban a user using their User ID.")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user)
    await interaction.response.send_message(f"🔓 **{user}** has been unbanned.")

@bot.tree.command(name="timeout", description="Timeout (mute) a member for a set duration in minutes.")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
    duration = datetime.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await interaction.response.send_message(f"🔇 **{member}** timed out for {minutes} minute(s). Reason: `{reason}`")

@bot.tree.command(name="untimeout", description="Remove timeout from a member.")
@app_commands.checks.has_permissions(moderate_members=True)
async def untimeout(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"🔊 Timeout removed for **{member}**.")

@bot.tree.command(name="purge", description="Delete a specified number of messages.")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        return await interaction.response.send_message("Please provide an amount between 1 and 100.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted `{len(deleted)}` messages.", ephemeral=True)

# ================================
# 3. SERVER MANAGEMENT & UTILITY
# ================================

@bot.tree.command(name="announce", description="Send an announcement embed to a specific channel.")
@app_commands.checks.has_permissions(administrator=True)
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str):
    embed = discord.Embed(title=title, description=message, color=discord.Color.gold())
    embed.set_footer(text=f"Announcement by {interaction.user}", icon_url=interaction.user.display_avatar.url)
    await channel.send(embed=embed)
    await interaction.response.send_message(f"Announcement sent to {channel.mention}!", ephemeral=True)

@bot.tree.command(name="lock", description="Lock down the current channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 Channel locked.")

@bot.tree.command(name="unlock", description="Unlock the current channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 Channel unlocked.")

@bot.tree.command(name="slowmode", description="Set channel slowmode in seconds (0 to disable).")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"⏱️ Slowmode set to `{seconds}` seconds.")

@bot.tree.command(name="dm", description="Send a direct message to a user.")
@app_commands.checks.has_permissions(administrator=True)
async def dm(interaction: discord.Interaction, member: discord.Member, message: str):
    try:
        await member.send(f"📩 **Message from {interaction.guild.name}:**\n{message}")
        await interaction.response.send_message(f"Direct message sent to **{member}**.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("Could not send DM to this user (DMs disabled).", ephemeral=True)

# ================================
# 4. INFORMATION COMMANDS
# ================================

@bot.tree.command(name="userinfo", description="Get info about a server member.")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    roles = [role.mention for role in target.roles if role.name != "@everyone"]
    
    embed = discord.Embed(title=f"User Info - {target}", color=target.color)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="ID", value=target.id, inline=True)
    embed.add_field(name="Joined Server", value=target.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Account Created", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name=f"Roles [{len(roles)}]", value=", ".join(roles) if roles else "None", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Display server statistics and info.")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"{guild.name} Statistics", color=discord.Color.green())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Text Channels", value=len(guild.text_channels), inline=True)
    embed.add_field(name="Voice Channels", value=len(guild.voice_channels), inline=True)
    embed.add_field(name="Created On", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="Get a user's profile avatar.")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(title=f"{target.name}'s Avatar", color=discord.Color.purple())
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="Check bot latency.")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: `{latency}ms`")

@bot.tree.command(name="help", description="List available slash commands.")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Bot Command Directory", color=discord.Color.blurple())
    embed.add_field(name="🎟️ Tickets", value="`/ticket`", inline=False)
    embed.add_field(name="🛡️ Moderation", value="`/kick`, `/ban`, `/unban`, `/timeout`, `/untimeout`, `/purge`", inline=False)
    embed.add_field(name="⚙️ Management", value="`/announce`, `/lock`, `/unlock`, `/slowmode`, `/dm`", inline=False)
    embed.add_field(name="ℹ️ Info", value="`/userinfo`, `/serverinfo`, `/avatar`, `/ping`, `/help`", inline=False)
    embed.add_field(name="🎉 Fun & Tools", value="`/roll`, `/coinflip`, `/8ball`, `/poll`, `/say`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ================================
# 5. FUN & UTILITY COMMANDS
# ================================

@bot.tree.command(name="roll", description="Roll a random number (1-100 or custom range).")
async def roll(interaction: discord.Interaction, max_number: int = 100):
    result = random.randint(1, max_number)
    await interaction.response.send_message(f"🎲 You rolled a **{result}** (1-{max_number})!")

@bot.tree.command(name="coinflip", description="Flip a coin.")
async def coinflip(interaction: discord.Interaction):
    outcome = random.choice(["Heads 🪙", "Tails 🪙"])
    await interaction.response.send_message(f"Coin landed on: **{outcome}**")

@bot.tree.command(name="8ball", description="Ask the Magic 8-Ball a question.")
async def eightball(interaction: discord.Interaction, question: str):
    responses = ["Yes, definitely.", "Without a doubt.", "Most likely.", "Ask again later.", "Cannot predict now.", "Don't count on it.", "My sources say no.", "Very doubtful."]
    reply = random.choice(responses)
    await interaction.response.send_message(f"❓ **Q:** {question}\n🎱 **A:** {reply}")

@bot.tree.command(name="poll", description="Create a quick yes/no reaction poll.")
async def poll(interaction: discord.Interaction, question: str):
    embed = discord.Embed(title="📊 Community Poll", description=question, color=discord.Color.teal())
    embed.set_footer(text=f"Started by {interaction.user}")
    
    # Send message then add reactions
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    await message.add_reaction("👍")
    await message.add_reaction("👎")

@bot.tree.command(name="say", description="Make the bot say something.")
@app_commands.checks.has_permissions(manage_messages=True)
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("Message sent!", ephemeral=True)
    await interaction.channel.send(message)

# --- RUN BOT ---
bot.run(TOKEN)