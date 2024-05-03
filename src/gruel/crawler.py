import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
import loggi
import scrapetools
from noiftimer import Timer
from pathier import Pathier, Pathish
from printbuddies import Progress, TimerColumn
from rich import print
from rich.console import Console
from typing_extensions import Any, Callable, override, Sequence, Type
from .core import ChoresMixin, ParserMixin, Gruel
from .requests import Response, request
import urllib.parse
from functools import lru_cache

root = Pathier(__file__).parent


class ThreadManager:
    def __init__(self, max_workers: int):
        self.max_workers = max_workers
        self.workers: list[Future[Any]] = []

    @property
    def finished_workers(self) -> list[Future[Any]]:
        """Returns a list of completed workers."""
        return [worker for worker in self.workers if worker.done()]

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
        if len(self.finished_workers) < len(self.workers):
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
    def __init__(self):
        self._crawled: deque[str] = deque()
        self._uncrawled: deque[str] = deque()
        # Separate lists for schemeless urls so we don't have to restrip the whole list
        # everytime we check if a url is already in the list
        self._schemeless: deque[str] = deque()
        self._schemeless_crawled: deque[str] = deque()

    @property
    def crawled(self) -> deque[str]:
        return self._crawled

    @property
    def uncrawled(self) -> deque[str]:
        return self._uncrawled

    @property
    def total(self) -> int:
        """Total crawled and uncrawled urls."""
        return len(self._schemeless)

    @lru_cache(None)
    def strip_scheme(self, url: str) -> str:
        """Remove the scheme from `url`."""
        parts = urllib.parse.urlsplit(url)
        return urllib.parse.urlunsplit(
            ["", parts.netloc, parts.path, parts.query, parts.fragment]
        )

    def filter_urls(self, urls: Sequence[str]) -> deque[str]:
        """Filters out duplicate urls and urls already in crawled or uncrawled."""
        filtered_urls: deque[str] = deque()
        for url in set(urls):
            # Prevents duplicates where only diff is http vs https
            schemeless_url = self.strip_scheme(url)
            if schemeless_url not in self._schemeless:
                self._schemeless.append(schemeless_url)
                filtered_urls.append(url)
        return filtered_urls

    def add_urls(self, urls: Sequence[str]):
        """Append `urls` to `self.uncrawled_urls`."""
        for url in urls:
            self._uncrawled.append(url)

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


class CrawlScraper(loggi.LoggerMixin, ParserMixin):

    @property
    def limits_exceeded(self) -> bool | str:
        """Put any scraper conditions here that should tell the crawler to stop crawling.

        Can choose to return a message string detailing what limit was exceeded instead of returning `True`.
        """
        return False

    def scrape(self, source: Response, **kwargs: Any):
        try:
            parsable_items = self.get_parsable_items(source)
            self.logger.info(
                f"Returned {len(parsable_items)} parsable items from `{source.url}`."
            )
        except Exception as e:
            self.logger.exception(f"Error getting parsable items from `{source.url}`.")
        else:
            parsable_items = self.parse_items(parsable_items, False)


class Crawler(loggi.LoggerMixin, ChoresMixin):
    @override
    def __init__(
        self,
        scraper: CrawlScraper | None = None,
        max_depth: int | None = None,
        max_time: float | None = None,
        name: str | int | loggi.LogName = loggi.LogName.CLASSNAME,
        log_dir: Pathish = "logs",
        max_threads: int = 3,
        same_site_only: bool = True,
        url_manager_class: Type[UrlManager] = UrlManager,
    ):
        self.init_logger(name, log_dir)
        self.urls = url_manager_class()
        self.max_time = max_time
        self.max_depth = max_depth
        self.timer = Timer()
        self.same_site_only = same_site_only
        self.thread_manager = ThreadManager(max_threads)
        self._scraper = scraper
        if self.scraper:
            self.scraper.logger = self.logger

    @property
    def scraper(self) -> CrawlScraper | None:
        return self._scraper

    @property
    def finished(self) -> bool:
        """Returns `True` if there are no uncrawled urls and no unfinished threads."""
        return not (self.urls.uncrawled or self.thread_manager.unfinished_workers)

    @property
    def limits_exceeded(self) -> bool:
        """Check if crawl limits have been exceeded."""
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
            print()
            self.logger.logprint(message)
            return True
        return False

    @property
    def max_depth_exceeded(self) -> bool:
        """Returns `True` if the crawl has a max depth and it has been exceeded."""
        if not self.max_depth:
            return False
        return len(self.thread_manager.finished_workers) > self.max_depth

    @property
    def max_time_exceeded(self) -> bool:
        """Returns `True` if the crawl has a max time and it has been exceeded."""
        if not self.max_time:
            return False
        else:
            return self.timer.elapsed > self.max_time

    @property
    def starting_url(self) -> str:
        return self.urls.crawled[0]

    def _dispatch_workers(self, executor: ThreadPoolExecutor):
        """Dispatch workers if there are open slots and new urls to be scraped."""
        while self.thread_manager.open_slots:
            url = self.urls.get_uncrawled()
            if url:
                self.thread_manager.add_future(executor.submit(self._handle_page, url))
            else:
                break

    def crawl(self, starting_url: str):
        self.timer.start()
        self.urls.add_urls([starting_url])
        self.prescrape_chores()
        self.logger.logprint(
            f"Starting crawl ({datetime.now():%H:%M:%S}) at {self.starting_url}"
        )
        with ThreadPoolExecutor(self.thread_manager.max_workers) as executor:
            columns = list(Progress.get_default_columns())
            columns[3] = TimerColumn(True)
            with Progress(*columns) as progress:
                crawler = progress.add_task()
                while not self.finished and (not self.limits_exceeded):
                    self._dispatch_workers(executor)
                    num_finished = len(self.thread_manager.finished_workers)
                    total = len(self.thread_manager.workers) + len(self.urls.uncrawled)
                    progress.update(
                        crawler,
                        total=total,
                        completed=num_finished,
                        description=f"{num_finished}/{total} urls",
                    )
                    time.sleep(0.1)
            self.thread_manager.shutdown()
        self.postscrape_chores()

    def extract_crawlable_urls(self, linkscraper: scrapetools.LinkScraper) -> list[str]:
        return linkscraper.get_links(
            "page",
            excluded_links=linkscraper.get_links("img"),
            same_site_only=self.same_site_only,
        )

    def request_page(self, url: str) -> Response:
        """Make a request to `url` and return the page."""
        return request(url, logger=self.logger)

    def _handle_page(self, url: str):
        self.logger.info(f"Scraping `{url}`.")
        response = self.request_page(url)
        urls = self.extract_crawlable_urls(response.get_linkscraper())
        new_urls = self.urls.filter_urls(urls)
        self.logger.info(f"Found {len(new_urls)} new urls on `{url}`.")
        self.urls.add_urls(new_urls)
        if self.scraper:
            self.scraper.scrape(response)
