from pathier import Pathier

from gruel import Gruel


class DummyGruel(Gruel):
    def __init__(self, check_val: int, name: str):
        super().__init__(name)
        self.check_val = check_val

    def scrape(self) -> tuple[int, str]:
        self.logger.close()
        return self.check_val, self.name


class SubDummyGruel(DummyGruel): ...


class NotSubGruel: ...
