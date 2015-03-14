#! /usr/bin/env python3

import os
import io
import csv
import json

import requests
from bs4 import BeautifulSoup
from flask import Flask, session, render_template, flash, request, redirect, url_for, jsonify

import members_database

members_db = members_database.MembersDatabase()

app = Flask(__name__)

@app.route('/')
def index():
    if 'appuser' in session:
        return render_template('index.html', expire=members_db.end_of_year())
    else:
        return redirect(url_for('login'))

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

@app.route('/search')
def search():
    if 'appuser' in session:
        records = members_db.search(request.args.get('query'))
        flash('{} records found.'.format(len(records)))
        return render_template('records.html', records=records)
    else:
        flash('You are not logged in.')
        return redirect(url_for('login'))

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'appuser' in session:
        if request.method == 'POST':
            rowid = members_db.add(request.form)
            flash('Record added.')
            return render_template('records.html', records=members_db.get(rowid))
        else:
            return redirect(url_for('index'))
    else:
        flash('You are not logged in.')
        return redirect(url_for('login'))

@app.route('/edit', methods=['GET', 'POST'])
def edit():
    if 'appuser' in session:
        if request.method == 'POST':
            rowid = request.form['rowid']
            members_db.edit(rowid=rowid, record=request.form)
            flash('Record updated.')
            return render_template('records.html', records=members_db.get(rowid))
        else:
            rowid = request.args.get('rowid')
            return render_template('edit.html', record=members_db.get(rowid)[0])
    else:
        flash('You are not logged in.')
        return redirect(url_for('login'))

@app.route('/delete', methods=['GET', 'POST'])
def delete():
    if 'appuser' in session:
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
    else:
        flash('You are not logged in.')
        return redirect(url_for('login'))

@app.route('/all', defaults={'args': ''})
@app.route('/all/<path:args>')
def all(args):
    if 'appuser' in session:
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

    else:
        flash('You are not logged in.')
        return redirect(url_for('login'))

@app.route('/export')
def json_export():
    if 'appuser' in session:
        return jsonify(records=members_db.all())
    else:
        flash('You are not logged in.')
        return redirect(url_for('login'))

@app.route('/import', methods=['GET', 'POST'])
def json_import():
    if 'appuser' in session:
        if request.method == 'POST':
            json_data = request.form['json_data']
            records = json.loads(json_data).get('records')
            members_db.add_multiple(records)
            flash('{} records imported.'.format(len(records)))
            return redirect(url_for('index'))
        else:
            return render_template('import.html')
    else:
        flash('You are not logged in.')
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.debug = True
    app.secret_key = os.urandom(32)
    app.run()
