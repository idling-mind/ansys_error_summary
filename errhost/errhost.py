#!/opt/anaconda3/bin/python3
import os
import sqlite3
import re
from flask import (Flask, request, redirect, url_for,
        render_template, current_app, g)

app = Flask(__name__)
app.config.from_object(__name__) # load config from this file , flaskr.py

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'errordb.db'),
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default',
    ERRCONFIDENCE=0.7,
    WEBSERVER="http://aerox33799:5000"
    ))

def connect_db():
    """Connects to the error database"""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def compare_errs(err1, err2, conf):
    """Function to compare two error strings and decide
    if they are simlar or not. Accepts two strings and a
    confidence level."""
    err1 = re.sub("\d+", "", err1)
    err2 = re.sub("\d+", "", err2)
    hit = 0
    for e1, e2 in zip(err1.split(), err2.split()):
        if e1 == e2:
            hit += 1
    if hit/len(err2.split()) > conf:
        return True
    else:
        return False

@app.before_request
def before_request():
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()

# Filters for Jinja
@app.template_filter('basename')
def basename(path):
    return os.path.basename(path)

@app.route("/", methods=['GET'])
def index():
    cur = g.db.execute('select * from uniq_errors')
    errlist = cur.fetchall()
    curr = g.db.execute('select count(*) from sessions')
    err_file_count = curr.fetchone()[0]
    curr = g.db.execute('select count(*) from uniq_errors')
    uniq_err_count = curr.fetchone()[0]
    curr = g.db.execute('select sum(filesize) from sessions')
    data_processed = curr.fetchone()[0]
    curr = g.db.execute('select count(distinct username) from sessions')
    no_of_users = curr.fetchone()[0]
    stats = {"err_file_count":err_file_count,
             "uniq_err_count":uniq_err_count,
             "data_processed":data_processed,
             "no_of_users":no_of_users}
    return render_template('index.html', errlist=errlist, stats=stats)

@app.route("/submit", methods=['POST'])
def submit():
    # Submitting one entry to the sesssion
    errs = request.get_json(force=True)
    cur = g.db.cursor()
    cur.execute('insert into sessions (username, filename, createdon, filesize)'
            ' values (?, ?, ?, ?)', [errs['user'], errs['fname'],
                errs['curdate'], errs['fsize']])
    g.last_req_id = cur.lastrowid
    g.db.commit()
    # Adding the errors
    cur = g.db.cursor()
    for err in errs['errors']:
        cur.execute('insert into errors (lineno, errtype, errmsg, numofdups, sessionid)'
                ' values (?, ?, ?, ?, ?)',
                [err[3], err[0], err[1], err[2], g.last_req_id])
    g.db.commit()

    # Fetching unique errors 
    cur = g.db.execute('select id, errtype, errmsg, rating, repeated from uniq_errors')
    uniq_errs = cur.fetchall()
    cur = g.db.cursor()
    for err in errs['errors']:
        for uniq_err in uniq_errs:
            if compare_errs(uniq_err[2], err[1], app.config['ERRCONFIDENCE']):
                cur.execute('update uniq_errors set repeated = ? where id = ?',
                        [uniq_err[4]+1, uniq_err[0]])
                break
        else:
            cur.execute('insert into uniq_errors '
                    '(errtype, errmsg, sessionid)'
                    ' values (?, ?, ?)',
                    [err[0], err[1], g.last_req_id])
    g.db.commit()

    return app.config["WEBSERVER"] + url_for('session',sessionid=g.last_req_id)

@app.route("/sessions")
def sessions():
    """Show a list of all sessions"""
    cur = g.db.execute('select sessionid, username, filename, createdon, filesize '
            'from sessions order by createdon desc')
    sessions = cur.fetchall()
    return render_template('sessions.html', sessions=sessions)


@app.route("/session/<int:sessionid>")
def session(sessionid):
    """Show the errors from a particular error file"""
    cur = g.db.execute('select lineno, errtype, errmsg, numofdups from errors'
            ' where sessionid=?', [sessionid,])
    errlist = cur.fetchall()
    cur = g.db.execute('select username, filename, createdon, filesize from '
            'sessions where sessionid=?',[sessionid,])
    sessdata = cur.fetchone()
    # Fetching unique errors 
    cur = g.db.execute('select id, errtype, errmsg, rating, repeated from uniq_errors')
    uniq_errs = cur.fetchall()
    ratings = []
    for err in errlist:
        for uniq_err in uniq_errs:
            if compare_errs(uniq_err[2], err[2], app.config['ERRCONFIDENCE']): 
                ratings.append(uniq_err[3])
                break
        else:
            ratings.append(0)
    return render_template('session.html', errlist=zip(errlist, ratings), sessdata=sessdata)

@app.route("/rate")
def rate():
    """Rate the unique errors in the database"""
    cur = g.db.execute('select id, errtype, errmsg, rating, repeated from uniq_errors' 
            ' order by id desc')
    uniq_errs = cur.fetchall()
    return render_template("rate.html", errlist=uniq_errs)

@app.route("/submitrating", methods=['POST'])
def submitrating():
    data = request.form
    cur = g.db.cursor()
    cur.execute('update uniq_errors set rating = ? where id = ?',
            [data['rating'], data['id']])
    g.db.commit()
    return str(data)
