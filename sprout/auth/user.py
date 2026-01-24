import json
from box import Box


class User(object):
    def __init__(self, name: str, organizaion: str, admin: bool, tags: list ):
        self.data = Box({
            "name": name,
            "organizaion": organizaion,
            "admin": admin,
            "tags": tags
        })

    def __str__(self):
        return json.dumps(self.data)

    @property
    def name(self):
        return self.data.name

    @property
    def organizaion(self):
        return self.data.organizaion

    @property
    def admin(self):
        return self.data.admin

    @property
    def tags(self) -> list:
        return self.data.tags
