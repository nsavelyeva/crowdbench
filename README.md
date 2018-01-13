# Crowdbench

A Flask application for distributed load testing in terms of web-users behavior simulation.
Master node 'talks' to slaves through SSH for code deployment and deleting old test run files.
Test run data are collected from slaves' monitoring agents through HTTP (AJAX).

## Tools
- Back-end (master): Flask + Flask-SQLAlchemy + Flask-WTForms, paramiko_expect, threading.
- Back-end (slaves): asyncio, aiohttp, multiprocessing, bottle.
- Database: SQLite + SQLAlchemy on master, SQLite on each slave.
- Frontend: Bootstrap 4 + amCharts + jQuery + Font Awesome and Jinja-templates.

## How to install
```bash
sudo pip3.6 install Flask\ 
                    Flask-SQLAlchemy\
                    Flask-WTF\ 
                    bottle\ 
                    PyYAML\ 
                    pathos\ 
                    paramiko-expect\ 
                    asyncio\
                    aiohttp\ 
                    cchardet\ 
                    aiodns
```
## Usage
- Put the code of user actions into app/engine/actions.py as described in example actions.
- If your actions rely on user identifiers - put them into app/engine/users.txt.
- Launch run.py and open http://127.0.0.1 in browser - this will be a master node.
- Navigate to http://127.0.0.1/install to set-up slave nodes.
> Note: you may need to install python packages on slaves manually - follow validation errors.
- Construct a test run at http://127.0.0.1/testruns/new and you will be redirected to a monitoring page.
- List existing test runs and modify/delete them if needed at http://127.0.0.1/testruns/list.

## Implemented
- Installation - deployment onto slaves if settings are valid:
  - define slaves using constructor form at /install
  - settings validation: SSH connectivity, packages, python version, port for monitoring agents.
  - files will be copied automatically onto slaves, in parallel.
  - monitoring agents will be (re)started on all slaves, in parallel.
- Construct a test run based on existing actions + settings validation + detailed test description.
- Monitor a test run on-the-fly:
  - display statistics & charts, separately failed/passed/incomplete operations, grouped errors.
  - display aggregated data from all slaves and separately for each slave.
  - charts filtering/switching.
  - collect debug info from slaves and display it on monitoring page.
- List existing test runs with navigation to quick view, deep view, edit, removal and monitoring.

## TODO
- Improve app architecture.
- Collect and group test run errors, save them in the database once test run is finished.
- Re-run existing test run as a new test run.
- Support parallel test runs on different sets of slaves.
- Add more info onto web-pages (tips, notes, etc.).
- Implement a view to upload actions.py and users.txt, including validation.
- Implement on-demand stopping monitoring agents on slaves.
- Improve app stability (e.g. display messages if something has failed or missing), cover:
  - code (re)deployment, start/stop monitoring agents, if a test run aborts externally, etc.
- Improve page markup to make the app good-looking.
- Refactor and optimize the code
  - e.g. create @threaded decorator to run tasks on slaves simultaneously.
- Add a brief user guide.
- Document the code.
- Implement unit tests.
- Retrospective - compare results to other load testing tools.
- Other.
