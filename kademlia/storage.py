import operator
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from itertools import takewhile
from typing import Iterator


class IStorage(ABC):
    """
    Local storage for this node.
    IStorage implementations of get must return the same type as put in by set

    Keys are tuples of the form (namespace, digest_bytes).
    - store_key: bytes : UTF-8 encoded string of the key to store.
    """

    @abstractmethod
    def set(self, key: bytes, value: any):
        """
        Set a (namespace, digest) key to the given value.
        """

    @abstractmethod
    def __getitem__(
        self,
        key: bytes,
    ) -> any:
        """
        Get the given (namespace, digest) key.
        If item doesn't exist, raises KeyError.
        """

    @abstractmethod
    def get(self, key: bytes, default=None) -> any:
        """
        Get the given (namespace, digest) key.
        If not found, return default.
        """

    @abstractmethod
    def iter_older_than(
        self, seconds_old: float
    ) -> Iterator[tuple[tuple[str, bytes], any]]:
        """
        Return an iterator of ((namespace, digest), value) for items older
        than the given seconds_old.
        """

    @abstractmethod
    def __iter__(self) -> Iterator[tuple[tuple[str, bytes], any]]:
        """
        Get an iterator over ((namespace, digest), value) in this storage.
        """


class ForgetfulStorage(IStorage):
    def __init__(self, ttl=604800):
        """
        By default, max age is a week.
        """
        self.data = OrderedDict()
        self.ttl = ttl

    def __setitem__(self, key, value):
        if key in self.data:
            del self.data[key]
        self.data[key] = (time.monotonic(), value)
        self.cull()

    def cull(self):
        for _, _ in self.iter_older_than(self.ttl):
            self.data.popitem(last=False)

    def get(self, key, default=None):
        self.cull()
        if key in self.data:
            return self[key]
        return default

    def __getitem__(self, key):
        self.cull()
        return self.data[key][1]

    def __repr__(self):
        self.cull()
        return repr(self.data)

    def iter_older_than(self, seconds_old):
        min_birthday = time.monotonic() - seconds_old
        zipped = self._triple_iter()
        matches = takewhile(lambda r: min_birthday >= r[1], zipped)
        return list(map(operator.itemgetter(0, 2), matches))

    def _triple_iter(self):
        ikeys = self.data.keys()
        ibirthday = map(operator.itemgetter(0), self.data.values())
        ivalues = map(operator.itemgetter(1), self.data.values())
        return zip(ikeys, ibirthday, ivalues)

    def __iter__(self):
        self.cull()
        ikeys = self.data.keys()
        ivalues = map(operator.itemgetter(1), self.data.values())
        return zip(ikeys, ivalues)
