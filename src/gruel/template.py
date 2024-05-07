from typing import Any

from typing_extensions import Sequence, override

from gruel import Gruel


class SubGruel(Gruel):
    @override
    def get_source(self) -> Any:
        """Fetch and return source content.

        Most commonly just a webpage request and returning a `Response` object."""
        raise NotImplementedError

    @override
    def get_parsable_items(self, source: Any) -> list[Any]:
        """Get relevant webpages and extract raw data that needs to be parsed.

        e.g. first 10 results for an endpoint that returns json content
        >>> return self.request(some_url).json()[:10]"""
        raise NotImplementedError

    @override
    def parse_item(self, item: Any) -> Any:
        """Parse `item` and return parsed data."""
        raise NotImplementedError

    @override
    def store_items(self, items: Sequence[Any]) -> None:
        """Store `item`."""
        raise NotImplementedError
