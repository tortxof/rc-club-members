import os
import base64
import datetime

from peewee import (
    Model, ForeignKeyField, CharField, DateField,
    IntegrityError
    )
from playhouse.sqlite_ext import SqliteExtDatabase, FTSModel, SearchField
from playhouse.reflection import Introspector
from playhouse.migrate import migrate, SqliteMigrator

def mk_id():
    """Generate a random unique id."""
    return base64.urlsafe_b64encode(os.urandom(15)).decode()

database = PostgresqlExtDatabase(
    os.environ.get('PG_NAME'),
    host = os.environ.get('PG_HOST'),
    user = os.environ.get('PG_USER'),
    password = os.environ.get('PG_PASSWORD'),
)

class CharNullField(CharField):
    def db_value(self, value):
        if not value:
            return None
        return value

class BaseModel(Model):
    class Meta():
        database = database

class BaseFTSModel(FTSModel):
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
    dob = DateField(default='')

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

    def migrate():
        migrator = SqliteMigrator(database)
        introspector = Introspector.from_database(database)
        try:
            member_model = introspector.generate_models()['member']
        except KeyError:
            pass
        else:
            member_fields = member_model._meta.fields.keys()
            if 'dob' not in member_fields:
                with database.transaction():
                    migrate(
                        migrator.add_column(
                            'member',
                            'dob',
                            DateField(default='')
                        )
                    )

class MemberIndex(BaseFTSModel):
    id = SearchField()
    first_name = SearchField()
    last_name = SearchField()
    ama = SearchField()
    phone = SearchField()
    address = SearchField()
    city = SearchField()
    state = SearchField()
    zip_code = SearchField()
    email = SearchField()
    expire = SearchField()
    dob = SearchField()

    class Meta:
        extension_options = {'content': Member}
