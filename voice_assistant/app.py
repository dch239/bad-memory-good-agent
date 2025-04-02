#!/usr/bin/env python3
import os
import time
import json
import threading
import datetime
import subprocess
import platform
import tempfile
from dateutil import parser
from dotenv import load_dotenv
import speech_recognition as sr
from pynput import keyboard
from together import Together
from gtts import gTTS
import pygame

# Load environment variables from .env file
load_dotenv()

# Set up Together.ai API client
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
if not TOGETHER_API_KEY:
    raise ValueError("No Together.ai API key found. Please set the TOGETHER_API_KEY environment variable.")

# Initialize Together.ai client
together_client = Together(api_key=TOGETHER_API_KEY)

# Default model
DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"

# Global variables
is_listening = False
recognizer = sr.Recognizer()
pending_action = None  # Store pending action that needs confirmation
last_interaction_time = None  # Track last user interaction

# Enhanced memory structure
memory = {
    "long_term": {
        "facts": [],  # General facts about the user
        "preferences": {},  # User preferences and habits
        "events": [],  # Past and future events
        "reminders": [],  # Active and completed reminders
        "conversations": []  # Historical conversations
    },
    "contextual": {
        "recent_conversations": [],  # Last 7 days of conversations
        "active_context": [],  # Current conversation context
        "relevant_facts": [],  # Facts relevant to current conversation
        "upcoming_events": [],  # Events in next 24 hours
        "active_reminders": []  # Active reminders
    }
}

# Memory management constants
CONTEXT_WINDOW_DAYS = 7  # How long to keep contextual memory
LONG_TERM_WINDOW_DAYS = 365  # How long to keep long-term memory
MAX_CONTEXT_CONVERSATIONS = 50  # Maximum number of recent conversations to keep
MAX_ACTIVE_CONTEXT = 10  # Maximum number of items in active context

# Constants for automatic turn initiation
TURN_TIMEOUT = 300  # 5 minutes in seconds
IMPORTANT_UPDATE_THRESHOLD = 1800  # 30 minutes in seconds

# Get the current directory for storing memory
current_dir = os.path.dirname(os.path.abspath(__file__))
memory_file = os.path.join(current_dir, "memory.json")
print(f"Memory will be saved to: {memory_file}")

# System prompt for the LLM
SYSTEM_PROMPT = """You are a helpful voice assistant that helps users manage their life by remembering things, setting reminders, and keeping track of events. You have access to both long-term and contextual memory.

Current time context:
- Current date and time: {current_time}
- Current timezone: {timezone}

Your responses should be in JSON format with the following structure:
{{
    "action": "action_name",
    "message": "your response message",
    "data": {{  # Optional, only include if needed for the action
        "key": "value"
    }}
}}

Available actions:
1. set_reminder: Set a new reminder or event
   {{
       "action": "set_reminder",
       "message": "I'll set a reminder for [message] at [time]",
       "data": {{
           "message": "reminder message",
           "suggested_time": "YYYY-MM-DD HH:MM:SS",
           "type": "reminder" or "event"
       }}
   }}

2. read_back_reminders: Read back active reminders
   {{
       "action": "read_back_reminders",
       "message": "Here are your active reminders: [list of reminders]"
   }}

3. clear_reminders: Clear all active reminders
   {{
       "action": "clear_reminders",
       "message": "I've cleared all your active reminders",
       "needs_confirmation": true
   }}

4. clear_all_memory: Clear all memory (reminders, events, facts)
   {{
       "action": "clear_all_memory",
       "message": "I've cleared all memory",
       "needs_confirmation": true
   }}

5. remember_fact: Store a new fact about the user
   {{
       "action": "remember_fact",
       "message": "I've noted that [fact]",
       "data": {{
           "content": "fact content",
           "category": "fact category"
       }}
   }}

6. query_memory: Answer a question based on memory
   {{
       "action": "query_memory",
       "message": "Based on my records, [answer]",
       "data": {{
           "response": "detailed answer"
       }}
   }}

7. general_query: Handle general questions or statements
   {{
       "action": "general_query",
       "message": "your response message",
       "data": {{
           "response": "detailed response"
       }}
   }}

Important rules for time handling:
1. When setting reminders or events:
   - For relative times (e.g., "in 2 minutes", "tomorrow at 3 PM"):
     - ALWAYS calculate from the current time: {current_time}
     - For "in X minutes/hours", add exactly that duration to current time
     - For "tomorrow", add exactly 24 hours to current date
   - For absolute times (e.g., "April 2nd at 2:21 AM"):
     - Use the exact specified time
     - If no year is specified, use current year
     - If time has already passed today, schedule for next occurrence
2. Always include the full datetime in YYYY-MM-DD HH:MM:SS format
3. Double-check time calculations to ensure accuracy
4. For relative times, explicitly state the calculated absolute time in your response

Example time calculations:
- Current time: 2024-04-02 02:19:00
- "in 2 minutes" → 2024-04-02 02:21:00
- "tomorrow at 3 PM" → 2024-04-03 15:00:00
- "April 2nd at 2:21 AM" → 2024-04-02 02:21:00

Your responses should be natural and conversational while maintaining the required JSON structure. Always verify time calculations before setting reminders or events."""

def get_system_prompt():
    """Get the system prompt with current time context"""
    current_time = datetime.datetime.now()
    timezone = datetime.datetime.now().astimezone().tzinfo.tzname(None)
    return SYSTEM_PROMPT.format(
        current_time=current_time.strftime("%Y-%m-%d %H:%M:%S"),
        timezone=timezone
    )

def load_memory():
    global memory
    try:
        if os.path.exists(memory_file):
            with open(memory_file, 'r') as f:
                loaded_memory = json.load(f)
                # Handle legacy memory format
                if "reminders" in loaded_memory and "facts" in loaded_memory:
                    memory["long_term"]["reminders"] = loaded_memory.get("reminders", [])
                    memory["long_term"]["facts"] = loaded_memory.get("facts", [])
                    memory["long_term"]["events"] = loaded_memory.get("events", [])
                    memory["long_term"]["preferences"] = loaded_memory.get("preferences", {})
                    memory["long_term"]["conversations"] = loaded_memory.get("conversations", [])
                else:
                    memory = loaded_memory
                print(f"Loaded memory from {memory_file}")
                print(f"Found {len(memory['long_term']['reminders'])} reminders, {len(memory['long_term']['facts'])} facts")
        else:
            print(f"No existing memory file found at {memory_file}, starting fresh")
    except Exception as e:
        print(f"Error loading memory from {memory_file}: {e}")

def save_memory():
    try:
        with open(memory_file, 'w') as f:
            json.dump(memory, f, indent=2)
        print(f"Saved memory to {memory_file}")
    except Exception as e:
        print(f"Error saving memory to {memory_file}: {e}")

def update_intent_display():
    """Update the intent display with current context"""
    try:
        now = datetime.datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # Get upcoming reminders
        upcoming = []
        for r in memory["long_term"]["reminders"]:
            if r.get("status") == "active":
                try:
                    reminder_time = datetime.datetime.strptime(r["datetime"], "%Y-%m-%d %H:%M:%S")
                    if reminder_time > now:
                        upcoming.append(r)
                except ValueError:
                    print(f"Invalid datetime format in reminder: {r}")
                    continue
        
        upcoming.sort(key=lambda x: x["datetime"])
        
        # Get recent facts
        recent_facts = memory["long_term"]["facts"][-3:] if memory["long_term"]["facts"] else []
        
        # Get recent events
        recent_events = memory["long_term"]["events"][-3:] if memory["long_term"]["events"] else []
        
        # Create intent display
        intent_display = "\n=== Intent Display ===\n"
        intent_display += f"Current time: {current_time}\n\n"
        
        if upcoming:
            intent_display += "Upcoming Reminders:\n"
            for r in upcoming[:3]:
                intent_display += f"- {r['message'][:30]}... ({r['datetime']})\n"
            if len(upcoming) > 3:
                intent_display += f"... and {len(upcoming)-3} more\n"
        
        if recent_facts:
            intent_display += "\nRecent Facts:\n"
            for f in recent_facts:
                intent_display += f"- {f['content'][:30]}...\n"
        
        if recent_events:
            intent_display += "\nRecent Events:\n"
            for e in recent_events:
                intent_display += f"- {e['description'][:30]}... ({e['datetime']})\n"
        
        intent_display += "\n=== End Display ===\n"
        print(intent_display)
        
    except Exception as e:
        print(f"Error updating intent display: {e}")

def show_notification(title, message, timeout=5):
    """Show a notification using the most reliable method for the platform"""
    print(f"\n[NOTIFICATION] {title}: {message}")
    
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(["which", "terminal-notifier"], 
                                 capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                subprocess.run([
                    "terminal-notifier",
                    "-title", title,
                    "-message", message,
                    "-sound", "default"
                ], check=False)
                return
                
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], 
                         capture_output=True, check=False)
            
        except Exception as e:
            print(f"Notification error: {e}")

def on_press(key):
    global is_listening
    try:
        # F12 for voice input
        if key == keyboard.Key.f12:
            if not is_listening:  # Only start listening if not already listening
                print("Listening... (Speak now)")
                threading.Thread(target=listen_and_process).start()
        # F11 to update intent display
        elif key == keyboard.Key.f11:
            update_intent_display()
        # F10 to show weekly calendar
        elif key == keyboard.Key.f10:
            display_weekly_calendar()
    except AttributeError:
        pass

def should_initiate_turn():
    """Determine if the assistant should initiate a turn"""
    global last_interaction_time
    
    if last_interaction_time is None:
        return True
        
    now = datetime.datetime.now()
    time_since_last_interaction = (now - last_interaction_time).total_seconds()
    
    # Check for important updates
    if time_since_last_interaction >= IMPORTANT_UPDATE_THRESHOLD:
        return True
        
    # Check for general timeout
    if time_since_last_interaction >= TURN_TIMEOUT:
        return True
        
    return False

def initiate_turn():
    """Initiate a turn with the user based on context"""
    try:
        now = datetime.datetime.now()
        
        # Check for upcoming reminders
        upcoming_reminders = []
        for r in memory["long_term"]["reminders"]:
            if r.get("status") == "active":
                reminder_time = datetime.datetime.strptime(r["datetime"], "%Y-%m-%d %H:%M:%S")
                if reminder_time > now:
                    time_diff = (reminder_time - now).total_seconds()
                    if time_diff <= 3600:  # Within next hour
                        upcoming_reminders.append(r)
        
        # Check for recent events
        recent_events = []
        for e in memory["long_term"]["events"]:
            event_time = datetime.datetime.strptime(e["datetime"], "%Y-%m-%d %H:%M:%S")
            if event_time > now:
                time_diff = (event_time - now).total_seconds()
                if time_diff <= 3600:  # Within next hour
                    recent_events.append(e)
        
        # Prepare context-aware message
        if upcoming_reminders:
            reminder_text = " and ".join([f"{r['message']} at {format_datetime(r['datetime'])}" 
                                        for r in upcoming_reminders])
            speak(f"Sir, I wanted to remind you about {reminder_text}")
            
        elif recent_events:
            event_text = " and ".join([f"{e['description']} at {format_datetime(e['datetime'])}" 
                                     for e in recent_events])
            speak(f"Sir, you have upcoming events: {event_text}")
            
        elif should_initiate_turn():
            # If no immediate reminders/events, provide a general status update
            memory_summary = get_memory_summary()
            if memory_summary != "No active memories":
                speak(f"Sir, {memory_summary}. Is there anything you need help with?")
            else:
                speak("Sir, I'm here if you need anything. How can I assist you?")
        
        # Start listening automatically after speaking
        if not is_listening:  # Only start listening if not already listening
            print("Listening for your response...")
            threading.Thread(target=listen_and_process).start()
        
    except Exception as e:
        print(f"Error initiating turn: {e}")

def listen_and_process():
    global is_listening, last_interaction_time
    if is_listening:  # Prevent multiple simultaneous listening attempts
        return
        
    is_listening = True
    with sr.Microphone() as source:
        try:
            print("Listening... (Speak now)")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=5)
            print("Processing...")
            
            text = recognizer.recognize_google(audio)
            print(f"You said: {text}")
            
            # Update last interaction time
            last_interaction_time = datetime.datetime.now()
            
            process_with_llm(text)
            
        except sr.WaitTimeoutError:
            print("No speech detected")
        except sr.UnknownValueError:
            print("Could not understand audio")
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            is_listening = False

def process_with_llm(text):
    current_time = datetime.datetime.now()
    current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Create context from both long-term and contextual memory
    context = {
        "current_time": current_time_str,
        "long_term": {
            "reminders": memory["long_term"]["reminders"],
            "facts": memory["long_term"]["facts"][-5:],
            "events": memory["long_term"]["events"][-5:],
            "conversations": memory["long_term"]["conversations"][-5:]
        },
        "contextual": {
            "recent_conversations": memory["contextual"]["recent_conversations"],
            "relevant_facts": memory["contextual"]["relevant_facts"],
            "upcoming_events": memory["contextual"]["upcoming_events"],
            "active_reminders": memory["contextual"]["active_reminders"]
        }
    }
    
    system_prompt = get_system_prompt()
    
    user_prompt = f"""Current Context:
{json.dumps(context, indent=2)}

User message: "{text}"

Provide a response in this JSON format:

If it's a reminder or event:
{{
    "action": "set_reminder",
    "message": "I'll set a reminder for [message] at [time]",
    "data": {{
        "message": "The complete reminder message",
        "suggested_time": "YYYY-MM-DD HH:MM:SS format",
        "type": "reminder" or "event",
        "needs_confirmation": true/false,
        "confirmation_message": "Message to ask for confirmation if needed"
    }}
}}

If it's a fact to remember:
{{
    "action": "remember_fact",
    "message": "I'll remember that [fact]",
    "data": {{
        "content": "The fact to remember",
        "category": "personal", "preference", "habit", etc.
    }}
}}

If it's clearing reminders:
{{
    "action": "clear_reminders",
    "message": "I'll clear all your active reminders",
    "needs_confirmation": true,
    "confirmation_message": "I found X active reminders. Would you like me to clear them all?"
}}

If it's reading back reminders:
{{
    "action": "read_back_reminders",
    "message": "Here are your active reminders: [list of reminders]"
}}

If it's a question about past events or facts:
{{
    "action": "query_memory",
    "message": "Based on my records, [answer]",
    "data": {{
        "response": "Your answer based on available context"
    }}
}}

If it's a general query:
{{
    "action": "general_query",
    "message": "Your brief, relevant response",
    "data": {{
        "response": "Your detailed response"
    }}
}}

Important:
1. For reminders, always include both the top-level "message" and the "message" field in the "data" object
2. The top-level "message" should be a natural confirmation of what you're doing
3. The "data.message" should contain the actual reminder text
4. Always include all required fields in the correct structure
5. Return only the JSON object, nothing else."""
    
    try:
        completion = together_client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        response_text = completion.choices[0].message.content
        print(f"LLM Response: {response_text}")  # Debug log
        
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > 0:
                json_str = response_text[start_idx:end_idx]
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON from response: {json_str}")
                    return
            else:
                print(f"Could not find JSON in response: {response_text}")
                return
        
        if not isinstance(result, dict) or "action" not in result:
            print(f"Invalid response format: {result}")
            return
            
        handle_action(result, text)
        
    except Exception as e:
        print(f"Error processing with LLM: {e}")

def speak(text):
    """Speak the given text using Google Text-to-Speech"""
    try:
        # Initialize pygame mixer with specific device
        pygame.mixer.quit()  # Ensure mixer is clean
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        
        # Create a temporary file for the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            temp_filename = fp.name
        
        # Generate speech using gTTS
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(temp_filename)
        
        # Load and play the audio
        pygame.mixer.music.load(temp_filename)
        pygame.mixer.music.play()
        
        # Wait for the audio to finish playing
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        
        # Clean up
        pygame.mixer.quit()
        os.unlink(temp_filename)
        
        # Add a small delay after speaking to ensure the audio is fully played
        time.sleep(0.5)
        
    except Exception as e:
        print(f"Error in speech: {e}")
        print(f"Text to speak: {text}")
        # Try fallback to say command if pygame fails
        try:
            escaped_text = text.replace('"', '\\"').replace("'", "\\'")
            subprocess.run(['say', '-v', 'Alex', escaped_text], check=False)
        except Exception as e2:
            print(f"Error in fallback speech: {e2}")

def format_datetime(datetime_str):
    """Format datetime string to be more natural in speech"""
    try:
        dt = datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%B %d at %I:%M %p")
    except:
        return datetime_str

def get_memory_summary():
    """Get a brief summary of relevant memories"""
    summary = []
    
    # Get active reminders
    active_reminders = [r for r in memory["long_term"]["reminders"] if r.get("status") == "active"]
    if active_reminders:
        summary.append(f"You have {len(active_reminders)} active reminder{'s' if len(active_reminders) > 1 else ''}")
    
    # Get recent facts
    recent_facts = memory["long_term"]["facts"][-3:] if memory["long_term"]["facts"] else []
    if recent_facts:
        summary.append(f"You've shared {len(recent_facts)} recent fact{'s' if len(recent_facts) > 1 else ''}")
    
    # Get upcoming events
    upcoming_events = [e for e in memory["long_term"]["events"] 
                      if datetime.datetime.strptime(e["datetime"], "%Y-%m-%d %H:%M:%S") > datetime.datetime.now()]
    if upcoming_events:
        summary.append(f"You have {len(upcoming_events)} upcoming event{'s' if len(upcoming_events) > 1 else ''}")
    
    return " and ".join(summary) if summary else "No active memories"

def clear_reminders():
    """Clear all active reminders with confirmation"""
    active_reminders = [r for r in memory["long_term"]["reminders"] if r.get("status") == "active"]
    if not active_reminders:
        return "You don't have any active reminders to clear."
    
    # Mark all active reminders as completed
    for reminder in active_reminders:
        reminder["status"] = "completed"
        reminder["completed_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    save_memory()
    update_intent_display()
    return f"I've cleared {len(active_reminders)} active reminder{'s' if len(active_reminders) > 1 else ''}."

def clean_memory():
    """Clean up memory by removing old data"""
    try:
        now = datetime.datetime.now()
        
        # Clean up long-term memory
        memory["long_term"]["reminders"] = [
            r for r in memory["long_term"]["reminders"]
            if r.get("status") == "active" or
            (r.get("completed_at") and
             (now - datetime.datetime.strptime(r["completed_at"], "%Y-%m-%d %H:%M:%S")).days < LONG_TERM_WINDOW_DAYS)
        ]
        
        memory["long_term"]["events"] = [
            e for e in memory["long_term"]["events"]
            if (now - datetime.datetime.strptime(e["datetime"], "%Y-%m-%d %H:%M:%S")).days < LONG_TERM_WINDOW_DAYS
        ]
        
        memory["long_term"]["facts"] = [
            f for f in memory["long_term"]["facts"]
            if (now - datetime.datetime.strptime(f["timestamp"], "%Y-%m-%d %H:%M:%S")).days < LONG_TERM_WINDOW_DAYS
        ]
        
        memory["long_term"]["conversations"] = [
            c for c in memory["long_term"]["conversations"]
            if (now - datetime.datetime.strptime(c["timestamp"], "%Y-%m-%d %H:%M:%S")).days < LONG_TERM_WINDOW_DAYS
        ]
        
        # Remove duplicate facts
        seen_facts = set()
        unique_facts = []
        for fact in memory["long_term"]["facts"]:
            content = fact["content"].lower().strip()
            if content not in seen_facts:
                seen_facts.add(content)
                unique_facts.append(fact)
        memory["long_term"]["facts"] = unique_facts
        
        # Update contextual memory
        update_contextual_memory()
        
        save_memory()
        print("Memory cleaned up successfully")
        
    except Exception as e:
        print(f"Error cleaning memory: {e}")

def clear_all_memory():
    """Clear all memory data"""
    try:
        memory["long_term"]["reminders"] = []
        memory["long_term"]["facts"] = []
        memory["long_term"]["events"] = []
        memory["long_term"]["preferences"] = {}
        memory["long_term"]["conversations"] = []
        save_memory()
        return "I've cleared all your memories. We're starting fresh."
    except Exception as e:
        print(f"Error clearing memory: {e}")
        return "I encountered an error while clearing your memories."

def handle_action(action_data, original_text):
    global pending_action, is_listening
    try:
        # Store conversation for context
        memory["long_term"]["conversations"].append({
            "text": original_text,
            "action": action_data["action"],
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Update contextual memory
        update_contextual_memory()
        
        # Get memory summary
        memory_summary = get_memory_summary()
        print(f"\nMemory Context: {memory_summary}")
        
        # Display relevant memories and calendar
        display_relevant_memories()
        display_weekly_calendar()
        
        # Handle confirmation if there's a pending action
        if pending_action and "yes" in original_text.lower():
            if pending_action["action"] == "clear_reminders":
                response = clear_reminders()
                print(f"Response: {response}")
                speak(response)
                show_notification(
                    title="Reminders Cleared",
                    message=response,
                    timeout=5
                )
            elif pending_action["action"] == "clear_all_memory":
                response = clear_all_memory()
                print(f"Response: {response}")
                speak(response)
                show_notification(
                    title="Memory Cleared",
                    message=response,
                    timeout=5
                )
            elif pending_action["action"] == "set_reminder":
                # Handle the pending reminder
                reminder_data = pending_action["data"]
                if reminder_data["type"] == "event":
                    memory["long_term"]["events"].append({
                        "description": reminder_data["message"],
                        "datetime": reminder_data["suggested_time"],
                        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    response = f"I've added the event: {reminder_data['message']} for {format_datetime(reminder_data['suggested_time'])}"
                else:
                    memory["long_term"]["reminders"].append({
                        "message": reminder_data["message"],
                        "datetime": reminder_data["suggested_time"],
                        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "active"
                    })
                    response = f"I've set a reminder for {reminder_data['message']} at {format_datetime(reminder_data['suggested_time'])}"
                
                print(f"Response: {response}")
                speak(response)
                save_memory()
                show_notification(
                    title="Memory Updated",
                    message=f"Added {reminder_data['type']}: {reminder_data['message'][:50]}...",
                    timeout=5
                )
            
            pending_action = None
            # Start listening after confirmation
            is_listening = True
            return
            
        # Handle new actions
        if action_data["action"] == "read_back_reminders":
            active_reminders = [r for r in memory["long_term"]["reminders"] if r.get("status") == "active"]
            if not active_reminders:
                response = "You don't have any active reminders at the moment."
            else:
                # Sort reminders by time
                active_reminders.sort(key=lambda x: x["datetime"])
                # Create a natural summary
                reminder_list = []
                for r in active_reminders:
                    reminder_list.append(f"{r['message']} at {format_datetime(r['datetime'])}")
                response = f"Here are your active reminders: {'; '.join(reminder_list)}"
            
            print(f"Response: {response}")
            speak(response)
            show_notification(
                title="Active Reminders",
                message=response,
                timeout=10
            )
            # Start listening after reading reminders
            is_listening = True
            return
            
        elif action_data["action"] == "clear_reminders":
            active_reminders = [r for r in memory["long_term"]["reminders"] if r.get("status") == "active"]
            if not active_reminders:
                response = "You don't have any active reminders to clear."
                print(f"Response: {response}")
                speak(response)
                return
                
            if action_data.get("needs_confirmation", False):
                pending_action = action_data
                response = f"I found {len(active_reminders)} active reminder{'s' if len(active_reminders) > 1 else ''}. Would you like me to clear {'them' if len(active_reminders) > 1 else 'it'}?"
                print(f"Response: {response}")
                speak(response)
                return
            else:
                response = clear_reminders()
                print(f"Response: {response}")
                speak(response)
                show_notification(
                    title="Reminders Cleared",
                    message=response,
                    timeout=5
                )
            return
            
        elif action_data["action"] == "clear_all_memory":
            if action_data.get("needs_confirmation", False):
                pending_action = action_data
                response = "I found several items in your memory. Would you like me to clear everything? This will remove all reminders, events, facts, and conversation history."
                print(f"Response: {response}")
                speak(response)
                return
            else:
                response = clear_all_memory()
                print(f"Response: {response}")
                speak(response)
                show_notification(
                    title="Memory Cleared",
                    message=response,
                    timeout=5
                )
            return
            
        if action_data["action"] == "set_reminder":
            # Extract reminder data from the nested structure
            reminder_data = action_data.get("data", {})
            if not reminder_data or "message" not in reminder_data or "suggested_time" not in reminder_data:
                print(f"Invalid reminder data: {action_data}")
                return
                
            # Ask for confirmation if the time is ambiguous
            reminder_time = datetime.datetime.strptime(reminder_data["suggested_time"], "%Y-%m-%d %H:%M:%S")
            if reminder_time < datetime.datetime.now():
                response = f"I notice this time has already passed. Would you like me to set this for tomorrow instead?"
                print(f"Response: {response}")
                speak(response)
                pending_action = {
                    "action": "set_reminder",
                    "data": reminder_data,
                    "confirmation_message": response
                }
                return
                
            if reminder_data.get("needs_confirmation", False):
                pending_action = {
                    "action": "set_reminder",
                    "data": reminder_data,
                    "confirmation_message": reminder_data.get("confirmation_message", "Would you like me to set this reminder?")
                }
                response = pending_action["confirmation_message"]
                print(f"Response: {response}")
                speak(response)
                return
                
            if reminder_data["type"] == "event":
                # Check for duplicate events
                for event in memory["long_term"]["events"]:
                    if (event["description"].lower() == reminder_data["message"].lower() and 
                        event["datetime"] == reminder_data["suggested_time"]):
                        response = f"I notice you already have this event scheduled. Would you like me to update it instead?"
                        print(f"Response: {response}")
                        speak(response)
                        return
                
                memory["long_term"]["events"].append({
                    "description": reminder_data["message"],
                    "datetime": reminder_data["suggested_time"],
                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                response = f"I've added the event: {reminder_data['message']} for {format_datetime(reminder_data['suggested_time'])}"
            else:
                # Check for duplicate reminders
                for reminder in memory["long_term"]["reminders"]:
                    if (reminder["message"].lower() == reminder_data["message"].lower() and 
                        reminder["datetime"] == reminder_data["suggested_time"]):
                        response = f"I notice you already have this reminder set. Would you like me to update it instead?"
                        print(f"Response: {response}")
                        speak(response)
                        return
                
                memory["long_term"]["reminders"].append({
                    "message": reminder_data["message"],
                    "datetime": reminder_data["suggested_time"],
                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "active"
                })
                response = f"I've set a reminder for {reminder_data['message']} at {format_datetime(reminder_data['suggested_time'])}"
            
            print(f"Response: {response}")
            speak(response)
            save_memory()
            show_notification(
                title="Memory Updated",
                message=f"Added {reminder_data['type']}: {reminder_data['message'][:50]}...",
                timeout=5
            )
        
        elif action_data["action"] == "remember_fact":
            if "content" not in action_data or "category" not in action_data:
                print(f"Invalid fact data: {action_data}")
                return
                
            # Check for similar facts
            content = action_data["content"].lower().strip()
            for fact in memory["long_term"]["facts"]:
                if fact["content"].lower().strip() == content:
                    response = f"I already know that {action_data['content']}. Would you like me to update it with any new information?"
                    print(f"Response: {response}")
                    speak(response)
                    return
            
            memory["long_term"]["facts"].append({
                "content": action_data["content"],
                "category": action_data["category"],
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            response = f"I've noted that {action_data['content']}"
            print(f"Response: {response}")
            speak(response)
            save_memory()
            show_notification(
                title="Memory Updated",
                message=f"Remembered: {action_data['content'][:50]}...",
                timeout=5
            )
        
        elif action_data["action"] == "query_memory":
            if "response" not in action_data:
                print(f"Invalid query response: {action_data}")
                return
                
            response = f"Based on my records, {action_data['response']}"
            print(f"Response: {response}")
            speak(response)
            show_notification(
                title="Memory Query",
                message=action_data["response"],
                timeout=10
            )
        
        elif action_data["action"] == "general_query":
            if "response" not in action_data:
                print(f"Invalid general query response: {action_data}")
                return
                
            response = action_data["response"]
            print(f"Response: {response}")
            speak(response)
            show_notification(
                title="Assistant Response",
                message=action_data["response"],
                timeout=10
            )
        
        # Clean up memory after each action
        clean_memory()
        
        # Update intent display after each action
        update_intent_display()
        
        # Start listening after handling any action
        is_listening = True
        
    except Exception as e:
        print(f"Error handling action: {e}")
        # Start listening even if there's an error
        is_listening = True

def check_reminders():
    """Check for upcoming reminders and notify the user"""
    while True:
        try:
            now = datetime.datetime.now()
            
            # Check for upcoming reminders
            upcoming_reminders = []
            for reminder in memory["long_term"]["reminders"][:]:
                if reminder.get("status") != "active":
                    continue
                    
                reminder_time = datetime.datetime.strptime(reminder["datetime"], "%Y-%m-%d %H:%M:%S")
                
                # If reminder time has passed, mark it as completed
                if reminder_time < now:
                    reminder["status"] = "completed"
                    reminder["completed_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    continue
                
                # Check if reminder is within next 5 minutes
                if 0 < (reminder_time - now).total_seconds() <= 300:  # 5 minutes
                    upcoming_reminders.append(reminder)
            
            # Notify about upcoming reminders
            if upcoming_reminders:
                for reminder in upcoming_reminders:
                    message = f"Reminder: {reminder['message']}"
                    print(f"\n{message}")
                    speak(message)
                    show_notification(
                        title="Upcoming Reminder",
                        message=message,
                        timeout=10
                    )
            
            time.sleep(30)
            
        except Exception as e:
            print(f"Error checking reminders: {e}")
            time.sleep(30)

def display_weekly_calendar():
    """Display a simple weekly calendar in the terminal"""
    try:
        now = datetime.datetime.now()
        start_of_week = now - datetime.timedelta(days=now.weekday())
        end_of_week = start_of_week + datetime.timedelta(days=6, hours=23, minutes=59)
        
        # Get all events and reminders for the week
        weekly_items = []
        
        # Add events
        for event in memory["long_term"]["events"]:
            event_time = datetime.datetime.strptime(event["datetime"], "%Y-%m-%d %H:%M:%S")
            if start_of_week <= event_time <= end_of_week:
                weekly_items.append({
                    "time": event_time,
                    "text": f"Event: {event['description']}",
                    "type": "event"
                })
        
        # Add active reminders
        for reminder in memory["long_term"]["reminders"]:
            if reminder.get("status") == "active":
                reminder_time = datetime.datetime.strptime(reminder["datetime"], "%Y-%m-%d %H:%M:%S")
                if start_of_week <= reminder_time <= end_of_week:
                    weekly_items.append({
                        "time": reminder_time,
                        "text": f"Reminder: {reminder['message']}",
                        "type": "reminder"
                    })
        
        # Sort items by time
        weekly_items.sort(key=lambda x: x["time"])
        
        # Create calendar display
        print("\n=== Weekly Calendar ===")
        print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Week of: {start_of_week.strftime('%B %d, %Y')}")
        print("\nUpcoming events and reminders:")
        
        if not weekly_items:
            print("No events or reminders scheduled for this week.")
        else:
            for item in weekly_items:
                time_str = item["time"].strftime("%a %B %d at %I:%M %p")
                print(f"• {time_str}: {item['text']}")
        
        # Display completed reminders from the past week
        completed_reminders = [
            r for r in memory["long_term"]["reminders"]
            if r.get("status") == "completed" and
            start_of_week <= datetime.datetime.strptime(r["completed_at"], "%Y-%m-%d %H:%M:%S") <= end_of_week
        ]
        
        if completed_reminders:
            print("\nCompleted reminders from this week:")
            for reminder in completed_reminders:
                completed_time = datetime.datetime.strptime(reminder["completed_at"], "%Y-%m-%d %H:%M:%S")
                time_str = completed_time.strftime("%a %B %d at %I:%M %p")
                print(f"• {time_str}: {reminder['message']}")
        
        print("\n=== End Calendar ===\n")
        
    except Exception as e:
        print(f"Error displaying calendar: {e}")

def update_contextual_memory():
    """Update contextual memory based on current state"""
    try:
        now = datetime.datetime.now()
        
        # Update recent conversations
        memory["contextual"]["recent_conversations"] = [
            conv for conv in memory["long_term"]["conversations"]
            if (now - datetime.datetime.strptime(conv["timestamp"], "%Y-%m-%d %H:%M:%S")).days <= CONTEXT_WINDOW_DAYS
        ][-MAX_CONTEXT_CONVERSATIONS:]
        
        # Update upcoming events
        memory["contextual"]["upcoming_events"] = [
            event for event in memory["long_term"]["events"]
            if (datetime.datetime.strptime(event["datetime"], "%Y-%m-%d %H:%M:%S") - now).total_seconds() <= 86400  # 24 hours
        ]
        
        # Update active reminders
        memory["contextual"]["active_reminders"] = [
            reminder for reminder in memory["long_term"]["reminders"]
            if reminder.get("status") == "active"
        ]
        
        # Update relevant facts based on recent conversations
        recent_topics = set()
        for conv in memory["contextual"]["recent_conversations"][-5:]:  # Last 5 conversations
            # Extract topics from conversation text
            words = conv["text"].lower().split()
            recent_topics.update(words)
        
        # Find facts related to recent topics
        memory["contextual"]["relevant_facts"] = [
            fact for fact in memory["long_term"]["facts"]
            if any(topic in fact["content"].lower() for topic in recent_topics)
        ][:MAX_ACTIVE_CONTEXT]
        
    except Exception as e:
        print(f"Error updating contextual memory: {e}")

def display_relevant_memories():
    """Display memories relevant to the current context"""
    try:
        print("\n=== Relevant Memories ===")
        
        if memory["contextual"]["relevant_facts"]:
            print("\nRelated Facts:")
            for fact in memory["contextual"]["relevant_facts"]:
                print(f"• {fact['content']}")
        
        if memory["contextual"]["upcoming_events"]:
            print("\nUpcoming Events (Next 24 Hours):")
            for event in memory["contextual"]["upcoming_events"]:
                time_str = format_datetime(event["datetime"])
                print(f"• {time_str}: {event['description']}")
        
        if memory["contextual"]["active_reminders"]:
            print("\nActive Reminders:")
            for reminder in memory["contextual"]["active_reminders"]:
                time_str = format_datetime(reminder["datetime"])
                print(f"• {time_str}: {reminder['message']}")
        
        print("\n=== End Memories ===\n")
        
    except Exception as e:
        print(f"Error displaying relevant memories: {e}")

def main():
    load_memory()
    
    reminder_thread = threading.Thread(target=check_reminders, daemon=True)
    reminder_thread.start()
    
    print("Personal Assistant started.")
    print("F12: Activate voice input")
    print("F11: Update intent display")
    print("F10: Show weekly calendar")
    print("Make sure you've set your TOGETHER_API_KEY in the .env file.")
    
    # Initial intent display
    update_intent_display()
    display_weekly_calendar()
    display_relevant_memories()
    
    # Welcome message and initial turn
    speak("Hello, I'm your personal assistant. How can I help you today? Press F12 anytime to speak with me.")
    last_interaction_time = datetime.datetime.now()
    
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

if __name__ == "__main__":
    main() 