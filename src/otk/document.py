import logging
from copy import deepcopy
from typing import Any

from .constant import PREFIX_TARGET, NAME_VERSION
from .error import NoTargetsError, ParseVersionError

log = logging.getLogger(__name__)


class Omnifest:
    # Underlying data is a dictionary containing the validated deserialized
    # contents of the bytes that were used to create this omnifest.
    _underlying_data: dict[str, Any]

    def __init__(self, underlying_data: dict[str, Any]) -> None:
        Omnifest.ensure(underlying_data)
        self._underlying_data = underlying_data

    @classmethod
    def ensure(cls, deserialized_data: dict[str, Any]) -> None:
        """Take a dictionary and ensure that its keys and values would be
        considered an Omnifest."""

        # And that dictionary needs to contain certain keys to indicate this
        # being an Omnifest.
        if NAME_VERSION not in deserialized_data:
            raise ParseVersionError("omnifest must contain a key by the name of %r" % (NAME_VERSION,))

        target_available = {
            key.removeprefix(PREFIX_TARGET): val for key, val in deserialized_data.items() if key.startswith(PREFIX_TARGET)
        }
        if not target_available:
            raise NoTargetsError("input does not contain any targets")

    @property
    def tree(self) -> dict[str, Any]:
        return deepcopy(self._underlying_data)
