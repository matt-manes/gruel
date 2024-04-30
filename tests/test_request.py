import loggi
import pytest
from pathier import Pathier

import gruel

root = Pathier(__file__).parent

logger = loggi.getLogger("test_request", "logs")


def flush_log():
    log = loggi.get_log(logger)
    if log and log.path:
        log.path.write_text("")


def test__get_request():
    flush_log()
    url = "https://httpbin.org/get"
    response = gruel.request(url, logger=logger)
    log = loggi.get_log(logger)
    assert log
    assert "GET" in log.events[0].message and url in log.events[0].message
    assert "completed with status code `200`" in log.events[1].message
    flush_log()


def test__redirect():
    flush_log()
    response = gruel.request("https://httpbin.org/redirect/5", logger=logger)
    log = loggi.get_log(logger)
    assert log
    assert len(log) == 12
    messages = "\n".join(event.message for event in log.events)
    assert "completed with status code `200`" in messages
    assert "completed with status code `302`" in messages
    flush_log()


def test__retry():
    flush_log()
    with pytest.raises(Exception) as e:
        response = gruel.request("https://httpbin.org/status/503", logger=logger)
    log = loggi.get_log(logger)
    assert log
    assert len(log.filter_levels(["ERROR"]))
    response = gruel.request("https://httpbin.org/status/505", logger=logger)
    log = loggi.get_log(logger)
    assert log
    assert len(log.filter_messages(["*completed with status code `505`*"]))
    flush_log()


def test__Session():
    flush_log()
    with gruel.Session(logger=logger) as session:
        response = session.get("https://httpbin.org/cookies/set/test/yeet")
        assert session.cookies["test"] == "yeet"
        response2 = session.get("https://httpbin.org/get")
        assert (
            response.request.headers["User-Agent"]
            != response2.request.headers["User-Agent"]
        )
        assert "test" not in session.cookies
    with gruel.Session(False, False, logger=logger) as session:
        response = session.get("https://httpbin.org/cookies/set/test/yeet")
        assert session.cookies["test"] == "yeet"
        response2 = session.get("https://httpbin.org/get")
        assert (
            response.request.headers["User-Agent"]
            == response2.request.headers["User-Agent"]
        )
        assert session.cookies["test"] == "yeet"
    flush_log()


def test__get_soup():
    soup = gruel.request("https://httpbin.org/html").get_soup()
    h1 = soup.find("h1")
    assert h1
    assert h1.text == "Herman Melville - Moby-Dick"
