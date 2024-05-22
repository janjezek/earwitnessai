import tkinter as tk
from tkinter import simpledialog, Label
import pyperclip
import pyautogui
import time
import threading
import pyaudio
import wave
import requests
from pynput import keyboard

# Audio Parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "output.wav"
frames = []

# Global Variables
recording = False
stream = None
root = None
label = None

def start_recording():
    global frames, stream, recording, label
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS,
                    rate=RATE, input=True,
                    frames_per_buffer=CHUNK)
    frames = []
    recording = True
    label.config(text="Recording...")
    while recording:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

def stop_recording():
    global stream, recording, label
    recording = False
    stream.stop_stream()
    stream.close()
    label.config(text="Processing...")

def save_recording():
    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(pyaudio.PyAudio().get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
def transcribe_audio():
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {
        "Authorization": ""
    }
    # Replace "your-model-name" with the actual model name, e.g., "whisper-large"
    data = {
        "model": "whisper-1"
    }
    files = {
        "file": ("output.wav", open(WAVE_OUTPUT_FILENAME, "rb"), "audio/wav")
    }
    response = requests.post(url, headers=headers, data=data, files=files)
    
    if response.status_code == 200:
        transcription_data = response.json()
        # Assuming the API response structure, adjust as necessary based on actual API documentation
        transcription = transcription_data['text']
        print(f"Status: {response.status_code}, Details: {transcription}")
        # Copy transcription to clipboard
        pyperclip.copy(transcription)
        # Wait a moment for clipboard to update
        # Simulate paste operation
        with pyautogui.hold(['command']):     
            time.sleep(1)     
            pyautogui.press('v')
        return transcription
    else:
        print(f"Error: {response.status_code}, Details: {response.text}")
        return "Transcription failed."

def update_ui_with_transcription(transcription):
    global label
    label.config(text=transcription)

def on_activate():
    global recording
    if not recording:
        threading.Thread(target=start_recording, daemon=True).start()
    else:
        stop_recording()
        save_recording()
        transcription = transcribe_audio()
        update_ui_with_transcription(transcription)

def for_canonical(f):
    return lambda k: f(listener.canonical(k))

def show_dialog():
    global root, label
    root = tk.Tk()
    root.title("Voice Recognition")
    label = tk.Label(text="Hello, Tkinter", fg="white", bg="black")
    label.pack(pady=20)
    root.geometry("400x100")
    root.mainloop()

hotkey = keyboard.HotKey(
    keyboard.HotKey.parse('<ctrl>+<cmd>+h'),
    on_activate)

listener = keyboard.Listener(
    on_press=for_canonical(hotkey.press),
    on_release=for_canonical(hotkey.release))
listener.start()

show_dialog()