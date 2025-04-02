# Personal Voice Assistant

A sophisticated voice-enabled personal assistant that helps you manage your daily life with natural conversation and memory capabilities.

## Features

- 🎙️ Voice Interaction: Natural voice commands and responses
- 📅 Smart Reminders: Set and manage reminders with natural language
- 📝 Event Tracking: Keep track of your schedule and events
- 🧠 Memory System: 
  - Long-term memory for persistent information
  - Contextual memory for relevant recent information
  - Automatic memory cleanup and organization
  - Memory clearing and updating capabilities
- 📊 Weekly Calendar: View your schedule at a glance
- 🔔 Smart Notifications: Get timely reminders and updates
- 🎯 Intent Display: Real-time view of your assistant's current context
- 🔄 Automatic Listening: Assistant automatically starts listening after speaking

## Technical Stack

- Python 3.x
- Speech Recognition (Google Speech-to-Text)
- Text-to-Speech (Google Text-to-Speech)
- Together.ai API for natural language processing
- Pygame for audio playback
- Platform-specific notifications

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/voice_assistant.git
   cd voice_assistant
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   Create a `.env` file in the project root with:
   ```
   TOGETHER_API_KEY=your_together_ai_api_key
   ```

4. Run the assistant:
   ```bash
   python voice_assistant/app.py
   ```

## Usage

- Press F12 to activate voice input
- Press F11 to update the intent display
- Press F10 to show the weekly calendar

## Voice Commands

The assistant understands natural language commands for:
- Setting reminders
- Managing events
- Reading back reminders
- Clearing reminders
- Asking questions about past events
- Storing and retrieving information
- Clearing all memory
- Updating existing reminders and events

## Memory System

The assistant maintains two types of memory:
1. Long-term Memory:
   - Reminders
   - Events
   - Facts about you
   - Conversation history
   - Persists between sessions
   - Automatically cleaned up after 365 days

2. Contextual Memory:
   - Recent conversations
   - Active context
   - Relevant facts
   - Upcoming events
   - Active reminders
   - Updated in real-time
   - Maintains last 7 days of context

### Memory Management

The assistant provides several ways to manage your memory:

1. Clearing Memory:
   - Clear all active reminders
   - Clear all memory (reminders, events, facts, conversations)
   - Automatic cleanup of old data
   - Confirmation required for destructive actions

2. Updating Memory:
   - Update existing reminders
   - Modify event details
   - Add new information to facts
   - Automatic status updates for completed reminders

3. Memory Organization:
   - Automatic categorization of information
   - Smart cleanup of duplicate entries
   - Context-based relevance tracking
   - Weekly calendar view of all events and reminders

## Development Notes

- The assistant uses Together.ai's API for natural language processing
- Memory is automatically cleaned up to maintain efficiency
- The system adapts to your usage patterns over time
- **Current Limitations**: 
  - The memory system may experience performance issues with very long conversations
  - Future improvements will focus on better memory indexing and retrieval mechanisms
  - Consider implementing vector databases or more sophisticated memory management for large-scale usage

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

*Note: This project was developed with assistance from AI tools. While every effort has been made to ensure reliability, some features may require fine-tuning based on your specific needs and environment.* 