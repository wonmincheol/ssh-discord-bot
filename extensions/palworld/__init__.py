"""Palworld support as an optional Discord extension."""

async def setup(bot):
    # Keep service/settings importable without discord.py, which makes the
    # feature boundary easier to test and reuse outside Discord.
    from .cog import PalworldCog

    await bot.add_cog(PalworldCog(bot))
