import ffmpeg
import threading
import os
import queue

from pywhispercpp.model import Model


audio_queue = queue.Queue()

model_path = os.environ['WHISPER_MODEL']

# 30 seconds of 16kHZ:
# sample_rate(16000 samples/sec) * 30 sec * 2 bytes/sample
CHUNK_SIZE = 7 * 16000 * 2

w = Model(model_path)


def audio_worker():
    while True:
        item = audio_queue.get()
        if item is None:
            audio_queue.task_done()
            break

        in_data, index = item
        process_audio(in_data, index)
        audio_queue.task_done()


def process_audio(in_data, index=0):
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

    chunk_wav_path = f"/tmp/chunk_{index}.wav"
    with open(chunk_wav_path, 'wb') as f:
        f.write(wav_bytes)
    # You can add your audio processing logic here
    w.transcribe(chunk_wav_path,
                 language="es",
                 new_segment_callback=print)


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

    # Read and process audio data from stdout
    try:
        while True:
            in_bytes = process.stdout.read(2)
            if not in_bytes:
                if accumulated:
                    audio_queue.put((accumulated, chunk_index))
                break

            accumulated += in_bytes

            while len(accumulated) >= CHUNK_SIZE:
                chunk = accumulated[:CHUNK_SIZE]
                audio_queue.put((chunk, chunk_index))
                chunk_index += 1
                accumulated = accumulated[CHUNK_SIZE:]
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
