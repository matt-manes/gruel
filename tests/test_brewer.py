from pathier import Pathier, Pathish

import gruel

root = Pathier(__file__).parent
dummy_root = root / "dummy"


def test__brewer_args():
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
    results = brewer.brew()
    assert results == [(check_val, str(check_val)) for check_val in check_vals]
    for i in range(scraper_count):
        try:
            (Pathier.cwd() / "logs" / f"{i}.log").delete()
        except Exception as e:
            pass


def test__brewer_no_args():
    print()
    finder = gruel.GruelFinder()
    module = finder.load_module_from_file(dummy_root / "dummy2.py")
    assert module
    subgruel = module.DummyGruel
    scrapers = [subgruel]
    brewer = gruel.Brewer(scrapers)
    brewer.brew()
    data = (dummy_root / "dummy_data.txt").split()
    assert len(data) == 3
    assert data[0] == "Sample Slide Show"
    assert data[1] == "Wake up to WonderWidgets!"
    assert data[2] == "Overview"
    (dummy_root / "dummy_data.txt").delete()
