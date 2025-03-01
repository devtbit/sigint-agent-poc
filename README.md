# SIGINT Agent

A simple SIGINT agent that captures, transcribes, and analyzes radio communications through an interactive chat interface. This proof-of-concept application connects to a GQRX software-defined radio receiver to monitor and control frequencies, transcribes audio in real-time using Groq's Whisper model, and provides an AI-powered chat interface for interacting with the captured data.

![SIGINT Agent](https://dummyimage.com/800x400/000/fff&text=SIGINT+Agent)

## Features

- **Radio Control**: Interface with GQRX software-defined radio to monitor and control frequencies
- **Real-time Audio Transcription**: Capture and transcribe radio communications using Groq's Whisper
- **Spanish Focused**: Optimized for transcribing Spanish language communications with noise filtering
- **Persistent Storage**: Store transcribed communications and session data in a SQLite database
- **AI-powered Chat Interface**: Interactive terminal-based chat agent for controlling radio and analyzing transcriptions
- **Language Model Integration**: Leverages Groq's LLM (default: llama-3.3-70b-versatile) for intelligent responses
- **Session Recording**: Records audio sessions for later analysis
- **Silence Filtering**: Automatically filters silent chunks to avoid unnecessary transcription calls

## Prerequisites

- Python 3.8+
- GQRX software-defined radio application running with remote control enabled
- Groq API access (for transcription and language model capabilities)
- FFmpeg installed on your system

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/devtbit/sigint-agent-poc.git
   cd sigint-agent-poc
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .env
   source .env/bin/activate  # On Windows: .env\Scripts\activate
   ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp env.example.sh env.sh
   # Edit env.sh with your GQRX host and Groq API key
   source env.sh
   ```

## Configuration

Configure the application by setting the following environment variables:

- `GQRX_HOST`: IP address or hostname of the GQRX server (default: 127.0.0.1)
- `GROQ_API_KEY`: Your Groq API key for transcription and language model access
- `GROQ_MODEL`: The Groq model to use (default: llama-3.3-70b-versatile)
- `DBNAME`: Database file name (default: transcripts.db)

## Usage

1. Ensure GQRX is running with remote control enabled (typically on port 7356)
2. Configure GQRX to stream audio via UDP (typically to port 7355)
3. Start the SIGINT Agent:
   ```bash
   python app.py
   ```
4. Interact with the agent through the terminal chat interface
5. Type `.exit` or `.quit` to end the session

### Agent Commands

The SIGINT Agent supports the following commands through natural language interaction:

- **Set Frequency**: Request the agent to tune to a specific frequency (e.g., "Tune to 420.120 MHz")
- **Get Current Frequency**: Ask for the currently monitored frequency
- **Get Recent Intercepts**: Request the last 10 minutes of intercepted communications
- **Get Frequency Summary**: Request a summary of all intercepted communications on a specific frequency

The agent responds in a secret agent style, providing intelligence analysis rather than raw transcripts.

## System Architecture

The SIGINT Agent consists of several key components:

- **app.py**: Main application that initializes the system and orchestrates components
- **gqrx_client.py**: Handles communication with the GQRX radio server
- **stream_groq_whisper.py**: Processes audio streams and performs transcription
- **chat_interface.py**: Provides the interactive terminal UI
- **agent.py**: Implements the AI agent using Groq's language models
- **database.py**: Manages the SQLite database for storing transcriptions and sessions
- **tools.py**: Defines the agent's function calling capabilities for radio control and data retrieval

## Data Flow

1. Audio is streamed from GQRX via UDP to the application
2. The audio stream is processed and transcribed in real-time using Groq's Whisper model
3. Noise filtering is applied to remove common Spanish false positives
4. Transcriptions are stored in a SQLite database
5. Users interact with the system through a terminal-based chat interface
6. Commands can be sent to GQRX to change frequencies
7. The Groq LLM provides intelligence analysis of intercepted communications

## Directory Structure

- `logs/`: Contains application logs
- `sessions/`: Stores recorded audio sessions
- `prompts/`: Contains system prompts for the AI agent
- `transcripts.db`: SQLite database for storing transcriptions and session data

## Audio Processing

The system:
1. Receives UDP audio stream from GQRX at 48kHz
2. Resamples to 16kHz for transcription
3. Saves a copy of the resampled audio for later analysis
4. Processes 30-second chunks for real-time transcription
5. Performs silence detection to skip processing silent audio

## Disclaimer

This software is intended for educational and legitimate signal intelligence purposes only. Users are responsible for compliance with all applicable laws and regulations regarding radio communications monitoring in their jurisdiction.
