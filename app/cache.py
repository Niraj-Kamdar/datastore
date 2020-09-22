import pickle

from pymemcache.client import base


class Cache:
    """ 
    dummy memcached for heroku since memcached extension is paid! 
    Cons: This will only work if no. of workers is one.
    """

    def __init__(self):
        self.data = {}

    def __getitem__(self, key):
        value = self.data.get(key)
        if value:
            return pickle.loads(value)
        else:
            raise KeyError

    def __setitem__(self, key, value):
        self.data[key] = pickle.dumps(value)

    def __delitem__(self, key):
        value = self.data.get(key)
        if value:
            del self.data[key]
        else:
            raise KeyError
