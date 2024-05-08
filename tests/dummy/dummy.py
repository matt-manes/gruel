from pathier import Pathier
from typing_extensions import Any

from gruel import Gruel


class DummyGruel(Gruel):
    def __init__(self, check_val: int, name: str):
        super().__init__(name)
        self.check_val = check_val

    def get_source(self, *args: Any, **kwargs: Any) -> Any:
        return super().get_source(*args, **kwargs)

    def get_parsable_items(self, source: Any) -> list[Any]:
        return []

    def parse_item(self, item: Any) -> Any:
        return None

    def store_items(self, items: Any) -> Any:
        return None

    def scrape(self) -> tuple[int, str]:  # type: ignore
        self.logger.close()
        return self.check_val, self.name


class SubDummyGruel(DummyGruel):
    ...


class NotSubGruel:
    ...
