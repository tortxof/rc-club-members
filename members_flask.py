#! /usr/bin/env python3

import os

import requests
from bs4 import BeautifulSoup
from flask import Flask, session, render_template, flash, request, redirect, url_for

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

if __name__ == '__main__':
    app.debug = True
    app.secret_key = b']\xcaS\x83w\x07\x0f\xef1}\xd4ed\x1fv\xe5z)\x9b3\x10\xbeSA"\xe6\xb4d\x8a<\x9eo'
    app.run()
