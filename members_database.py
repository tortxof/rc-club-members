import os
import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

class MembersDatabase(object):
    def __init__(self, dbfile):
        self.sort_sql = ' order by expire desc, last asc, first asc'
        self.dbfile = dbfile

    def db_conn(self):
        conn = sqlite3.connect(self.dbfile)
        conn.row_factory = sqlite3.Row
        return conn

    def get_fields(self):
        '''Returns a tuple of column names in "create table" order.'''
        conn = self.db_conn()
        r = conn.execute('pragma table_info(members)').fetchall()
        fields =  tuple(i['name'] for i in r)
        conn.close()
        return fields

    def get_fields_str(self):
        '''Turns column names from get_fields() into a string for sqlite named style placeholders.'''
        fields = tuple(':' + i for i in self.get_fields())
        return ', '.join(fields)

    def mk_id(self):
        '''Generate a random unique id.'''
        alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        base = len(alphabet)
        i = int.from_bytes(os.urandom(16), 'little')
        out = ''
        if i == 0:
            out = alphabet[0]
        while i > 0:
            remainder = i % base
            i = i // base
            out += alphabet[remainder]
        return out[::-1]

    def new_db(self):
        conn = self.db_conn()
        conn.execute('create table members (mid text primary key not null, first, last, ama, phone, address, city, state, zip, email, expire)')
        conn.execute('create virtual table members_fts using fts4(content="members", mid, first, last, ama, phone, address, city, state, zip, email, expire, notindexed=mid, notindexed=expire)')
        conn.execute('create table appusers (appuser text primary key not null, password text)')
        conn.commit()
        conn.close()

    def rebuild(self):
        conn = self.db_conn()
        conn.execute('insert into members_fts(members_fts) values ("rebuild")')
        conn.commit()
        conn.close()

    def new_appuser(self, appuser, password):
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        conn = self.db_conn()
        conn.execute('insert into appusers values(?, ?)', (appuser, password_hash))
        conn.commit()
        conn.close()

    def password_valid(self, appuser, password):
        conn = self.db_conn()
        password_hash = conn.execute('select password from appusers where appuser=?', (appuser,)).fetchone()[0]
        conn.close()
        return check_password_hash(password_hash, password)

    def add(self, record):
        record['mid'] = self.mk_id()
        conn = self.db_conn()
        conn.execute('insert into members values(' + self.get_fields_str() + ')', record)
        conn.commit()
        conn.close()
        self.rebuild()
        return record['mid']

    def add_multiple(self, records):
        fields_str = self.get_fields_str()
        conn = self.db_conn()
        for record in records:
            if not record.get('mid'):
                record['mid'] = self.mk_id()
            conn.execute('insert into members values(' + fields_str + ')', record)
        conn.commit()
        conn.close()
        self.rebuild()

    def edit(self, record):
        mid = record.get('mid')
        fields = self.get_fields()
        record = tuple(record.get(field) for field in fields)
        set_string = ','.join(field + '=?' for field in fields)
        conn = self.db_conn()
        conn.execute('update members set ' + set_string + ' where mid=?', record + (mid,))
        conn.commit()
        conn.close()
        self.rebuild()

    def remove(self, mid):
        conn = self.db_conn()
        conn.execute('delete from members where mid=?', (mid,))
        conn.commit()
        conn.close()
        self.rebuild()

    def get(self, mid):
        conn = self.db_conn()
        record = conn.execute('select * from members where mid=?', (mid,)).fetchone()
        conn.close()
        if record:
            return [dict(record)]
        else:
            return []

    def all(self):
        conn = self.db_conn()
        records = conn.execute('select * from members' + self.sort_sql).fetchall()
        conn.close()
        return [dict(record) for record in records]

    def expired(self):
        conn = self.db_conn()
        records = conn.execute('select * from members where expire<date("now")' + self.sort_sql).fetchall()
        conn.close()
        return [dict(record) for record in records]

    def current(self):
        conn = self.db_conn()
        records = conn.execute('select * from members where expire>=date("now")' + self.sort_sql).fetchall()
        conn.close()
        return [dict(record) for record in records]

    def end_of_year(self):
        conn = sqlite3.connect(':memory:')
        out = conn.execute('select date("now","+1 year","start of year","-1 day")').fetchone()[0]
        conn.close()
        return out

    def search(self, query):
        conn = self.db_conn()
        records = conn.execute('select * from members_fts where members_fts match ?' + self.sort_sql, (query,)).fetchall()
        conn.close()
        return [dict(record) for record in records]
