import inspect
from typing import Any

import loggi
from noiftimer import Timer
from pathier import Pathier, Pathish
from printbuddies import track


class ChoresMixin:
    def prescrape_chores(self):
        """Chores to do before scraping."""
        ...

    def postscrape_chores(self):
        """Chores to do after scraping."""
        ...


class ParserMixin:

    def get_parsable_items(self, source: Any) -> list[Any]:
        """Get atomic chunks to be parsed from `source` and return as a list."""
        raise NotImplementedError

    def parse_item(self, item: Any) -> Any:
        """Parse `item` and return parsed data."""
        raise NotImplementedError

    def store_item(self, item: Any) -> Any:
        """Store `item`."""
        raise NotImplementedError

    def parse_items(self, parsable_items: list[Any], show_progress: bool) -> list[Any]:
        parsed_items: list[Any] = []
        for item in track(parsable_items, disable=not show_progress):
            parsed_item = self.parse_item(item)
            # Don't store if `None`
            if parsed_item:
                self.store_item(parsed_item)
            # Append to `parsable_items` even if `None`
            # so `parsable_items` and `parsed_items` are equal length
            parsed_items.append(parsed_item)
        return parsed_items


class Gruel(loggi.LoggerMixin, ChoresMixin, ParserMixin):
    def __init__(self, name: str | None = None, log_dir: Pathish = "logs"):
        """
        :params:
        * `name`: The name of this scraper. If `None`, the name will be the stem of the file this class/subclass was defined in.
        i.e. A `Gruel` subclass located in a file called `myscraper.py` will have the name `"myscraper"`.
        * `log_dir`: The directory this scraper's logs should be saved to.
        """
        self._name = name
        self.init_logger(self.name, log_dir)
        self.timer = Timer()
        self.success_count = 0
        self.fail_count = 0
        self.failed_to_get_parsable_items = False
        self.unexpected_failure_occured = False
        self.parsable_items: list[Any] = []
        self.parsed_items: list[Any] = []

    @property
    def name(self) -> str:
        """Returns the name given to __init__ or the stem of the file this instance was defined in if one wasn't given."""
        return self._name or Pathier(inspect.getsourcefile(type(self))).stem  # type: ignore

    @property
    def had_failures(self) -> bool:
        """`True` if getting parsable items, parsing items, or unexpected failures occured."""
        return (
            (self.fail_count > 0)
            or self.failed_to_get_parsable_items
            or self.unexpected_failure_occured
        )

    def get_source(self) -> Any:
        """Fetch and return source content.

        Most commonly just a webpage request and returning a `Response` object."""
        raise NotImplementedError

    def scrape(
        self, parse_items_prog_bar_display: bool = False, *args: Any, **kwargs: Any
    ):
        """Run the scraper:
        1. prescrape chores
        2. get parsable items
        3. parse and store items
        5. postscrape chores"""
        try:
            self.timer.start()
            self.logger.info("Scrape started.")
            self.prescrape_chores()
            try:
                source = self.get_source()
            except Exception as e:
                self.logger.exception(f"Error getting source data.")
            else:
                try:
                    self.parsable_items = self.get_parsable_items(source)
                    self.logger.info(
                        f"{self.name}:get_parsable_items() returned {(len(self.parsable_items))} items."
                    )
                except Exception:
                    self.failed_to_get_parsable_items = True
                    self.logger.exception(f"Error in {self.name}:get_parsable_items().")
                else:
                    self.parse_items(self.parsable_items, parse_items_prog_bar_display)
                    self.logger.info(
                        f"Scrape completed in {self.timer.elapsed_str} with {self.success_count} successes and {self.fail_count} failures."
                    )
        except Exception:
            self.unexpected_failure_occured = True
            self.logger.exception(f"Unexpected failure in {self.name}:scrape()")
        self.postscrape_chores()
        loggi.close(self.logger)
