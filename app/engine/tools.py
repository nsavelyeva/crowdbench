"""Common functions and classes."""
import os
import datetime
import time
import json
import yaml
import sqlite3


CODES = {'CancelledError': 0,  # can appear and this is in normal
         # all below exceptions should not appear, try to decrease load then:
         'ServerDisconnectedError': -1,
         'ClientOSError': -2,
         }


def get_timestamp():
    return time.time()


def timestamp2str(fmt):
    return datetime.datetime.now().strftime(fmt)


def log_timestamp_str():
    return timestamp2str('[%Y-%m-%d %H:%M:%S.%f]')


def generate_test_run_id():
    return timestamp2str('%Y-%m-%d_%H-%M-%S_%f')


def get_last_logs(lines):
    return '\n'.join([line.replace('"', '') for line in lines if 'HTTP/1.1 200' not in line][-10:])


def load_testrun_data(file_name):
    """Test run load is described in a json file <test_run_title>.json.
    A function reads the json file and returns a Python dictionary.
    """
    load = {}
    if os.path.isfile(file_name):
        with open(file_name, 'r+') as _f:
            load = json.loads(_f.read())
    return load


def load_conf(file_name='conf.yaml'):
    """A function reads slaves configuration from a YAML-file stored on master in app folder."""
    hosts = []
    if os.path.isfile(file_name):
        with open(file_name, 'r+') as _f:
            hosts = yaml.load(_f.read())['hosts']
    return hosts


def save_conf(hosts, file_name='conf.yaml'):
    """A function (re)writes slaves configuration in a YAML-file stored on master in app folder."""
    with open(file_name, 'w+') as _f:
       _f.write(yaml.safe_dump({'hosts': hosts}, default_flow_style=False))
    return True


def load_users(file_name='users.txt', folder=None):
    """A function reads users ids from a txt-file stored on master in app/engine folder."""
    lines = []
    folder = folder or os.path.dirname(os.path.abspath(__file__))
    file_name = os.path.join(folder, file_name)
    if os.path.isfile(file_name):
        with open(file_name, 'r') as _f:
            lines = _f.readlines()
    users = list(set([line.strip() for line in lines if line.strip()]))
    if len(lines) != len(users):
        with open(file_name, 'w') as _f:
            _f.write('\n'.join(users))
    return users


def get_db_conn(file_name, folder=None):
    folder = folder or os.path.dirname(os.path.abspath(__file__))
    db = os.path.join(folder, file_name)
    db_conn = sqlite3.connect(db)
    return db_conn


def db_init(db_conn):
    sqls = ['''CREATE TABLE IF NOT EXISTS recs (\
                             id INTEGER PRIMARY KEY, \
                             atomic BOOLEAN default 1, \
                             timestamp TEXT, \
                             action TEXT, \
                             user TEXT, \
                             latency TEXT default NULL, \
                             code INTEGER default NULL, \
                             reason TEXT default NULL);''',
            '''CREATE TABLE IF NOT EXISTS info (\
                             id INTEGER PRIMARY KEY, \
                             test_run_id TEXT NOT NULL, \
                             test_run_status TEXT default 'IN PROGRESS',
                             slave_name TEXT NOT NULL, \
                             timestamp_started TEXT NOT NULL, \
                             timestamp_completed TEXT, \
                             total_load_info TEXT,
                             slave_load_info TEXT);''',
            'DELETE FROM recs;',
            'DELETE FROM info;']
    for sql in sqls:
        db_conn.execute(sql)
    db_conn.commit()
    return True


def db_query(db_conn, sql):
    cur = db_conn.cursor()
    try:
        cur.execute(sql)
        db_conn.commit()
        return cur.lastrowid, cur.fetchall()
    except Exception as err:
        print('ERROR DB: %s' % err)
        return 0, []


def log_sql(func):  # to be applied only to act() methods of classes inherited from Action()
    async def wrapper(*args):
        timestamp = get_timestamp()
        sql = "INSERT INTO recs (atomic, timestamp, action, user) VALUES (0, '%s', '%s', '%s')" \
              % (timestamp, args[0].action, args[0].user)
        row_id = db_query(args[0].conn, sql)[0]  # args[0] is an instance of Action
        code, reason = await func(*args)
        sql = "UPDATE recs SET latency='%s', code=%d, reason='%s' WHERE id=%s" \
              % (get_timestamp() - timestamp, code, reason, row_id)
        db_query(args[0].conn, sql)
        return code, reason
    return wrapper


class LogSQL(object):
    """A class used for logging in atomic_get/atomic_post methods of Action-based classes."""
    def __init__(self, conn, action, user):
        self.conn = conn
        self.action = action
        self.user = user
        self.row_id = None  # id of a row in the database (each request is kept in one row)
        self.code = None    # response code of the atomic HTTP request
        self.reason = None  # returned reason of the atomic HTTP request
        self.timestamp = get_timestamp()

    def __enter__(self):
        sql = "INSERT INTO recs (timestamp, action, user) VALUES ('%s', '%s', '%s')" \
              % (self.timestamp, self.action, self.user)
        self.row_id = db_query(self.conn, sql)[0]
        return self

    def __exit__(self, type, value, traceback):
        sql = "UPDATE recs SET latency='%s', code=%d, reason='%s' WHERE id=%s" \
              % (get_timestamp() - self.timestamp, self.code, self.reason, self.row_id)
        db_query(self.conn, sql)
        return False

