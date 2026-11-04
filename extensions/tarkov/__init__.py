"""Optional SPT + Fika server control."""


async def setup(bot):
    from .cog import TarkovCog

    await bot.add_cog(TarkovCog(bot))
