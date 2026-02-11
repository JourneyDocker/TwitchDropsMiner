from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from collections import abc
from typing import Callable, TYPE_CHECKING
from urllib.parse import urlparse

import aiohttp
import apprise

from utils import RateLimiter, notification_urls


logger = logging.getLogger("TwitchDrops")
DISCORD_HOSTS = {
    "discord.com",
    "discordapp.com",
    "ptb.discord.com",
    "canary.discord.com",
}
PLACEHOLDER_IMAGE = "https://placehold.co/460x215.jpg?text=Cant+load+image"
PLACEHOLDER_THUMBNAIL = "https://placehold.co/80x80.jpg?text=No+image"

if TYPE_CHECKING:
    from inventory import TimedDrop


@dataclass(frozen=True)
class DiscordEmbed:
    title: str
    description: str
    color: int
    footer: str
    image_url: str | None = None
    thumbnail_url: str | None = None

    def to_payload(self) -> dict[str, object]:
        embed: dict[str, object] = {
            "title": self.title,
            "description": self.description,
            "color": self.color,
            "footer": {"text": self.footer},
        }
        if self.image_url:
            embed["image"] = {"url": self.image_url}
        if self.thumbnail_url:
            embed["thumbnail"] = {"url": self.thumbnail_url}
        return {
            "embeds": [embed],
            "username": "Twitch Drops Miner",
            "avatar_url": (
                "https://raw.githubusercontent.com/DevilXD/TwitchDropsMiner/refs/heads/master/"
                "icons/pickaxe.ico"
            ),
        }


class AppriseNotifier:
    def __init__(self, get_session: Callable[[], abc.Awaitable[aiohttp.ClientSession]]):
        self._get_session = get_session
        self._urls: list[str] = []
        self._apprise: apprise.Apprise = apprise.Apprise()
        self._discord_rps = RateLimiter(capacity=50, window=1)
        self._discord_rpm = RateLimiter(capacity=30, window=60)

    def reload(self, urls: str | abc.Iterable[str]) -> None:
        self._urls = notification_urls(urls, mode="list")
        self._apprise = apprise.Apprise()
        if self._urls:
            for entry in self._urls:
                if _discord_webhook_url(entry) is None:
                    self._apprise.add(entry)

    def configured(self) -> bool:
        return bool(self._urls)

    def notify_drop(self, drop: TimedDrop) -> asyncio.Task[None] | None:
        if not self._urls:
            return None
        return asyncio.create_task(self._notify_drop(drop))

    def notify_test(self) -> asyncio.Task[None] | None:
        if not self._urls:
            return None
        return asyncio.create_task(self._notify_test())

    async def _notify_test(self) -> None:
        embed = DiscordEmbed(
            title="Test Notification",
            description="This is a test notification from TwitchDropsMiner.",
            color=0x9146FF,
            footer="TwitchDropsMiner",
            image_url=PLACEHOLDER_IMAGE,
            thumbnail_url=PLACEHOLDER_THUMBNAIL,
        )
        await self._notify(embed=embed, title=embed.title, body=embed.description)

    async def _notify_drop(self, drop: TimedDrop) -> None:
        game_name = f"{drop.campaign.game.name} ({drop.campaign.claimed_drops}/{drop.campaign.total_drops})"
        description = f"Campaign: {drop.campaign.name}\nDrop: {drop.name}"
        image_url = drop.benefits[0].image_url if drop.benefits else None
        thumbnail_url = drop.campaign.image_url
        image = str(image_url) if image_url else PLACEHOLDER_IMAGE
        thumbnail = str(thumbnail_url) if thumbnail_url else PLACEHOLDER_THUMBNAIL
        embed = DiscordEmbed(
            title=f"Claimed Drop: {game_name}",
            description=description,
            color=0x9146FF,
            footer="TwitchDropsMiner",
            image_url=image,
            thumbnail_url=thumbnail,
        )
        await self._notify(embed=embed, title=embed.title, body=embed.description)

    async def _notify(self, *, embed: DiscordEmbed, title: str, body: str) -> None:
        try:
            discord_urls = [entry for entry in self._urls if _discord_webhook_url(entry) is not None]
            other_urls = [entry for entry in self._urls if _discord_webhook_url(entry) is None]
            for entry in discord_urls:
                webhook_url = _discord_webhook_url(entry)
                if webhook_url is not None:
                    await self._post_discord_webhook(webhook_url, embed)
            if other_urls:
                apprise_client = apprise.Apprise()
                for entry in other_urls:
                    apprise_client.add(entry)
                await asyncio.to_thread(apprise_client.notify, title=title, body=body)
        except Exception:
            logger.exception("Failed to send Apprise notification")

    async def _post_discord_webhook(self, webhook_url: str, embed: DiscordEmbed) -> None:
        async with self._discord_rps, self._discord_rpm:
            session = await self._get_session()
            async with session.post(webhook_url, json=embed.to_payload()) as response:
                if response.status >= 400:
                    details = await response.text()
                    logger.warning(
                        "Discord webhook notification failed (%s): %s",
                        response.status,
                        details,
                    )


def _discord_webhook_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"}:
        host = parsed.netloc.lower()
        if any(host.endswith(allowed) for allowed in DISCORD_HOSTS):
            if "/api/webhooks/" in parsed.path:
                webhook_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    webhook_url = f"{webhook_url}?{parsed.query}"
                return webhook_url
        return None
    if parsed.scheme != "discord":
        return None
    webhook_id = parsed.netloc
    if "@" in webhook_id:
        webhook_id = webhook_id.split("@", 1)[1]
    path_parts = [part for part in parsed.path.split("/") if part]
    if not webhook_id or not path_parts:
        return None
    webhook_token = path_parts[0]
    return f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
