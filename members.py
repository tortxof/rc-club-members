#! /usr/bin/env python3

from functools import wraps
import os
import stat
import io
import csv
import json
import time
import datetime

import requests
from bs4 import BeautifulSoup
import xlsxwriter
from flask import Flask, Markup, session, render_template, flash, request, redirect, url_for, jsonify, send_file
from itsdangerous import URLSafeSerializer
import misaka

import members_database

app = Flask(__name__)

if not os.path.isfile('/members-data/key'):
    with open('/members-data/key', 'wb') as f:
        f.write(os.urandom(32))
    os.chmod('/members-data/key', stat.S_IREAD)

with open('/members-data/key', 'rb') as f:
    app.config['SECRET_KEY'] = f.read()

if os.path.isfile('/members-data/mailgun.json'):
    with open('/members-data/mailgun.json') as f:
        app.config['mailgun'] = json.load(f)

app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

members_db = members_database.MembersDatabase('/members-data/members.db')

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if ('appuser' in session) or (('readonly' in session) and (request.method == 'GET')):
            return f(*args, **kwargs)
        else:
            flash('You are not logged in.')
            return redirect(url_for('login'))
    return wrapper

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
            flash('Create the first user.')
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
    for i in tuple(session.keys()):
        session.pop(i, None)
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
        flash('Add a new user.')
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
        mid = members_db.add(request.form.to_dict())
        flash('Record added.')
        return render_template('records.html', records=members_db.get(mid))
    else:
        return redirect(url_for('index'))

@app.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    if request.method == 'POST':
        mid = request.form['mid']
        members_db.edit(record=request.form.to_dict())
        flash('Record updated.')
        return render_template('records.html', records=members_db.get(mid))
    else:
        mid = request.args.get('mid')
        records = members_db.get(mid)
        if records:
            return render_template('edit.html', record=records[0])
        else:
            flash('Record not found.')
            return redirect(url_for('index'))

@app.route('/delete', methods=['GET', 'POST'])
@login_required
def delete():
    if request.method == 'POST':
        mid = request.form['mid']
        flash('Record deleted.')
        out = render_template('records.html', records=members_db.get(mid))
        members_db.remove(mid)
        return out
    else:
        mid = request.args.get('mid')
        records = members_db.get(mid)
        if records:
            flash('Are you sure you want to delete this record?')
            return render_template('confirm_delete.html', records=records, mid=mid)
        else:
            flash('Record not found.')
            return redirect(url_for('index'))

@app.route('/all', defaults={'args': ''})
@app.route('/all/<path:args>')
@login_required
def all(args):
    args = args.split('/')

    if 'expired' in args:
        records = members_db.expired()
    elif 'current' in args:
        records = members_db.current()
    elif 'previous' in args:
        records = members_db.previous()
    else:
        records = members_db.all()

    if 'email' in args:
        emails = ''
        for record in records:
            email = record['email']
            if len(email) > 0:
                emails += email + '\n'
        flash('{} records found.'.format(len(records)))
        return render_template('text.html', content=emails)
    elif 'csv' in args:
        csv_data = io.StringIO()
        writer = csv.DictWriter(csv_data, fieldnames=members_db.get_fields())
        writer.writeheader()
        for record in records:
            writer.writerow(record)
        flash('{} records found.'.format(len(records)))
        return render_template('text.html', content=csv_data.getvalue())
    elif 'xlsx' in args:
        col_names = [('first', 'First'), ('last', 'Last'), ('ama', 'AMA'),
        ('phone', 'Phone'), ('address', 'Address'), ('city', 'City'),
        ('state', 'State'), ('zip', 'ZIP'), ('email', 'E-mail'),
        ('expire', 'Expiration')]
        xlsx_data = io.BytesIO()
        workbook = xlsxwriter.Workbook(xlsx_data)
        worksheet = workbook.add_worksheet('Members')
        worksheet.set_landscape()
        header = workbook.add_format({'bold': True, 'bottom': True})
        for col, name in enumerate(col_names):
            worksheet.write(0, col, name[1], header)
        for row, record in enumerate(records, start=1):
            for col, field in enumerate(col_names):
                worksheet.write(row, col, record.get(field[0]))
        worksheet.merge_range(len(records)+2, 0, len(records)+2, len(col_names)-1, '{} members'.format(len(records)))
        worksheet.merge_range(len(records)+3, 0, len(records)+3, len(col_names)-1, 'Generated: {}'.format(datetime.date.today().isoformat()))
        worksheet.print_area(0, 0, len(records)+3, len(col_names)-1)
        worksheet.fit_to_pages(1, 1)
        workbook.close()
        xlsx_data.seek(0)
        return send_file(xlsx_data, as_attachment=True, attachment_filename='bsrcc-roster-{}.xlsx'.format(datetime.date.today().isoformat()))
    else:
        flash('{} records found.'.format(len(records)))
        return render_template('records.html', records=records)


@app.route('/export')
@login_required
def json_export():
    return jsonify(members=members_db.all())

@app.route('/import', methods=['GET', 'POST'])
@login_required
def json_import():
    if request.method == 'POST':
        json_data = request.form['json_data']
        records = json.loads(json_data).get('members')
        members_db.add_multiple(records)
        flash('{} records imported.'.format(len(records)))
        return redirect(url_for('index'))
    else:
        return render_template('import.html')

@app.route('/verify')
@login_required
def verify():
    record = members_db.get(request.args.get('mid'))[0]
    ama_url = 'http://www.modelaircraft.org/MembershipQuery.aspx'
    ama_page = requests.get(ama_url)
    soup = BeautifulSoup(ama_page.text)
    viewstate = soup.find_all('input', attrs={'name':'__VIEWSTATE'})[0]['value']
    eventvalidation = soup.find_all('input', attrs={'name':'__EVENTVALIDATION'})[0]['value']
    flash('By clicking Verify you will be submitting the following name and AMA number on modelaircraft.org to verify membership.')
    return render_template('verify.html', record=record, eventvalidation=eventvalidation, viewstate=viewstate)

@app.route('/send', methods=['GET', 'POST'])
@login_required
def send_email():
    if request.method == 'POST':
        if 'confirm-send' in request.form:
            s = URLSafeSerializer(app.config.get('SECRET_KEY'))
            try:
                email_data = s.loads(request.form.get('email_data'))
            except:
                flash('Error decoding email data.')
                return redirect(url_for('send_email'))
            mailgun_response = requests.post('https://api.mailgun.net/v3/{}/messages'.format(app.config.get('mailgun')['domain']),
                auth = ('api', app.config.get('mailgun')['key']),
                data = email_data)
            flash('Response from mailgun: {}'.format(mailgun_response.text))
            return redirect(url_for('index'))
        if 'send-current' in request.form:
            members = members_db.current()
        elif 'send-previous' in request.form:
            members = members_db.previous()
        elif 'send-test' in request.form:
            members = [{'first': request.form.get('test-first'),
                        'last': request.form.get('test-last'),
                        'email': request.form.get('test-email')}]
        else:
            flash('Missing form field. Please report this error.')
            return redirect(url_for('index'))
        recipient_variables = {}
        for member in members:
            if member.get('email'):
                recipient_variables[member.get('email')] = {}
                recipient_variables[member.get('email')]['name'] = '{} {}'.format(member.get('first'), member.get('last'))
                recipient_variables[member.get('email')]['id'] = member.get('mid')
        email_data = {'from': '{} <{}@{}>'.format(request.form.get('from-name'), request.form.get('from-email'), app.config.get('mailgun')['domain']),
            'to': [email for email in recipient_variables.keys()],
            'subject': request.form.get('subject'),
            'text': request.form.get('body'),
            'html': render_template('email_layout.html', body=Markup(misaka.html(request.form.get('body'))), subject=request.form.get('subject')),
            'recipient-variables': json.dumps(recipient_variables)}
        s = URLSafeSerializer(app.config.get('SECRET_KEY'))
        return render_template('send_email_confirm.html',
                               num_recipients=len(email_data['to']),
                               email_body=Markup(misaka.html(request.form.get('body').replace('%recipient.name%', 'John Doe'))),
                               email_data=email_data,
                               email_data_json=s.dumps(email_data))
    else:
        return render_template('send_email.html', month=datetime.date.today().strftime('%B'), domain=app.config.get('mailgun', {}).get('domain'))

@app.route('/get-ro-token')
@login_required
def get_ro_token():
    if 'appuser' in session:
        s = URLSafeSerializer(app.config.get('SECRET_KEY'))
        data = {}
        data['time'] = int(time.time())
        data['readonly'] = True
        slug = s.dumps(data)
        return render_template('get_ro_token.html', slug=slug)
    else:
        return redirect(url_for('index'))

@app.route('/ro/<slug>')
def ro_auth(slug):
    s = URLSafeSerializer(app.config.get('SECRET_KEY'))
    try:
        data = s.loads(slug)
    except:
        flash('Authorization failed.')
        return redirect(url_for('index'))
    # 7257600 is 12 weeks in seconds.
    if (data.get('readonly') == 'OK' or data.get('readonly')) and data.get('time') + 7257600 >= int(time.time()):
        session['readonly'] = True
        flash('You have read only access.')
        return render_template('ro_authorized.html')
    else:
        flash('Authorization failed.')
        return redirect(url_for('index'))

@app.route('/about')
def about():
    with open('.git/refs/heads/master') as f:
        version = f.read()
    version = version.strip()[:8]
    return render_template('about.html', version=version)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
