from sprout.database.base_object import AbstractDataTable as DataTable
import base64

from sprout.database.seralizers import json_seralizer_list, json_seralizer_dict, data_field


class SMS(DataTable):
    SERALIZERS = {
        list: json_seralizer_list,
        dict: json_seralizer_dict
    }

    @property
    def headers(self) -> list:
        return self.data.headers

    @property
    def from_field(self) -> str:
        return self.data.from_field

    @property
    def to_field(self) -> str:
        return self.data.to_field

    @property
    def subject_field(self) -> str:
        return self.data.subject_field

    @property
    def body_field(self) -> str:
        return base64.b64decode(self.data.body_field).decode('utf-8')

    @property
    def date_field(self) -> str:
        return self.data.date_field
