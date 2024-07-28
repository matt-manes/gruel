import pytest
from bs4 import BeautifulSoup, Tag
from pathier import Pathier

import gruel

root = Pathier(__file__).parent

soup = BeautifulSoup((root / "ridewithgps.html").read_text(), "html.parser")


def test__simple_exists():
    strainer = gruel.SoupStrainer(soup)
    assert strainer.exists("head")
    assert strainer.exists("head", "title")


def test__simple_no_exists():
    strainer = gruel.SoupStrainer(soup)
    assert not strainer.exists("yeet")
    assert not strainer.exists("head", "yeet")


def test__specifier_exists():
    strainer = gruel.SoupStrainer(soup)
    assert strainer.exists(gruel.Specifier("div", class_="globalNav"))
    assert strainer.exists(
        gruel.Specifier("div", attrs={"id": "page_wrapper"}),
        gruel.Specifier("g", attrs={"id": "Symbols"}),
    )


def test__wrong_parent_exists():
    strainer = gruel.SoupStrainer(soup)
    wrong_parent = gruel.Specifier("div", class_="globalNav")
    right_parent = gruel.Specifier("div", attrs={"id": "page-content"})
    child = gruel.Specifier("section", class_="steps")
    assert not strainer.exists(wrong_parent, child)
    assert strainer.exists(right_parent, child)


def test__find():
    strainer = gruel.SoupStrainer(soup)
    parent = gruel.Specifier("div", class_="mobile")
    img = strainer.find(parent, "img")
    assert isinstance(img, Tag)
    assert img.get("src") == "/images/revised_layout/home-step-1.jpg"
    assert strainer.find(parent, "div", "h2").text == "Discover routes"


def test__find_exception():
    strainer = gruel.SoupStrainer(soup)
    parent = gruel.Specifier("div", class_="mobile")
    with pytest.raises(gruel.MissingElementError) as e:
        strainer.find(parent, "div", gruel.Specifier("section", class_="steps"))
    print(e)
    with pytest.raises(gruel.MissingElementError) as e:
        strainer.find("yeet")
    print(e)


def test__find_no_args():
    strainer = gruel.SoupStrainer(soup)
    with pytest.raises(ValueError, match="No specifiers provided."):
        strainer.find()
