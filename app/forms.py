from wtforms import validators, Form, FieldList, FormField, \
    SubmitField, StringField, PasswordField, IntegerField, SelectField, TextAreaField
from wtforms.widgets import PasswordInput
from . import db_queries, helpers, tools


class ServerForm(Form):
    """A class describing a form for one slave host."""
    host = StringField('Host',
                       [validators.DataRequired(), validators.IPAddress()],
                       default='127.0.0.1', render_kw={'size': 15, 'class': 'form-control form-control-sm'})
    ssh_port = IntegerField('SSH port',
                            [validators.DataRequired()],
                            default=22, render_kw={'size': 5, 'class': 'form-control form-control-sm'})
    username = StringField('SSH User',
                           [validators.DataRequired(), validators.Length(min=1, max=30)],
                           default='user', render_kw={'size': 15, 'class': 'form-control form-control-sm'})
    password = PasswordField('Password',
                           [validators.DataRequired(), validators.Length(min=1, max=50)],
                           widget=PasswordInput(hide_value=False),
                           default='', render_kw={'size': 15, 'class': 'form-control form-control-sm'})
    python3 = StringField('Python 3 location',
                           [validators.DataRequired(), validators.Length(min=8, max=128)],
                           default='/path/to/python3', render_kw={'size': 20, 'class': 'form-control form-control-sm'})
    folder = StringField('Desired scripts location',
                           [validators.DataRequired(), validators.Length(min=8, max=128)],
                           default='/path/to/scripts', render_kw={'size': 20, 'class': 'form-control form-control-sm'})
    web_port = IntegerField('Web port',
                            [validators.DataRequired(), validators.NumberRange(80, 9000)],
                            default=8081, render_kw={'size': 5, 'class': 'form-control form-control-sm'})
    clone = SubmitField('Clone', render_kw={'class': 'btn btn-primary btn-sm'})
    remove = SubmitField('Remove', render_kw={'class': 'btn btn-primary btn-sm'})


class ConfigForm(Form):
    """A class describing a form for all slave hosts."""
    hosts = FieldList(FormField(ServerForm), min_entries=1, max_entries=5)

    def slaves_errors(self):
        errors = self._same_hosts() + helpers.validate_slaves(self)
        return errors

    def _same_hosts(self):
        ips = [item['host'] for item in self.hosts.data]
        if len(ips) != len(set(ips)):
            return ['Same IP address detected for different host entries.']
        return []

    def _python_version(self, ssh, host):
        cmd = '%s --version' % host['python3']
        out = tools.ssh_runcmd(ssh, cmd)[1].read().strip().decode('utf-8').split('\n')[-1]
        try:
            version = out.split()
            if version[-2].lower() == 'python' and version[-1] >= '3.6':
                return []
        except (ValueError, IndexError):
            pass
        return ['Cannot detect Python version on %s using "%s" command.' % (host['host'], cmd)]

    def _ports_available(self, host, port):
        if tools.check_connectivity(host, port, 2):
            return ['Port %s is already in use on %s.' % (port, host)]
        return []

    def _packages_installed(self, ssh, host):
        modules = ['aiohttp', 'aiodns', 'asyncio', 'bottle', 'cchardet',
                   'paramiko_expect', 'pathos', 'sqlite3', 'uvloop', 'yaml']
        missing = []
        for module in modules:
            cmd = '%s -c "import %s"' % (host['python3'], module)
            out, err = tools.ssh_runcmd(ssh, cmd)[1:]
            output = (out.read() + err.read()).strip().decode('utf-8')
            if 'ModuleNotFoundError' in output:
                missing.append(module)
        if missing:
            return ['Packages missing on %s: %s.' % (host['host'], ', '.join(missing))]
        return []


class TestViewForm(Form):
    """A class describing a form to modify a test run."""
    title = StringField('Title',
                        [validators.DataRequired(), validators.Length(min=1, max=30)],
                        render_kw={'size': 50})
    status = SelectField('Status',
                         [validators.DataRequired()], coerce=int,
                         choices=[(item.id, item.name) for item in db_queries.get_all_states()]
                              )
    submitted = StringField('Submitted',
                           [validators.DataRequired(), validators.Length(min=1, max=30)],
                           render_kw={'size': 30})
    completed = StringField('Completed',
                           [validators.DataRequired(), validators.Length(min=1, max=30)],
                           render_kw={'size': 30})
    description = TextAreaField('Description',
                                [validators.DataRequired(), validators.Length(min=0, max=8152)],
                                render_kw={'cols': 100, 'rows': 10})
    comment = TextAreaField('Comment',
                            [validators.Length(min=0, max=1024)],
                            render_kw={'cols': 100, 'rows': 10})


class TestStepForm(Form):
    """A class describing a form for one test run step."""
    locals()['start'] = IntegerField('Start at second #:',
                       [validators.DataRequired(), validators.NumberRange(0, 600)],
                       default=0, render_kw={'readonly': 'readonly', 'class': 'form-control form-control-sm'})
    locals()['duration'] = IntegerField('Duration (seconds):',
                            [validators.DataRequired(), validators.NumberRange(1, 600)],
                            default=1, render_kw={'class': 'form-control form-control-sm'})
    for action in tools.collect_actions():
        locals()[action] = IntegerField('%s:<br>delta users' % action,
                            [validators.DataRequired(), validators.NumberRange(-5000, 5000)],
                            description='Use positive integers to add users, negative - to remove',
                            default=0, render_kw={'class': 'form-control form-control-sm'})
    clone = SubmitField('Clone', render_kw={'class': 'btn btn-primary btn-sm btn-block'})
    remove = SubmitField('Remove', render_kw={'class': 'btn btn-primary btn-sm btn-block'})


class TestRunForm(Form):
    """A class describing a form for all steps of a test run."""
    steps = FieldList(FormField(TestStepForm), min_entries=1, max_entries=5)

    def collect_load(self):
        intervals = []
        actions = [item for item in list(self.steps.data[0].keys()) if item.startswith('Action')]
        deltas = {action: [] for action in actions}
        errors = []
        for item in self.steps.data:
            if item['duration'] > 0:
                intervals.append(item['duration'])
            else:
                errors.append('Got non-positive duration for at least one test step.')
            for action in actions:
                deltas[action].append(item[action])
                current_users_count_for_action = sum(deltas[action])
                if current_users_count_for_action < 0:
                    errors.append('Got negative users count (=%s) for action %s at %s' %
                                  (current_users_count_for_action, action, item['start']))
        users_count = 0
        users = {action: [0, 0] for action in actions}
        for action in actions:
            users[action][0] = users_count
            users_action = 0
            for item in self.steps.data:
                users_action += item[action] if item[action] > 0 else 0
            users_count += users_action
            users[action][1] = users_count
        result = {'errors': errors, 'users_count': users_count,
                  'intervals': intervals, 'actions': deltas, 'users': users}
        return result