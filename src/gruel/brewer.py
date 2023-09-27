from younotyou import younotyou
from concurrent.futures import ThreadPoolExecutor
from gruel import Gruel
from pathier import Pathier, Pathish
import importlib
from printbuddies import ProgBar
import inspect
from typing import Any
import time
import logging
import argparse


class Brewer:
    def __init__(
        self,
        subgruel_classes: list[str],
        file_exclude_patterns: list[str] = [],
        scan_path: Pathish = Pathier.cwd(),
        file_include_patterns: list[str] = ["*.py"],
        recursive: bool = True,
    ):
        """Run `Gruel` scrapers.

        #### :params:

        `subgruel_classes`: A list of class names for scrapers that should be loaded.
        In order to be loaded, a scraper class must have a name in this list and have `Gruel` somewhere in its inheritance hierarchy.

        `file_exclude_patterns`: Files that match these patterns will not be scanned.

        `scan_path`: The path to scan for scraper classes.

        `file_include_patterns`: Files that match these patterns will be scanned.

        `recursive`: Whether the scan should be recursive or not.

        >>> brewer = Brewer(["VenueScraper"], ["*template*", "*giggruel*"], "scrapers")
        >>> brewer.brew()"""
        self._init_logger()
        self.subgruel_classes = subgruel_classes
        self.file_exclude_patterns = file_exclude_patterns
        self.file_include_patterns = file_include_patterns
        self.scan_path = Pathier(scan_path)
        self.recursive = recursive

    def _init_logger(self):
        self.logger = logging.getLogger(Pathier(__file__).stem)
        if not self.logger.hasHandlers():
            handler = logging.FileHandler(Pathier(__file__).stem + ".log")
            handler.setFormatter(
                logging.Formatter(
                    "{levelname}|-|{asctime}|-|{message}",
                    style="{",
                    datefmt="%m/%d/%Y %I:%M:%S %p",
                )
            )
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def load_scrapers(self) -> list[Gruel]:
        """Load scraper classes that inherit from `Gruel`.

        #### :params:

        `directory`: The path to scan for scraper classes.

        `class_names`: A list of class names for scrapers that should be loaded.
        In order to be loaded, a scraper class must have a name in this list and have `Gruel` somewhere in its inheritance hierarchy.

        `include_patterns`: Files that match these patterns will be scanned.

        `exclude_patterns`: Files that match these patterns will not be scanned.

        `recursive`: Whether the search should be recursive or not.

        >>> load_scrapers("getToTheGig/scrapers", ["VenueScraper"], ["*.py"], ["*template*", "*giggruel*"])"""
        self.scan_path.add_to_PATH()
        globber = self.scan_path.glob
        if self.recursive:
            globber = self.scan_path.rglob
        files = [
            str(file)
            for pattern in self.file_include_patterns
            for file in globber(pattern)
        ]
        files = younotyou(files, exclude_patterns=self.file_exclude_patterns)
        modules = []
        for file in files:
            try:
                modules.append(importlib.import_module(Pathier(file).stem))
            except Exception as e:
                ...
        gruels = [
            getattr(module, class_)
            for module in modules
            for class_ in self.subgruel_classes
            if class_ in dir(module) and self.is_subgruel(getattr(module, class_))
        ]
        self.logger.info(
            "\n".join(
                [f"Imported {len(gruels)} scrapers: "]
                + [str(gruel) for gruel in gruels]
            )
        )
        return gruels

    def get_bases(self, object: Any) -> list[Any]:
        """Returns a recursive list of all the classes `object` inherits from."""
        parents = []
        bases = object.__bases__
        if not bases:
            return parents
        for base in bases:
            parents.append(base)
            parents.extend(self.get_bases(base))
        return parents

    def is_subgruel(self, object: Any) -> bool:
        """Returns whether `object` inherits from `Gruel` somewhere in its ancestory."""
        if not inspect.isclass(object) or Gruel not in self.get_bases(object):
            return False
        return True

    def prescrape_chores(self):
        """Override to add any tasks to be done before running the scrapers."""
        ...

    def postscrape_chores(self):
        """Override to add any tasks to be done after running the scrapers."""
        ...

    def scrape(self, scrapers: list[Gruel]):
        """Run the `scrape()` method for each scraper in `scrapers`.

        Execution is multithreaded."""
        num_scrapers = len(scrapers)
        with ProgBar(num_scrapers) as bar:
            with ThreadPoolExecutor() as executor:
                threads = [executor.submit(scraper().scrape) for scraper in scrapers]  # type: ignore
                while (
                    num_complete := len([thread for thread in threads if thread.done()])
                ) < num_scrapers:
                    bar.display(
                        prefix=f"{bar.runtime}",
                        counter_override=num_complete,
                    )
                    time.sleep(1)
            bar.display(
                prefix=f"{bar.runtime}",
                counter_override=num_complete,
            )

    def brew(self):
        """Execute pipeline.

        1. self.prescrape_chores()
        2. self.load_scrapers()
        3. self.scrape()
        4. self.postscrape_chores()"""
        self.logger.info("Beginning brew")
        print("Beginning brew")
        print("Executing prescrape chores...")
        self.prescrape_chores()
        print("Loading scrapers...")
        scrapers = self.load_scrapers()
        print(f"Loaded {len(scrapers)} scrapers.")
        print("Starting scrape...")
        self.scrape(scrapers)
        print("Scrape complete.")
        print("Executing postscrape chores...")
        self.postscrape_chores()
        print("Brew complete.")
        self.logger.info("Brew complete.")


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "subgruel_classes",
        type=str,
        nargs="*",
        help=""" A list of Gruel scraper class names to find and import. """,
    )
    parser.add_argument(
        "-e",
        "--excludes",
        type=str,
        nargs="*",
        default=[],
        help=""" A list of glob style file patterns to exclude from the scan. """,
    )
    parser.add_argument(
        "-i",
        "--includes",
        type=str,
        nargs="*",
        default=["*.py"],
        help=""" A list of glob style file patterns to include in the scan. Defaults to "*.py". """,
    )
    parser.add_argument(
        "-p",
        "--path",
        type=str,
        default=Pathier.cwd(),
        help=""" The directory path to scan. Defaults to the current working directory. """,
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help=""" Whether -p/--path should be scanned recursively or not. """,
    )
    args = parser.parse_args()
    args.path = Pathier(args.path)

    return args


def main(args: argparse.Namespace | None = None):
    if not args:
        args = get_args()
    brewer = Brewer(
        args.subgruel_classes, args.excludes, args.path, args.includes, args.recursive
    )
    brewer.brew()


if __name__ == "__main__":
    main(get_args())
