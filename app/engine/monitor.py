import os
import socket
import argparse
import bottle
import tools


@bottle.route('/_get_chartdata', method='OPTIONS')
@bottle.route('/_get_summary', method='OPTIONS')
@bottle.route('/_get_logs', method='OPTIONS')
def options():
    return {}


@bottle.route('/_get_chartdata', method='GET')
def get_chartdata():
    """Collect data from a slave to build a chart on the monitoring web-page."""
    callback = bottle.request.query.get('callback')
    y_axis = bottle.request.query.get('y_axis').strip()
    w_acts = ["action='%s'" % act for act in bottle.request.query.get('actions').strip().split(',')]
    w_acts = 'AND (%s)' % ' OR '.join(w_acts) if w_acts else ''
    f_value = 'AVG(latency)' if y_axis.startswith('avg') else 'COUNT(timestamp)'
    atomic = 1 if y_axis in ['aops', 'avgl'] else 0

    db_conn = tools.get_db_conn('%s.db' % bottle.request.query.test_run_id)
    sql = 'SELECT test_run_status, timestamp_started, timestamp_completed FROM info LIMIT 1'
    status, started, finished = tools.db_query(db_conn, sql)[1][0]
    progress = int(float(finished) - float(started)) if finished \
        else int(tools.get_timestamp() - float(started))

    sql = 'SELECT substr(timestamp, 0, 11), code, %s FROM recs ' % f_value + \
          'WHERE atomic=%s %s GROUP BY code, substr(timestamp, 0, 11) ' % (atomic, w_acts) + \
          'ORDER BY id DESC LIMIT 3600'  # last 1 hour activity

    result = tools.db_query(db_conn, sql)[1] if finished else tools.db_query(db_conn, sql)[1][:-1]
    result = list(reversed(result))
    results = {str(abs(int(item[0]) - int(float(started)))):
               {'failed': 0, 'passed': 0, 'incomplete': 0} for item in result}
    for item in result:  # item[0] - timestamp, item[1] - code (None if incomplete), item[2] - value
        timestamp = str(int(item[0]) - int(float(started)))
        value = item[2] or 0
        results[timestamp]['failed'] += value if item[1] and item[1] != 200 else 0
        results[timestamp]['passed'] += value if item[1] == 200 else 0
        results[timestamp]['incomplete'] += value if item[1] == None else 0
    results = [{'timestamp': key, 'failed': value['failed'], 'passed': value['passed'],
                'incomplete': value['incomplete']} for key, value in results.items()]
    result = {bottle.request.query.slave: results, 'status': status,
              'started': started, 'finished': finished or '(not finished)', 'progress': progress}
    return '{0}({1})'.format(callback, result)


@bottle.route('/_get_summary', method='GET')
def get_summary():
    """Collect summary of responses from a slave to display it on the monitoring web-page."""
    callback = bottle.request.query.get('callback')
    db_conn = tools.get_db_conn('%s.db' % bottle.request.query.test_run_id)
    sql = 'SELECT code, reason, COUNT(*) FROM recs GROUP BY reason'
    result = tools.db_query(db_conn, sql)[1]
    results = [{'reason': item[1] or 'Incompleted (still running or aborted)',
                'count': item[2], 'code': str(item[0])} for item in result if item[2]]
    return '{0}({1})'.format(callback, results)


@bottle.route('/_get_logs', method='GET')
def get_logs():
    """Collect logs from monitor.py and slave.py from a slave."""
    callback = bottle.request.query.get('callback')
    folder = os.path.dirname(os.path.abspath(__file__))
    test_run_title = bottle.request.query.test_run_id
    results = {'logs': {'monitor': '', 'testrun': ''}, 'host': bottle.request.headers.get('host')}
    try:
        with open(os.path.join(folder, 'monitor.log'), 'r+') as _f:
            results['logs'].update({'monitor': tools.get_last_logs(_f.readlines())})
        with open(os.path.join(folder, '%s-testrun.log' % test_run_title), 'r+') as _f:
            results['logs'].update({'testrun': tools.get_last_logs(_f.readlines())})
    except IOError as err:
        key = 'monitor' if 'monitor' in str(err) else 'testrun'
        results['logs'].update({key: 'Could not find logs: %s' % err})
    return '{0}({1})'.format(callback, [results])


def main():
    parser = argparse.ArgumentParser(description='Monitoring agent for CrowdBench app.')

    parser.add_argument('-s', '--server', default='0.0.0.0', required=False,
                        help='IP address of a network interface for monitoring agent to run on.')
    parser.add_argument('-p', '--port', default=8081, type=int, required=False,
                        help='a port number for monitoring agent to listen on.')

    args = vars(parser.parse_args())

    try:
        bottle.run(bottle.app(), host=args['server'], port=args['port'])
    except socket.gaierror as err:
        print('Cannot start Monitoring agent for CrowdBench app due to socket error:\n\t%s.' % err)
        print('Is the network interface %s correct?' % args['server'])
        print('Try "monitor.py -h" to see launching options.')
    except OSError as err:
        print('Cannot start Monitoring agent for CrowdBench app due to OS error:\n\t%s.' % err)
        print('Is the port %s already in use?' % args['port'])
        print('Try "monitor.py -h" to see launching options.')


if __name__ == '__main__':
    main()
