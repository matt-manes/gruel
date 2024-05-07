from typing_extensions import Any, override, Sequence
from pathier import Pathier, Pathish
from gruel import Gruel, request, Response

root = Pathier(__file__).parent


class DummyGruel(Gruel):
    @override
    def get_source(self, *args: Any, **kwargs: Any) -> Any:
        url = "https://httpbin.org/json"
        return request(url, logger=self.logger)

    @override
    def get_parsable_items(self, source: Response) -> list[dict[str, Any]]:
        return [source.json()]

    @override
    def parse_item(self, item: dict[str, Any]) -> list[str]:
        titles = [item["slideshow"]["title"]]
        slides = item["slideshow"]["slides"]
        titles.extend([slide["title"] for slide in slides])
        return titles

    @override
    def store_items(self, items: Sequence[list[str]]):
        (root / "dummy_data.txt").join(items[0])
