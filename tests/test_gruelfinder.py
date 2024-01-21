import gruel
from pathier import Pathier, Pathish

root = Pathier(__file__).parent
dummy_root = root / "dummy"


def test__gruelfinder_glob():
    finder = gruel.GruelFinder(scan_path=dummy_root)
    files = finder.glob_files()
    assert dummy_root / "__init__.py" in files
    assert dummy_root / "dummy.py" in files


def test__gruelfinder_load_module_from_file():
    file = dummy_root / "dummy.py"
    finder = gruel.GruelFinder(scan_path=dummy_root)
    module = finder.load_module_from_file(file)
    assert module
    assert module.__name__ == "dummy"


def test__gruelfinder_strain_for_gruel():
    file = dummy_root / "dummy.py"
    finder = gruel.GruelFinder(scan_path=dummy_root)
    module = finder.load_module_from_file(file)
    assert module
    modules = [module]
    gruels = finder.strain_for_gruel(modules)
    class_names = [class_.__name__ for class_ in gruels]
    assert "DummyGruel" in class_names
    assert "SubDummyGruel" in class_names
    assert "NotSubGruel" not in class_names


def test__gruelfinder_find():
    finder = gruel.GruelFinder(scan_path=dummy_root)
    gruels = finder.find()
    class_names = [class_.__name__ for class_ in gruels]
    assert "DummyGruel" in class_names
    assert "SubDummyGruel" in class_names
    assert "NotSubGruel" not in class_names

    finder = gruel.GruelFinder(subgruel_classes=["Sub*"], scan_path=dummy_root)
    gruels = finder.find()
    class_names = [class_.__name__ for class_ in gruels]
    assert "DummyGruel" not in class_names
    assert "SubDummyGruel" in class_names
    assert "NotSubGruel" not in class_names
