from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag
from typing_extensions import Any


class Specifier:
    def __init__(
        self,
        name: str | None = None,
        attrs: dict[str, str] = {},
        recursive: bool = True,
        string: str | None = None,
        **kwargs: Any,
    ):
        self.name = name
        self.attrs = attrs
        self.recursive = recursive
        self.string = string
        self.kwargs = kwargs

    def __str__(self) -> str:
        attributes = ""
        if "class_" in self.kwargs:
            attributes = f'class="{self.kwargs["class_"]}"'
        attributes += " " + " ".join(
            f'{key}="{value}"' for key, value in self.attrs.items()
        )
        return (
            "<"
            + f"{self.name.strip() if self.name else ''} {attributes.strip()}".strip()
            + ">"
        )


class MissingElementError(RuntimeError):
    def __init__(self, missing_element: Specifier, *parent_elements: Specifier):
        message = f"Could not find `{missing_element}` element"
        if parent_elements:
            sub_message = " -> ".join(str(element) for element in parent_elements)
            message += f" under `{sub_message}` parent element(s)."
        else:
            message += "."
        super().__init__(message)


class SoupStrainer:
    def __init__(self, soup: BeautifulSoup):
        self.soup = soup

    def _convert_to_specifier(self, specifier: str | Specifier) -> Specifier:
        return Specifier(specifier) if isinstance(specifier, str) else specifier

    def exists(self, *specifiers: str | Specifier) -> bool:
        """`specifiers`: Any number of specifiers where each element specifier is a child of the preceeding element.

        Returns `True` if the final element was found."""
        parent = self.soup
        for specifier in specifiers:
            specifier = self._convert_to_specifier(specifier)
            element = parent.find(
                specifier.name,
                specifier.attrs,
                specifier.recursive,
                specifier.string,
                **specifier.kwargs,
            )
            if not isinstance(element, Tag):
                return False
            parent = element
        return True

    def find(self, *specifiers: str | Specifier) -> Tag:
        """`specifiers`: Any number of specifiers where each element specifier is a child of the preceeding element.

        Raises a `MissingElement` exception if not found."""
        parent = self.soup
        converted_specifiers = [
            self._convert_to_specifier(specifier) for specifier in specifiers
        ]
        element = None
        for i, specifier in enumerate(converted_specifiers):
            specifier = self._convert_to_specifier(specifier)
            element = parent.find(
                specifier.name,
                specifier.attrs,
                specifier.recursive,
                specifier.string,
                **specifier.kwargs,
            )
            if not isinstance(element, Tag):
                raise MissingElementError(specifier, *converted_specifiers[:i])
            parent = element
        if not element:
            raise ValueError("No specifiers provided.")
        return element
