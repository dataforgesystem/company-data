from base.storage import DataStorage
from interfaces.iconfig import IDatabaseConfig
from models.company_data import CompanyData

from pymongo import MongoClient
from pymongo.results import UpdateResult
from pymongo.database import Database
from pymongo.collection import Collection


class MongoDBStorage(DataStorage):
    def __init__(self, config: IDatabaseConfig) -> None:
        self.config = config

    def connect(self):
        self.mongo_connection = MongoClient(
            self.config.dsn, **self.config.extra_options
        )
        self.db: Database = self.mongo_connection[self.config.name]
        self.company_data_collection: Collection = self.db["company_data"]

    def store_data(self, company_data: CompanyData) -> UpdateResult:
        filter_q = {"company_domain": company_data.company_domain}
        set_q = {"$set": company_data.model_dump()}
        result = self.company_data_collection.update_one(
            filter=filter_q, update=set_q, upsert=True
        )
        return result
