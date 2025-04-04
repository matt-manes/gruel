import abc
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from threading import BoundedSemaphore

import loggi
import scrapetools
from noiftimer import Timer
from pathier import Pathier, Pathish
from printbuddies import ColorMap, Progress, TimerColumn
from rich.console import Console
from rich.progress import ProgressColumn, TaskID
from seleniumuser.seleniumuser import User
from typing_extensions import Any, Callable, Sequence, override

from .core import ChoresMixin, ParserMixin, ScraperMetricsMixin
from .models import Url
from .requests import Response, SeleniumResponse, request

root = Pathier(__file__).parent
color_map = ColorMap()
console = Console(style="pink1")


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
    def cancelled_workers(self) -> list[Future[Any]]:
        """Returns a list of cancelled workers."""
        return [worker for worker in self.workers if worker.cancelled()]

    @property
    def completed_workers(self) -> list[Future[Any]]:
        """Returns a list of completed workers."""
        return [
            worker
            for worker in self.workers
            if worker.done() and worker not in self.cancelled_workers
        ]

    @property
    def finished_workers(self) -> list[Future[Any]]:
        """Returns a list of completed workers."""
        return [worker for worker in self.workers if worker.done()]

    @property
    def num_cancelled_workers(self) -> int:
        return len(self.cancelled_workers)

    @property
    def num_completed_workers(self) -> int:
        return len(self.completed_workers)

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
        return self.max_workers - self.num_running_workers

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
            console.print(f"{color_map.o1}Attempting to cancel remaining workers...")
            self.cancel_workers()
        if running_workers := self.running_workers:
            console.print(
                f"{color_map.c}Waiting for {color_map.sg2}{len(running_workers)}[/] workers to finish..."
            )
            num_running: Callable[
                [list[Future[Any]]], str
            ] = lambda n: f"[pink1]{len(n)} running workers..."
            with Console().status(
                num_running(running_workers), spinner="arc", spinner_style="deep_pink1"
            ) as c:
                while running_workers := self.running_workers:
                    c.update(num_running(running_workers))


class UrlManager:
    """Manages crawled and uncrawled urls."""

    def __init__(self):
        self._crawled: set[Url] = set()  # deque[Url] = deque()
        self._uncrawled: deque[Url] = deque()
        # Separate lists for schemeless urls so we don't have to restrip the whole list
        # everytime we check if a url is already in the list
        self._schemeless: set[Url] = set()  # deque[Url] = deque()
        self._schemeless_crawled: set[Url] = set()  # deque[Url] = deque()

    @property
    def crawled(self) -> set[Url]:
        """Urls that have been or are currently being crawled."""
        return self._crawled

    @property
    def total(self) -> int:
        """Total crawled and uncrawled urls."""
        return len(self._schemeless)

    @property
    def uncrawled(self) -> deque[Url]:
        """Urls that have yet to be crawled."""
        return self._uncrawled

    def add_urls(self, urls: Sequence[Url]):
        """Append `urls` to `self.uncrawled_urls`."""
        for url in urls:
            self._uncrawled.append(url)

    def filter_urls(self, urls: Sequence[Url]) -> deque[Url]:
        """
        Filters out:
          * duplicate urls
          * already crawled urls
          * urls with schemes other than `http` and `https`
        """
        filtered_urls: deque[Url] = deque()
        for url in set(urls):
            if not url.scheme.startswith("http"):
                continue
            # Prevents duplicates where only diff is http vs https
            schemeless_url = url.schemeless
            if schemeless_url not in self._schemeless:
                self._schemeless.add(schemeless_url)
                filtered_urls.append(url)
        return filtered_urls

    def get_uncrawled(self) -> Url | None:
        """Get an uncrawled url from the front of the list.

        Returns `None` if uncrawled list is empty."""
        # while self._uncrawled:
        if self._uncrawled:
            url = self._uncrawled.popleft()
            # schemeless_url = url.schemeless
            # double check url hasn't been crawled (cause threading)
            # if schemeless_url not in self._schemeless_crawled:
            self._schemeless_crawled.add(url.schemeless)
            self._crawled.add(url)
            return url
        return None


class CrawlLimit(abc.ABC):
    @property
    @abc.abstractmethod
    def exceeded(self) -> bool:
        """Return whether this limit has been exceeded or not."""

    def __str__(self) -> str:
        """Customize the message used when this limit is exceeded."""
        return "Scraper limits exceeded."

    def __rich__(self) -> str:
        return self.__str__()


class MaxDepthLimit(CrawlLimit):
    def __init__(self, max_depth: int | None, thread_manager: ThreadManager):
        self.max_depth = max_depth
        self.thread_manager = thread_manager

    @property
    @override
    def exceeded(self) -> bool:
        if self.max_depth:
            return self.thread_manager.num_completed_workers >= self.max_depth
        return False

    @property
    def should_block(self) -> bool:
        """Whether adding new workers should be blocked."""
        if self.max_depth:
            return self.thread_manager.num_workers >= self.max_depth
        return False

    def __str__(self) -> str:
        return f"Max depth of {self.max_depth} exceeded."

    def __rich__(self) -> str:
        return f"Max depth of [bright_red]{self.max_depth}[/] exceeded."


class MaxTimeLimit(CrawlLimit):
    def __init__(self, max_time: float | None, timer: Timer):
        self.max_time = max_time
        self.timer = timer

    @property
    @override
    def exceeded(self) -> bool:
        if self.max_time:
            return self.timer.elapsed > self.max_time
        return False

    def __str__(self) -> str:
        return f"Max time of {self.timer.format_time(self.max_time) if self.max_time else 'None'} exceeded."

    def __rich__(self) -> str:
        return f"Max time of [bright_red]{self.timer.format_time(self.max_time) if self.max_time else 'None'}[/] exceeded."


class LimitCheckerMixin:
    @staticmethod
    def get_limits(obj: Any) -> list[CrawlLimit]:
        """Returns a list of `CrawlLimit` instances from `obj`."""
        return [
            member
            for member in obj.__dict__.values()
            if issubclass(type(member), CrawlLimit)
        ]

    @property
    def limits(self) -> list[CrawlLimit]:
        """Returns a list of `CrawlLimit` objects belonging to this instance."""
        return self.get_limits(self)

    @property
    def limits_exceeded(self) -> bool:
        return any(limit.exceeded for limit in self.limits)

    @property
    def exceeded_limits(self) -> list[CrawlLimit]:
        return [limit for limit in self.limits if limit.exceeded]


class CrawlScraper(ParserMixin, ScraperMetricsMixin, loggi.LoggerMixin, ChoresMixin):
    def __init__(self):
        super().__init__()

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
            parsed_items = self.parse_items(parsable_items)
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


class Crawler(loggi.LoggerMixin, ChoresMixin, LimitCheckerMixin):
    """A mutli-threaded web crawler framework."""

    def __init__(
        self,
        scrapers: Sequence[CrawlScraper] = [],
        max_depth: int | None = None,
        max_time: float | None = None,
        log_name: str | int | loggi.LogName = loggi.LogName.CLASSNAME,
        log_dir: Pathish = "logs",
        max_threads: int = 3,
        same_site_only: bool = True,
        custom_url_manager: UrlManager | None = None,
    ):
        """
        Create a `Crawler` instance.

        #### :params:
        * `scraper`: An optional list of `CrawlScraper` or child instances to implement what happens for each crawled page.
        (NOTE: The `scraper` instances will have its logger set to this crawler's logger.)
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
        self.thread_manager = ThreadManager(max_threads)
        self.timer = Timer()
        self.max_time = MaxTimeLimit(max_time, self.timer)
        self.max_depth = MaxDepthLimit(max_depth, self.thread_manager)
        self.same_site_only = same_site_only
        self._scrapers: list[CrawlScraper] = []
        self._was_cancelled = False
        self.url_manager_lock = BoundedSemaphore()
        for scraper in scrapers:
            self.register_scraper(scraper)

    @property
    def display_columns(self) -> list[ProgressColumn]:
        """The display columns to be used by the progress bar."""
        columns = list(Progress.get_default_columns())
        columns[3] = TimerColumn(True)
        return columns

    @property
    def finished(self) -> bool:
        """Returns `True` if there are no uncrawled urls and no unfinished threads."""
        with self.url_manager_lock:
            return not (
                self.url_manager.uncrawled or self.thread_manager.unfinished_workers
            )

    @property
    @override
    def limits(self) -> list[CrawlLimit]:
        limits = super().limits
        # ? Should scraper limits only halt that particular scraper or the whole crawl
        # ? Separate class or flag to have both options
        for scraper in self.scrapers:
            limits.extend(self.get_limits(scraper))
        return limits

    @property
    def scrapers(self) -> list[CrawlScraper]:
        """The scraper being used by this crawler."""
        return self._scrapers

    def register_scraper(self, scraper: CrawlScraper):
        """
        Add this `scraper` instance to the list of scrapers.

        This `Crawler` instance's logger will be passed to the logger attribute of `scraper`.
        """
        scraper.logger = self.logger
        self._scrapers.append(scraper)

    @property
    def starting_url(self) -> Url:
        """The starting url of the last crawl."""
        return self._starting_url

    @property
    def was_cancelled(self) -> bool:
        """Returns if this crawler was intentionally terminated (e.g. keyboard interrupt)."""
        return self._was_cancelled

    def _dispatch_workers(self, executor: ThreadPoolExecutor):
        """Dispatch workers if there are open slots and new urls to be scraped."""
        while self.thread_manager.open_slots and not self.max_depth.should_block:
            with self.url_manager_lock:
                url = self.url_manager.get_uncrawled()
            if url:
                self.thread_manager.add_future(executor.submit(self._handle_page, url))
            else:
                break

    def _handle_page(self, url: Url):
        self.logger.info(f"Scraping `{url}`.")
        response = self.request_page(url)
        urls = self.extract_crawlable_urls(response.get_linkscraper())
        with self.url_manager_lock:
            new_urls = self.url_manager.filter_urls(urls)
        self.logger.info(f"Found {len(new_urls)} new urls on `{url}`.")
        with self.url_manager_lock:
            self.url_manager.add_urls(new_urls)
        for scraper in self.scrapers:
            scraper.scrape(response)

    def print_exceeded_limits(self):
        for limit in self.exceeded_limits:
            self.logger.info(str(limit))
            console.print(limit)

    def _update_progress(self, progress: Progress, task: TaskID):
        num_completed = self.thread_manager.num_completed_workers
        total = self.thread_manager.num_workers + len(self.url_manager.uncrawled)
        progress.update(
            task,
            total=total,
            completed=num_completed,
            description=f"{num_completed}/{total} urls",
        )

    def crawl(self, starting_url: str):
        """Start crawling at `starting_url`."""
        self._starting_url = Url(starting_url)
        self.url_manager.add_urls([self._starting_url])
        self.prescrape_chores()
        with ThreadPoolExecutor(self.thread_manager.max_workers) as executor:
            try:
                with Progress(*self.display_columns) as progress:
                    crawler = progress.add_task()
                    while not self.finished and not self.limits_exceeded:
                        self._dispatch_workers(executor)
                        self._update_progress(progress, crawler)
                        time.sleep(0.1)
                    self._update_progress(progress, crawler)
                self.print_exceeded_limits()
            except KeyboardInterrupt:
                self._was_cancelled = True
            except Exception as e:
                print(str(e))
                self.thread_manager.shutdown()
                self.logger.close()
                raise e
            self.thread_manager.shutdown()
        self.postscrape_chores()
        self.logger.close()

    def extract_crawlable_urls(self, linkscraper: scrapetools.LinkScraper) -> list[Url]:
        """Returns a list of urls that can be added to the crawl list."""
        urls = [
            Url(link).fragmentless
            for link in linkscraper.get_links(
                "page",
                excluded_links=linkscraper.get_links("img"),
                same_site_only=self.same_site_only,
            )
        ]
        if self.same_site_only:
            urls = [url for url in urls if self.starting_url.is_same_site(url)]
        return urls

    @override
    def postscrape_chores(self):
        self.timer.stop()
        self.logger.info(f"Crawl completed in {self.timer.elapsed_str}.")
        console.print(
            f"{color_map.sg3}Crawl completed in {color_map.go1}{self.timer.elapsed_str}[/]."
        )
        for scraper in self.scrapers:
            scraper.postscrape_chores()

    @override
    def prescrape_chores(self):
        self.timer.start()
        for scraper in self.scrapers:
            scraper.prescrape_chores()
        start_time = f"{datetime.now():%H:%M:%S}"
        self.logger.info(f"Starting crawl ({start_time}) at {self.starting_url}")
        console.print(
            f"Starting crawl ({color_map.go1}{start_time}[/]) at {color_map.or_}{self.starting_url}"
        )

    def request_page(self, url: Url) -> Response:
        """Make a request to `url` and return the page."""
        return request(url.address, logger=self.logger)


class SeleniumCrawler(Crawler):
    """
    Requires Firefox to be installed and for `geckodriver.exe` to be in system PATH.

    Currently `max_threads` is hardcoded to `1`.
    """

    @override
    def __init__(
        self,
        scrapers: Sequence[CrawlScraper] = [],
        max_depth: int | None = None,
        max_time: float | None = None,
        log_name: str | int | loggi.LogName = loggi.LogName.CLASSNAME,
        log_dir: Pathish = "logs",
        same_site_only: bool = True,
        custom_url_manager: UrlManager | None = None,
        headless: bool = True,
        download_dir: Pathish | None = None,
    ):
        super().__init__(
            scrapers,
            max_depth,
            max_time,
            log_name,
            log_dir,
            1,
            same_site_only,
            custom_url_manager,
        )
        if download_dir:
            download_dir = Pathier(download_dir)
        self.user = User(headless, download_dir=Pathier(download_dir) if download_dir else None)  # type: ignore

    @override
    def request_page(self, url: Url) -> SeleniumResponse:
        self.user.get(url.address)
        return SeleniumResponse.from_selenium_user(self.user)

    @override
    def crawl(self, starting_url: str):
        super().crawl(starting_url)
        self.user.close_browser()
