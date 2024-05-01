import argparse
import importlib
import importlib.machinery
import importlib.util
import inspect
from types import ModuleType
from typing import Any, Sequence, Type

import loggi
import quickpool
from pathier import Pathier, Pathish
from younotyou import Matcher, younotyou

from .core import Gruel


class GruelFinder(loggi.LoggerMixin):
    """Find and load classes that subclass `Gruel`."""

    def __init__(
        self,
        subgruel_classes: list[str] = ["*"],
        file_exclude_patterns: list[str] = [],
        scan_path: Pathier | None = None,
        file_include_patterns: list[str] = ["*.py"],
        recursive: bool = True,
        log_dir: Pathish = "logs",
    ):
        """#### :params:

        `subgruel_classes`: A list of class names for scrapers that should be loaded.
        In order to be loaded, a scraper class must have a name in this list and have `Gruel` somewhere in its inheritance hierarchy.
        Can use wildcard ('*') patterns for matching.

        `file_exclude_patterns`: Files that match these patterns will not be scanned.

        `scan_path`: The path to scan for scraper classes.

        `file_include_patterns`: Files that match these patterns will be scanned.

        `recursive`: Whether the scan should be recursive or not.

        `log_dir`: The directory this instance's log should be saved to.

        Will find and load all classes in the "scrapers" directory that inherit from `Gruel`
        and start with "MySubGruel", but don't contain "Scratch" in the name:
        >>> finder = finder(["MySubGruel*"], ["*Scratch*"], "scrapers")
        >>> gruels = finder.find()"""
        self.subgruel_classes = subgruel_classes
        self.file_exclude_patterns = file_exclude_patterns
        self.scan_path = scan_path or Pathier.cwd()
        self.file_include_patterns = file_include_patterns
        self.recursive = recursive
        self.init_logger("gruel_finder", log_dir)

    def get_bases(self, object: Any) -> list[Any]:
        """Returns a recursive list of all the classes `object` inherits from."""
        parents: list[Any] = []
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
            str(file)
            for pattern in self.file_include_patterns
            for file in globber(pattern)
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

    def strain_for_gruel(self, modules: list[ModuleType]) -> list[Type[Gruel]]:
        """Searches `modules` for classes that inherit from `Gruel` and are in `self.subgruel_classes`.

        Returns the list of classes."""
        matcher = Matcher(self.subgruel_classes)
        return [
            getattr(module, class_)
            for module in modules
            for class_ in dir(module)
            if class_ in matcher and self.is_subgruel(getattr(module, class_))
        ]

    def find(self) -> list[Type[Gruel]]:
        """Run the scan and return `Gruel` subclasses."""
        files = self.glob_files()
        modules: list[ModuleType] = []
        for file in files:
            if module := self.load_module_from_file(file):
                modules.append(module)
        return self.strain_for_gruel(modules)


class Brewer(loggi.LoggerMixin):
    """Use to do multithreaded execution of a list of scrapers.

    Intended to be used with `Gruel` scrapers, but anything with a `scrape` method can be passed.

    To run any `Gruel` scrapers from the current directory:
    >>> Brewer(GruelFinder().find()).brew()

    The `prescrape_chores` and `postscrape_chores` can be set/overridden like the same methods in `Gruel`.

    When calling the `brew` method they will be executed once before and after all the scrapers have been executed.

    i.e.
    >>> brewer = Brewer(GruelFinder().find())
    >>> brewer.prescrape_chores()
    >>> results = brewer.scrape()
    >>> brewer.postscrape_chores()

    is equivalent to
    >>> results = Brewer(GruelFinder().find()).brew()

    except `brew()` has some logging."""

    def __init__(
        self,
        scrapers: Sequence[Type[Gruel]],
        scraper_args: Sequence[Sequence[Any]] = [],
        scraper_kwargs: Sequence[dict[str, Any]] = [],
        log_dir: Pathish = "logs",
    ):
        """#### :params:

        `scrapers`: A list of scraper classes to initialize and execute.
        A scraper should not be instantiated before being passed.
        When `Brewer` runs a scraper it will instantiate the object at execution time and call it's `scrape` method.

        `scraper_args`: A list where each element is a list of positional arguments to be passed to the corresponding scraper's `__init__` function.

        `scraper_kwargs`: A list of dictionaries where each dictionary is a set of keyword arguments to be passed to the corresponding scraper's `__init__` function.

        `log_dir`: The directory to store `Brewer` logs in. Defaults to "logs".

        e.g.
        >>> class MyGruel(Gruel):
        >>>   def __init__(self, value:int):
        >>>     super().__init__()
        >>>     self.value = value
        >>>
        >>>   def scrape(self)->int:
        >>>     return self.value
        >>>
        >>> num_scrapers = 5
        >>> values = list(range(5))
        >>> brewer = Brewer(
        >>>   [MyGruel]*num_scrapers,
        >>>   [(val,) for val in values]
        >>> results = brewer.brew()
        >>> print(results)
        >>> [0, 1, 2, 3, 4]"""
        self.init_logger(log_dir=log_dir)
        self.scrapers = scrapers
        num_scrapers = len(self.scrapers)
        # Pad args and kwargs if there aren't any given
        self.scraper_args: Sequence[Any] = scraper_args or [[]] * num_scrapers
        self.scraper_kwargs: Sequence[dict[str, Any]] = (
            scraper_kwargs or [{}] * num_scrapers
        )

    def prescrape_chores(self):
        """Override to add any tasks to be done before running the scrapers."""
        ...

    def postscrape_chores(self):
        """Override to add any tasks to be done after running the scrapers."""
        ...

    def _prep_scrapers(self) -> list[tuple[Any, Sequence[Any], dict[str, Any]]]:
        return [
            (scraper, args, kwargs)
            for scraper, args, kwargs in zip(
                self.scrapers, self.scraper_args, self.scraper_kwargs
            )
        ]

    def scrape(self) -> list[Any]:
        """Run the `scrape()` method for each scraper in `scrapers`.

        Execution is multithreaded."""

        def execute(scraper: Type[Gruel], args: Sequence[Any], kwargs: dict[str, Any]):
            return scraper(*args, **kwargs).scrape()

        pool = quickpool.ThreadPool(
            [execute] * len(self.scrapers), self._prep_scrapers()
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
    parser = argparse.ArgumentParser(
        prog="Brewer", description="Invoke `Brewer` from the command line."
    )

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
        default="logs",
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
