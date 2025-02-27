import datetime
import os
from peewee import (
    BooleanField,
    CharField,
    DateTimeField,
    Model,
    SqliteDatabase,
)

# Get database name from environment variable or use default
database_name = os.environ.get("DBNAME", "transcripts.db")

# Initialize database connection
db = SqliteDatabase(database_name)


class Transcript(Model):
    timestamp = DateTimeField(default=datetime.datetime.now())
    text = CharField(null=False)
    frequency = CharField(null=True)

    class Meta:
        database = db


class Session(Model):
    timestamp = DateTimeField(default=datetime.datetime.now())
    frequency = CharField(null=True)
    is_active = BooleanField(default=True)

    class Meta:
        database = db


def initialize_db():
    """Initialize database connection and create tables if they don't exist."""
    db.connect()
    db.create_tables([Transcript, Session])


def save_transcript(text, frequency, timestamp=None):
    """Save a transcript to the database.
    
    Args:
        text (str): The transcribed text
        timestamp (datetime, optional): When the audio was captured
    
    Returns:
        Transcript: The saved transcript instance
    """
    t = Transcript.create(
        text=text,
        timestamp=timestamp or datetime.datetime.now(),
        frequency=frequency,
    )
    t.save()
    return t


def save_session(frequency):
    """Save a session to the database. Deactivate any existing session.

    Args:
        frequency (str): The frequency of the session
    """
    Session.update(is_active=False).where(Session.is_active == True).execute()
    s = Session.create(frequency=frequency)
    s.save()
    return s


def get_current_session():
    """Get the current session from the database."""
    return Session.get(Session.is_active == True)