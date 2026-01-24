from sprout.database.base_object import AbstractDataTable as DataTable

class Tweet(DataTable):
    @property
    def tweet_id(self) -> str:
        return self.data.tweet_id

    @property
    def text(self) -> str:
        return self.data.text

    @property
    def created_at(self) -> str:
        return self.data.created_at

    @property
    def retweet_count(self) -> int:
        return self.data.retweet_count
        
    @property
    def favorite_count(self) -> int:
        return self.data.favorite_count
        
    @property
    def fetched_at(self) -> int:
        return self.data.fetched_at
