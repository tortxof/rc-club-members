#! /usr/bin/env python3

import sqlite3

import requests
from bs4 import BeautifulSoup
from flask import Flask, session, render_template, flash, request, redirect, url_for

import members_database

members_db = members_database.MembersDatabase()

app = Flask(__name__)

@app.route('/')
def index():
    if 'appuser' in session:
        pass
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        pass
    else:
        return render_template('login.html')

if __name__ == '__main__':
    app.debug = True
    app.run()
