# Voice Assistant with Persistent Memory

A personal voice assistant that helps you manage your life by remembering things, setting reminders, and keeping track of events. Built with Together.ai's generous API credits and designed for long-term use.

## ⚠️ Important Disclosure

This project was developed with significant assistance from AI tools (including GitHub Copilot and Claude) for boilerplate code generation and linting. While the core logic and architecture were carefully designed, there may be unexpected bugs or edge cases that weren't caught during development. Please use at your own risk and report any issues you encounter.

## Why I Built This

I'm terrible at remembering things. Whether it's important dates, personal preferences, or even what I had for lunch yesterday, my memory is unreliable. I needed a personal assistant that could:

1. Remember things I tell it, so I don't have to
2. Proactively remind me about upcoming events and tasks
3. Learn from our interactions to provide better context
4. Be available 24/7 without requiring a constant internet connection
5. Have a long-term memory that persists between sessions

This assistant is designed to be your long-term companion, learning about you over time and helping you manage your life more effectively.

## Features

### 🧠 Smart Memory System
- **Long-term Memory**: Stores information for up to 365 days
- **Contextual Memory**: Maintains relevant context from recent conversations
- **Topic-based Relevance**: Automatically identifies and recalls related information
- **Memory Cleanup**: Automatically manages and cleans up old data

### 📅 Calendar & Reminders
- **Weekly Calendar View**: See all your events and reminders for the week
- **Smart Reminders**: Set reminders with natural language
- **Event Tracking**: Keep track of upcoming events and appointments
- **Proactive Notifications**: Get reminded about upcoming events and tasks

### 🎯 Voice Interface
- **Natural Voice Interaction**: Speak naturally with your assistant
- **Google Text-to-Speech**: High-quality voice output
- **Fallback to System TTS**: Works even without internet connection
- **Automatic Turn Taking**: Assistant automatically listens after speaking

### 🔄 Persistent Storage
- **Local Memory File**: All data stored locally in JSON format
- **Automatic Backup**: Memory persists between sessions
- **Memory Management**: Automatic cleanup of old data
- **Data Privacy**: Your information stays on your device

### 🎮 Easy Controls
- `F12`: Activate voice input
- `F11`: Update intent display
- `F10`: Show weekly calendar

## Technical Stack

- **Speech Recognition**: `speech_recognition` with Google Speech-to-Text
- **Text-to-Speech**: `gTTS` (Google Text-to-Speech) with `pygame` for playback
- **LLM**: Together.ai's API (generous free tier with $1 credit that lasts forever)
- **Input Handling**: `pynput` for keyboard controls
- **Date Handling**: `python-dateutil` for smart date parsing
- **Environment Management**: `python-dotenv` for API key management

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/voice-assistant.git
cd voice-assistant
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root:
```bash
TOGETHER_API_KEY=your_api_key_here
```

5. Run the assistant:
```bash
python voice_assistant/app.py
```

## Usage

1. Start the assistant and wait for the welcome message
2. Press `F12` to start speaking
3. Speak naturally to:
   - Set reminders: "Remind me to call mom tomorrow at 2 PM"
   - Add events: "I have a meeting on Friday at 10 AM"
   - Share information: "Remember that I prefer dark mode"
   - Ask questions: "What do I have scheduled for tomorrow?"
   - Read reminders: "What are my active reminders?"

4. Use `F10` to view your weekly calendar
5. Use `F11` to update the intent display

## Memory Management

The assistant maintains two types of memory:
- **Long-term Memory**: Stores information for up to 365 days
- **Contextual Memory**: Keeps track of recent conversations and relevant information

Memory is automatically cleaned up to prevent bloat, and you can clear all memory at any time by saying "Clear all memory" (requires confirmation).

## Contributing

Feel free to submit issues and enhancement requests! This project is open source and welcomes contributions.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Together.ai for their generous API credits
- Google for their excellent speech recognition and text-to-speech services
- The open-source community for the various Python libraries used in this project
- AI tools (GitHub Copilot, Claude) for assistance with code generation and linting 