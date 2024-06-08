from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit

from typing_extensions import Self


@dataclass
class Url:
    address: str

    def __post_init__(self):
        self.address = self.address.strip("/ ")

    @property
    def _parsed(self) -> SplitResult:
        """Returns this instance's `address` split into scheme, netloc, path, query, and fragment."""
        return urlsplit(self.address.strip("/ "))

    def _from_parts(
        self, scheme: str, netloc: str, path: str, query: str, fragment: str
    ) -> Self:
        """Return a new `Url` object from url parts."""
        return self.__class__(urlunsplit((scheme, netloc, path, query, fragment)))

    @property
    def scheme(self) -> str:
        """The scheme of the url."""
        return self._parsed.scheme

    @scheme.setter
    def scheme(self, scheme: str):
        self.address = self._from_parts(
            scheme, self.netloc, self.path, self.query, self.fragment
        ).address

    @property
    def netloc(self) -> str:
        """The netloc (net location) of the url."""
        return self._parsed.netloc

    @netloc.setter
    def netloc(self, netloc: str):
        self.address = self._from_parts(
            self.scheme, netloc, self.path, self.query, self.fragment
        ).address

    @property
    def path(self) -> str:
        """The path portion of the url (contains leading slash)."""
        return self._parsed.path

    @path.setter
    def path(self, path: str):
        self.address = self._from_parts(
            self.scheme, self.netloc, path, self.query, self.fragment
        ).address

    @property
    def query(self) -> str:
        """The query portion of the url."""
        return self._parsed.query

    @query.setter
    def query(self, query: str):
        self.address = self._from_parts(
            self.scheme, self.netloc, self.path, query, self.fragment
        ).address

    @property
    def fragment(self) -> str:
        """The fragment portion of the url."""
        return self._parsed.fragment

    @fragment.setter
    def fragment(self, fragment: str):
        self.address = self._from_parts(
            self.scheme, self.netloc, self.path, self.query, fragment
        ).address

    @property
    def fragmentless(self) -> Self:
        """A `Url` object with no fragment."""
        return self._from_parts(self.scheme, self.netloc, self.path, self.query, "")

    @property
    def base(self) -> Self:
        """Returns a `Url` with just scheme and netloc."""
        return self._from_parts(self.scheme, self.netloc, "", "", "")

    @property
    def schemeless(self) -> Self:
        """Returns a `Url` with no scheme."""
        return self._from_parts("", self.netloc, self.path, self.query, self.fragment)

    def __str__(self) -> str:
        return self.address

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__) or not issubclass(
            type(other), self.__class__
        ):
            raise ValueError(f"Can't compare `Url` object to non-`Url` object.")
        return self.address == getattr(other, "address")

    def __hash__(self) -> int:
        return hash(self.address)
