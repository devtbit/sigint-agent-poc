import datetime
import ffmpeg
import threading
import queue
import os
import logging
import numpy as np
import wave
import io

from groq import Groq
import database

# Configure logging
logger = logging.getLogger("sigint_audio_stream")

client = Groq()

audio_queue = queue.Queue()

# 30 seconds of 16kHZ:
# sample_rate(16000 samples/sec) * 20 sec * 2 bytes/sample
CHUNK_SIZE = 15 * 16000 * 2

# Global variable to store the current resampled audio filename
current_resampled_filename = None


def is_audio_silent(wav_bytes, silence_threshold=150.0):
    """
    Determine if the audio data is silent based on RMS amplitude.
    
    Args:
        wav_bytes: WAV file data as bytes
        silence_threshold: RMS threshold below which audio is considered silent
        
    Returns:
        is_silent: bool, True if audio is silent, False otherwise
        rms: float, the calculated RMS value (useful for logging)
    """
    try:
        # Read WAV data using wave module and numpy
        with io.BytesIO(wav_bytes) as wav_io:
            with wave.open(wav_io, 'rb') as wav_file:
                # Get audio as numpy array
                frames = wav_file.getnframes()
                audio_data = wav_file.readframes(frames)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                # Calculate RMS (Root Mean Square) of the audio signal
                rms = np.sqrt(np.mean(np.square(audio_array.astype(np.float32))))
                
                # Determine if silent based on threshold
                is_silent = rms < silence_threshold
                
                return is_silent, rms
    except Exception as e:
        # If there's an error, assume it's not silent to be safe
        logger.warning(f"Error during silence detection: {e}")
        return False, 0.0


def audio_worker():
    logger.info("Audio worker thread started")
    processed_chunks = 0
    while True:
        item = audio_queue.get()
        if item is None:
            audio_queue.task_done()
            logger.info(
                "Audio worker thread stopping, "
                f"processed {processed_chunks} chunks")
            break

        # Unpack the item to include capture_time
        in_data, index, capture_time = item
        process_audio(in_data, index, capture_time, current_resampled_filename)
        processed_chunks += 1
        audio_queue.task_done()


def process_audio(in_data, index=0, capture_time=None, source_file=None):
    # Process the audio data here
    frequency = database.get_current_session().frequency
    logger.debug(
        f"Processing audio chunk {index}, captured at {capture_time}, "
        f"frequency: {frequency}")
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

    # Check if the audio is silent to avoid unnecessary API calls
    is_silent, rms = is_audio_silent(wav_bytes)
    if is_silent:
        logger.info(f"Chunk {index} detected as silence (RMS: {rms:.2f}), skipping transcription")
        return
    
    logger.debug(f"Chunk {index} contains audio (RMS: {rms:.2f}), proceeding with transcription")

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
                source_file=source_file,
            )

            logger.debug(
                "Saved transcript to database: "
                f"{transcription.text[:30]}...")
        except Exception as e:
            logger.error(f"Failed to save transcript to database: {e}")


# Global variable to track the audio stream thread
audio_stream_thread = None
ffmpeg_process = None


def run_audio_stream():
    """Main function to run the audio stream processing in a background thread.
    This function is meant to be called from app.py."""
    global audio_stream_thread

    # Create and start the thread if it doesn't exist already
    if audio_stream_thread is None or not audio_stream_thread.is_alive():
        audio_stream_thread = threading.Thread(
            target=run_ffmpeg,
            # Set as daemon so it exits when the main thread exits
            daemon=True,
            name="AudioStreamThread"
        )
        audio_stream_thread.start()
        logger.info("Audio stream thread started")
    else:
        logger.warning("Audio stream thread is already running")

    return audio_stream_thread


def stop_audio_stream():
    """Stop the audio stream processing.
    This function is meant to be called from app.py during shutdown."""
    global audio_stream_thread, ffmpeg_process

    logger.info("Stopping audio stream...")

    # Signal the audio worker to stop
    if audio_queue.qsize() > 0:
        logger.info(f"Clearing audio queue ({audio_queue.qsize()} items)...")
        while not audio_queue.empty():
            try:
                audio_queue.get_nowait()
                audio_queue.task_done()
            except queue.Empty:
                break

    # Add None to queue to stop the audio worker
    audio_queue.put(None)

    # Terminate the FFmpeg process if it's running
    if ffmpeg_process is not None:
        logger.info("Terminating FFmpeg process...")
        try:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)
        except Exception as e:
            logger.error(f"Error terminating FFmpeg process: {e}")

    # Wait for the thread to finish if it's running
    if audio_stream_thread is not None and audio_stream_thread.is_alive():
        logger.info("Waiting for audio stream thread to finish...")
        audio_stream_thread.join(timeout=5)
        if audio_stream_thread.is_alive():
            logger.warning("Audio stream thread did not finish in time")

    logger.info("Audio stream stopped")


# Add a function to continuously read from stderr to prevent buffer filling up
def stderr_reader(process):
    """
    Read from stderr in a separate thread to prevent buffer from filling up.
    """
    logger.info("FFmpeg stderr reader thread started")
    while True:
        try:
            line = process.stderr.readline()
            if not line:
                logger.info("FFmpeg stderr closed, exiting reader thread")
                break
            # Log any non-empty output at debug level
            line_str = line.decode('utf-8', errors='replace').strip()
            if line_str:
                logger.debug(f"FFmpeg: {line_str}")
        except Exception as e:
            logger.error(f"Error reading FFmpeg stderr: {e}")
            break
    logger.info("FFmpeg stderr reader thread stopped")


def run_ffmpeg():
    logger.info("Starting FFmpeg processing pipeline")
    global ffmpeg_process, current_resampled_filename

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
    resampled_filename = os.path.join(
        sessions_dir, f"{timestamp}_resampled.wav")

    # Store the filename in the global variable
    current_resampled_filename = resampled_filename

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
    ffmpeg_process = ffmpeg.merge_outputs(output1, output2).run_async(
        pipe_stdout=True,
        pipe_stderr=True
    )

    # Start stderr reader thread to prevent buffer filling up
    stderr_thread = threading.Thread(
        target=stderr_reader,
        args=(ffmpeg_process,),
        daemon=True
    )
    stderr_thread.start()

    accumulated = b''
    chunk_index = 0
    # Store the start time of the current chunk being accumulated
    current_chunk_start_time = datetime.datetime.now()

    logger.info("Starting to process audio stream")
    # Read and process audio data from stdout
    try:
        while True:
            in_bytes = ffmpeg_process.stdout.read(2)
            if not in_bytes:
                if accumulated:
                    logger.debug(
                        "Processing final accumulated chunk "
                        f"({len(accumulated)} bytes)")
                    audio_queue.put((
                        accumulated,
                        chunk_index,
                        current_chunk_start_time))
                break

            accumulated += in_bytes

            while len(accumulated) >= CHUNK_SIZE:
                chunk = accumulated[:CHUNK_SIZE]
                # Pass the capture time along with the audio data
                audio_queue.put((chunk, chunk_index, current_chunk_start_time))
                logger.debug(
                    f"Queued chunk {chunk_index} for processing, "
                    f"size: {len(chunk)} bytes")
                chunk_index += 1
                accumulated = accumulated[CHUNK_SIZE:]
                # Reset the start time for the next chunk
                current_chunk_start_time = datetime.datetime.now()
    except Exception as e:
        logger.error(
            "Error occurred during FFmpeg processing: "
            f"{e}", exc_info=True)
    finally:
        logger.info("Cleaning up FFmpeg process")
        if ffmpeg_process:
            ffmpeg_process.stdout.close()
            ffmpeg_process.stderr.close()
            ffmpeg_process.wait()

        logger.info("Stopping audio worker thread")
        audio_queue.put(None)
        worker_thread.join()
        logger.info(f"Processing completed, processed {chunk_index} chunks")
