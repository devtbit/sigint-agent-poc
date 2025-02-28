import datetime
import os
import logging
from peewee import (
    BooleanField,
    CharField,
    DateTimeField,
    Model,
    SqliteDatabase,
    DoesNotExist
)

# Get logger for this module
logger = logging.getLogger("sigint_database")

# Get database name from environment variable or use default
database_name = os.environ.get("DBNAME", "transcripts.db")

# Initialize database connection
db = SqliteDatabase(database_name)


class Transcript(Model):
    timestamp = DateTimeField(default=datetime.datetime.now())
    text = CharField(null=False)
    frequency = CharField(null=True)
    source_file = CharField(null=True)

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
    logger.info(f"Initializing database: {database_name}")
    db.connect()
    db.create_tables([Transcript, Session])

    # Create default session if none exists
    try:
        get_current_session()
    except DoesNotExist:
        logger.info("No active session found, creating default session")
        save_session("unknown")


def save_transcript(text, frequency, timestamp=None, source_file=None):
    """Save a transcript to the database.

    Args:
        text (str): The transcribed text
        frequency (str): The frequency when the transcript was recorded
        timestamp (datetime, optional): When the audio was captured
        source_file (str, optional): The name of the source audio file

    Returns:
        Transcript: The saved transcript instance
    """
    msg_preview = text[:30] + "..." if len(text) > 30 else text
    logger.debug(f"Saving transcript: {msg_preview}")
    t = Transcript.create(
        text=text,
        timestamp=timestamp or datetime.datetime.now(),
        frequency=frequency,
        source_file=source_file,
    )
    t.save()
    return t


def get_transcripts(frequency, max_results=100):
    """Get all transcripts for a given frequency.

    Args:
        frequency (str): The frequency to filter transcripts by
        max_results (int, optional): The maximum number of results to return

    Returns:
        list: A list of Transcript instances
    """
    return Transcript.select() \
        .where(Transcript.frequency == frequency) \
        .limit(max_results)


def get_last_transcripts(frequency, last_minutes=5):
    """Get the last 5 minutes of transcripts for a given frequency.

    Args:
        frequency (str): The frequency to filter transcripts by
        last_minutes (int, optional): The number of minutes to look back

    Returns:
        list: A list of Transcript instances
    """
    cutoff = datetime.datetime.now() - datetime.timedelta(minutes=last_minutes)
    return Transcript.select().where(
        (Transcript.frequency == frequency) & (Transcript.timestamp < cutoff)
    )


def save_session(frequency):
    """Save a session to the database. Deactivate any existing session.

    Args:
        frequency (str): The frequency of the session

    Returns:
        Session: The created session
    """
    logger.info(f"Creating new session with frequency: {frequency}")
    Session.update(is_active=False).where(Session.is_active).execute()
    s = Session.create(frequency=frequency)
    s.save()
    return s


def get_current_session():
    """Get the current session from the database.

    Returns:
        Session: The current active session

    Raises:
        DoesNotExist: If no active session exists
    """
    try:
        return Session.get(Session.is_active)
    except DoesNotExist:
        logger.warning("No active session found in database")
        # Create a default session
        return save_session("unknown")
