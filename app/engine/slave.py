import argparse
import json
from pathos.helpers import mp
import tools
from aload import CrowdLoad


class TestSlave(object):
    """A class responsible for a test run using multiprocessing - one process per action."""
    def __init__(self, slave_name, test_run_id, load_fname):
        self.name = slave_name
        self.test_run_id = test_run_id
        self.test = tools.load_testrun_data(load_fname)
        self.load = self.test[slave_name]
        self.intervals = self.load['intervals']
        self.duration = sum(self.intervals)
        self.start()

    def start(self):
        """Create a test-run database on the slave and insert information about the test run."""
        conn = tools.get_db_conn('%s.db' % self.test_run_id)
        tools.db_init(conn)
        sql = "INSERT INTO info " + \
              "(test_run_id, slave_name, timestamp_started, total_load_info, slave_load_info) " + \
              "VALUES ('%s', '%s', '%s', '%s', '%s')"
        tools.db_query(conn, sql % (self.test_run_id, self.name, tools.get_timestamp(),
                                    json.dumps(self.test, sort_keys=True, indent=4),
                                    json.dumps(self.load, sort_keys=True, indent=4)))

    def complete(self):
        """Update a local test-run database on the slave once test run is completed."""
        tools.db_query(tools.get_db_conn('%s.db' % self.test_run_id),
                       "UPDATE info SET test_run_status = 'FINISHED', timestamp_completed = '%s'"
                       % tools.get_timestamp())

    def worker(self, action, send_end):
        """Method to execute one action in a loop by one user, in one process."""
        crowd = CrowdLoad(self.name, self.test_run_id, self.load, action)
        schedule_dict = crowd.get_schedule(self.load['actions'][action], self.intervals, action)
        crowd.schedule(self.duration, schedule_dict['schedule'])

    def processor(self):
        """A method to execute load - a separate process is spawned for each action."""
        pipe_list = []
        actions_processes = []
        for action in list(self.load['actions'].keys()):
            recv_end, send_end = mp.Pipe(False)
            proc = mp.Process(target=self.worker, args=(action, send_end))
            actions_processes.append(proc)
            pipe_list.append(recv_end)
        for proc in actions_processes:
            proc.start()
        for proc in actions_processes:
            proc.join()


def main():
    parser = argparse.ArgumentParser(description='Start Worker for CrowdBench app.')

    parser.add_argument('-n', '--name', required=True,
                        help='a name for the slave node, use slave\'s IP address.')
    parser.add_argument('-t', '--testrunid', required=True,
                        help='Test run identifier, should be same for all slave nodes.')
    parser.add_argument('-f', '--file', required=True,
                        help='an absolute path to the JSON file describing the load.')

    args = vars(parser.parse_args())

    test_obj = TestSlave(args['name'], args['testrunid'], args['file'])
    test_obj.start()
    print('%s Started\n' % tools.log_timestamp_str())
    test_obj.processor()
    print('\n%s Stopped\n' % tools.log_timestamp_str())
    test_obj.complete()


if __name__ == '__main__':
    main()
