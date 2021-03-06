import os
import base64
import datetime

from peewee import (
    fn, Model, ForeignKeyField, CharField, DateField,
    IntegrityError, ProgrammingError
    )
from playhouse.postgres_ext import PostgresqlExtDatabase, TSVectorField

def mk_id():
    """Generate a random unique id."""
    return base64.urlsafe_b64encode(os.urandom(15)).decode()

database = PostgresqlExtDatabase(
    os.environ.get('PG_NAME', 'members'),
    host = os.environ.get('PG_HOST', 'localhost'),
    user = os.environ.get('PG_USER', 'postgres'),
    password = os.environ.get('PG_PASSWORD', 'postgres'),
    register_hstore = False,
)

class CharNullField(CharField):
    def db_value(self, value):
        if not value:
            return None
        return value

class DateNullField(DateField):
    def db_value(self, value):
        if not value:
            return None
        return value
    def python_value(self, value):
        if not value:
            return ''
        return value

class BaseModel(Model):
    class Meta():
        database = database

class User(BaseModel):
    username = CharField(unique=True)
    password = CharField()

class Member(BaseModel):
    id = CharField(primary_key=True, default=mk_id)
    first_name = CharField()
    last_name = CharField()
    ama = CharField()
    phone = CharField()
    address = CharField()
    city = CharField()
    state = CharField()
    zip_code = CharField()
    email = CharNullField(unique=True, null=True)
    expire = DateField()
    dob = DateNullField(default=None, null=True)
    search_content = TSVectorField(default='')

    class Meta:
        order_by = ('-expire', 'last_name', 'first_name')

    def expired():
        """Members where expire date is in the past."""
        today = datetime.date.today()
        return Member.select().where(Member.expire < today)

    def current():
        """Members where expire date is today or in the future."""
        today = datetime.date.today()
        return Member.select().where(Member.expire >= today)

    def previous():
        """Members where expire date is December 31 of last year or later."""
        end_of_last_year = (
            datetime.date.today().replace(month=1, day=1) -
            datetime.timedelta(days=1)
            )
        return Member.select().where(Member.expire >= end_of_last_year)

    def active():
        """Members who are not delinquent. Returns previous() for first three
        months of the year, then returns current()."""
        if datetime.date.today().month <= 3:
            return Member.previous()
        else:
            return Member.current()

    def update_search_content(self):
        search_content = ' '.join([
            str(getattr(self, field)) for field in
            (
                'first_name',
                'last_name',
                'ama',
                'address',
                'city',
                'state',
                'zip_code',
                'email',
            )
        ])
        self.search_content = fn.to_tsvector('simple', search_content)
        self.save()
