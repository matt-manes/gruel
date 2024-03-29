from typing import Any

from gruel import Gruel, ParsableItem


class SubGruel(Gruel):
    def get_parsable_items(self) -> list[ParsableItem]:
        """Get relevant webpages and extract raw data that needs to be parsed.

        e.g. first 10 results for an endpoint that returns json content
        >>> return self.request(some_url).json()[:10]"""
        raise NotImplementedError

    def parse_item(self, item: ParsableItem) -> Any:
        """Parse `item` and return parsed data.

        e.g.
        >>> try:
        >>>     parsed = {}
        >>>     parsed["thing1"] = item["element"].split()[0]
        >>>     self.successes += 1
        >>>     return parsed
        >>> except Exception:
        >>>     self.logger.exception("message")
        >>>     self.failures += 1
        >>>     return None"""
        raise NotImplementedError

    def store_item(self, item: Any) -> Any:
        """Store `item`."""
        raise NotImplementedError
