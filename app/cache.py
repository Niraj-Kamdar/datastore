import os
import pickle
from collections import defaultdict
from math import inf
from time import time


class TimeValue:
    def __init__(self):
        self.time = []
        self.value = []

    def append(self, _value, _time):
        self.value.append(_value)
        self.time.append(_time)

    def __getitem__(self, i):
        return self.value[i], self.time[i]

    def __bool__(self):
        return bool(self.time)


class TTLCache:
    def __init__(self):
        self._data = defaultdict(TimeValue)
        self.size = 0

    def __getitem__(self, k):
        current_time = int(time())
        values = self._data[k]  # raises KeyError when invalid
        new_values = TimeValue()
        for i, t in enumerate(values.time):
            if t > current_time:
                new_values.append(*values[i])
            else:
                self.size -= 1
        if new_values:
            self._data[k] = new_values
            return new_values.value
        del self._data[k]
        return None

    def __setitem__(self, k, v):
        if isinstance(v, tuple):
            if v[1] <= 0:
                raise ValueError("TTL can't be less than 1")
            self._data[k].append(v[0], v[1] + int(time()))
        else:
            self._data[k].append(v, inf)
        self.size += 1

    def __delitem__(self, k):
        del self._data[k]

    def flush(self):
        self._data = defaultdict(TimeValue)
        self.size = 0

    @classmethod
    def load(cls, filename):
        with open(filename, "rb") as f:
            instance = pickle.load(f)
        return instance

    def save(self, filename):
        with open(filename, "wb") as f:
            pickle.dump(self, f)

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        for key in self._data:
            yield key

    def items(self):
        for key in self._data:
            yield key, self[key]


class Cache:
    """ 
    dummy memcached for heroku since heroku memcached extension is paid! 
    Cons: This will only work if no. of workers is one.
    """

    def __init__(self):
        self.ttl = int(os.getenv("MEMCACHED_TTL", default=0)) or 360 # 10 minutes
        self.data = TTLCache()

    def __getitem__(self, key):
        value = self.data[key]
        if value:
            return value[0]
        else:
            raise KeyError

    def __setitem__(self, key, value):
        self.data[key] = value, self.ttl

    def __delitem__(self, key):
        value = self.data[key]
        if value:
            del self.data[key]
        else:
            raise KeyError
