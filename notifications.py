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

    def to_payload(self, botname: str | None = None) -> dict[str, object]:
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
            "username": botname if botname else "TwitchDropsMiner",
            "avatar_url": "https://i.imgur.com/muLruAh.png",
        }


class AppriseNotifier:
    def __init__(self, get_session: Callable[[], abc.Awaitable[aiohttp.ClientSession]]):
        self._get_session = get_session
        self._urls: list[str] = []
        self._discord_webhooks: list[tuple[str, str | None]] = []
        self._apprise: apprise.Apprise = apprise.Apprise()
        self._discord_rps = RateLimiter(capacity=50, window=1)
        self._discord_rpm = RateLimiter(capacity=30, window=60)

    def reload(self, urls: str | abc.Iterable[str]) -> None:
        self._urls = notification_urls(urls, mode="list")
        self._apprise = apprise.Apprise()
        self._discord_webhooks.clear()

        for entry in self._urls:
            webhook_info = _discord_webhook_url(entry)
            if webhook_info:
                self._discord_webhooks.append(webhook_info)
            else:
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

        image = str(drop.benefits[0].image_url) if drop.benefits and drop.benefits[0].image_url else PLACEHOLDER_IMAGE
        thumbnail = str(drop.campaign.image_url) if drop.campaign.image_url else PLACEHOLDER_THUMBNAIL

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
            for webhook_url, botname in self._discord_webhooks:
                await self._post_discord_webhook(webhook_url, botname, embed)

            if len(self._apprise) > 0:
                await asyncio.to_thread(self._apprise.notify, title=title, body=body)

        except Exception:
            logger.exception("Failed to send notification")

    async def _post_discord_webhook(self, webhook_url: str, botname: str | None, embed: DiscordEmbed) -> None:
        async with self._discord_rps, self._discord_rpm:
            session = await self._get_session()
            async with session.post(webhook_url, json=embed.to_payload(botname)) as response:
                if response.status >= 400:
                    details = await response.text()
                    logger.warning(
                        "Discord webhook notification failed (%s): %s",
                        response.status,
                        details,
                    )


def _discord_webhook_url(url: str) -> tuple[str, str | None] | None:
    parsed = urlparse(url)

    if parsed.scheme in {"http", "https"}:
        if "discord" in parsed.netloc.lower() and "/api/webhooks/" in parsed.path:
            return url, None
        return None

    if parsed.scheme == "discord":
        netloc_parts = parsed.netloc.split("@", 1)
        webhook_id = netloc_parts[-1]

        botname = netloc_parts[0] if len(netloc_parts) > 1 else None

        path_parts = [part for part in parsed.path.split("/") if part]

        if webhook_id and path_parts:
            webhook_token = path_parts[0]
            webhook_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
            return webhook_url, botname

    return None
