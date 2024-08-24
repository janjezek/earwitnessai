<p align="center">
  <img src="ear-witness-ai-logo.png" alt="EarWitnessAI Logo">
</p>

# EarWitnessAI Voice Recognition App

This application allows you to record audio, transcribe it using OpenAI's Whisper API, and automatically paste the transcription into the active window. It's designed to be a quick and efficient tool for voice-to-text input across whole operating system.

## Features

- Record audio with a simple keyboard shortcut
- Transcribe audio using OpenAI's Whisper API
- Automatically copy and paste transcription into the active window
- Automatically clears the clipboard after pasting

## How It Works

1. The app runs in the background, listening for a specific keyboard shortcut (default: Ctrl+Space).
2. When the shortcut is pressed, it starts recording audio from the default microphone.
3. Pressing the shortcut again stops the recording.
4. The recorded audio is saved as a WAV file.
5. The WAV file is sent to OpenAI's Whisper API for transcription.
6. The transcribed text is copied to the clipboard and automatically pasted into the active window.
7. The clipboard is cleared after pasting.

## Setup and Customization

1. Clone the repository:

   ```
   git clone https://github.com/yourusername/earwitnessai.git
   cd earwitnessai
   ```

2. Install the required dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root and add your OpenAI API key:

   ```
   OPENAI_API_KEY=your_api_key_here
   ```

4. Customize the keyboard shortcut:

   - Open `earwitnessai.py`
   - Locate the `hotkey` variable (around line 159)
   - Modify the keyboard combination as desired, e.g.:
     ```python
     hotkey = keyboard.HotKey(
         keyboard.HotKey.parse('<ctrl>+<space>'),
         on_activate)
     ```

5. Run the application:
   ```
   python earwitnessai.py
   ```

## Requirements

- Python 3.7+
- OpenAI API key
- Dependencies listed in `requirements.txt`

## Note

This application requires access to your microphone and simulates keyboard input for pasting. Make sure you trust the source and have reviewed the code before running it on your system.

## License

[MIT License](LICENSE)
