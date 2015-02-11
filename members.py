#! /usr/bin/env python3

import os
import subprocess
import codecs
import time
import sqlite3

import bcrypt
import cherrypy

def toHex(s):
    '''Returns hex string.'''
    return codecs.encode(s, 'hex').decode()

def fromHex(s):
    '''Returns bytes.'''
    return codecs.decode(s, 'hex')

def genHex(length=32):
    '''Generate random hex string.'''
    return toHex(os.urandom(length))

def loggedIn():
    '''Checks if current auth cookie is valid.'''
    cookie = cherrypy.request.cookie
    if 'auth' in cookie.keys():
        if auth_keys.valid(cookie['auth'].value):
            return True
    return False

def load_templates(template_dir):
    templates = [template.split('.html')[0] for template in os.listdir(path=template_dir)]
    html = dict()
    for template in templates:
        with open(template_dir + '/' + template + '.html') as f:
            html[template] = f.read()
    return html

html = load_templates('templates')

class AuthKeys(object):
    def __init__(self):
        self.keys = dict()
        self.keyExpTime = 60 * 60

    def add(self, appuser):
        key = genHex()
        date = int(time.time())
        self.keys[key] = {'appuser': appuser, 'date': date}
        return key

    def delete(self, key):
        if key in self.keys:
            del self.keys[key]
            return True
        else:
            return False

    def valid(self, key):
        now = self.expire()
        if key in self.keys:
            self.keys[key]['date'] = now
            return True
        else:
            return False

    def user(self, key):
        if key in self.keys:
            return self.keys[key]['appuser']

    def expire(self):
        now = int(time.time())
        exp_date = now - self.keyExpTime
        keys = list(self.keys.keys())
        for key in keys:
            if self.keys[key]['date'] < exp_date:
                del self.keys[key]
        return now

auth_keys = AuthKeys()

class MembersDatabase(object):
    def __init__(self):
        self.dbfile = 'members.db'
        self.fields = ('first', 'last', 'ama', 'phone', 'address', 'city', 'state', 'zip', 'email', 'expire', 'rowid')

    def new_db(self):
        conn = sqlite3.connect(self.dbfile)
        conn.execute('create virtual table members using fts4(' + ', '.join(self.fields[:-1]) + ')')
        conn.execute('create table appusers (appuser text primary key not null, password text)')
        conn.commit()
        conn.close()

    def new_appuser(self, appuser, password):
        password = bcrypt.hashpw(password, bcrypt.gensalt())
        conn = sqlite3.connect(self.dbfile)
        conn.execute('insert into appusers values(?, ?)', (appuser, password))
        conn.commit()
        conn.close()

    def password_valid(self, appuser, password):
        conn = sqlite3.connect(self.dbfile)
        stored_password = conn.execute('select password from appusers where appuser=?', (appuser,)).fetchone()[0]
        conn.close()
        return bcrypt.checkpw(password, stored_password)

    def add(self, record):
        conn = sqlite3.connect(self.dbfile)
        cur = conn.cursor()
        cur.execute('insert into members values(' + ', '.join('?' * (len(self.fields) - 1)) + ')', tuple(record.get(field) for field in self.fields[:-1]))
        rowid = cur.lastrowid
        conn.commit()
        conn.close()
        return rowid

    def edit(self, rowid, record):
        conn = sqlite3.connect(self.dbfile)
        fields = tuple(record.get(field) for field in self.fields[:-1])
        set_string = ','.join([field + '=?' for field in self.fields[:-1]])
        conn.execute('update members set ' + set_string + ' where rowid=?', fields + (rowid,))
        conn.commit()
        conn.close()

    def remove(self, rowid):
        conn = sqlite3.connect(self.dbfile)
        conn.execute('delete from members where rowid=?', (rowid,))
        conn.commit()
        conn.close()

    def get(self, rowid):
        conn = sqlite3.connect(self.dbfile)
        record = conn.execute('select *,rowid from members where rowid=?', (rowid,)).fetchone()
        conn.close()
        return dict(zip(self.fields, record))

    def all(self):
        conn = sqlite3.connect(self.dbfile)
        records = conn.execute('select *,rowid from members').fetchall()
        conn.close()
        return [dict(zip(self.fields, record)) for record in records]

    def expired(self):
        conn = sqlite3.connect(self.dbfile)
        records = conn.execute('select *,rowid from members where expire<date("now")').fetchall()
        conn.close()
        return [dict(zip(self.fields, record)) for record in records]

    def current(self):
        conn = sqlite3.connect(self.dbfile)
        records = conn.execute('select *,rowid from members where expire>=date("now")').fetchall()
        conn.close()
        return [dict(zip(self.fields, record)) for record in records]

    def end_of_year(self):
        conn = sqlite3.connect(':memory:')
        out = conn.execute('select date("now","+1 year","start of year","-1 day")').fetchone()[0]
        conn.close()
        return out

    def search(self, query):
        conn = sqlite3.connect(self.dbfile)
        records = conn.execute('select *,rowid from members where members match ?', (query,)).fetchall()
        conn.close()
        return [dict(zip(self.fields, record)) for record in records]

members_db = MembersDatabase()

class Root(object):
    @cherrypy.expose
    def index(self):
        if not os.path.isfile(members_db.dbfile):
            out = html['setup']
        else:
            if loggedIn():
                out = html['search']
                out += html['add'].format(expire=members_db.end_of_year())
            else:
                out = html['login']
        return html['template'].format(content=out)

    @cherrypy.expose
    def setup(self, user, password):
        out = ''
        if not os.path.isfile(members_db.dbfile):
            members_db.new_db()
            members_db.new_appuser(user, password)
            out += html['message'].format(content='Setup complete.')
            out += html['search']
        else:
            out += html['message'].format(content='Setup is already complete.')
        return html['template'].format(content=out)

    @cherrypy.expose('new-user')
    def new_user(self, appuser=None, password=None):
        out = ''
        if loggedIn():
            if appuser and password:
                members_db.new_appuser(appuser, password)
                out += html['message'].format(content='User has been added.')
            else:
                out += html['new_user']
        else:
            out += html['message'].format(content='You must log in to add a user.')
        return html['template'].format(content=out)

    @cherrypy.expose
    def login(self, appuser=None, password=None):
        out = ''
        if appuser and password:
            if members_db.password_valid(appuser, password):
                cookie = cherrypy.response.cookie
                cookie['auth'] = auth_keys.add(appuser)
                out += html['message'].format(content='You are now logged in.')
                out += html['search']
            else:
                out += html['message'].format(content='Incorrect username or password.')
        else:
            out += html['login']
        return html['template'].format(content=out)

    @cherrypy.expose
    def logout(self):
        out = ''
        if loggedIn():
            auth_keys.delete(cherrypy.request.cookie['auth'].value)
            out += html['message'].format(content='You have been logged out.')
        else:
            out += html['message'].format(content='You are not logged in.')
        return html['template'].format(content=out)

    @cherrypy.expose
    def search(self, query):
        out = html['search']
        for record in members_db.search(query):
            out += html['record'].format(**record)
        return html['template'].format(content=out)

    @cherrypy.expose
    def all(self):
        out = html['search']
        for record in members_db.all():
            out += html['record'].format(**record)
        return html['template'].format(content=out)

    @cherrypy.expose
    def add(self, **kwargs):
        out = ''
        if loggedIn():
            if len(kwargs.keys()) > 0:
                rowid = members_db.add(kwargs)
                out += html['message'].format(content='Record added.')
                out += html['record'].format(**members_db.get(rowid))
            else:
                out += html['add'].format(expire=members_db.end_of_year())
        else:
            out += html['message'].format(content='You must log in to add records.')
        return html['template'].format(content=out)

    @cherrypy.expose
    def edit(self, rowid, **kwargs):
        out = ''
        if loggedIn():
            if len(kwargs.keys()) > 0:
                members_db.edit(rowid=rowid, record=kwargs)
                out += html['message'].format(content='Record updated.')
                out += html['record'].format(**members_db.get(rowid))
            else:
                out += html['edit'].format(**members_db.get(rowid))
        else:
            out += html['message'].format(content='You must log in to edit records.')
        return html['template'].format(content=out)

    @cherrypy.expose
    def delete(self, rowid, confirm=False):
        out = ''
        if loggedIn():
            if confirm == 'true':
                out += html['record'].format(**members_db.get(rowid))
                out += html['message'].format(content='Record has been deleted.')
                members_db.remove(rowid)
            else:
                out += html['record'].format(**members_db.get(rowid))
                out += html['message'].format(content='Are you sure you want to delete this record?')
                out += html['confirm_delete'].format(rowid=rowid)
        else:
            out += html['message'].format(content='You must log in to delete records.')
        return html['template'].format(content=out)

cherrypy.config.update('server.conf')

if __name__ == '__main__':
    cherrypy.quickstart(Root(), '/', 'app.conf')
