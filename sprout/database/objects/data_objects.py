from sprout.database.base_object import AbstractDataTable

class TestResults(AbstractDataTable):
    def __init__(self, id=None):
        super().__init__(id)
        # Inferred properties from usage
        self._question = 0
        self._result = False
        
    @property
    def question(self) -> int:
        return self._question
        
    @question.setter
    def question(self, value: int):
        self._question = value
        
    @property
    def result(self) -> bool:
        return self._result
        
    @result.setter
    def result(self, value: bool):
        self._result = value

class MetaData(AbstractDataTable):
    def __init__(self, id=None):
        super().__init__(id)
        self._databaseVersion = 0
        
    @property
    def databaseVersion(self) -> int:
        return self._databaseVersion
        
    @databaseVersion.setter
    def databaseVersion(self, value: int):
        self._databaseVersion = value
