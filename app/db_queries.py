from sqlalchemy import exc
from .models import TestRuns, TestStates, db, startup


def get_all_states():
    try:
        data = TestStates.query.all()
    except exc.OperationalError:
        startup()
        data = TestStates.query.all()
    return data


def get_test_run(trid):
    data = db.session.query(TestRuns).filter_by(id=trid).first()
    return data


def get_test_run_by_title(title):
    data = db.session.query(TestRuns).filter_by(title=title).first()
    return data


def get_test_run_fields(fields, trid):
    query = TestRuns.query.join(TestStates, TestRuns.status == TestStates.id)
    test_run = query.filter(TestRuns.id == trid).add_columns(*fields).first()
    return test_run


def get_all_test_runs(fields=None):
    fields = fields or [TestRuns.id, TestRuns.title, TestRuns.description,
                        TestRuns.submitted, TestRuns.completed, TestRuns.status, TestRuns.comment]
    query = TestRuns.query.join(TestStates, TestRuns.status == TestStates.id)
    data = query.order_by(TestRuns.id.desc()).add_columns(*fields)
    return data


def create_test_run(title, description, load):
    try:
        test_run = TestRuns(title, description, load)
        db.session.add(test_run)
        db.session.commit()
    except exc.IntegrityError as err:
        msg = '"%s" due to Integrity error: %s' % (title, err)
        return 'Could not save test run due to integrity issue: %s' % msg, 'danger', None
    return 'Test Run "%s" has been created.' % title, 'success', test_run


def update_test_run(trid, values):
    db.session.query(TestRuns).filter_by(id=trid).update(values)
    db.session.commit()
    return 'Data for Test Run "%s" have been updated.' % trid, 'success'


def update_test_run_by_title(title, values):
    db.session.query(TestRuns).filter_by(title=title).update(values)
    db.session.commit()
    return 'Data for Test Run "%s" have been updated.' % title, 'success'


def remove_test_run(trid):
    test_run = TestRuns.query.get(trid)
    db.session.delete(test_run)
    db.session.commit()
    return test_run.title
