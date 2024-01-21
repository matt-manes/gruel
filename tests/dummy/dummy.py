from gruel import Gruel
from pathier import Pathier


class DummyGruel(Gruel):
    def __init__(self, check_val: int, name: str):
        super().__init__(name)
        self.check_val = check_val

    def scrape(self) -> tuple[int, str]:
        return self.check_val, self.name


class SubDummyGruel(DummyGruel):
    ...


class NotSubGruel:
    ...
