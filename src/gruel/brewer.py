import argparse
import importlib
import importlib.machinery
import importlib.util
import inspect
from types import ModuleType
from typing import Any, Sequence

import loggi
import quickpool
from pathier import Pathier, Pathish
from younotyou import Matcher, younotyou

from gruel import Gruel


class GruelFinder:
    def __init__(
        self,
        subgruel_classes: list[str] = ["*"],
        file_exclude_patterns: list[str] = [],
        scan_path: Pathier | None = None,
        file_include_patterns: list[str] = ["*.py"],
        recursive: bool = True,
        log_dir: Pathish | None = None,
    ):
        self.subgruel_classes = subgruel_classes
        self.file_exclude_patterns = file_exclude_patterns
        self.scan_path = scan_path or Pathier.cwd()
        self.file_include_patterns = file_include_patterns
        self.recursive = recursive
        self.logger = loggi.getLogger(
            "gruel_finder", Pathier(log_dir) if log_dir else Pathier.cwd()
        )

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

    def glob_files(self) -> list[Pathier]:
        """Search `self.scan_path` for files according to `self.file_include_patterns` and `self.file_exclude_patterns`.

        Returns the file list."""
        globber = self.scan_path.rglob if self.recursive else self.scan_path.glob
        files = [
            str(
                file
                for pattern in self.file_include_patterns
                for file in globber(pattern)
            )
        ]
        files = [
            Pathier(file)
            for file in younotyou(files, exclude_patterns=self.file_exclude_patterns)
        ]
        return files

    def load_module_from_file(self, file: Pathier) -> ModuleType | None:
        """Attempts to load and return a module from `file`."""
        module_name = file.stem
        try:
            module = importlib.machinery.SourceFileLoader(
                module_name, str(file)
            ).load_module()
            self.logger.info(f"Successfully imported `{module_name}` from `{file}`.")
            return module
        except Exception as e:
            self.logger.exception(f"Failed to load `{module_name}` from `{file}`.")

    def strain_for_gruel(self, modules: list[ModuleType]) -> list[Gruel]:
        """Searches `modules` for classes that inherit from `Gruel` and are in `self.subgruel_classes`.

        Returns the list of classes."""
        matcher = Matcher(self.subgruel_classes)
        return [
            getattr(module, class_)
            for module in modules
            for class_ in dir(module)
            if class_ in matcher and self.is_subgruel(getattr(module, class_))
        ]

    def find(self) -> list[Gruel]:
        """Run the scan and return `Gruel` subclasses."""
        files = self.glob_files()
        modules = []
        for file in files:
            if module := self.load_module_from_file(file):
                modules.append(module)
        return self.strain_for_gruel(modules)


class Brewer:
    def __init__(
        self,
        scrapers: Sequence[Any],
        log_dir: Pathish | None = None,
    ):
        """Run `Gruel` scrapers.

        #### :params:

        `subgruel_classes`: A list of class names for scrapers that should be loaded.
        In order to be loaded, a scraper class must have a name in this list and have `Gruel` somewhere in its inheritance hierarchy.

        `file_exclude_patterns`: Files that match these patterns will not be scanned.

        `scan_path`: The path to scan for scraper classes.

        `file_include_patterns`: Files that match these patterns will be scanned.

        `recursive`: Whether the scan should be recursive or not.

        `log_dir`: The directory this instance's log should be saved to.
        If `None`, it will be saved to the current working directory.

        >>> brewer = Brewer(["VenueScraper"], ["*template*", "*giggruel*"], "scrapers")
        >>> brewer.brew()"""
        self._init_logger(log_dir)
        self.scrapers = scrapers

    def _init_logger(self, log_dir: Pathish | None = None):
        # When Brewer is subclassed, use that file's stem instead of `brewer`
        log_dir = Pathier(log_dir) if log_dir else Pathier.cwd()
        source_file = inspect.getsourcefile(type(self))
        if source_file:
            log_name = Pathier(source_file).stem
        else:
            log_name = Pathier(__file__).stem
        self.logger = loggi.getLogger(log_name, log_dir)

    def prescrape_chores(self):
        """Override to add any tasks to be done before running the scrapers."""
        ...

    def postscrape_chores(self):
        """Override to add any tasks to be done after running the scrapers."""
        ...

    def scrape(self) -> list[Any]:
        """Run the `scrape()` method for each scraper in `scrapers`.

        Execution is multithreaded."""
        execute = lambda scraper: scraper().scrape()
        pool = quickpool.ThreadPool(
            [execute] * len(self.scrapers), [(scraper,) for scraper in self.scrapers]
        )
        return pool.execute()

    def brew(self) -> list[Any] | None:
        """Execute pipeline.

        1. self.prescrape_chores()
        2. self.scrape()
        3. self.postscrape_chores()"""

        try:
            self.logger.logprint("Beginning brew")
            # 1--------------------------------------------
            self.logger.logprint("Executing prescrape chores")
            self.prescrape_chores()
            # 2--------------------------------------------
            self.logger.logprint("Starting scrape")
            results = self.scrape()
            self.logger.logprint("Scrape complete")
            # 4--------------------------------------------
            self.logger.logprint("Executing postscrape chores")
            self.postscrape_chores()
            self.logger.logprint("Brew complete")
            return results
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
    parser.add_argument(
        "-l",
        "--log_dir",
        type=str,
        default=None,
        help=""" The directory to save the brew log to.""",
    )
    args = parser.parse_args()
    args.path = Pathier(args.path)

    return args


def main(args: argparse.Namespace | None = None):
    if not args:
        args = get_args()
    finder = GruelFinder(
        args.subgruel_classes,
        args.excludes,
        args.path,
        args.includes,
        args.recursive,
        args.log_dir,
    )
    brewer = Brewer(
        finder.find(),
        args.log_dir,
    )
    brewer.brew()


if __name__ == "__main__":
    main(get_args())
