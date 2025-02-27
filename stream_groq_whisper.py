import datetime
import ffmpeg
import threading
import queue
import os
import time

from groq import Groq
from peewee import (
    CharField,
    DateTimeField,
    Model,
    SqliteDatabase,
)


client = Groq()

audio_queue = queue.Queue()

database_name = os.environ.get("DBNAME", "transcripts.db")

db = SqliteDatabase(database_name)


class Transcript(Model):
    timestamp = DateTimeField(default=datetime.datetime.now())
    text = CharField(null=False)
    frequency = CharField(null=True)

    class Meta:
        database = db


db.connect()
db.create_tables([Transcript])

# 30 seconds of 16kHZ:
# sample_rate(16000 samples/sec) * 30 sec * 2 bytes/sample
CHUNK_SIZE = 10 * 16000 * 2


def audio_worker():
    while True:
        item = audio_queue.get()
        if item is None:
            audio_queue.task_done()
            break

        # Unpack the item to include capture_time
        in_data, index, capture_time = item
        process_audio(in_data, index, capture_time)
        audio_queue.task_done()


def process_audio(in_data, index=0, capture_time=None):
    # Process the audio data here
    try:
        wav_bytes, _ = (
            ffmpeg.input(
                'pipe:',
                format='s16le',
                ar='16000',
                ac='1',
            ).output(
                'pipe:',
                format='wav',
                acodec='pcm_s16le',
                ac=1,
                ar=16000,
            ).run(
                input=in_data,
                cmd=['ffmpeg', '-nostdin'],
                capture_stdout=True,
                capture_stderr=True,
            )
        )
    except ffmpeg.Error as e:
        print(f"ffmpeg error during chunk->wav: {e.stderr.decode()}")
        return

    transcription = client.audio.transcriptions.create(
        file=(f"chunk_{index}.wav", wav_bytes),
        model="whisper-large-v3-turbo",
        language="es",
    )

    # Weird edge case, background noise detected as these phrases
    # in Spanish communications.
    if transcription.text not in [
       " Gracias.",
       " ¡Gracias!",
       " Gracias por ver el video.",
       " ¡Suscríbete al canal!"]:
        print(transcription.text, flush=True)
        t = Transcript.create(
            text=transcription.text,
            timestamp=capture_time,
        )
        t.save()


def run_ffmpeg():
    worker_thread = threading.Thread(target=audio_worker,
                                     daemon=True)
    worker_thread.start()

    # Define the input stream
    input_stream = ffmpeg.input(
        'udp://@:7355',
        format='s16le',
        ar='48000',
        ac='1'
    )

    # Split the audio stream into two streams
    split_stream = input_stream.filter_multi_output('asplit', 2)
    stream_to_file = split_stream.stream(0)
    stream_to_process = split_stream[1]

    # Resample the 'stream_to_process' from 48kHz to 16kHz
    resampled_stream = stream_to_process.filter(
        'aresample',
        resampler='soxr',
        sample_rate='16000')

    # Split the resampled stream again
    multi_resampled_stream = resampled_stream.filter_multi_output(
        'asplit', 2)
    multi_stream_to_file = multi_resampled_stream.stream(0)
    multi_stream_to_process = multi_resampled_stream[1]

    # Define the first output to save the original audio to 'output.wav'
    output1 = ffmpeg.output(stream_to_file, 'output.wav')

    # Define the second output to save the resampled audio to 'resampled.wav'
    output2 = ffmpeg.output(multi_stream_to_file, 'resampled.wav')

    # Define the second output to pipe (stdout) the resampled audio
    output3 = ffmpeg.output(
        multi_stream_to_process,
        'pipe:',
        format='s16le',
        acodec='pcm_s16le',
        ar='16000',
        ac='1'
    )

    # Merge the two outputs and run asynchronously
    process = ffmpeg.merge_outputs(output1, output2, output3).run_async(
        pipe_stdout=True,
        pipe_stderr=True
    )

    accumulated = b''
    chunk_index = 0
    # Store the start time of the current chunk being accumulated
    current_chunk_start_time = datetime.datetime.now()

    # Read and process audio data from stdout
    try:
        while True:
            in_bytes = process.stdout.read(2)
            if not in_bytes:
                if accumulated:
                    audio_queue.put((accumulated, chunk_index, current_chunk_start_time))
                break

            accumulated += in_bytes

            while len(accumulated) >= CHUNK_SIZE:
                chunk = accumulated[:CHUNK_SIZE]
                # Pass the capture time along with the audio data
                audio_queue.put((chunk, chunk_index, current_chunk_start_time))
                chunk_index += 1
                accumulated = accumulated[CHUNK_SIZE:]
                # Reset the start time for the next chunk
                current_chunk_start_time = datetime.datetime.now()
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        process.stdout.close()
        process.stderr.close()
        process.wait()

        audio_queue.put(None)
        worker_thread.join()


if __name__ == '__main__':
    # Run the ffmpeg process in a separate thread
    run_ffmpeg()
