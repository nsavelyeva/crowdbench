import asyncio
from aiohttp import ServerDisconnectedError, ClientOSError
from abc import ABCMeta, abstractmethod
import tools
# TODO: refactor the code of Action.atomic_*() methods


class Action(object):
    """An abstract class all custom actions should inherit from."""
    __metaclass__ = ABCMeta

    def __init__(self, conn, session, user, action):
        self.conn = conn
        self.session = session
        self.user = user
        self.action = action

    @abstractmethod
    async def act(self):
        """A method to imitate a single action by a single user."""
        pass

    async def atomic_get(self, url, headers=None):
        """Async method sends an HTTP GET request and awaits for response.
        On start, an entry is inserted into the database; on end - the entry is updated.

        :return: a 3-tuple (response code, response reason, response body).
        """
        with tools.LogSQL(self.conn, self.action, self.user) as sql:
            sql.code = -1
            sql.reason = 'Exception occurred but not caught (TODO).'
            body = ''
            try:
                async with self.session.get(url, headers=headers) as response:
                    await response.read()
                    sql.code = response.status
                    sql.reason = response.reason
                    body = response.read()
            except asyncio.CancelledError:
                sql.code = tools.CODES['CancelledError']
                sql.reason = 'Task cancelled by scheduler, exception suppressed'
            except ServerDisconnectedError:
                sql.code = tools.CODES['ServerDisconnectedError']
                sql.reason = 'ServerDisconnectedError, exception suppressed'
            except ClientOSError:
                sql.code = tools.CODES['ClientOSError']
                sql.reason = 'ClientOSError, exception suppressed'
            return sql.code, sql.reason, body

    async def atomic_post(self, url, headers=None, data=None):
        """Async method sends an HTTP POST request and awaits for response.
        On start, an entry is inserted into the database; on end - the entry is updated.

        :return: a 3-tuple (response code, response reason, response body).
        """
        with tools.LogSQL(self.conn, self.action, self.user) as sql:
            sql.code = -1
            sql.reason = 'Exception occurred but not caught (TODO).'
            body = ''
            try:
                async with self.session.post(url, data=data, headers=headers) as response:
                    await response.read()
                    sql.code = response.status
                    sql.reason = response.reason
                    body = response.read()
            except asyncio.CancelledError:
                    sql.code = tools.CODES['CancelledError']
                    sql.reason = 'Task cancelled by scheduler, exception suppressed'
            except ServerDisconnectedError:
                sql.code = tools.CODES['ServerDisconnectedError']
                sql.reason = 'ServerDisconnectedError, exception suppressed'
            except ClientOSError:
                sql.code = tools.CODES['ClientOSError']
                sql.reason = 'ClientOSError, exception suppressed'
            return sql.code, sql.reason, body
