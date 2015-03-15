#! /usr/bin/env python3

from functools import wraps
import os
import subprocess
import io
import csv
import json

import requests
from bs4 import BeautifulSoup
from flask import Flask, session, render_template, flash, request, redirect, url_for, jsonify

import members_database

members_db = members_database.MembersDatabase()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'appuser' in session:
            return f(*args, **kwargs)
        else:
            flash('You are not logged in.')
            return redirect(url_for('login'))
    return wrapper

app = Flask(__name__)

@app.route('/')
@login_required
def index():
    return render_template('index.html', expire=members_db.end_of_year())

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if not os.path.isfile(members_db.dbfile):
        if request.method == 'POST':
            members_db.new_db()
            members_db.new_appuser(request.form['appuser'], request.form['password'])
            flash('New database created.')
            return redirect(url_for('login'))
        else:
            return render_template('setup.html')
    else:
        flash('Database already exists.')
        return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if members_db.password_valid(request.form['appuser'], request.form['password']):
            session['appuser'] = request.form['appuser']
            flash('You are now logged in.')
            return redirect(url_for('index'))
        else:
            flash('Incorrect user name or password.')
            return redirect(url_for('login'))
    else:
        return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('appuser', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/new-user', methods=['GET', 'POST'])
@login_required
def new_user():
    if request.method == 'POST':
        members_db.new_appuser(request.form['appuser'], request.form['password'])
        flash('New user created.')
        return redirect(url_for('index'))
    else:
        return render_template('new_user.html')

@app.route('/search')
@login_required
def search():
    records = members_db.search(request.args.get('query'))
    flash('{} records found.'.format(len(records)))
    return render_template('records.html', records=records)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        rowid = members_db.add(request.form)
        flash('Record added.')
        return render_template('records.html', records=members_db.get(rowid))
    else:
        return redirect(url_for('index'))

@app.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    if request.method == 'POST':
        rowid = request.form['rowid']
        members_db.edit(rowid=rowid, record=request.form)
        flash('Record updated.')
        return render_template('records.html', records=members_db.get(rowid))
    else:
        rowid = request.args.get('rowid')
        return render_template('edit.html', record=members_db.get(rowid)[0])

@app.route('/delete', methods=['GET', 'POST'])
@login_required
def delete():
    if request.method == 'POST':
        rowid = request.form.get('rowid')
        flash('Record deleted.')
        out = render_template('records.html', records=members_db.get(rowid))
        members_db.remove(rowid)
        return out
    else:
        rowid = request.args.get('rowid')
        flash('Are you sure you want to delete this record?')
        return render_template('confirm_delete.html', records=members_db.get(rowid), rowid=rowid)

@app.route('/all', defaults={'args': ''})
@app.route('/all/<path:args>')
@login_required
def all(args):
    args = args.split('/')

    if 'expired' in args:
        records = members_db.expired()
    elif 'current' in args:
        records = members_db.current()
    else:
        records = members_db.all()

    flash('{} records found.'.format(len(records)))

    if 'email' in args:
        emails = ''
        for record in records:
            email = record['email']
            if len(email) > 0:
                emails += email + '\n'
        return render_template('text.html', content=emails)
    elif 'csv' in args:
        csv_data = io.StringIO()
        writer = csv.DictWriter(csv_data, fieldnames=members_db.get_fields())
        writer.writeheader()
        for record in records:
            del record['rowid']
            writer.writerow(record)
        return render_template('text.html', content=csv_data.getvalue())
    else:
        return render_template('records.html', records=records)


@app.route('/export')
@login_required
def json_export():
    return jsonify(records=members_db.all())

@app.route('/import', methods=['GET', 'POST'])
@login_required
def json_import():
    if request.method == 'POST':
        json_data = request.form['json_data']
        records = json.loads(json_data).get('records')
        members_db.add_multiple(records)
        flash('{} records imported.'.format(len(records)))
        return redirect(url_for('index'))
    else:
        return render_template('import.html')

@app.route('/verify')
@login_required
def verify():
    record = members_db.get(request.args.get('rowid'))[0]
    ama_url = 'http://www.modelaircraft.org/MembershipQuery.aspx'
    ama_page = requests.get(ama_url)
    soup = BeautifulSoup(ama_page.text)
    viewstate = soup.find_all('input', attrs={'name':'__VIEWSTATE'})[0]['value']
    eventvalidation = soup.find_all('input', attrs={'name':'__EVENTVALIDATION'})[0]['value']
    flash('By clicking Verify you will be submitting the following name and AMA number on modelaircraft.org to verify membership.')
    return render_template('verify.html', record=record, eventvalidation=eventvalidation, viewstate=viewstate)

@app.route('/about')
def about():
    version = subprocess.check_output(['git','rev-parse','--short','HEAD']).decode().strip()
    return render_template('about.html', version=version)

if __name__ == '__main__':
    app.debug = True
    app.secret_key = os.urandom(32)
    app.run()
