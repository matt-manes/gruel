from typing import Any

import requests
import requests.adapters
import requests.cookies
import urllib3.util  # type: ignore
from bs4 import BeautifulSoup
from typing_extensions import Self, override
from whosyouragent import whosyouragent


class Response(requests.Response):
    """Override of `requests.Response` adding the following convenience methods:

    * `get_soup()`
    """

    def get_soup(self, features: str = "html.parser") -> BeautifulSoup:
        """Returns a `BeautifulSoup` instance for this response."""
        return BeautifulSoup(self.text, features)

    @classmethod
    def from_base_response(cls, response: requests.Response) -> Self:
        """Convert a `requests.Response` object into a `gruel.Response` object."""
        self = cls()
        self.__dict__ = response.__dict__.copy()
        return self


class Session(requests.Session):
    @override
    def __init__(
        self,
        randomize_useragent: bool = True,
        clear_cookies: bool = True,
        retry_count: int = 3,
        retry_backoff_factor: float = 0.1,
    ):
        """Create a `Session` object.

        #### :params:
        `randomize_useragent`: If `True`, each request will have a randomized `User-Agent` string.
        `clear_cookies`: If `True`, cookies will be cleared from the session prior to each request.
        `retry_count`: The number of times to retry a failed request.
        `retry_backoff_factor`: For each failed request, the time before retrying will be `retry_backoff_factor * (2 ** retry_number)`
        """
        super().__init__()
        self.randomize_useragent = randomize_useragent
        self.clear_cookies = clear_cookies
        self.timeout = 10
        self.set_retry(total=retry_count, backoff_factor=retry_backoff_factor)

    def set_retry(self, *args: Any, **kwargs: Any):
        """Set the retry policy for failed requests.

        `*args` and `**kwargs` are any parameters accepted by `urllib3.util.Retry()`."""
        retries = urllib3.util.Retry(*args, **kwargs)
        self.mount("http://", requests.adapters.HTTPAdapter(max_retries=retries))
        self.mount("https://", requests.adapters.HTTPAdapter(max_retries=retries))

    @override
    def prepare_request(self, request: requests.Request) -> requests.PreparedRequest:
        if self.randomize_useragent:
            self.headers["User-Agent"] = whosyouragent.get_agent()
        if self.clear_cookies:
            self.cookies = requests.cookies.RequestsCookieJar()
        return super().prepare_request(request)

    @override
    def request(self, *args: Any, **kwargs: Any) -> Response:
        response = super().request(*args, **kwargs)
        return Response.from_base_response(response)


def request(
    url: str,
    method: str = "get",
    retry_count: int = 3,
    retry_backoff_factor: float = 0.1,
    *args: Any,
    **kwargs: Any,
) -> Response:
    """
    Constructs and sends a :class:`Request <Request>`.

    `url`: URL for the new :class:`Request` object.
    `method`: method for the new :class:`Request` object: ``GET``, ``OPTIONS``, ``HEAD``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``.

    * `retry_count`: The number of times to retry a failed request.
    * `retry_backoff_factor`: For each failed request, the time before retrying will be `retry_backoff_factor * (2 ** retry_number)`

    `params`: dict, list of tuples or bytes to send in the query string for the :class:`Request`.
    `data`: dict, list of tuples, bytes, or file-like object to send in the body of the :class:`Request`.
    `json`: A JSON serializable Python object to send in the body of the :class:`Request`.
    `headers`: dict of HTTP Headers to send with the :class:`Request`. The `User-Agent` header will be randomized unless supplied.
    `cookies`: dict or CookieJar object to send with the :class:`Request`.
    `files`: dict of ``'name': file-like-objects`` (or ``{'name': file-tuple}``) for multipart encoding upload.
        ``file-tuple`` can be a 2-tuple ``('filename', fileobj)``, 3-tuple ``('filename', fileobj, 'content_type')``
        or a 4-tuple ``('filename', fileobj, 'content_type', custom_headers)``, where ``'content-type'`` is a string
        defining the content type of the given file and ``custom_headers`` a dict-like object containing additional headers
        to add for the file.
    `auth`: Auth tuple to enable Basic/Digest/Custom HTTP Auth.
    `timeout`: float | tuple, How many seconds to wait for the server to send data
        before giving up, as a float, or a :ref:`(connect timeout, read
        timeout) <timeouts>` tuple.
    `allow_redirects`: bool. Enable/disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection. Defaults to ``True``.
    `proxies`: dict mapping protocol to the URL of the proxy.
    `verify`: Either a bool, in which case it controls whether we verify
            the server's TLS certificate, or a string, in which case it must be a path
            to a CA bundle to use. Defaults to ``True``.
    `stream`: if ``False``, the response content will be immediately downloaded.
    `cert`: if String, path to ssl client cert file (.pem). If Tuple, ('cert', 'key') pair.
    """
    with Session(
        retry_count=retry_count, retry_backoff_factor=retry_backoff_factor
    ) as session:
        return session.request(method, url, *args, **kwargs)
