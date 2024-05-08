# Changelog

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
