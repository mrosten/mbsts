from sprout.database.base_object import AbstractDataTable


class HttpLog(AbstractDataTable):

    @property
    def remote(self) -> str:
        return self.data.remote

    @property
    def time(self) -> int:
        return self.data.time

    @property
    def args(self) -> list:
        return self.data.args

    @property
    def body(self) -> dict:
        return self.data.body
