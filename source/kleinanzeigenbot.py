from io import BytesIO
import logging
import certifi
import pycurl
import re
from bs4 import BeautifulSoup

DEFAULT_HEADERS = ["User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"]

TEST_URL = "https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/preis::1000/c203l3331+wohnung_mieten.verfuegbarm_i:10%2C+wohnung_mieten.verfuegbary_i:2023%2C"


class KleinanzeigenItem:

    def __init__(self, article) -> None:
        # Default values so the object is always fully initialized, even if
        # the article markup is unexpected. `valid` tells callers whether this
        # looked like a real listing and should be used.
        self.url = article.get("data-href", "")
        self.id = self.url.split("/")[-1] if self.url else ""
        self.title = "No title"
        self.location = "location unknown"
        self.price = "? €"
        self.valid = False

        if not self.url:
            # Not a real listing article (promo slot, placeholder, etc.)
            return

        main = article.find("div", {"class": "aditem-main"})
        if main is None:
            # Article without the expected main block: skip it silently.
            return

        location_el = main.find("div", {"class": "aditem-main--top--left"})
        price_el = main.find("p", {"class": "aditem-main--middle--price-shipping--price"})
        title_el = main.find("h2", {"class": "text-module-begin"})

        self.title = title_el.get_text(strip=True) if title_el else "No title"
        self.location = location_el.get_text(strip=True) if location_el else "location unknown"
        self.price = price_el.get_text(strip=True) if price_el else "? €"
        self.valid = True


    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, KleinanzeigenItem) and self.url == __value.url

    def __str__(self) -> str:
        out_str = self.url + "\n"
        out_str += self.title + "\n"
        out_str += self.price + " - "
        out_str += self.location
        return out_str

    def __hash__(self) -> int:
        return hash(self.id)

    @classmethod
    def from_known(cls, id: str, url: str) -> "KleinanzeigenItem":
        """
        Build a lightweight item from a persisted (id, url) pair, without
        scraping. Used to seed the seen-baseline after a restart so known
        listings are not reported as new again.
        """
        item = cls.__new__(cls)
        item.url = url
        item.id = id
        item.title = "No title"
        item.location = "location unknown"
        item.price = "? €"
        item.valid = True
        return item

    def to_dict(self) -> dict:
        """Serialize the identifying fields needed for dedup across restarts."""
        return {"id": self.id, "url": self.url}

    def check_filters(self, filters):
        for pattern in filters:
            # Use re.search with IGNORECASE flag to check if the pattern matches self.url case-insensitively
            if re.search(pattern, self.url, re.IGNORECASE):
                return False  # Return False if a match is found

        return True


class KleinanzeigenBot:
    """
    Bot that querries a specified link and returns new articles if found
    """

    def __init__(self, url: str, name: str) -> None:
        self.name = name
        self.url = url

        self.mainSet = self._parse_articles()

        self.invalid_link_flag = len(self.mainSet) <= 0

    @classmethod
    def from_state(cls, url: str, name: str, known_items: list) -> "KleinanzeigenBot":
        """
        Reconstruct a bot from persisted state without re-baselining.

        The seen-baseline is seeded from the persisted (id, url) pairs, then a
        fresh scrape is merged in so that listings which appeared while the bot
        was down are also treated as already-seen (not retro-notified). The
        first live poll after this will only report genuinely new listings.
        """
        bot = cls.__new__(cls)
        bot.name = name
        bot.url = url

        # Seed from persisted ids first.
        bot.mainSet = {
            KleinanzeigenItem.from_known(entry["id"], entry["url"])
            for entry in known_items
        }

        # Merge whatever is currently on the page into the baseline.
        try:
            bot.mainSet |= bot._parse_articles()
        except Exception as e:
            logging.error("initial scrape for restored bot '%s' failed: %s", name, e)

        bot.invalid_link_flag = False
        return bot

    def to_dict(self) -> dict:
        """Serialize the bot: its url, name and seen-listing ids."""
        return {
            "name": self.name,
            "url": self.url,
            "seen": [item.to_dict() for item in self.mainSet],
        }

    def _parse_articles(self) -> set:
        """
        Fetch the page and return the set of valid listings found on it.

        Articles that don't parse into a real listing (missing data-href or
        main block) are skipped rather than added as broken items.
        """
        data = self.get_site_curl()

        articles = data.find_all("article")
        items = set()
        for article in articles:
            item = KleinanzeigenItem(article)
            if item.valid:
                items.add(item)

        logging.info(
            "scrape '%s': %d article(s) found, %d valid listing(s)",
            self.name,
            len(articles),
            len(items),
        )
        return items

    def get_new_articles(self) -> set[KleinanzeigenItem]:
        newSet = self._parse_articles()

        newArticles = newSet.difference(self.mainSet)
        self.mainSet = self.mainSet.union(newArticles)

        return newArticles

    def get_site_curl(self) -> BeautifulSoup:
        """
        Get the site contents using curl and return the parsed html.

        :return: the parsed DOM tree
        """
        buffer = BytesIO()
        curl = pycurl.Curl()
        curl.setopt(pycurl.URL, self.url)
        curl.setopt(pycurl.WRITEDATA, buffer)
        curl.setopt(pycurl.HTTPHEADER, DEFAULT_HEADERS)
        curl.setopt(pycurl.CAINFO, certifi.where())  # to be able to use HTTPS

        curl.perform()
        curl.close()

        body = buffer.getvalue().decode()

        return BeautifulSoup(body, "html.parser")

    def show_articles(self) -> None:
        for item in self.mainSet:
            print(item)

    def num_items(self):
        return len(self.mainSet)


if __name__ == "__main__":
    bot = KleinanzeigenBot(TEST_URL, "test")

    bot.show_articles()
