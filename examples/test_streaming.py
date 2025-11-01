#!/usr/bin/env python3
"""
AssemblyAI Streaming Transcription Test Service for macOS

This script provides a simple service to test real-time transcription
using your microphone on macOS.

Requirements:
- pip install assemblyai python-dotenv

Usage:
    python test_streaming.py

Press Ctrl+C to stop the transcription.
"""

import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    StreamingSessionParameters,
    TerminationEvent,
    TurnEvent,
)
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Type

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Load API key from environment variable
api_key = os.getenv("ASSEMBLYAI_API_KEY")
if not api_key:
    logger.error("ASSEMBLYAI_API_KEY environment variable is not set")
    logger.error(f"Please check your .env file at: {env_path}")
    sys.exit(1)

logger.info("API key loaded successfully")


def on_begin(self: Type[StreamingClient], event: BeginEvent):
    """Called when the streaming session begins"""
    print("\n" + "="*60)
    print(f"🎤 Transcription session started!")
    print(f"Session ID: {event.id}")
    print("="*60)
    print("\nSpeak into your microphone... (Press Ctrl+C to stop)\n")


def on_turn(self: Type[StreamingClient], event: TurnEvent):
    """Called when a transcription turn is received"""
    if event.transcript:
        # Print the transcript with visual indicators
        status = "✓" if event.end_of_turn else "..."
        print(f"[{status}] {event.transcript}")

    # Request formatted turns if not already enabled
    if event.end_of_turn and not event.turn_is_formatted:
        params = StreamingSessionParameters(
            format_turns=True,
        )
        self.set_params(params)


def on_terminated(self: Type[StreamingClient], event: TerminationEvent):
    """Called when the streaming session terminates"""
    print("\n" + "="*60)
    print(f"📊 Session terminated")
    print(f"Total audio processed: {event.audio_duration_seconds:.2f} seconds")
    print("="*60 + "\n")


def on_error(self: Type[StreamingClient], error: StreamingError):
    """Called when an error occurs"""
    logger.error(f"❌ Error occurred: {error}")


def main():
    """Main function to run the streaming transcription service"""
    try:
        logger.info("Initializing AssemblyAI Streaming Client...")

        # Create streaming client
        client = StreamingClient(
            StreamingClientOptions(
                api_key=api_key,
                api_host="streaming.assemblyai.com",
            )
        )

        # Register event handlers
        client.on(StreamingEvents.Begin, on_begin)
        client.on(StreamingEvents.Turn, on_turn)
        client.on(StreamingEvents.Termination, on_terminated)
        client.on(StreamingEvents.Error, on_error)

        logger.info("Connecting to AssemblyAI streaming service...")

        # Connect to the streaming service
        client.connect(
            StreamingParameters(
                sample_rate=16000,
                format_turns=True
            )
        )

        logger.info("Starting microphone stream...")

        # Start streaming from microphone
        client.stream(
            aai.extras.MicrophoneStream(sample_rate=16000)
        )

    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping transcription...")
        logger.info("User interrupted the session")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        try:
            client.disconnect(terminate=True)
            logger.info("Client disconnected successfully")
        except:
            pass


if __name__ == "__main__":
    print("\n🎙️  AssemblyAI Real-time Transcription Service")
    print("=" * 60)
    main()
    print("\n👋 Goodbye!\n")
