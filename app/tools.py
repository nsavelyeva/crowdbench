import os
import sys
import urllib.request
import telnetlib
import socket
import paramiko
import paramiko_expect
from .engine import actions  # do not remove - required for collect_actions()


def http_get(url):
    """A simple way to open a url and return a response instance."""
    return urllib.request.urlopen(url)


def collect_actions():
    """A function to collect names of user defined actions, in fact, it returns a list of strings -
    names of Action-inherited classes defined in actions.py.
    """
    actions = [item for item in dir(sys.modules['app.engine.actions'])
               if item.startswith('Action') and item != 'Action']
    return actions


def check_connectivity(host, port, timeout=5):
    """A function to check if a port is open on a remote host."""
    telnet = telnetlib.Telnet()
    try:
        telnet.open(host, port, timeout)
        telnet.sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError) as err:
        print('No connection to %s:%s (%s).' % (host, port, err))
    return False


def ssh_connect_errors(ssh, cnf, timeout=3):
    """Try to connect to a remote host through SSH."""
    errors = []
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(cnf['host'], cnf['ssh_port'], cnf['username'], cnf['password'], timeout=timeout)
    except (paramiko.SSHException, socket.error) as err:
        errors = ['SSH Connection from %s (%s) to %s host failed: %s' %
                 (socket.gethostname(), socket.gethostbyname(socket.getfqdn()), cnf['host'], err)]
    return errors


def ssh_runcmd(ssh, cmd):
    """Execute any command on a remote host through SSH."""
    return ssh.exec_command(cmd, get_pty=True)


def ssh_transfer(ssh, cnf, files):
    """A function to read content of files stored locally and write same files on a remote host."""
    errors = []
    sftp = ssh.open_sftp()
    for fname in files:
        if os.path.isfile(fname):
            with open(fname, 'r+') as _f:
                content = _f.read()
        else:
            errors.append('Could not find file "%s" to copy onto slave %s.' % (fname, cnf['host']))
            continue
        remote_path = '%s/%s' % (cnf['folder'], fname.split(os.sep)[-1])
        try:
            with sftp.open(remote_path, 'w+') as remote_f:
                remote_f.write(content)
        except IOError as err:
            errors.append('Error accessing file %s on %s: %s' % (remote_path, cnf['host'], err))
    return errors


def ssh_interact(ssh, cnf, cmd, expect_msg='$'):
    """A function to start a command on remote host through SSH, without waiting until it ends,
    exit when expect_msg is displayed.
    """
    errors = []
    with paramiko_expect.SSHClientInteraction(ssh, timeout=5, display=False) as sshi:
        sshi.send(cmd)
        try:
            sshi.expect(expect_msg, timeout=1)
        except socket.timeout:
            output = sshi.current_output.strip()
            if 'Traceback' in output or 'Cannot start' in output:
                errors = ['Command "%s" failed on slave %s. %s' % (cmd, cnf['host'], output)]
    return errors


def collect_threads_results(queue):
    """Get all elements from a queue -
    a function is used to collect results returned by all slaves in a queue shared between threads.
    """
    results = []
    while not queue.empty():
        results.append(queue.get())
    return results
