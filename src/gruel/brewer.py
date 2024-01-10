import argparse
import importlib
import importlib.machinery
import importlib.util
import inspect
from typing import Any

import loggi
import quickpool
from pathier import Pathier, Pathish
from younotyou import younotyou

from gruel import Gruel


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
        # When Brewer is subclassed, use that file's stem instead of `brewer`
        source_file = inspect.getsourcefile(type(self))
        if source_file:
            log_name = Pathier(source_file).stem
        else:
            log_name = Pathier(__file__).stem
        self.logger = loggi.getLogger(log_name)

    def load_scrapers(self) -> list[Gruel]:
        """Load scraper classes that inherit from `Gruel`.

        NOTE: Classes are loaded, but scraper objects are not instantiated until the `scrape()` method is called.

        #### :params:

        `directory`: The path to scan for scraper classes.

        `class_names`: A list of class names for scrapers that should be loaded.
        In order to be loaded, a scraper class must have a name in this list and have `Gruel` somewhere in its inheritance hierarchy.

        `include_patterns`: Files that match these patterns will be scanned.

        `exclude_patterns`: Files that match these patterns will not be scanned.

        `recursive`: Whether the search should be recursive or not.

        >>> load_scrapers("getToTheGig/scrapers", ["VenueScraper"], ["*.py"], ["*template*", "*giggruel*"])
        """
        globber = self.scan_path.glob
        if self.recursive:
            globber = self.scan_path.rglob
        files = [
            str(file)
            for pattern in self.file_include_patterns
            for file in globber(pattern)
        ]
        files = younotyou(files, exclude_patterns=self.file_exclude_patterns)
        self.modules = {}
        self._module_names = []
        for file in files:
            module_name = Pathier(file).stem
            try:
                module = importlib.machinery.SourceFileLoader(
                    module_name, file
                ).load_module()
            except Exception as e:
                self.logger.exception(
                    f"Failed to load module '{module_name}' from '{file}'."
                )
            else:
                self._module_names.append(module_name)
                self.modules[module] = module
        gruels = [
            getattr(module, class_)
            for module in self.modules.values()
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

    def pop_modules(self):
        """Unload modules."""
        for module in self.modules:
            del module
        self._module_names = []

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
        self.pop_modules()

    def scrape(self, scrapers: list[Gruel]):
        """Run the `scrape()` method for each scraper in `scrapers`.

        Execution is multithreaded."""
        execute = lambda scraper: scraper().scrape()
        pool = quickpool.ThreadPool(
            [execute] * len(scrapers), [(scraper,) for scraper in scrapers]
        )
        pool.execute()

    def logprint(self, message: str):
        """Log and print `message`."""
        self.logger.info(message)
        print(message)

    def brew(self):
        """Execute pipeline.

        1. self.prescrape_chores()
        2. self.load_scrapers()
        3. self.scrape()
        4. self.postscrape_chores()"""

        try:
            self.logprint("Beginning brew")
            # 1--------------------------------------------
            self.logprint("Executing prescrape chores")
            self.prescrape_chores()
            # 2--------------------------------------------
            self.logprint("Loading scrapers")
            scrapers = self.load_scrapers()
            print(f"Loaded {len(scrapers)} scrapers")
            # 3--------------------------------------------
            self.logprint("Starting scrape")
            self.scrape(scrapers)
            self.logprint("Scrape complete")
            # 4--------------------------------------------
            self.logprint("Executing postscrape chores")
            self.postscrape_chores()
            self.logprint("Brew complete")
        except Exception as e:
            print(e)
            self.logger.exception("Exception occured during brew():")


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
