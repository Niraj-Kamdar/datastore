import pickle

from pymemcache.client import base


class Cache:
    def __init__(self, host="localhost", port=11211, ttl=86400):
        self.client = base.Client((host, port))
        self.ttl = ttl

    def __getitem__(self, key):
        value = self.client.get(key)
        if value:
            return pickle.loads(value)
        else:
            raise KeyError

    def __setitem__(self, key, value):
        self.client.set(key, pickle.dumps(value), expire=self.ttl)

    def __delitem__(self, key):
        value = self.client.get(key)
        if value:
            self.client.delete(key)
        else:
            raise KeyError
