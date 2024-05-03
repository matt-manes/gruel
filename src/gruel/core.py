import inspect

import loggi
from noiftimer import Timer
from pathier import Pathier, Pathish
from printbuddies import track
from typing_extensions import Any, override

from .requests import Response, request


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
        """Parse items and return them."""
        parsed_items: list[Any] = []
        for item in track(parsable_items, disable=not show_progress):
            parsed_item = self.parse_item_wrapper(item)
            parsed_items.append(parsed_item)
        return parsed_items

    def parse_item_wrapper(self, item: Any) -> Any:
        """
        Override this to control what happens around `self.parse_item()` everytime it's called.

        This way related subclasses can have the same auxillary things happen on calls to `parse_item`
        while having different `parse_item` implementations.

        When overriding, you should call `parse_item`, pass it `item`, and return the result.

        Without overriding, this function simply calls and returns `self.parse_item(item)`.

        basic e.g.:
        >>> def parse_item_wrapper(self, item:Any)->Any:
        >>>   try:
        >>>     return self.parse_item(item)
        >>>   except Exception as e:
        >>>     print(e)
        """
        return self.parse_item(item)


class ScraperData:
    def __init__(self):
        self.timer: Timer = Timer()
        self.success_count: int = 0
        self.fail_count: int = 0
        self.failed_to_get_parsable_items: bool = False
        self.unexpected_failure_occured: bool = False

    @property
    def had_failures(self) -> bool:
        """`True` if getting parsable items, parsing items, or unexpected failures occured."""
        return (
            (self.fail_count > 0)
            or self.failed_to_get_parsable_items
            or self.unexpected_failure_occured
        )


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
        """Should fetch and return the raw data to be scraped.

        Typically would request a webpage and return the response."""
        raise NotImplementedError

    def request(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """
        Note: For convenience, passes this instances logger to the request functions

        Constructs and sends a :class:`Request <Request>`.

        `url`: URL for the new :class:`Request` object.
        `method`: method for the new :class:`Request` object: ``GET``, ``OPTIONS``, ``HEAD``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``.

        * `retry_count`: The number of times to retry a failed request.
        * `retry_backoff_factor`: For each failed request, the time before retrying will be `retry_backoff_factor * (2 ** retry_number)`
        * `retry_on_codes`: List of status codes to retry requests on. Default is `[408, 413, 444, 499, 500, 502, 503, 504]`.

        `params`: dict, list of tuples or bytes to send in the query string for the :class:`Request`.
        `data`: dict, list of tuples, bytes, or file-like object to send in the body of the :class:`Request`.
        `json`: A JSON serializable Python object to send in the body of the :class:`Request`.
        `headers`: dict of HTTP Headers to send with the :class:`Request`. The `User-Agent` header will be randomized unless supplied.
        `cookies`: dict or CookieJar object to send with the :class:`Request`.
        `files`: dict of ``'name': file-like-objects`` (or ``{'name': file-tuple}``) for multipart encoding upload.
            ``file-tuple`` can be a 2-tuple ``('filename', fileobj)``, 3-tuple ``('filename', fileobj, 'content_type')``
            or a 4-tuple ``('filename', fileobj, 'content_type', custom_headers)``, where ``'content-type'`` is a string
            defining the content type of the given file and ``custom_headers`` a dict-like object containing additional headers
            to add for the file.
        `auth`: Auth tuple to enable Basic/Digest/Custom HTTP Auth.
        `timeout`: float | tuple, How many seconds to wait for the server to send data
            before giving up, as a float, or a :ref:`(connect timeout, read
            timeout) <timeouts>` tuple.
        `allow_redirects`: bool. Enable/disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection. Defaults to ``True``.
        `proxies`: dict mapping protocol to the URL of the proxy.
        `verify`: Either a bool, in which case it controls whether we verify
                the server's TLS certificate, or a string, in which case it must be a path
                to a CA bundle to use. Defaults to ``True``.
        `stream`: if ``False``, the response content will be immediately downloaded.
        `cert`: if String, path to ssl client cert file (.pem). If Tuple, ('cert', 'key') pair.
        """
        kwargs["logger"] = self.logger
        return request(*args, **kwargs)

    @override
    def parse_item_wrapper(self, item: Any) -> Any:
        """Returns a parsed item or `None` if parsing failed."""
        try:
            parsed_item = self.parse_item(item)
            self.success_count += 1
            return parsed_item
        except Exception as e:
            self.logger.exception("Failure to parse item:")
            self.logger.error(str(item))
            self.fail_count += 1
            return None

    def scrape(self, parse_items_prog_bar_display: bool = False):
        """Run the scraper:
        1. prescrape chores
        2. get parsable items
        3. parse items
        4. store items
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
                    self.parsed_items = self.parse_items(
                        self.parsable_items, parse_items_prog_bar_display
                    )
                    self.logger.info(
                        f"Scrape completed in {self.timer.elapsed_str} with {self.success_count} successes and {self.fail_count} failures."
                    )
            for item in self.parsed_items:
                self.store_item(item)
        except Exception:
            self.unexpected_failure_occured = True
            self.logger.exception(f"Unexpected failure in {self.name}:scrape()")
        self.postscrape_chores()
        loggi.close(self.logger)
