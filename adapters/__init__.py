"""Adapters package for Clara.

This package contains platform adapters that implement the PlatformAdapter interface
defined in clara_core.platform. Each adapter translates between platform-native
objects (e.g., Discord messages) and Clara's platform-agnostic abstractions.

Available adapters:
    - discord: Discord bot adapter (adapters.discord.DiscordAdapter)

As new platforms are added, their adapters will be registered here.
"""
