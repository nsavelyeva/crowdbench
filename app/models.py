import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc
from app import app


db = SQLAlchemy(app)


def get_time_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class TestRuns(db.Model):
    __tablename__ = 'testruns'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50), unique=True)
    test = db.Column(db.String(4096))
    description = db.Column(db.String(8152))
    submitted = db.Column(db.String(30))
    completed = db.Column(db.String(30))
    status = db.Column(db.Integer, db.ForeignKey('states.id'))
    status_relation = db.relationship('TestStates', backref=db.backref('testruns', lazy='dynamic'))
    comment = db.Column(db.String(1024))  # analysis notes after test finishes

    def __init__(self, title, description, load_str):
        self.title = title
        self.test = load_str  # JSON string describing entire test
        self.description = description
        self.submitted = get_time_str()
        self.completed = ''
        self.status = 1  # In progress by default
        self.comment = ''

    def __repr__(self):
        return '[TestRun #%s]' % self.id

    def __str__(self):
        return json.dumps(self, indent=4, sort_keys=True)


class TestStates(db.Model):
    __tablename__ = 'states'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return json.dumps(self, indent=4, sort_keys=True)

    def __str__(self):
        return self.name


@app.before_first_request
def startup():
    db.create_all()
    for name in ['IN PROGRESS', 'COMPLETED', 'ABORTED', 'CANCELLED']:
        state = TestStates(name)
        db.session.add(state)
    try:
        db.session.commit()
    except exc.IntegrityError:
        db.session.rollback()
