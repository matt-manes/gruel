from typing_extensions import Any, override
from pathier import Pathier, Pathish
from gruel import Gruel, request

root = Pathier(__file__).parent


class DummyGruel(Gruel):
    @override
    def get_parsable_items(self) -> list[dict[str, Any]]:
        url = "https://httpbin.org/json"
        return [request(url, logger=self.logger).json()]

    @override
    def parse_item(self, item: dict[str, Any]) -> list[str]:
        titles = [item["slideshow"]["title"]]
        slides = item["slideshow"]["slides"]
        titles.extend([slide["title"] for slide in slides])
        return titles

    @override
    def store_item(self, item: list[str]):
        (root / "dummy_data.txt").join(item)
