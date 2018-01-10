import sys
import asyncio
from aiohttp import ClientSession
import tools
import actions     # import is required, to let AsyncLoad.fetch() method work.
try:
    import uvloop  # fails on Windows - RuntimeError: uvloop does not support Windows at the moment.
except ImportError:
    pass


def create_loop():
    """Function creates and returns an asyncio loop (on Windows) or uvloop (on Linux) instance.
    Slaves will use uvloop for test runs,
    Windows-based master will use loop from asyncio: no impact at all, it's for imports correctness.
    """
    try:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except NameError:
        pass
    loop = asyncio.get_event_loop()
    return loop


def stop_loop(loop):
    loop.stop()


class AsyncLoad(object):
    """A class to perform actions - keep each user doing the same action in a loop."""
    def __init__(self, test_run_id, slave_load):
        self.test_run_id = test_run_id
        self.slave_load = slave_load
        self.db_conn = tools.get_db_conn('%s.db' % self.test_run_id) if test_run_id else None
        self.users = tools.load_users('users.txt')

    async def fetch(self, session, user, action):
        """Imitate activity of one user - keep doing a particular action in infinite loop,
        until the task is stopped by the event loop according to the schedule.
        Note: keep 'import actions' to let this work.
        """
        obj = getattr(sys.modules['actions'], action)(self.db_conn, session, user, action)
        while True:
            await obj.act()

    async def bound_fetch(self, sem, session, user, action):
        async with sem:
            await self.fetch(session, user, action)

    async def run_action(self, action):
        """Start doing given action by unique users, user ids are kept in 'users.txt'."""
        tasks = []
        sem = asyncio.Semaphore(1000)
        async with ClientSession() as session:
            for i in range(*self.slave_load['users'][action]):
                task = asyncio.ensure_future(self.bound_fetch(sem, session, self.users[i], action))
                tasks.append(task)
            responses = asyncio.gather(*tasks)
            await responses


class CrowdLoad(AsyncLoad):
    """A class to simulate user behavior by a particular slave."""
    def __init__(self, slave_name, test_run_id, slave_load, action_name):
        super(CrowdLoad, self).__init__(test_run_id, slave_load)
        self.action_name = action_name
        self.slave_name = slave_name
        self.loop = create_loop()

    def schedule_load(self, duration, loop, action, delta):
        """A method to decide for how long the task should be running,
        the method is responsible to start and stop the task.
        """
        future = asyncio.ensure_future(self.run_action(action), loop=loop)
        asyncio.wait_for(future, duration, loop=loop)
        loop.call_later(duration, future.cancel)

    def schedule(self, duration, schedule):
        """A method to schedule all tasks of the test run."""
        for item in schedule:
            num_second, step_duration, users_count, action = item
            self.loop.call_later(num_second, self.schedule_load, step_duration,
                                 self.loop, action, users_count)
        self.loop.call_later(duration, stop_loop, self.loop)
        self.loop.run_forever()

    @staticmethod
    def get_schedule(deltas, intervals, action):
        """Schedule load changes in order to abort as less users as possible
        when need to remove users.
        Method calculates total duration, makes a schedule structure, generates a text description.
        """
        schedule = []
        msg = ''
        counts = [sum(deltas[:num]) for num in range(1, len(deltas) + 1)]
        i = m = t = 0
        tmp = [item - m for item in counts]
        while i < len(counts):
            j = i       # start from i because there is no need to look back "in the past"
            x = tmp[i]  # users count to be scheduled during this iteration
            if x > 0:   # negative deltas will be skipped
                msg += '\n%s%s-th second: need to have %s users doing %s:' % \
                       ('#%s:\n' % action if t == 0 else '', t, x, action)
                while j < len(tmp):
                    p = j + tmp[j:].index(0) if 0 in tmp[j:] else len(tmp)  # index of next zero
                    # q: slice from "now" to that "next" zero, should not contain zeros!
                    # m: minimum of remaining users count and values from the slice
                    q = [item for item in tmp[j:p]]
                    m = min(q + [x]) if q else x
                    if m:
                        # k: how many time intervals users should act
                        # d: partial duration for m users to keep acting
                        k = tmp[j:].index(0) if 0 in tmp[j:] else len(tmp[j:])
                        d = sum(intervals[j:j + k + 1])
                        msg += '\n\t\t- scheduling %s users to act for %s seconds.' % (m, d)
                        schedule.append((t, d, m, action))
                        # now update counts of users which are still to be scheduled:
                        for num in range(i, len(tmp)):
                            if tmp[num] == 0:
                                break    # no need to consider users deltas after first zero
                            tmp[num] = tmp[num] - m  # users remaining to act after partial duration
                    x -= m  # remaining users count
                    j += 1
                    if x <= 0:  # all users for this iteration are scheduled, go to next iteration
                        break
            else:
                msg += '\n%s-th second: stopping %s users.' % (t, abs(deltas[i]))
            t += intervals[i]
            i += 1
        return {'duration': sum(intervals), 'schedule': schedule, 'description': msg}
