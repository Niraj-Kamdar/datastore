import os
import pickle

from pymemcache.client import base


class Cache:
    HOST = os.getenv("MEMCACHED_HOST")
    PORT = os.getenv("MEMCACHED_PORT")
    TTL = os.getenv("MEMCACHED_TTL")

    def __init__(self, host="localhost", port=11211, ttl=86400):
        self.host = self.__class__.HOST or host
        self.port = self.__class__.PORT or port
        self.ttl = self.__class__.TTL or ttl
        self.client = base.Client((self.host, self.port))

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
