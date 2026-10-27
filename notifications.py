from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from collections import abc
from typing import Any, Callable, Mapping, TYPE_CHECKING
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp

from utils import RateLimiter, notification_urls

logger = logging.getLogger("TwitchDrops")
PLACEHOLDER_IMAGE = "https://placehold.co/460x215.jpg?text=Cant+load+image"
PLACEHOLDER_THUMBNAIL = "https://placehold.co/80x80.jpg?text=No+image"

# Discord webhook API endpoint, defined in one place so it's easy to override.
DISCORD_API_WEBHOOK_BASE = "https://discord.com/api/webhooks"
DISCORD_WEBHOOK_HOSTS = frozenset({
    "discord.com",
    "discordapp.com",
    "canary.discord.com",
    "ptb.discord.com",
})
DISCORD_EMBED_TITLE_LIMIT = 256
DISCORD_EMBED_DESCRIPTION_LIMIT = 4096
DISCORD_EMBED_FOOTER_LIMIT = 2048
DISCORD_USERNAME_LIMIT = 80
DISCORD_RATE_LIMIT_RETRIES = 3
DISCORD_MAX_RETRY_WAIT = 60.0

if TYPE_CHECKING:
    from inventory import TimedDrop


class NotificationError(RuntimeError):
    """Raised when a notification couldn't be delivered."""


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
            "title": _truncate(self.title, DISCORD_EMBED_TITLE_LIMIT),
            "description": _truncate(self.description, DISCORD_EMBED_DESCRIPTION_LIMIT),
            "color": self.color,
            "footer": {"text": _truncate(self.footer, DISCORD_EMBED_FOOTER_LIMIT)},
        }
        if self.image_url:
            embed["image"] = {"url": self.image_url}
        if self.thumbnail_url:
            embed["thumbnail"] = {"url": self.thumbnail_url}

        return {
            "embeds": [embed],
            "username": _truncate(botname, DISCORD_USERNAME_LIMIT) if botname else "TwitchDropsMiner",
            "avatar_url": "https://i.imgur.com/muLruAh.png",
        }


@dataclass(frozen=True)
class DiscordWebhook:
    webhook_id: str
    token: str = field(repr=False)
    botname: str | None = None
    thread_id: str | None = None

    @property
    def url(self) -> str:
        url = f"{DISCORD_API_WEBHOOK_BASE}/{self.webhook_id}/{self.token}"
        if self.thread_id:
            url = f"{url}?thread_id={self.thread_id}"
        return url

    def __str__(self) -> str:
        # the webhook token is a secret, so it's never included in log messages
        prefix = f"{self.botname}@" if self.botname else ""
        return f"{prefix}{self.webhook_id}"


class DiscordNotifier:
    def __init__(self, get_session: Callable[[], abc.Awaitable[aiohttp.ClientSession]]):
        self._get_session = get_session
        self._webhooks: list[DiscordWebhook] = []
        self._discord_rps = RateLimiter(capacity=50, window=1)
        self._discord_rpm = RateLimiter(capacity=30, window=60)

    def reload(self, urls: str | abc.Iterable[str]) -> None:
        self._webhooks.clear()

        for entry in notification_urls(urls, mode="list"):
            webhook = parse_discord_webhook(entry)
            if webhook is None:
                logger.warning(
                    "Ignoring unsupported notification URL (only Discord webhooks are supported): %s",
                    _redact_url(entry),
                )
            elif webhook not in self._webhooks:
                self._webhooks.append(webhook)

        if self._webhooks:
            logger.debug(
                "Discord notifications enabled for %d webhook(s)", len(self._webhooks)
            )

    def configured(self) -> bool:
        return bool(self._webhooks)

    def notify_drop(self, drop: TimedDrop) -> asyncio.Task[None] | None:
        if not self._webhooks:
            return None
        return asyncio.create_task(self._notify_drop(drop))

    def notify_test(self) -> asyncio.Task[None] | None:
        if not self._webhooks:
            logger.warning(
                "No valid Discord webhook is configured, the test notification was not sent"
            )
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
        await self._notify(embed=embed)

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
        await self._notify(embed=embed)

    async def _notify(self, *, embed: DiscordEmbed) -> None:
        # snapshot the webhooks, so a concurrent reload() can't misalign the results
        webhooks = tuple(self._webhooks)
        if not webhooks:
            return

        results = await asyncio.gather(
            *(self._post_discord_webhook(webhook, embed) for webhook in webhooks),
            return_exceptions=True,
        )
        # a failure on one webhook must not affect delivery to the remaining ones
        for webhook, result in zip(webhooks, results):
            if isinstance(result, NotificationError):
                logger.warning("Discord notification via webhook %s failed: %s", webhook, result)
            elif isinstance(result, BaseException):
                logger.error(
                    "Discord notification via webhook %s failed", webhook, exc_info=result
                )

    async def _post_discord_webhook(self, webhook: DiscordWebhook, embed: DiscordEmbed) -> None:
        payload = embed.to_payload(webhook.botname)

        for attempt in range(DISCORD_RATE_LIMIT_RETRIES + 1):
            retry_after = 1.0

            async with self._discord_rps, self._discord_rpm:
                session = await self._get_session()
                async with session.post(webhook.url, json=payload) as response:
                    if response.status < 400:
                        return

                    text = await response.text()
                    body = _parse_response_body(text)
                    details = _describe_response(response, body, text)

                    if response.status in {401, 403, 404}:
                        raise NotificationError(
                            "webhook was rejected, it's likely deleted or has an invalid "
                            f"ID/token (HTTP {response.status}): {details}"
                        )
                    if response.status != 429:
                        raise NotificationError(
                            f"request failed (HTTP {response.status}): {details}"
                        )
                    if attempt >= DISCORD_RATE_LIMIT_RETRIES:
                        raise NotificationError(
                            "still rate limited after "
                            f"{DISCORD_RATE_LIMIT_RETRIES} retries: {details}"
                        )
                    retry_after = _retry_after(response, body)

            logger.warning(
                "Discord webhook %s is rate limited, retrying in %.1fs",
                webhook,
                retry_after,
            )
            await asyncio.sleep(retry_after)


def parse_discord_webhook(entry: str) -> DiscordWebhook | None:
    """Parse a Discord webhook URL into its parts, or `None` if it's not one."""
    try:
        parsed = urlparse(entry.strip())
    except ValueError:
        # malformed URLs (e.g. an unterminated IPv6 bracket) can raise here
        return None
    scheme = parsed.scheme.lower()

    if scheme == "discord":
        # legacy apprise-style URL: discord://botname@webhook_id/webhook_token
        netloc_parts = parsed.netloc.rsplit("@", 1)
        botname = unquote(netloc_parts[0]) if len(netloc_parts) > 1 else None
        webhook_id = netloc_parts[-1]
        path_parts = [part for part in parsed.path.split("/") if part]
        if not webhook_id.isdigit() or not path_parts:
            return None
        return DiscordWebhook(
            webhook_id=webhook_id,
            token=path_parts[0],
            botname=botname or None,
        )

    if scheme not in {"http", "https"}:
        return None
    if parsed.hostname not in DISCORD_WEBHOOK_HOSTS:
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    if "webhooks" not in path_parts:
        return None

    webhook_parts = path_parts[path_parts.index("webhooks") + 1:]
    if len(webhook_parts) < 2:
        return None

    webhook_id, token = webhook_parts[0], webhook_parts[1]
    if not webhook_id.isdigit() or not token:
        return None

    thread_id = parse_qs(parsed.query).get("thread_id", [None])[0]
    return DiscordWebhook(webhook_id=webhook_id, token=token, thread_id=thread_id)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _redact_url(entry: str) -> str:
    try:
        parsed = urlparse(entry)
    except ValueError:
        return "<invalid URL>"
    if not parsed.scheme:
        return "<invalid URL>"
    return f"{parsed.scheme}://{parsed.hostname or '...'}/..."


def _parse_response_body(text: str) -> Mapping[str, Any] | None:
    if not text:
        return None
    try:
        body = json.loads(text)
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def _describe_response(
    response: aiohttp.ClientResponse,
    body: Mapping[str, Any] | None,
    text: str,
) -> str:
    if body is not None and isinstance(body.get("message"), str):
        return body["message"]
    return text.strip()[:200] or f"HTTP {response.status}"


def _retry_after(response: aiohttp.ClientResponse, body: Mapping[str, Any] | None) -> float:
    value: Any = body.get("retry_after") if body is not None else None
    if value is None:
        value = response.headers.get("Retry-After")
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = 1.0
    return min(max(seconds, 0.0), DISCORD_MAX_RETRY_WAIT)
