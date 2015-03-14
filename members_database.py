class MembersDatabase(object):
    def __init__(self):
        self.sort_sql = ' order by expire desc, last asc, first asc'
        self.dbfile = 'members.db'

    def db_conn(self):
        conn = sqlite3.connect(self.dbfile)
        conn.row_factory = sqlite3.Row
        return conn

    def get_fields(self):
        conn = self.db_conn()
        r = conn.execute('pragma table_info(members)').fetchall()
        fields =  tuple(i['name'] for i in r)
        conn.close()
        return fields

    def new_db(self):
        conn = self.db_conn()
        conn.execute('create virtual table members using fts4(first, last, ama, phone, address, city, state, zip, email, expire, notindexed=expire)')
        conn.execute('create table appusers (appuser text primary key not null, password text)')
        conn.commit()
        conn.close()

    def new_appuser(self, appuser, password):
        password = bcrypt.hashpw(password, bcrypt.gensalt())
        conn = self.db_conn()
        conn.execute('insert into appusers values(?, ?)', (appuser, password))
        conn.commit()
        conn.close()

    def password_valid(self, appuser, password):
        conn = self.db_conn()
        stored_password = conn.execute('select password from appusers where appuser=?', (appuser,)).fetchone()[0]
        conn.close()
        return bcrypt.checkpw(password, stored_password)

    def add(self, record):
        conn = self.db_conn()
        fields = self.get_fields()
        cur = conn.cursor()
        cur.execute('insert into members values(' + ', '.join('?' * len(fields)) + ')', tuple(record.get(field) for field in fields))
        rowid = cur.lastrowid
        conn.commit()
        conn.close()
        return rowid

    def edit(self, rowid, record):
        conn = self.db_conn()
        fields = self.get_fields()
        record = tuple(record.get(field) for field in fields)
        set_string = ','.join([field + '=?' for field in fields])
        conn.execute('update members set ' + set_string + ' where rowid=?', record + (rowid,))
        conn.commit()
        conn.close()

    def remove(self, rowid):
        conn = self.db_conn()
        conn.execute('delete from members where rowid=?', (rowid,))
        conn.commit()
        conn.close()

    def get(self, rowid):
        conn = self.db_conn()
        record = conn.execute('select *,rowid from members where rowid=?', (rowid,)).fetchone()
        conn.close()
        return [dict(record)]

    def all(self):
        conn = self.db_conn()
        records = conn.execute('select *,rowid from members' + self.sort_sql).fetchall()
        conn.close()
        return [dict(record) for record in records]

    def expired(self):
        conn = self.db_conn()
        records = conn.execute('select *,rowid from members where expire<date("now")' + self.sort_sql).fetchall()
        conn.close()
        return [dict(record) for record in records]

    def current(self):
        conn = self.db_conn()
        records = conn.execute('select *,rowid from members where expire>=date("now")' + self.sort_sql).fetchall()
        conn.close()
        return [dict(record) for record in records]

    def end_of_year(self):
        conn = sqlite3.connect(':memory:')
        out = conn.execute('select date("now","+1 year","start of year","-1 day")').fetchone()[0]
        conn.close()
        return out

    def search(self, query):
        conn = self.db_conn()
        records = conn.execute('select *,rowid from members where members match ?' + self.sort_sql, (query,)).fetchall()
        conn.close()
        return [dict(record) for record in records]
