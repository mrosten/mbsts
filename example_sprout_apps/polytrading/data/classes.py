from sprout.database.base_object import AbstractDataTable as DataTable

class ActiveMarket(DataTable):
    @property
    def title(self) -> str:
        return self.data.title

    @property
    def market_count(self) -> int:
        return self.data.market_count
        
    @property
    def timestamp(self) -> int:
        return self.data.timestamp

class PriceHistory(DataTable):
    @property
    def market_id(self) -> str:
        return self.data.market_id

    @property
    def outcome(self) -> str:
        return self.data.outcome

    @property
    def price(self) -> float:
        return self.data.price
        
    @property
    def timestamp(self) -> int:
        return self.data.timestamp
