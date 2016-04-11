import os
import base64
import datetime

from peewee import (
    Model, SqliteDatabase, ForeignKeyField, CharField, DateField,
    IntegrityError
    )

def mk_id():
    """Generate a random unique id."""
    return base64.urlsafe_b64encode(os.urandom(15)).decode()

database = SqliteDatabase('/data/data.db')

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
    email = CharField(unique=True, null=True)
    expire = DateField()

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
