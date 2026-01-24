from sprout.database.base_object import AbstractDataTable as DataTable
import base64

from sprout.database.seralizers import json_seralizer_list, json_seralizer_dict, data_field


class Wallet(DataTable):
    @property
    def network(self) -> str:
        return self.data.network

    @property
    def creation_date(self) -> int:
        return self.data.creation_date

    @property
    def balance(self) -> int:
        return self.data.balance

    @property
    def denom(self) -> str:
        return self.data.denom

class Account(DataTable):
    @property
    def counterparty(self) -> str:
        return self.data.counterparty

    @property
    def open_date(self) -> int:
        return self.data.open_date

    @property
    def number(self) -> str:
        return self.data.number

    @property
    def balance(self) -> int:
        return self.data.balance

    @property
    def denom(self) -> str:
        return self.data.denom

class FinancialTransaction(DataTable):
    @property
    def account(self) -> str:
        return self.data.account

    @property
    def debt(self) -> int:
        return self.data.debt

    @property
    def credit(self) -> int:
        return self.data.credit

    @property
    def time(self) -> int:
        return self.data.time

    @property
    def bal_at_apply(self) -> str:
        return self.data.bal_at_apply

    @property
    def comment(self) -> str:
        return self.data.comment

    @property
    def tags(self) -> list:
        return self.data.tags

class StockTicker(DataTable):
    @property
    def symbol(self) -> str:
        return self.data.symbol

    @property
    def price(self) -> float:
        return self.data.price
        
    @property
    def timestamp(self) -> int:
        return self.data.timestamp