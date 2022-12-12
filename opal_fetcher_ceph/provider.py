"""
Simple fetch provider for niginx ceph
This fetcher also serves as an example how to build custom OPAL Fetch Providers.
"""
from typing import Optional, List
import urllib.request
import tarfile
import json
import asyncpg
from asyncpg.transaction import Transaction
from asyncpg.exceptions import DataError
from pydantic import BaseModel, Field
from tenacity import wait, stop, retry_unless_exception_type

from opal_common.fetcher.fetch_provider import BaseFetchProvider
from opal_common.fetcher.events import FetcherConfig, FetchEvent
from opal_common.logger import logger
from io import BytesIO


class NginxCephFetcherConfig(FetcherConfig):
    """
    Config for PostgresFetchProvider, inherits from `FetcherConfig`.
    * In your own class, you must set the value of the `fetcher` key to be your custom provider class name.
    """
    fetcher: str = "NginxCephFetchProvider"


class NginxCephFetchEvent(FetchEvent):
    """
    When writing a custom provider, you must create a custom FetchEvent subclass, just like this class.
    In your own class, you must:
    * set the value of the `fetcher` key to be your custom provider class name.
    * set the type of the `config` key to be your custom config class (the one just above).
    """
    fetcher: str = "NginxCephFetchProvider"
    config: NginxCephFetcherConfig = None


class NginxCephFetchProvider(BaseFetchProvider):
    """
    An OPAL fetch provider for postgres.
    
    We fetch data from a postgres database by running a SELECT query, 
    transforming the results to json and dumping the results into the policy store.
    When writing a custom provider, you must:
    - derive your provider class (inherit) from BaseFetchProvider
    - create a custom config class, as shown above, that derives from FetcherConfig
    - create a custom event class, as shown above, that derives from FetchEvent
    At minimum, your custom provider class must implement:
    - __init__() - and call super().__init__(event)
    - parse_event() - this method gets a `FetchEvent` object and must transform this object to *your own custom event class*.
        - Notice that `FetchEvent` is the base class
        - Notice that `PostgresFetchEvent` is the custom event class
    - _fetch_() - your custom fetch method, can use the data from your event
    and config to figure out *what and how to fetch* and actually do it.
    - _process_() - if your fetched data requires some processing, you should do it here.
        - The return type from this method must be json-able, i.e: can be serialized to json.
    
    You may need to implement:
    - __aenter__() - if your provider has state that needs to be cleaned up,
    (i.e: http session, postgres connection, etc) the state may be initialized in this method.
    - __aexit__() - if you initialized stateful objects (i.e: acquired resources) in your __aenter__, you must release them in __aexit__
    """
    RETRY_CONFIG = {
        'wait': wait.wait_random_exponential(),
        'stop': stop.stop_after_attempt(10),
        'retry': retry_unless_exception_type(DataError),  # query error (i.e: invalid table, etc)
        'reraise': True
    }

    def __init__(self, event: NginxCephFetchEvent) -> None:
        """
        inits your provider class
        """
        super().__init__(event)

    def parse_event(self, event: FetchEvent) -> NginxCephFetchEvent:
        """
        deserializes the fetch event type from the general `FetchEvent` to your derived fetch event (i.e: `PostgresFetchEvent`)
        """
        return NginxCephFetchEvent(**event.dict(exclude={"config"}), config=event.config)

    # if you require context to cleanup or guard resources, you can use __aenter__() and __aexit__()
    async def __aenter__(self):
        # initializing parameters from the event/config
        self._event: NginxCephFetchEvent
        dsn: str = self._event.url
        connection_params: dict = {} if self._event.config.connection_params is None else self._event.config.connection_params.dict(
            exclude_none=True)

        # connect to the postgres database
        # self._connection: asyncpg.Connection = await asyncpg.connect(dsn, **connection_params)

        # start a readonly transaction (we don't want OPAL client writing data due to security!)
        self._transaction: Transaction = self._connection.transaction(readonly=True)
        await self._transaction.__aenter__()

        return self

    async def __aexit__(self, exc_type=None, exc_val=None, tb=None):
        # End the transaction
        if self._transaction is not None:
            await self._transaction.__aexit__(exc_type, exc_val, tb)
        # Close the connection
        if self._connection is not None:
            await self._connection.close()

    async def _fetch_(self):
        """
        the actual logic that you need to implement to fetch the `DataSourceEntry`.
        Can reference your (derived) `FetcherConfig` object to access your fetcher attributes.
        """
        self._event: NginxCephFetchEvent  # type casting

        if self._event.url is None:
            logger.warning("incomplete fetcher config: fetcher require a url to specify from where data to fetch!")
            return

        logger.debug(f"{self.__class__.__name__} fetching from {self._url}")
        data = self.fetch_tar_file_data(self._url)
        return data

    async def _process_(self, data):
        """
        optional processing of the data returned by _fetch_().
        must return a jsonable python object (i.e: an object that can be dumped to json,
        e.g: a list or a dict that contains only serializable objects).
        """
        return json.loads(data)

    async def fetch_tar_file_data(self, url):
        ftpstream = urllib.request.urlopen(url)
        # BytesIO creates an in-memory temporary file.
        # See the Python manual: http://docs.python.org/3/library/io.html
        tmpfile = BytesIO()
        while True:
            # Download a piece of the file from the connection
            s = ftpstream.read(16384)

            # Once the entire file has been downloaded, tarfile returns b''
            # (the empty bytes) which is a falsey value
            if not s:
                break

            # Otherwise, write the piece of the file to the temporary file.
            tmpfile.write(s)
            ftpstream.close()

            # Now that the FTP stream has been downloaded to the temporary file,
            # we can ditch the FTP stream and have the tarfile module work with
            # the temporary file.  Begin by seeking back to the beginning of the
            # temporary file.
            tmpfile.seek(0)

            # Now tell the tarfile module that you're using a file object
            # that supports seeking backward.
            # r|gz forbids seeking backward; r:gz allows seeking backward
            tfile = tarfile.open(fileobj=tmpfile, mode="r:gz")

            # You want to limit it to the .nxml files
            tfile_data = [filename
                          for filename in tfile.getnames()
                          if filename.endswith('.json')]

            tfile_extract1 = tfile.extractfile(tfile_data[0])
            tfile_extract1_text = tfile_extract1.read()
            # jsonData = json.loads(tfile_extract1_text)
            # And when you're done extracting json:
            tfile.close()
            tmpfile.close()
            return tfile_extract1_text
