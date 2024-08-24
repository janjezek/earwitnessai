import logging
import threading
import pyaudio
import wave
import requests
import pyperclip
from pynput import keyboard
from pynput.keyboard import Key, Controller
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Audio Parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024
WAVE_OUTPUT_FILENAME = "output.wav"

# Global Variables
recording = False
frames = []
lock = threading.Lock()

class AudioHandler:
    def __init__(self):
        self.p = None
        self.stream = None

    def __enter__(self):
        self.p = pyaudio.PyAudio()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.p:
            self.p.terminate()

    def start_stream(self):
        self.stream = self.p.open(format=FORMAT, channels=CHANNELS,
                                  rate=RATE, input=True,
                                  frames_per_buffer=CHUNK)

def start_recording():
    global frames, recording
    frames = []
    with lock:
        recording = True
    
    with AudioHandler() as audio:
        audio.start_stream()
        while recording:
            try:
                data = audio.stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            except IOError as e:
                logging.warning(f"IOError during recording: {e}")

def stop_recording():
    global recording
    with lock:
        recording = False
    logging.info("Recording stopped")

def save_recording():
    global frames
    try:
        logging.info("Saving recording")
        if not frames:
            logging.warning("No frames to save")
            return
        with AudioHandler() as audio:
            wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()
        logging.info("Recording saved")
    except Exception as e:
        logging.error(f"Error saving recording: {e}")
    finally:
        frames = []

def transcribe_audio_process(queue):
    try:
        logging.info("Starting transcription")
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
        }
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        
        with open(WAVE_OUTPUT_FILENAME, "rb") as f:
            files = {"file": (WAVE_OUTPUT_FILENAME, f, "audio/wav")}
            data = {"model": "whisper-1"}
            logging.info("Sending request to OpenAI API")
            
            response = session.post(url, headers=headers, files=files, data=data)
            logging.info(f"API Response status code: {response.status_code}")
            response.raise_for_status()
            transcription = response.json()['text']
            # Capitalize only the first word
            transcription = ' '.join([word.capitalize() if i == 0 else word for i, word in enumerate(transcription.split())])
            logging.info(f"Transcription: {transcription}")
            return transcription
        
    except Exception as e:
        logging.error(f"Unexpected error in transcription: {e}")
        return "Transcription failed due to unexpected error."

def transcribe_audio():
    return transcribe_audio_process(None)  # Remove queue argument

def copy_and_paste_transcription(text):
    try:
        logging.info("Copying transcription to clipboard")
        pyperclip.copy(text)
        logging.info("Transcription copied to clipboard")

        # Simulate Cmd+V to paste
        keyboard_controller = Controller()
        keyboard_controller.press(Key.cmd)
        keyboard_controller.press('v')
        keyboard_controller.release('v')
        keyboard_controller.release(Key.cmd)
        logging.info("Transcription pasted")

        # Add a short delay before clearing the clipboard
        time.sleep(0.5)

        # Clear the clipboard
        pyperclip.copy('')
        logging.info("Clipboard cleared")
    except Exception as e:
        logging.error(f"Error copying, pasting, or clearing transcription: {e}")

def on_activate():
    global recording
    if not recording:
        threading.Thread(target=start_recording, daemon=True).start()
    else:
        stop_recording()
        save_recording()
        transcription = transcribe_audio()
        copy_and_paste_transcription(transcription)

hotkey = keyboard.HotKey(
    keyboard.HotKey.parse('<ctrl>+<space>'),
    on_activate)

def for_canonical(f):
    return lambda k: f(listener.canonical(k))

listener = keyboard.Listener(
    on_press=for_canonical(hotkey.press),
    on_release=for_canonical(hotkey.release))

if __name__ == "__main__":
    try:
        listener.start()
        logging.info("Voice recognition app is running. Press Ctrl+Space to start/stop recording.")
        listener.join()
    except Exception as e:
        logging.error(f"Error in main thread: {e}")
    finally:
        if recording:
            stop_recording()