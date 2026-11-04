import html
import logging
from typing import Callable, List, Optional

from telegram.ext import ContextTypes, Job
from kleinanzeigenbot import KleinanzeigenBot, KleinanzeigenItem


class ChatClient:
    def __init__(self, chat_id: int) -> None:
        self.registered_bots: List[KleinanzeigenBot] = []
        self.id: int = chat_id
        self.fetch_job: Job | None = None
        self.filters: List[str] = []
        # whether polling should be running; persisted so it can auto-resume
        self.active: bool = False
        # optional callback invoked whenever persisted state changes
        self.on_change: Optional[Callable[[], None]] = None

    def _notify_change(self) -> None:
        if self.on_change is not None:
            try:
                self.on_change()
            except Exception as e:
                logging.error("failed to persist state: %s", e)

    def to_dict(self) -> dict:
        """Serialize this chat's searches, filters and running state."""
        return {
            "id": self.id,
            "active": self.active,
            "filters": list(self.filters),
            "bots": [bot.to_dict() for bot in self.registered_bots],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatClient":
        """Reconstruct a ChatClient from persisted state (without a job)."""
        client = cls(int(data["id"]))
        client.filters = list(data.get("filters", []))
        client.active = bool(data.get("active", False))
        for bot_data in data.get("bots", []):
            client.registered_bots.append(
                KleinanzeigenBot.from_state(
                    bot_data["url"], bot_data["name"], bot_data.get("seen", [])
                )
            )
        return client

    def fetch_job_running(self) -> bool:
        return self.fetch_job != None

    async def start_fetch_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Start the fetch job for this ChatClient

        :param context: the current context.
        """

        # check if there are any bots to start
        if len(self.registered_bots) <= 0:
            await context.bot.send_message(
                chat_id=self.id,
                text=f"There are not bots to sart yet. Try adding some with /add_bot",
            )
            return

        if context.job_queue is None:
            await context.bot.send_message(
                chat_id=self.id,
                text=f"Could not start due to internal error 501",
            )
            print("context has no job_queue")
            return

        if self.fetch_job_running():
            await context.bot.send_message(
                chat_id=self.id,
                text=f"Fetch job is already running.",
            )
            return

        # Create and schedule the job
        self.fetch_job = context.job_queue.run_repeating(self.fetch_articles, interval=120, first=10)
        self.active = True
        self._notify_change()
        await context.bot.send_message(
            chat_id=self.id,
            text=f"Fetch job for {len(self.registered_bots)} bots is now running!",
        )

    def stop_fetch_job(self) -> None:
        self.active = False
        if self.fetch_job is None:
            print("tried to remove none running job")
            self._notify_change()
            return

        self.fetch_job.schedule_removal()
        self.fetch_job = None
        self._notify_change()

    async def fetch_articles(self, context: ContextTypes.DEFAULT_TYPE):
        found_new = False
        for bot in self.registered_bots:
            articles = bot.get_new_articles()

            logging.info("poll '%s': %d new article(s) detected", bot.name, len(articles))

            if len(articles) <= 0:
                continue

            found_new = True
            sent = 0
            for a in articles:
                if not a.check_filters(self.filters):
                    logging.info("  '%s': filtered out %s", bot.name, a.url)
                    continue

                # Escape dynamic fields: titles/prices/locations can contain
                # &, <, > which would otherwise break parse_mode="HTML".
                title = html.escape(a.title)
                price = html.escape(a.price)
                location = html.escape(a.location)
                message = (
                    f"<b>{title}</b>\n{price} -- <i>{location}</i>\n"
                    f"https://www.kleinanzeigen.de{a.url}\n<i>search: {html.escape(bot.name)}</i>"
                )
                try:
                    await context.bot.send_message(chat_id=self.id, text=message, parse_mode="HTML")
                    sent += 1
                except Exception as e:
                    logging.error("  '%s': failed to send message for %s: %s", bot.name, a.url, e)

            logging.info("poll '%s': %d message(s) sent", bot.name, sent)

        # Persist newly-seen listing ids so they are not re-notified on restart.
        if found_new:
            self._notify_change()

    def add_bot(self, bot: KleinanzeigenBot):
        self.registered_bots.append(bot)
        self._notify_change()

    def remove_bot(self, link: str) -> bool:
        before = len(self.registered_bots)

        self.registered_bots = list(filter(lambda x: x.name != link, self.registered_bots))

        after = len(self.registered_bots)

        changed = after < before
        if changed:
            self._notify_change()
        return changed

    def add_filter(self, filter: str):
        self.filters.append(filter)
        self._notify_change()
