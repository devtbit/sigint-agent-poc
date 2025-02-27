import datetime
import os
from peewee import (
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


def initialize_db():
    """Initialize database connection and create tables if they don't exist."""
    db.connect()
    db.create_tables([Transcript])


def save_transcript(text, timestamp=None):
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
    )
    t.save()
    return t 