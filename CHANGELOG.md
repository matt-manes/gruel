# Changelog

## v4.6.0 (2025-03-31)

#### Performance improvements

* wrap url manager in a semaphore and change most deques to sets

## v4.5.0 (2024-07-23)

#### Refactorings

* add explicity `randomize_useragent` param to `request`

## v4.4.3 (2024-07-16)

#### Docs

* add docstring to `Gruel`

## v4.4.2 (2024-06-16)

#### Fixes

* fix non-same site urls getting crawled when `same_site_only` is set to `True`

## v4.4.1 (2024-06-10)

#### Refactorings

* add `is_same_site()` method to `Url` model

## v4.4.0 (2024-06-08)

#### New Features

* implement `Url` model

#### Performance improvements

* strip fragments from extracted urls

## v4.3.0 (2024-05-26)

#### New Features

* add property to store if crawler was intentionally interupted

## v4.2.2 (2024-05-26)

#### Refactorings

* add `download_dir` arg to `SeleniumCrawler()`

## v4.2.1 (2024-05-24)

#### Refactorings

* add `headless` init arg to `SeleniumCrawler`

## v4.2.0 (2024-05-24)

#### Refactorings

* POTENTIALLY BREAKING remove optional arg for showing prog bar during item parsing and instead make it a `ParserMixin` property

## v4.1.2 (2024-05-21)

#### Performance improvements

* update progress bar after crawl is finished or limits are exceeded
* better prevent running workers from exceeding max depth

#### Refactorings

* add additional properties to `ThreadManager`

## v4.1.1 (2024-05-21)

#### Fixes

* fix max depth limit not working in `SeleniumCrawler` because it's using a stale `ThreadManager` instance

#### Refactorings

* change default crawl threads from 5 to 3

## v4.1.0 (2024-05-19)

#### New Features

* add `SeleniumCrawler` class for crawling with javascript rendering

#### Refactorings

* POTENTIALLY BREAKING `Crawler` takes a sequence of `CrawlScrapers` instead of just one

## v4.0.0 (2024-05-07)

#### New Features

* implement `CrawlLimit` class
* implement `Crawler` class.
* add wrapper around `parse_item()`
* add convenience request function to `Gruel`
* add `get_linkscraper()` to `Response`
* add logging to sending requests and receiving responses
* BREAKING add `get_source()` abstract method to `Gruel`

#### Refactorings

* update template
* implement `ScraperMetricsMixin`
* implement `ChoresMixin`
* break up `Gruel` into smaller mixin classes
* use `LoggerMixin` from `loggi` package
* export `retry_on_codes`
* move log closing out of `postscrape_chores()`
* separate requests functionality and expose more access to the requests module
* add `override` decorator to template
* BREAKING remove `ParsableItem` type alias

## v3.0.1 (2024-02-17)

#### Refactorings

* use disable param of `track` instead of ifelse statement

## v3.0.0 (2024-02-17)

#### Refactorings

* BREAKING change `request` from static method of `Gruel` to independent method
* improve type annotation coverage

## v2.1.1 (2024-01-26)

#### New Features

* add json input to request method

## v2.1.0 (2024-01-25)

#### New Features

* add members to `Gruel` to better track scrape runtime status and results

## v2.0.2 (2024-01-21)

#### Docs

* fix type annotations

## v2.0.1 (2024-01-21)

#### Fixes

* avoid potential circular import issues

## v2.0.0 (2024-01-21)

#### New Features

* add init args and kwargs for scrapers being brewed

#### Refactorings

* BREAKING: separate gruel finding logic from `Brewer` class

#### Docs

* add prog and description to cli argparser

#### Others

* add imports
* add to gitignore

## v1.0.0 (2024-01-19)

#### New Features

* BREAKING: change `Gruel.get_page()` to `Gruel.request()` and make both it and `Gruel.as_soup()` into static methods

## v0.6.1 (2024-01-18)

#### Fixes

* remove erroneous `print()` call

## v0.6.0 (2024-01-18)

#### Refactorings

* add additional parameters to `get_page()`

## v0.5.1 (2024-01-14)

#### Fixes

* remove redundant dependency from pyproject

## v0.5.0 (2024-01-14)

#### New Features

* add options to specify log directories

#### Docs

* add class and `__init__` docstrings

#### Others

* remove pytest and specify less than 3.12 py version

## v0.4.1 (2024-01-09)

#### Fixes

* prevent crashing caused by too many files open

## v0.4.0 (2023-10-29)

#### Refactorings

* change how modules are unloaded

## v0.3.1 (2023-10-26)

#### Fixes

* fix not passing log_dir to getLogger

## v0.3.0 (2023-10-26)

#### Refactorings

* replace logging with loggi

## v0.2.0 (2023-10-25)

#### Fixes

* fix Gruel.name not returning the given name if there was one

#### Performance improvements

* improve logging

#### Refactorings

* make logprint a member function
* replace printbuddies.PoolBar with quickpool.ThreadPool

## v0.1.0 (2023-10-23)

#### Performance improvements

* add additional logging

## v0.0.2 (2023-10-19)

#### Fixes

* fix progbar display when using default option in scrape()

## v0.0.1 (2023-10-19)

#### Fixes

* fix partially initialized import error
