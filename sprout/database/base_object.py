import json
from abc import abstractmethod, ABC
from enum import Enum

from box import Box

from sprout.util import get_property_type_map


class Serialization(Enum):
    STRING = 1
    JSON = 2
    DICT = 3


class AbstractDataTable:
    DATABASE_IMPL = None

    def __init__(self, id):
        self.objid = id
        self.data: Box = None


    def seralize(self, s: Serialization):
        if s is Serialization.STRING:
            data = {}
            for k, _ in get_property_type_map(self):
                data[k] = getattr(self, k)
            return json.dumps(data)
        elif s is Serialization.JSON:
            data = {}
            for k, _ in get_property_type_map(self):
                data[k] = getattr(self, k)
            return json.dumps(data)
        elif s is Serialization.DICT:
            data = {}
            for k, _ in get_property_type_map(self):
                data[k] = getattr(self, k)
            return data
        else:
            raise Exception(f"unknown serialization {s}")


    @property
    def id(self):
        return self.data.id

    async def read(self):
        return await AbstractDataTable.DATABASE_IMPL._read(self, self.objid)

    async def set(self, **kwargs):
        return await AbstractDataTable.DATABASE_IMPL._set(self, self.objid, **kwargs)
