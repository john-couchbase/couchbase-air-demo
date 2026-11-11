"""Dedicated collection adapter. No whole-collection scans or deletes."""
from datetime import timedelta
from couchbase.exceptions import CasMismatchException, DocumentNotFoundException, DocumentExistsException
from couchbase.options import InsertOptions, ReplaceOptions
from .sessions import Conflict, Missing

class CouchbaseStore:
    def __init__(self,collection): self.collection=collection
    def insert(self,key,value):
        try: self.collection.insert(key,value,InsertOptions(expiry=timedelta(hours=24)))
        except DocumentExistsException: raise Conflict() from None
    def get(self,key):
        try:
            r=self.collection.get(key)
            return r.content_as[dict],r.cas
        except DocumentNotFoundException: raise Missing() from None
    def replace(self,key,value,cas):
        try: self.collection.replace(key,value,ReplaceOptions(cas=cas,preserve_expiry=True))
        except CasMismatchException: raise Conflict() from None
        except DocumentNotFoundException: raise Missing() from None
