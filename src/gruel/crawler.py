import abc
import time
import urllib.parse
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from functools import lru_cache

import loggi
import scrapetools
from noiftimer import Timer
from pathier import Pathier, Pathish
from printbuddies import Progress, TimerColumn
from rich import print
from rich.console import Console
from rich.progress import ProgressColumn
from typing_extensions import Any, Callable, Sequence, override

from .core import ChoresMixin, ParserMixin, ScraperMetricsMixin
from .requests import Response, request

root = Pathier(__file__).parent


class ThreadManager:
    """
    Manages workers when used with `concurrent.futures.ThreadPoolExecutor`.

    Pass the returned future from `concurrent.futures.ThreadPoolExecutor.submit()` to `add_future()`.

    e.g.
    >>> list_of_functions = [some_function for i in range(1000)]
    >>> thread_manager = ThreadManager()
    >>> with concurrent.futures.ThreadPoolExecutor() as executor:
    >>>   while list_of_functions or thread_manager.unfinished_workers:
    >>>     if thread_manager.open_slots:
    >>>       future = executor.submit(list_of_functions.pop())
    >>>       thread_manager.add_future(future)
    """

    def __init__(self, max_workers: int):
        self.max_workers = max_workers
        self.workers: list[Future[Any]] = []

    @property
    def finished_workers(self) -> list[Future[Any]]:
        """Returns a list of completed workers."""
        return [worker for worker in self.workers if worker.done()]

    @property
    def num_finished_workers(self) -> int:
        return len(self.finished_workers)

    @property
    def num_running_workers(self) -> int:
        return len(self.running_workers)

    @property
    def num_unfinished_workers(self) -> int:
        return len(self.unfinished_workers)

    @property
    def num_workers(self) -> int:
        return len(self.workers)

    @property
    def open_slots(self) -> int:
        """Returns the difference between max_workers and number of running workers."""
        return self.max_workers - len(self.running_workers)

    @property
    def running_workers(self) -> list[Future[Any]]:
        """Returns a list of currently executing futures."""
        return [worker for worker in self.workers if worker.running()]

    @property
    def unfinished_workers(self) -> list[Future[Any]]:
        """Returns a list of unfinished futures."""
        return [worker for worker in self.workers if not worker.done()]

    def add_future(self, future: Future[Any]):
        """Add a future to `self.workers`."""
        self.workers.append(future)

    def cancel_workers(self):
        """Attempt to cancel any unfinished futures."""
        for worker in self.unfinished_workers:
            worker.cancel()

    def shutdown(self):
        """Attempt to cancel remaining futures and wait for running futures to finish."""
        if self.num_finished_workers < self.num_workers:
            print("Attempting to cancel remaining workers...")
            self.cancel_workers()
        if running_workers := self.running_workers:
            print(f"Waiting for {len(running_workers)} workers to finish...")
            num_running: Callable[[list[Future[Any]]], str] = (
                lambda n: f"[pink1]{len(n)} running workers..."
            )
            with Console().status(
                num_running(running_workers), spinner="arc", spinner_style="deep_pink1"
            ) as c:
                while running_workers := self.running_workers:
                    c.update(num_running(running_workers))


class UrlManager:
    """Manages crawled and uncrawled urls."""

    def __init__(self):
        self._crawled: deque[str] = deque()
        self._uncrawled: deque[str] = deque()
        # Separate lists for schemeless urls so we don't have to restrip the whole list
        # everytime we check if a url is already in the list
        self._schemeless: deque[str] = deque()
        self._schemeless_crawled: deque[str] = deque()

    @property
    def crawled(self) -> deque[str]:
        """Urls that have been or are currently being crawled."""
        return self._crawled

    @property
    def total(self) -> int:
        """Total crawled and uncrawled urls."""
        return len(self._schemeless)

    @property
    def uncrawled(self) -> deque[str]:
        """Urls that have yet to be crawled."""
        return self._uncrawled

    def add_urls(self, urls: Sequence[str]):
        """Append `urls` to `self.uncrawled_urls`."""
        for url in urls:
            self._uncrawled.append(url)

    def filter_urls(self, urls: Sequence[str]) -> deque[str]:
        """Filters out duplicate urls and urls already in crawled or uncrawled."""
        filtered_urls: deque[str] = deque()
        for url in set(urls):
            url = url.strip("/")
            # Prevents duplicates where only diff is http vs https
            schemeless_url = self.strip_scheme(url)
            if schemeless_url not in self._schemeless:
                self._schemeless.append(schemeless_url)
                filtered_urls.append(url)
        return filtered_urls

    def get_uncrawled(self) -> str | None:
        """Get an uncrawled url from the front of the list.

        Returns `None` if uncrawled list is empty."""
        while self._uncrawled:
            url = self._uncrawled.popleft()
            schemeless_url = self.strip_scheme(url)
            # double check url hasn't been crawled (cause threading)
            if schemeless_url not in self._schemeless_crawled:
                self._schemeless_crawled.append(schemeless_url)
                self._crawled.append(url)
                return url
        return None

    @lru_cache(None)
    def strip_scheme(self, url: str) -> str:
        """Remove the scheme from `url`."""
        parts = urllib.parse.urlsplit(url)
        return urllib.parse.urlunsplit(
            ["", parts.netloc, parts.path, parts.query, parts.fragment]
        )


class CrawlScraper(ParserMixin, ScraperMetricsMixin, loggi.LoggerMixin, ChoresMixin):
    def __init__(self):
        super().__init__()

    @property
    def limits_exceeded(self) -> bool | str:
        """Put any scraper conditions here that should tell the crawler to stop crawling.

        Can choose to return a message string detailing what limit was exceeded instead of returning `True`.
        """
        return False

    @override
    def flush_items(self):
        self.parsable_items: deque[Any] = deque()  # type: ignore
        self.parsed_items: deque[Any] = deque()  # type: ignore

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

    def scrape(self, source: Response):
        """
        Scrape `source` and store results.
        """
        try:
            parsable_items = self.get_parsable_items(source)
            self.logger.info(
                f"Returned {len(parsable_items)} parsable items from `{source.url}`."
            )
        except Exception as e:
            self.logger.exception(f"Error getting parsable items from `{source.url}`.")
        else:
            # Since likely usage is multithreaded,
            # don't want to pull from shared `self.parsed_items` container
            # when storing items
            parsed_items = self.parse_items(parsable_items, False)
            for item in parsed_items:
                self.parsed_items.append(item)
            self.store_items(parsed_items)

    @abc.abstractmethod
    def store_items(self, items: Sequence[Any]) -> None:
        """
        Unless the crawler using this scraper has `max_threads` set to 1,
        storage method/destination should be thread safe.

        Override this method with `pass` or `...` if you'd rather use a different function
        to store all parsed items after the crawl is completed.
        """


class Crawler(loggi.LoggerMixin, ChoresMixin):
    """A mutli-threaded web crawler framework."""

    def __init__(
        self,
        scraper: CrawlScraper | None = None,
        max_depth: int | None = None,
        max_time: float | None = None,
        log_name: str | int | loggi.LogName = loggi.LogName.CLASSNAME,
        log_dir: Pathish = "logs",
        max_threads: int = 5,
        same_site_only: bool = True,
        custom_url_manager: UrlManager | None = None,
    ):
        """
        Create a `Crawler` instance.

        #### :params:
        * `scraper`: An optional `CrawlScraper` or child instance to implement what happens for each crawled page.
        (NOTE: The `scraper` instance will have its logger set to this crawler's logger.)
        * `max_depth`: The maximum number of pages to crawl.
        * `max_time`: The maximum amount of time to crawl in seconds.
        * `log_name`: The file stem for the log file. Defaults to this instance's class name.
        * `log_dir`: The directory to write the log file to. Defaults to "logs".
        * `max_threads`: The max number of threads to use.
        * `same_site_only`: When `True`, only urls pointing to the same website will be added to the crawl queue.
        * `custom_url_manager`: An optional instance that inherits from `gruel.UrlManager`.
        """
        self.init_logger(log_name, log_dir)
        self.url_manager = custom_url_manager or UrlManager()
        self.max_time = max_time
        self.max_depth = max_depth
        self.timer = Timer()
        self.same_site_only = same_site_only
        self.thread_manager = ThreadManager(max_threads)
        self._scraper = None
        if scraper:
            self.scraper = scraper

    @property
    def display_columns(self) -> list[ProgressColumn]:
        """The display columns to be used by the progress bar."""
        columns = list(Progress.get_default_columns())
        columns[3] = TimerColumn(True)
        return columns

    @property
    def finished(self) -> bool:
        """Returns `True` if there are no uncrawled urls and no unfinished threads."""
        return not (
            self.url_manager.uncrawled or self.thread_manager.unfinished_workers
        )

    @property
    def limits_exceeded(self) -> bool | str:
        """
        Check if crawl limits have been exceeded.

        If they have, return a message about the limit that was exceeded.
        """
        message = None
        if self.max_depth_exceeded:
            message = f"Max depth of {self.max_depth} exceeded."
        elif self.max_time_exceeded:
            message = f"Max time of {self.timer.format_time(self.max_time)} exceeded."  # type: ignore
        if self.scraper and (result := self.scraper.limits_exceeded):
            if isinstance(result, str):
                message = result
            else:
                message = "Scraper limits exceeded."
        if message:
            return message
        return False

    @property
    def max_depth_exceeded(self) -> bool:
        """Returns `True` if the crawl has a max depth and it has been exceeded."""
        if not self.max_depth:
            return False
        return self.thread_manager.num_finished_workers > self.max_depth

    @property
    def max_time_exceeded(self) -> bool:
        """Returns `True` if the crawl has a max time and it has been exceeded."""
        if not self.max_time:
            return False
        else:
            return self.timer.elapsed > self.max_time

    @property
    def scraper(self) -> CrawlScraper | None:
        """The scraper being used by this crawler."""
        return self._scraper

    @scraper.setter
    def scraper(self, scraper: CrawlScraper):
        """Set this scraper as the scraper to use and set this crawler's logger to be the scraper's logger."""
        self._scraper = scraper
        self._scraper.logger = self.logger

    @property
    def starting_url(self) -> str:
        """The starting url of the last crawl."""
        return self._starting_url

    def _dispatch_workers(self, executor: ThreadPoolExecutor):
        """Dispatch workers if there are open slots and new urls to be scraped."""
        while self.thread_manager.open_slots:
            url = self.url_manager.get_uncrawled()
            if url:
                self.thread_manager.add_future(executor.submit(self._handle_page, url))
            else:
                break

    def _handle_page(self, url: str):
        self.logger.info(f"Scraping `{url}`.")
        response = self.request_page(url)
        urls = self.extract_crawlable_urls(response.get_linkscraper())
        new_urls = self.url_manager.filter_urls(urls)
        self.logger.info(f"Found {len(new_urls)} new urls on `{url}`.")
        self.url_manager.add_urls(new_urls)
        if self.scraper:
            self.scraper.scrape(response)

    def crawl(self, starting_url: str):
        """Start crawling at `starting_url`."""
        self._starting_url = starting_url
        self.url_manager.add_urls([starting_url])
        self.prescrape_chores()
        with ThreadPoolExecutor(self.thread_manager.max_workers) as executor:
            try:
                with Progress(*self.display_columns) as progress:
                    crawler = progress.add_task()
                    while not self.finished and (not self.limits_exceeded):
                        self._dispatch_workers(executor)
                        num_finished = self.thread_manager.num_finished_workers
                        total = self.thread_manager.num_workers + len(
                            self.url_manager.uncrawled
                        )
                        progress.update(
                            crawler,
                            total=total,
                            completed=num_finished,
                            description=f"{num_finished}/{total} urls",
                        )
                        time.sleep(0.1)
                if message := self.limits_exceeded:
                    self.logger.logprint(str(message))
            except KeyboardInterrupt:
                self.thread_manager.shutdown()
            except Exception as e:
                raise e
            self.thread_manager.shutdown()
        self.postscrape_chores()
        self.logger.close()

    def extract_crawlable_urls(self, linkscraper: scrapetools.LinkScraper) -> list[str]:
        """Returns a list of urls that can be added to the crawl list."""
        return linkscraper.get_links(
            "page",
            excluded_links=linkscraper.get_links("img"),
            same_site_only=self.same_site_only,
        )

    @override
    def postscrape_chores(self):
        self.timer.stop()
        self.logger.logprint(f"Crawl completed in {self.timer.elapsed_str}.")
        if self.scraper:
            self.scraper.postscrape_chores()

    @override
    def prescrape_chores(self):
        self.timer.start()
        if self.scraper:
            self.scraper.prescrape_chores()
        self.logger.logprint(
            f"Starting crawl ({datetime.now():%H:%M:%S}) at {self.starting_url}"
        )

    def request_page(self, url: str) -> Response:
        """Make a request to `url` and return the page."""
        return request(url, logger=self.logger)
