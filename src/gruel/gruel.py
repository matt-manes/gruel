import logging
import time
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag
from noiftimer import Timer
from pathier import Pathier
from whosyouragent import get_agent

ParsableItem = dict | str | Tag


class Gruel:
    """Scraper base class."""

    def __init__(self, name: str | None = None):
        self._name = name
        self._init_logger()
        self.timer = Timer()
        self.success_count = 0
        self.fail_count = 0

    @property
    def name(self) -> str:
        """Returns the stem of the file this instance was defined in."""
        return Pathier(inspect.getsourcefile(type(self))).stem  # type: ignore

    def _init_logger(self):
        log_dir = Pathier.cwd() / "logs"
        log_dir.mkdir()
        self.logger = logging.getLogger(self.name)
        if not self.logger.hasHandlers():
            handler = logging.FileHandler(
                (log_dir / self.name).with_suffix(".log"), encoding="utf-8"
            )
            handler.setFormatter(
                logging.Formatter(
                    "{levelname}|-|{asctime}|-|{message}",
                    style="{",
                    datefmt="%m/%d/%Y %I:%M:%S %p",
                )
            )
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def get_page(self, url: str, headers: dict[str, str] = {}) -> requests.Response:
        """Request `url` and return the `requests.Response` object.

        By default, the only header sent is a randomized user agent string.

        This can be overridden by supplying a user agent in the `headers` param."""
        try:
            return requests.get(url, headers={"User-Agent": get_agent()} | headers)
        except Exception as e:
            time.sleep(1)
            return requests.get(url, headers={"User-Agent": get_agent()} | headers)

    def as_soup(self, response: requests.Response) -> BeautifulSoup:
        """Returns the text content of `response` as a `BeautifulSoup` object."""
        return BeautifulSoup(response.text, "html.parser")

    def get_soup(self, url: str, headers: dict[str, str] = {}) -> BeautifulSoup:
        """Request `url` with `headers` and return `BeautifulSoup` object."""
        return self.as_soup(self.get_page(url, headers))

    def clean_string(self, text: str) -> str:
        """Strip `\\n\\r\\t` and whitespace from `text`."""
        return text.strip(" \n\t\r")

    def prescrape_chores(self):
        """Chores to do before scraping."""
        self.timer.start()
        self.logger.info("Scrape started.")

    def postscrape_chores(self):
        """Chores to do after scraping."""
        self.timer.stop()
        self.logger.info(
            f"Scrape completed in {self.timer.elapsed_str} with {self.success_count} successes and {self.fail_count} failures."
        )

    def get_parsable_items(self) -> list[ParsableItem]:
        """Get relevant webpages and extract raw data that needs to be parsed.

        e.g. first 10 results for an endpoint that returns json content
        >>> return self.get_page(some_url).json()[:10]"""
        raise NotImplementedError

    def parse_item(self, item: ParsableItem) -> Any:
        """Parse `item` and return parsed data.

        e.g.
        >>> try:
        >>>     parsed = {}
        >>>     parsed["thing1"] = item["element"].split()[0]
        >>>     self.successes += 1
        >>>     return parsed
        >>> except Exception:
        >>>     self.logger.exception("message")
        >>>     self.failures += 1
        >>>     return None"""
        raise NotImplementedError

    def store_item(self, item: Any):
        """Store `item`."""
        raise NotImplementedError

    def scrape(self):
        """Run the scraper:
        1. prescrape chores
        2. get parsable items
        3. parse items
        4. store items
        5. postscrape chores"""
        try:
            self.prescrape_chores()
            try:
                parsable_items = self.get_parsable_items()
            except Exception:
                self.logger.exception(f"Error in {self.name}:get_parsable_items().")
            else:
                for item in parsable_items:
                    parsed_item = self.parse_item(item)
                    if parsed_item:
                        self.store_item(parsed_item)
        except Exception:
            self.logger.exception(f"Unexpected failure in {self.name}:scrape()")
        self.postscrape_chores()
