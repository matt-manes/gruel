from typing import Any

from typing_extensions import Sequence, override

from gruel import Gruel


class SubGruel(Gruel):
    @override
    def get_source(self) -> Any:
        raise NotImplementedError

    @override
    def get_parsable_items(self, source: Any) -> list[Any]:
        raise NotImplementedError

    @override
    def parse_item(self, item: Any) -> Any:
        raise NotImplementedError

    @override
    def store_items(self, items: Sequence[Any]) -> None:
        raise NotImplementedError
