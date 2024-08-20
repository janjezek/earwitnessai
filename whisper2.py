import logging
import threading
import pyaudio
import wave
import requests
import pyperclip
from pynput import keyboard
from pynput.keyboard import Key, Controller, Listener
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import multiprocessing
import warnings
import urllib3
import os
from dotenv import load_dotenv
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty, QObject, pyqtSignal, QThread, QEvent
from PyQt5.QtGui import QPainter, QLinearGradient, QColor, QPainterPath, QPen
import numpy as np
import sys

# Suppress LibreSSL warning
warnings.filterwarnings("ignore", category=urllib3.exceptions.NotOpenSSLWarning)

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

def create_ssl_context():
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context

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
            
            for attempt in range(3):
                try:
                    response = session.post(url, headers=headers, files=files, data=data)
                    logging.info(f"API Response status code: {response.status_code}")
                    response.raise_for_status()
                    transcription = response.json()['text']
                    logging.info(f"Transcription: {transcription}")
                    queue.put(transcription)
                    return
                except requests.exceptions.RequestException as e:
                    logging.error(f"Request error in transcription (attempt {attempt + 1}): {e}")
                    if attempt < 2:
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        queue.put("Transcription failed after multiple attempts.")
        
    except Exception as e:
        logging.error(f"Unexpected error in transcription: {e}")
        queue.put("Transcription failed due to unexpected error.")

def transcribe_audio():
    queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=transcribe_audio_process, args=(queue,))
    process.start()
    process.join(timeout=30)  # Wait for up to 30 seconds
    
    if process.is_alive():
        process.terminate()
        process.join()
        return "Transcription timed out"
    
    if not queue.empty():
        return queue.get()
    else:
        return "Transcription failed"

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
    except Exception as e:
        logging.error(f"Error copying or pasting transcription: {e}")

class SoundWaveWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sound Wave")
        self.setFixedSize(400, 150)  # Set a fixed size for the window
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Center the window horizontally and position it at the bottom 25% of the screen
        self.center_bottom()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)

        self.waveform_widget = WaveformWidget()
        self.layout.addWidget(self.waveform_widget)

        self.controls_widget = QWidget()
        self.controls_layout = QHBoxLayout(self.controls_widget)
        self.layout.addWidget(self.controls_widget)

        self.recording_indicator = RecordingIndicator()
        self.stop_button = QPushButton("Stop")
        self.cancel_button = QPushButton("Cancel")

        self.controls_layout.addWidget(self.recording_indicator)
        self.controls_layout.addStretch()
        self.controls_layout.addWidget(self.stop_button)
        self.controls_layout.addWidget(self.cancel_button)

        self.setStyleSheet("""
            QMainWindow {
                background-color: rgba(30, 30, 30, 200);
                border-radius: 10px;
            }
            QPushButton {
                background-color: rgba(60, 60, 60, 200);
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 200);
            }
        """)

        self.stop_button.clicked.connect(self.on_stop)
        self.cancel_button.clicked.connect(self.on_cancel)

    def center_bottom(self):
        screen = QApplication.primaryScreen().geometry()
        window_width = self.width()
        window_height = self.height()
        
        x = (screen.width() - window_width) // 2
        y = int(screen.height() * 0.75) - window_height // 2
        
        self.move(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10, 10)

        painter.setClipPath(path)
        painter.fillPath(path, QColor(30, 30, 30, 200))

    def on_stop(self):
        # Implement stop logic
        pass

    def on_cancel(self):
        global recording
        stop_recording()
        recording = False
        window_manager.hide_window.emit()
        # Clear the frames to ensure nothing is saved
        global frames
        frames = []

class WaveformWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(80)
        self.waveform_data = np.zeros(100)  # Initialize with zeros
        self.sensitivity = 15  # Increased sensitivity (adjust this value as needed)
        self.smoothing_factor = 0.2  # Smoothing factor for the waveform

    def update_waveform(self, new_data):
        # Amplify the signal and clip to [-1, 1]
        amplified_data = np.clip(new_data * self.sensitivity, -1, 1)
        
        # Apply smoothing
        self.waveform_data = self.waveform_data * (1 - self.smoothing_factor) + amplified_data[-100:] * self.smoothing_factor
        
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        mid_height = height // 2

        path = QPainterPath()
        path.moveTo(0, mid_height)

        for i, value in enumerate(self.waveform_data):
            x = i * (width / len(self.waveform_data))
            y = mid_height + value * (height / 2)
            path.lineTo(x, y)

        # White waveform with thicker line
        painter.setPen(QPen(QColor(255, 255, 255), 3))
        painter.drawPath(path)

        # Subtle white gradient fill
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, QColor(255, 255, 255, 100))
        gradient.setColorAt(1, QColor(255, 255, 255, 30))
        painter.fillPath(path, gradient)

class RecordingIndicator(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(20, 20)
        self._color = QColor(255, 0, 0, 255)  # Initialize with red color
        self.animation = QPropertyAnimation(self, b"color")
        self.animation.setDuration(1000)
        self.animation.setStartValue(QColor(255, 0, 0, 255))
        self.animation.setEndValue(QColor(255, 0, 0, 100))
        self.animation.setLoopCount(-1)
        self.animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self._color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.rect())

    def setColor(self, color):
        self._color = color
        self.update()

    def getColor(self):
        return self._color

    color = pyqtProperty(QColor, getColor, setColor)

class WindowManager(QObject):
    show_window = pyqtSignal()
    hide_window = pyqtSignal()
    update_plot = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.window = None
        self.show_window.connect(self._show_window)
        self.hide_window.connect(self._hide_window)
        self.update_plot.connect(self._update_plot)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot.emit)
        self.update_timer.start(33)  # Update every 33 ms (approximately 30 FPS)

    def _show_window(self):
        if self.window is None:
            self.window = SoundWaveWindow()
            self.make_draggable(self.window)
        self.window.show()
        # Set focus to the window to capture key events
        self.window.setFocus()

    def _hide_window(self):
        if self.window:
            self.window.hide()

    def _update_plot(self):
        if self.window and recording and frames:
            data = np.frombuffer(frames[-1], dtype=np.int16)
            normalized_data = data / 32768.0  # Normalize to [-1, 1]
            self.window.waveform_widget.update_waveform(normalized_data)

    def make_draggable(self, window):
        class Filter(QObject):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.mouse_press_pos = None

            def eventFilter(self, obj, event):
                if event.type() == QEvent.MouseButtonPress:
                    self.mouse_press_pos = event.globalPos() - window.pos()
                    return True
                elif event.type() == QEvent.MouseMove and self.mouse_press_pos is not None:
                    window.move(event.globalPos() - self.mouse_press_pos)
                    return True
                elif event.type() == QEvent.MouseButtonRelease:
                    self.mouse_press_pos = None
                    return True
                return False

        filter = Filter(window)
        window.installEventFilter(filter)

window_manager = None

def on_activate():
    global recording, window_manager
    if not recording:
        threading.Thread(target=start_recording, daemon=True).start()
        window_manager.show_window.emit()
    else:
        stop_recording()
        window_manager.hide_window.emit()
        save_recording()
        transcription = transcribe_audio()
        copy_and_paste_transcription(transcription)

def on_press(key):
    global recording, window_manager
    if key == Key.esc and recording:
        if window_manager.window:
            window_manager.window.on_cancel()

def for_canonical(f):
    return lambda k: f(k)

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        window_manager = WindowManager()
        
        # Set up the keyboard listeners
        hotkey = keyboard.HotKey(
            keyboard.HotKey.parse('<ctrl>+<cmd>+h'),
            on_activate)
        
        with keyboard.Listener(
            on_press=for_canonical(hotkey.press),
            on_release=for_canonical(hotkey.release)
        ) as hotkey_listener, keyboard.Listener(on_press=on_press) as esc_listener:
            
            logging.info("Voice recognition app is running. Press Ctrl+Cmd+H to start/stop recording. Press Esc to cancel.")
            app.exec_()
    except Exception as e:
        logging.error(f"Error in main thread: {e}")
    finally:
        if recording:
            stop_recording()