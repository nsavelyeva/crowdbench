import os
import json
import paramiko
from threading import Thread
from multiprocessing.dummy import Pool as ThreadPool
from queue import Queue
from .engine import tools as etools  # engine tools
from .forms import ConfigForm
from . import tools


def write_yaml_conf(form):
    """Function (re)writes a 'conf.yaml' file - keeps information about slave hosts there."""
    msg = ''
    hosts = []
    do_update = True
    for item in form.hosts.data:
        if item['clone'] or item['remove']:
            do_update = False
            break
        else:
            hosts.append({k: v for k, v in item.items() if k not in ['clone', 'remove']})
    if do_update:
        etools.save_conf(hosts, 'conf.yaml')
        msg = 'Settings have been successfully written to conf.yaml.'
    return form, msg


def load_yaml_conf(request_form):
    """Function loads details about slave hosts from a 'conf.yaml' file into a web form."""
    form = ConfigForm(request_form)
    hosts = etools.load_conf('conf.yaml')
    if hosts:
        while form.hosts.data:
            form.hosts.pop_entry()  # remove default values defined in ConfigForm class
        for host in hosts:
            host.update({'clone': False, 'remove': False})
            form.hosts.append_entry(host)
        msg = 'Hosts settings have been successfully loaded from conf.yaml.'
    else:
        msg = 'No conf.yaml found, please specify settings for installation.'
    return form, msg


def update_conf_form(form):
    """Function updates form values
    when 'Clone' or 'Remove' button is pressed on the hosts constructor web form.
    """
    msg = ''
    for host in form.hosts.data:
        if host['clone']:
            try:
                host.update({'clone': False, 'remove': False})
                form.hosts.append_entry(host)
            except AssertionError as err:
                msg = str(err)
            break
        elif host['remove']:
            tmp = [item for item in form.hosts.data if not item['remove']]
            if tmp:
                while form.hosts.data:
                    form.hosts.pop_entry()
                for item in tmp:
                    form.hosts.append_entry(item)
            break
    return form, msg


def update_constructor_form(form):
    """Function updates form values
    when 'Clone' or 'Remove' button is pressed on the test-run constructor web form.
    """
    msg = ''
    for step in form.steps.data:
        if step['clone']:
            try:
                step.update({'clone': False, 'remove': False})
                form.steps.append_entry(step)
            except AssertionError as err:
                msg = str(err)
            break
        elif step['remove']:
            tmp = [item for item in form.steps.data if not item['remove']]
            if tmp:
                while form.steps.data:
                    form.steps.pop_entry()
                for item in tmp:
                    form.steps.append_entry(item)
            break
    start = 0
    for entry in form.steps.entries:
        entry.start.data = start
        start += entry.duration.data
    return form, msg

# TODO: create a decorator @tools.threaded
def deploy_slaves(files):
    """Deploy all slaves in parallel using multiple threads. TODO: decorator for threading."""
    queue = Queue()

    args = []
    for cnf in etools.load_conf('conf.yaml'):
        args.append((cnf, files, queue))
    pool = ThreadPool(len(args))
    results = pool.starmap(deploy_slave, args)
    pool.close()
    pool.join()

    #for host in etools.load_conf('conf.yaml'):
    #    thread = Thread(target=deploy_slave, args=(host, files, queue))
    #    thread.start()
    #    thread.join()
    errors = tools.collect_threads_results(queue)
    return errors


def deploy_slave(cnf, files, queue):
    """Run OS commands on a slave host through SSH to create folders and start monitoring agent."""
    with paramiko.SSHClient() as ssh:
        errors = tools.ssh_connect_errors(ssh, cnf)
        if errors:
            return errors
        error = tools.ssh_runcmd(ssh, 'mkdir -p %s' % cnf['folder'])[2].read().strip()
        if error:
            return ['Could not create folders on %s: %s' % (cnf['host'], error.decode('utf-8'))]
        errors = tools.ssh_transfer(ssh, cnf, files)
        if not errors:
            cmd = 'cd %s && nohup %s monitor.py --server=%s --port=%s > monitor.log && disown\n' % \
                  (cnf['folder'], cnf['python3'], cnf['host'], cnf['web_port'])


            errors = tools.ssh_interact(ssh, cnf, cmd, 'Started')
    for error in errors:
        queue.put(error)
    return errors


def validate_slaves(form):
    """Validate all slaves in parallel using multiple threads. TODO: decorator for threading."""
    queue = Queue()
    for host in form.hosts.data:
        thread = Thread(target=validate_slave, args=(form, host, queue))
        thread.start()
        thread.join()
    errors = tools.collect_threads_results(queue)
    return errors


def validate_slave(form, cnf, queue):
    """A function to validate a slave host before saving the configuration about slave nodes.
    OS commands will be executed on a slave host through SSH to validate:
    - Python version,
    - required Python packages,
    - availability of the port for monitoring agent.
    """
    with paramiko.SSHClient() as ssh:
        if tools.ssh_connect_errors(ssh, cnf):
            queue.put('Cannot SSH onto %s.' % cnf['host'])
        else:
            host_errors = []
            cmd = "ps uxa | grep 'monitor.py --server' | grep -v grep " + \
                                  "| awk '{print $2}' | xargs kill -9 "
            out, err = tools.ssh_runcmd(ssh, cmd)[1:]  # kill monitors if any
            host_errors.extend(form._python_version(ssh, cnf))
            host_errors.extend(form._packages_installed(ssh, cnf))
            host_errors.extend(form._ports_available(cnf['host'], cnf['web_port']))
            if host_errors:
                error = 'Please fix:<br> - %s' % ('<br> - '.join(host_errors))
                queue.put(error)
    return []


def start_slaves(obj):
    """Start all slaves in parallel using multiple threads. TODO: decorator for threading."""
    fname = 'load-%s.json' % obj.test_run_id
    abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    with open(abs_path, 'w') as _f:
        _f.write(json.dumps(obj.part, sort_keys=True, indent=4))
    queue = Queue()

    args = []
    for cnf in etools.load_conf('conf.yaml'):
        cmd = 'slave.py -n=%s -t=%s -f=%s/%s' % (cnf['host'], obj.test_run_id, cnf['folder'], fname)
        args.append((cnf, obj.test_run_id, cmd, queue))
    pool = ThreadPool(len(args))
    results = pool.starmap(start_slave, args)
    pool.close()
    pool.join()
    #for cnf in etools.load_conf('conf.yaml'):
    #    cmd = 'slave.py -n=%s -t=%s -f=%s/%s' % (cnf['host'], obj.test_run_id, cnf['folder'], fname)
    #    thread = Thread(target=start_slave, args=(cnf, obj.test_run_id, cmd, queue))
    #    thread.start()
    #    thread.join()

    errors = tools.collect_threads_results(queue)
    if os.path.isfile(abs_path):
        os.remove(abs_path)
    return errors


def start_slave(cnf, test_run_id, command, queue):
    """Run OS commands on a slave host through SSH to start a test run."""
    with paramiko.SSHClient() as ssh:
        errors = tools.ssh_connect_errors(ssh, cnf)
        if errors:
            return errors
        load_fname = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'load-%s.json' % test_run_id)
        errors = tools.ssh_transfer(ssh, cnf, [load_fname])
        if not errors:
            cmd = 'cd %s && nohup %s %s > %s-testrun.log && disown' % \
                   (cnf['folder'], cnf['python3'], command, test_run_id)
            errors = tools.ssh_interact(ssh, cnf, cmd, 'Started')
    for error in errors:
        queue.put(error)
    return errors


def delete_testrun(test_run_title):
    """Delete test run files from slaves in parallel using multiple threads. TODO: decorator."""
    queue = Queue()
    for cnf in etools.load_conf('conf.yaml'):
        thread = Thread(target=delete_testrun_from_slave,
                        args=(cnf, cnf['folder'], test_run_title, queue))
        thread.start()
        thread.join()
    errors = tools.collect_threads_results(queue)
    if errors:
        return [(err, 'danger') for err in errors]
    return [('Removed test run files from slaves', 'success')]


def delete_testrun_from_slave(cnf, folder, test_run, queue):
    """Run OS commands on a slave host through SSH to delete db- and json-files of the test run."""
    with paramiko.SSHClient() as ssh:
        if tools.ssh_connect_errors(ssh, cnf):
            queue.put('Could not SSH onto slave %s.' % cnf['host'])
            return False
        files = ['%s/%s.db' % (folder, test_run), '%s/load-%s.json' % (folder, test_run)]
        tools.ssh_runcmd(ssh, 'rm -f %s' % ' '.join(files))
        out = tools.ssh_runcmd(ssh, 'ls -l %s' % folder)[1].read().decode('utf-8')
        for fname in files:
            if fname[fname.rfind('/')+1:] in out:
                queue.put('Could not remove %s from slave %s.' % (fname, cnf['host']))
    return True


def monitor_slaves(url):
    """Collect monitoring data from slaves in parallel using multiple threads. TODO: decorator."""
    url_right = url[url.rfind('/'):]
    queue = Queue()
    for cnf in etools.load_conf('conf.yaml'):
        url_left = 'http://%s:%s' % (cnf['host'], cnf['web_port'])
        thread = Thread(target=monitor_slave, args=(url_left + url_right, queue))
        thread.start()
        thread.join()
    data = tools.collect_threads_results(queue)
    if '_get_summary' in url:
        data = aggregate_summary(data)
    elif '_get_chartdata' in url:
        data = aggregate_chartdata(data)
    else:
        data = aggregate_logs(data)
    return data


def monitor_slave(url, queue):
    """Send HTTP GET request to a slave host to collect test run data."""
    response = tools.http_get(url)
    body = str(response.read()).replace("'", '"')
    body = body[body.find('(') + 1:body.rfind(')')]
    result = json.loads(body)
    if '_get_chartdata' in url:
        total = {item['timestamp']:
                 {'failed': item['failed'],
                  'passed': item['passed'],
                  'incomplete': item['incomplete']}
             for item in result['total']}
        result['total'] = total
    elif '_get_summary' in url:
        result = {item['reason']: {'code': item['code'], 'count': item['count']} for item in result}
    else:  # '_get_logs'
        result = result[0]
    queue.put(result)
    return response


def aggregate_chartdata(data):
    """Aggregate test run data collected from all slaves to draw an aggregated chart."""
    status = 'FINISHED'
    progress = 604801  # 1 week seconds + 1
    started = 'not defined'
    finished = '(not completed)'
    total = {}
    for item in data:
        for key, value in item['total'].items():
            if key not in total:
                total.update({key: {'failed': 0, 'passed': 0, 'incomplete': 0}})
            total[key]['failed'] += value['failed']
            total[key]['passed'] += value['passed']
            total[key]['incomplete'] += value['incomplete']
        status = 'IN PROGRESS' if item['status'] == 'IN PROGRESS' else status
        started = item['started'] if item['started'] < started else started
        finished = item['finished'] if item['finished'] > finished else finished
        progress = item['progress'] if item['progress'] < progress else progress
    total = [{'timestamp': key, 'failed': total[key]['failed'], 'passed': total[key]['passed'],
              'incomplete': total[key]['incomplete']}
             for key in sorted(total, key=lambda key: int(key))]
    result = {'total': total,
              'status': status, 'started': started, 'finished': finished,
              'progress': progress if progress < 604801 else 0}
    return result


def aggregate_summary(data):
    """Aggregate test run summary collected from all slaves to display an aggregated summary."""
    result = {}
    for item in data:
        for key, value in item.items():
            if key not in result:
                result.update({key: {'code': value['code'], 'count': 0}})
            result[key]['count'] += value['count']
    result = [{'reason': key, 'count': result[key]['count'], 'code': result[key]['code']}
              for key in sorted(result)]
    return result


def aggregate_logs(data):
    """Aggregate test run logs collected from all slaves to display an aggregated debug info."""
    result = [{'host': item['host'], 'logs': item['logs']} for item in data]
    return result
