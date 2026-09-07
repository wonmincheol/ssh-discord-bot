"""Discord role-backed command permissions."""


async def setup(bot):
    # Keep settings/store/service importable without the Discord dependency.
    from .cog import PermissionCog

    await bot.add_cog(PermissionCog(bot))
