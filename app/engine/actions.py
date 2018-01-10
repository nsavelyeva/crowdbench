"""Add custom actions here as follows:
 * create separate class for each action;
 * inherit from Action class, and the class name should start with 'Action';
 * act() methods should be decorated with @log_sql;
 * use atomic_get() and atomic_post() methods to send HTTP GET and HTTP POST requests.
 * append parameters to URLs if any, as usual: http://site/route?param1=value1&param2=value2.
 * to access user id inside act() methid, use self.user.
"""
from action import Action
from tools import log_sql


class ActionSample(Action):
    """Example of a custom action."""
    @log_sql
    async def act(self):
        result = await self.atomic_get("http://some.site.net:8080/sample")
        code, reason, body = await self.atomic_get("http://another.website.net:80/something/")
        return code, reason


class ActionExample(Action):
    """Another example of a custom action."""
    @log_sql
    async def act(self):
        await self.atomic_get("http://some.site.net:8080/example")
        code, reason, body = await self.atomic_get("http://another.website.net:80/anything/")
        return code, reason
