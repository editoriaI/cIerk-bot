import logging
import os

import discord
from bot_common import (
    build_price_response_text,
    configure_logging,
    perform_price_lookup,
    read_timeout_env,
)
from dotenv import load_dotenv
from pricing_engine import PriceEngine, normalize_item_name, parse_item_query
from shared_energy import DISCORD_READY_MESSAGE, ENERGY_TAG
from unboxing_store import get_discord_config, save_discord_config


configure_logging("clerk")
logger = logging.getLogger(__name__)

THEME_COLOR = discord.Color.from_rgb(240, 106, 192)
SUCCESS_COLOR = discord.Color.from_rgb(40, 220, 110)
ERROR_COLOR = discord.Color.from_rgb(230, 72, 72)


def build_themed_embed(
    title: str,
    description: str,
    *,
    color: discord.Color = THEME_COLOR,
    footer: str = "Miss Westie • Serving y2k realness",
) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=footer)
    return embed


class UnboxModal(discord.ui.Modal, title="Victor/Clerk Unboxing"):
    primary_mode = discord.ui.TextInput(
        label="Primary Mode",
        placeholder="trading / community / support / events",
        max_length=64,
    )
    moderation_style = discord.ui.TextInput(
        label="Moderation Style",
        placeholder="chill / balanced / strict",
        max_length=64,
    )
    engagement_style = discord.ui.TextInput(
        label="Engagement Style",
        placeholder="whisper-first / channel-first / hybrid",
        max_length=64,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                embed=build_themed_embed(
                    "🚫 Run this in a server",
                    "This setup flow needs a server context.",
                    color=ERROR_COLOR,
                ),
                ephemeral=True,
            )
            return

        answers = {
            "primary_mode": str(self.primary_mode).strip(),
            "moderation_style": str(self.moderation_style).strip(),
            "engagement_style": str(self.engagement_style).strip(),
        }
        save_discord_config(
            str(interaction.guild.id),
            interaction.user.name,
            answers,
        )
        await interaction.response.send_message(
            embed=build_themed_embed(
                "✨ Unboxing Complete",
                f"[{ENERGY_TAG}] Your server profile is now saved and ready to use.",
                color=SUCCESS_COLOR,
            ),
            ephemeral=True,
        )


def build_bot() -> discord.Client:
    intents = discord.Intents.default()
    bot = discord.Client(intents=intents)
    tree = discord.app_commands.CommandTree(bot)
    pricing = PriceEngine()
    price_timeout = read_timeout_env("PRICE_LOOKUP_TIMEOUT", 6.0)

    @bot.event
    async def on_ready() -> None:
        await tree.sync()
        logger.info("%s Logged in as %s.", DISCORD_READY_MESSAGE, bot.user)

    @tree.command(name="energy", description="Show Clerk shared energy")
    async def energy(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=build_themed_embed(
                "✨ Shared Energy",
                f"[{ENERGY_TAG}] Same vibe as Highrise Clerk. Commands are synced by tone.",
            )
        )

    @tree.command(name="bot", description="Highrise Clerk summon help")
    async def bot_command(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=build_themed_embed(
                "🎧 Summon Clerk",
                f"[{ENERGY_TAG}] Use `!bot` in Highrise to summon Clerk to your exact facing.",
            )
        )

    @tree.command(name="price", description="Check Highrise market pricing")
    @discord.app_commands.describe(query="Item name, hashtag, or 'how much is ...' text")
    async def price(interaction: discord.Interaction, query: str) -> None:
        normalized = parse_item_query(query) or normalize_item_name(query)
        if not normalized:
            await interaction.response.send_message(
                embed=build_themed_embed(
                    "🚫 Missing item",
                    "Provide an item name, hashtag, or pricing phrase.",
                    color=ERROR_COLOR,
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        result = await perform_price_lookup(pricing, normalized, price_timeout, logger)
        message = build_price_response_text(result, normalized, price_timeout)
        await interaction.followup.send(
            embed=build_themed_embed("💿 Price Lookup", message), ephemeral=True
        )

    @tree.command(name="unbox", description="Interactive setup for Victor/Clerk")
    async def unbox(interaction: discord.Interaction) -> None:
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not member or not (
            member.guild_permissions.administrator or member.guild_permissions.manage_guild
        ):
            await interaction.response.send_message(
                embed=build_themed_embed(
                    "🚫 Permission needed",
                    "Only higher-ranked users can run unboxing.",
                    color=ERROR_COLOR,
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(UnboxModal())

    @tree.command(name="unbox_status", description="See saved unboxing profile")
    async def unbox_status(interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                embed=build_themed_embed(
                    "🚫 Run this in a server",
                    "This command needs a server context.",
                    color=ERROR_COLOR,
                ),
                ephemeral=True,
            )
            return
        config = get_discord_config(str(interaction.guild.id))
        if not config:
            await interaction.response.send_message(
                embed=build_themed_embed(
                    "🪩 No profile yet",
                    "No unboxing profile is saved yet. Run `/unbox`.",
                    color=ERROR_COLOR,
                ),
                ephemeral=True,
            )
            return

        answers = config.get("answers", {})
        summary = (
            "🌟 **Saved Unboxing Profile**\n"
            f"• **Mode:** {answers.get('primary_mode', 'n/a')}\n"
            f"• **Moderation:** {answers.get('moderation_style', 'n/a')}\n"
            f"• **Engagement:** {answers.get('engagement_style', 'n/a')}"
        )
        await interaction.response.send_message(
            embed=build_themed_embed("📋 Unbox Status", summary, color=SUCCESS_COLOR),
            ephemeral=True,
        )

    return bot


if __name__ == "__main__":
    load_dotenv()
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing DISCORD_BOT_TOKEN in environment/.env.")

    app = build_bot()
    app.run(token)
