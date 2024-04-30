import inspect
from typing import Any

import loggi
from noiftimer import Timer
from pathier import Pathier, Pathish
from printbuddies import track


class Gruel:
    """Scraper base class.

    Classes subclassing `Gruel` need to implement the following methods:

    * `get_parsable_items(self) -> list[Any]`
    * `parse_item(self, item: Any)->Any`
    * `store_item(self, item: Any)`

    Calling the `scrape()` method will execute:
    1. `self.prescrape_chores()` (does nothing unless overridden)
    2. `self.get_parsable_items()`
    3. `self.parse_item()` for each item returned by `self.get_parsable_items()`
    4. `self.store_item()` for each successfully parsed item
    5. `self.postscrape_chores()` (does nothing unless overridden)

    If overriding `self.scrape()`, make a call to `loggi.close(self.logger)` at the end of the function,
    otherwise running a large number of scrapers can cause file handle limit issues."""

    def __init__(self, name: str | None = None, log_dir: Pathish = "logs"):
        """
        :params:
        * `name`: The name of this scraper. If `None`, the name will be the stem of the file this class/subclass was defined in.
        i.e. A `Gruel` subclass located in a file called `myscraper.py` will have the name `"myscraper"`.
        * `log_dir`: The directory this scraper's logs should be saved to.
        """
        self._name = name
        self._init_logger(log_dir)
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

    def _init_logger(self, log_dir: Pathish = "logs"):
        log_dir = Pathier(log_dir)
        self.logger = loggi.getLogger(self.name, log_dir)

    # |==============================================================================|
    # Overridables
    # |==============================================================================|
    def prescrape_chores(self):
        """Chores to do before scraping."""
        ...

    def postscrape_chores(self):
        """Chores to do after scraping."""
        ...

    def get_parsable_items(self) -> list[Any]:
        """Get relevant webpages and extract raw data that needs to be parsed.

        e.g. first 10 results for an endpoint that returns json content
        >>> return self.get_page(some_url).json()[:10]"""
        raise NotImplementedError

    def parse_item(self, item: Any) -> Any:
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

    def store_item(self, item: Any) -> Any:
        """Store `item`."""
        raise NotImplementedError

    def parse_items(self, show_progress: bool) -> Any:
        for item in track(self.parsable_items, disable=not show_progress):
            parsed_item = self.parse_item(item)
            if parsed_item:
                self.store_item(parsed_item)
            # Append to `self.parsable_items` even if `None`
            # so `parsable_items` and `parsed_items` are equal length
            self.parsed_items.append(parsed_item)

    def scrape(self, parse_items_prog_bar_display: bool = False):
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
                self.parsable_items = self.get_parsable_items()
                self.logger.info(
                    f"{self.name}:get_parsable_items() returned {(len(self.parsable_items))} items"
                )
            except Exception:
                self.failed_to_get_parsable_items = True
                self.logger.exception(f"Error in {self.name}:get_parsable_items().")
            else:
                self.parse_items(parse_items_prog_bar_display)
                self.logger.info(
                    f"Scrape completed in {self.timer.elapsed_str} with {self.success_count} successes and {self.fail_count} failures."
                )
        except Exception:
            self.unexpected_failure_occured = True
            self.logger.exception(f"Unexpected failure in {self.name}:scrape()")
        self.postscrape_chores()
        loggi.close(self.logger)
