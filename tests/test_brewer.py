import gruel
from pathier import Pathier, Pathish

root = Pathier(__file__).parent
dummy_root = root / "dummy"


def test__brewer():
    print()
    finder = gruel.GruelFinder()
    module = finder.load_module_from_file(dummy_root / "dummy.py")
    assert module
    scraper_count = 200
    subgruel = module.DummyGruel
    scrapers = [subgruel] * scraper_count
    check_vals = list(range(scraper_count))
    brewer = gruel.Brewer(
        scrapers,
        tuple((check_val,) for check_val in check_vals),
        tuple({"name": str(check_val)} for check_val in check_vals),
    )
    results = brewer.scrape()
    assert results == [(check_val, str(check_val)) for check_val in check_vals]
