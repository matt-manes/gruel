import inspect
import time
from typing import Any

import loggi
import requests
import whosyouragent
from bs4 import BeautifulSoup, Tag
from noiftimer import Timer
from pathier import Pathier, Pathish
from printbuddies import ProgBar

ParsableItem = dict[str, Any] | str | Tag


def request(
    url: str,
    method: str = "get",
    headers: dict[str, str] = {},
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    timeout: int | None = None,
    retry_on_fail: bool = True,
    json_: Any | None = None,
) -> requests.Response:
    """Send a request to `url` and return the `requests.Response` object.

    By default, the only header sent is a randomized user agent string.

    This can be overridden by supplying a user agent in the `headers` param.

    If `retry_on_fail` is `True`, the request will be repeated after 1 second if the originally request causes an exception to be thrown.
    Otherwise, the exception will be raised."""
    request_args = [method, url]
    headers = whosyouragent.get_header() | headers
    request_kwargs = {
        "headers": headers,
        "timeout": timeout,
        "params": params,
        "data": data,
        "json": json_,
    }
    try:
        response = requests.request(*request_args, **request_kwargs)
        return response
    except Exception as e:
        if retry_on_fail:
            time.sleep(1)
            return requests.request(*request_args, **request_kwargs)
        else:
            raise e


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
    5. `self.postscrape_chores()` (only closes this instance's log file unless overridden)

    When overriding `self.postscrape_chores`, it's recommended to either
    call `super().postscrape_chores()` or make sure to call `self.log.close()`.
    Otherwise running a large number of scrapers can cause file handle limit issues."""

    def __init__(self, name: str | None = None, log_dir: Pathish | None = None):
        """
        :params:
        * `name`: The name of this scraper. If `None`, the name will be the stem of the file this class/subclass was defined in.
        i.e. A `Gruel` subclass located in a file called `myscraper.py` will have the name `"myscraper"`.
        * `log_dir`: The directory this scraper's logs should be saved to.
        If `None`, the logs will be written to a folder called `"gruel_logs"` within the current working directory.
        """
        self._name = name
        self._init_logger(log_dir)
        self.timer = Timer()
        self.success_count = 0
        self.fail_count = 0
        self.failed_to_get_parsable_items = False
        self.unexpected_failure_occured = False
        self.parsable_items: list[ParsableItem] = []
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

    def _init_logger(self, log_dir: Pathish | None):
        log_dir = Pathier.cwd() / "gruel_logs" if not log_dir else Pathier(log_dir)
        self.logger = loggi.getLogger(self.name, log_dir)

    @staticmethod
    def as_soup(response: requests.Response) -> BeautifulSoup:
        """Returns the text content of `response` as a `BeautifulSoup` object."""
        return BeautifulSoup(response.text, "html.parser")

    def get_soup(
        self, url: str, method: str = "get", headers: dict[str, str] = {}
    ) -> BeautifulSoup:
        """Request `url` with `headers` and return `BeautifulSoup` object."""
        return self.as_soup(request(url, method, headers))

    def clean_string(self, text: str) -> str:
        """Strip `\\n\\r\\t` and whitespace from `text`."""
        return text.strip(" \n\t\r")

    # |==============================================================================|
    # Overridables
    # |==============================================================================|
    def prescrape_chores(self):
        """Chores to do before scraping."""
        ...

    def postscrape_chores(self):
        """Chores to do after scraping."""
        loggi.close(self.logger)

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

    def _parse_items_no_prog_bar(self):
        for item in self.parsable_items:
            parsed_item = self.parse_item(item)
            if parsed_item:
                self.store_item(parsed_item)
            # Append to `self.parsable_items` even if `None`
            # so `parsable_items` and `parsed_items` are equal length
            self.parsed_items.append(parsed_item)

    def _parse_items_prog_bar(self):
        with ProgBar(len(self.parsable_items)) as bar:
            for item in self.parsable_items:
                parsed_item = self.parse_item(item)
                if parsed_item:
                    self.store_item(parsed_item)
                    bar.display(f"{bar.runtime}")
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
                if parse_items_prog_bar_display:
                    self._parse_items_prog_bar()
                else:
                    self._parse_items_no_prog_bar()
                self.logger.info(
                    f"Scrape completed in {self.timer.elapsed_str} with {self.success_count} successes and {self.fail_count} failures."
                )
        except Exception:
            self.unexpected_failure_occured = True
            self.logger.exception(f"Unexpected failure in {self.name}:scrape()")
        self.postscrape_chores()
