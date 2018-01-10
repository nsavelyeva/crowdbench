import os
import json
from flask import render_template, redirect, url_for, request, jsonify, flash
from app import app
from . import helpers, db_queries, tools as atools
from .forms import ConfigForm, TestRunForm, TestViewForm
from .models import TestRuns, TestStates, db
from .engine import master, tools as etools


@app.route('/_test_info')
def get_test_run_info():
    """For AJAX requests, load test run descriptions for a quick view in the list of test runs."""
    trid = request.args.get('trid', 0, type=int)
    test_run = db_queries.get_test_run(trid)
    result = {'id': test_run.id, 'test_run_id': test_run.title, 'description': test_run.description}
    return jsonify(result)


@app.route('/_test_update')
def update_test_run_on_end():
    """For AJAX requests, when test is finished,
    update test run metadata in a local database on master node (if not updated before).
    """
    test_run_title = request.args.get('test_run_title')
    test_run = db_queries.get_test_run_by_title(test_run_title)
    if test_run.completed:  # No update needed, it was updated earlier
        result = {'test_run_title': test_run_title, 'message': 'Updated earlier. Nothing to do.'}
    else:  # test ended and DB should be updated
        values = {'completed': request.args.get('completed'),
                  'comment': request.args.get('comment'),
                  'status': request.args.get('status')}
        res = db_queries.update_test_run_by_title(test_run_title, values)
        result = {'test_run_title': test_run_title, 'message': res[0]}
    return jsonify(result)


@app.route('/_get_chartdata')
@app.route('/_get_summary')
@app.route('/_get_logs')
def get_aggregated_data():
    """For AJAX requests, used to collect and aggregate data from all slaves."""
    result = helpers.monitor_slaves(request.url)
    return '{0}({1})'.format(request.args.get('callback'), result)


@app.route('/monitor')
def monitor():
    """Monitoring page of a particular test run."""
    title = request.args.get('test_run_id', '', type=str)
    test_run = db_queries.get_test_run_by_title(title)
    duration = sum(json.loads(test_run.test)['intervals'])
    slaves = etools.load_conf()
    actions = atools.collect_actions()
    return render_template('monitor.html',
                           slaves=slaves, test_run_id=title, duration=duration, actions=actions)


@app.route('/testruns/new', methods=['GET', 'POST'])
def new_testrun():
    """Construct a test run, if load is valid, a test run will be started on all slaves in parallel.
    Metadata of a test run will be inserted into a local database on master node.
    TODO: slaves start not simultaneously - second slave starts ~3 sec after the first one.
    """
    form = TestRunForm(request.form)
    text = ''
    if request.method == 'POST':
        form = TestRunForm(request.form)
        form, msg = helpers.update_constructor_form(form)
        if request.form.get('load_starter') == 'start':
            load = form.collect_load()
            errors = load['errors']
            if not errors:
                flash('Load validation: no errors', 'success')
                obj = master.TestMaster(load)
                text = obj.describe_test()
                errors = helpers.start_slaves(obj)
                load_str = json.dumps(obj.load, sort_keys=True, indent=4)
                msg, style, test_run = db_queries.create_test_run(obj.test_run_id, text, load_str)
                flash(msg, style)
                if not errors:
                    return redirect(url_for('monitor', test_run_id=obj.test_run_id))
            for error in errors:
                flash(error, 'danger')
    return render_template('constructor.html', form=form, text=text)


@app.route('/install', methods=['GET', 'POST'])
def install():
    """(Re)deploy all slave nodes from a web-page:
    - if slaves settings are valid, conf.yaml is (re)written;
    - all files from engine folder except master.py and __init__.py are written onto slaves;
    - monitoring agents are (re)started on slaves.
    TODO: improve parsing output of SSH commands executed to handle slaves' errors better.
    """
    if request.method == 'GET':
        form, msg = helpers.load_yaml_conf(request.form)
        flash(msg, 'info')
    elif request.method == 'POST':
        form = ConfigForm(request.form)
        form, msg = helpers.update_conf_form(form)
        if msg:
            flash(msg, 'danger')
        if form.validate():
            errors = form.slaves_errors()
            for error in errors:
                flash(error, 'danger')
            if not errors:
                form, msg = helpers.write_yaml_conf(form)
                if msg:
                    flash(msg, 'info')
                    folder = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'engine')
                    files = ['%s' % os.path.join(folder, item)
                             for item in os.listdir(folder)
                             if item[item.rfind('.'):] in ['.py', '.txt']]
                    errors = helpers.deploy_slaves(files)
                    if not errors:
                        flash('All files have been deployed onto all slaves, ' +
                              'all monitoring agents are running.', 'success')
                    else:
                        for error in errors:
                            flash(error, 'danger')
        else:
            flash('Settings have not been processed due to form validation failure.', 'warning')
    return render_template('conf.html', form=form)


@app.route('/')
def home():
    """Display static text from home.html template."""
    return render_template('home.html')


@app.route('/about')
def about():
    """Display static text from about.html template."""
    return render_template('about.html')


@app.route('/testruns/view/<int:trid>', methods=['GET'])
def view_test_run(trid):
    """In a local database on master node search for a test run by its id and display all fields."""
    fields = [TestRuns.id, TestRuns.title, TestRuns.description,
              TestRuns.submitted, TestRuns.completed, TestStates.name, TestRuns.comment]
    test_run = db_queries.get_test_run_fields(fields, trid)
    return render_template('testrun.html', testrun=test_run, testrun_status=test_run.name)


@app.route('/testruns/delete/', methods=['POST'])
def delete_test_run():
    """Delete test run by id from a local database on master, remove db-,json-files from slaves."""
    if request.form and 'item' in request.form:
        trid = int(request.form.get('item', type=int))
        test_run_title = db_queries.remove_test_run(trid)
        if test_run_title:
            flash('Removed test run info from the database', 'success')
            for item in helpers.delete_testrun(test_run_title):
                flash(*item)
        else:
            flash('Could not remove Test Run from the database.', 'danger')
    return redirect(url_for('list_testruns'))


@app.route('/testruns/edit/<int:trid>', methods=['GET', 'POST'])
def edit_test_run(trid):
    """Edit test run by its id, in a local database on master node."""
    test_run = db_queries.get_test_run(trid)
    form = TestViewForm(obj=test_run)
    if request.method == 'POST' and form.validate():
        msg, style = db_queries.update_test_run(trid, request.form)
        flash(msg, style)
        if style == 'success':
            return redirect(url_for('list_testruns'))
    return render_template('sform.html', form=form, submit_name='Save')


@app.route('/testruns/list', defaults={'page': 1}, methods=['GET'])
@app.route('/testruns/list/<int:page>', methods=['GET'])
def list_testruns(page):
    """List test runs from a local database on master node, in reverse chronological order."""
    fields = [TestRuns.id, TestRuns.title]
    data = db_queries.get_all_test_runs(fields)
    pagination = data.paginate(page, 5, True)
    rows = pagination.items
    flash('Found %s Test Runs.' % pagination.total, 'info')
    return render_template('list.html', rows=rows, pagination=pagination, table='testruns',
                           fields=[field.__dict__['key'] for field in fields])


@app.errorhandler(404)
def page_not_found(e):
    error = 'Page Not Found'
    return render_template('error.html', code=404, error=error), 404


@app.errorhandler(500)
def internal_server_error(e):
    error = 'Internal Server Error'
    return render_template('error.html', code=500, error=error), 500


@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()
