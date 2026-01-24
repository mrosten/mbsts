import json


def data_field(seralizer=None):
     def wrapper(func):
        func._seralizer=seralizer
     return wrapper


def json_seralizer_list(func):
    def wrapper() -> list:
        return json.loads(func())


def json_seralizer_dict(func):
    def wrapper() -> dict:
        return json.loads(func())
