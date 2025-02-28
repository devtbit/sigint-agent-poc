import datetime
import ffmpeg
import threading
import queue
import os
import time
import logging

from groq import Groq
import database
import gqrx_client as gqrx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("sigint_agent.log")
    ]
)
logger = logging.getLogger("sigint_audio_stream")

client = Groq()

audio_queue = queue.Queue()

# Initialize the database using our new module
database.initialize_db()
logger.info("Database initialized")

# 30 seconds of 16kHZ:
# sample_rate(16000 samples/sec) * 30 sec * 2 bytes/sample
CHUNK_SIZE = 10 * 16000 * 2


def audio_worker():
    logger.info("Audio worker thread started")
    processed_chunks = 0
    while True:
        item = audio_queue.get()
        if item is None:
            audio_queue.task_done()
            logger.info(f"Audio worker thread stopping, processed {processed_chunks} chunks")
            break

        # Unpack the item to include capture_time
        in_data, index, capture_time = item
        process_audio(in_data, index, capture_time)
        processed_chunks += 1
        audio_queue.task_done()


def process_audio(in_data, index=0, capture_time=None):
    # Process the audio data here
    frequency = database.get_current_session().frequency
    logger.debug(f"Processing audio chunk {index}, captured at {capture_time}, frequency: {frequency}")
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
        logger.error(f"ffmpeg error during chunk->wav: {e.stderr.decode()}")
        return

    logger.debug(f"Sending chunk {index} to Groq Whisper API")
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
        logger.info(f"Transcription: {transcription.text}")
        # Save transcript to database
        try:
            database.save_transcript(
                text=transcription.text,
                frequency=frequency,
                timestamp=capture_time,
            )
            logger.debug(f"Saved transcript to database: {transcription.text[:30]}...")
        except Exception as e:
            logger.error(f"Failed to save transcript to database: {e}")


def run_ffmpeg():
    logger.info("Starting FFmpeg processing pipeline")
    worker_thread = threading.Thread(target=audio_worker,
                                     daemon=True)
    worker_thread.start()

    # Create sessions directory if it doesn't exist
    sessions_dir = "sessions"
    if not os.path.exists(sessions_dir):
        os.makedirs(sessions_dir)
        logger.info(f"Created sessions directory: {sessions_dir}")

    # Generate timestamp for the session
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create filename with timestamp prefix (only resampled audio)
    resampled_filename = os.path.join(sessions_dir, f"{timestamp}_resampled.wav")
    
    logger.info(f"Recording session: {timestamp}")
    logger.info(f"Saving resampled audio to: {resampled_filename}")

    # Define the input stream
    logger.info("Setting up FFmpeg UDP input stream on port 7355")
    input_stream = ffmpeg.input(
        'udp://@:7355',
        format='s16le',
        ar='48000',
        ac='1'
    )

    # Resample the input stream from 48kHz to 16kHz
    resampled_stream = input_stream.filter(
        'aresample',
        resampler='soxr',
        sample_rate='16000')

    # Split the resampled stream 
    split_resampled_stream = resampled_stream.filter_multi_output(
        'asplit', 2)
    stream_to_file = split_resampled_stream.stream(0)
    stream_to_process = split_resampled_stream[1]

    # Define the output to save the resampled audio with timestamp prefix
    output1 = ffmpeg.output(stream_to_file, resampled_filename)

    # Define the output to pipe (stdout) the resampled audio
    output2 = ffmpeg.output(
        stream_to_process,
        'pipe:',
        format='s16le',
        acodec='pcm_s16le',
        ar='16000',
        ac='1'
    )

    # Merge the outputs and run asynchronously
    logger.info("Starting FFmpeg process")
    process = ffmpeg.merge_outputs(output1, output2).run_async(
        pipe_stdout=True,
        pipe_stderr=True
    )

    accumulated = b''
    chunk_index = 0
    # Store the start time of the current chunk being accumulated
    current_chunk_start_time = datetime.datetime.now()
    
    logger.info("Starting to process audio stream")
    # Read and process audio data from stdout
    try:
        while True:
            in_bytes = process.stdout.read(2)
            if not in_bytes:
                if accumulated:
                    logger.debug(f"Processing final accumulated chunk ({len(accumulated)} bytes)")
                    audio_queue.put((accumulated, chunk_index, current_chunk_start_time))
                break

            accumulated += in_bytes

            while len(accumulated) >= CHUNK_SIZE:
                chunk = accumulated[:CHUNK_SIZE]
                # Pass the capture time along with the audio data
                audio_queue.put((chunk, chunk_index, current_chunk_start_time))
                logger.debug(f"Queued chunk {chunk_index} for processing, size: {len(chunk)} bytes")
                chunk_index += 1
                accumulated = accumulated[CHUNK_SIZE:]
                # Reset the start time for the next chunk
                current_chunk_start_time = datetime.datetime.now()
    except Exception as e:
        logger.error(f"Error occurred during FFmpeg processing: {e}", exc_info=True)
    finally:
        logger.info("Cleaning up FFmpeg process")
        process.stdout.close()
        process.stderr.close()
        process.wait()

        logger.info("Stopping audio worker thread")
        audio_queue.put(None)
        worker_thread.join()
        logger.info(f"Processing completed, processed {chunk_index} chunks")


if __name__ == '__main__':
    logger.info("SIGINT Audio Stream starting up")
    frequency = None
    try:
        logger.info("Getting current frequency from GQRX")
        frequency = gqrx.send("f")
    except Exception as e:
        logger.error(f"Error getting current frequency: {e}")
    finally:
        gqrx.close()

    if frequency:
        database.save_session(frequency)
        logger.info(f"Initialized session with frequency: {frequency}")

    # Run the ffmpeg process in a separate thread
    run_ffmpeg()
    logger.info("SIGINT Audio Stream shutting down")
