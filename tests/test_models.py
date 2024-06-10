import pytest

from gruel import models

raw_url = "https://www.website.com/page1/page2?var1=val1&var2=val2#frag"


def test__Url():
    url = models.Url(raw_url)
    assert url.address == raw_url
    assert url.scheme == "https"
    assert url.netloc == "www.website.com"
    assert url.path == "/page1/page2"
    assert url.query == "var1=val1&var2=val2"
    assert url.fragment == "frag"


def test__Url_base():
    url = models.Url(raw_url)
    assert url.base.address == "https://www.website.com"


def test__Url_schemeless():
    url = models.Url(raw_url)
    assert (
        url.schemeless.address == "www.website.com/page1/page2?var1=val1&var2=val2#frag"
    )


def test__Url_fragmentless():
    url = models.Url(raw_url)
    assert (
        url.fragmentless.address
        == "https://www.website.com/page1/page2?var1=val1&var2=val2"
    )


def test__Url_setters():
    url = models.Url("")
    url.scheme = "https"
    assert url.address == "https:"
    url.netloc = "www.website.com"
    assert url.address == "https://www.website.com"
    url.path = "page1/page2"
    assert url.address == "https://www.website.com/page1/page2"
    url.query = "var1=val1&var2=val2"
    assert url.address == "https://www.website.com/page1/page2?var1=val1&var2=val2"
    url.fragment = "frag"
    assert url.address == "https://www.website.com/page1/page2?var1=val1&var2=val2#frag"


def test__Url__eq__():
    url1 = models.Url(raw_url)
    url2 = models.Url(raw_url)
    assert url1 == url2
    url2.netloc = "anotherwebsite.org"
    assert url1 != url2
    with pytest.raises(ValueError):
        result = "yeet" == url1


def test__Url__hash__():
    url1 = models.Url(raw_url)
    url2 = models.Url(raw_url)
    url2.netloc = "anotherwebsite.org"
    url_dict = {url1: 1, url2: 2}


def test__Url_is_same_site():
    url1 = models.Url(raw_url)
    url2 = models.Url(raw_url)
    assert url1.is_same_site(url2)
    url2.netloc = "anotherwebsite.org"
    assert not url1.is_same_site(url2)
    url2 = models.Url(raw_url)
    url2.path = "some/other/path"
    assert url1.is_same_site(url2)
    url2.netloc = url2.netloc.replace("www", "subdomain")
    assert url1.is_same_site(url2)
    url2.netloc = url2.netloc.replace("subdomain.", "")
    assert url1.is_same_site(url2)
