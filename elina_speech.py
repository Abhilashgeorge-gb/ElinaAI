import speech_recognition as sr
import requests
import platform
from fuzzywuzzy import fuzz
import openai
import pyaudio
import wave
from datetime import datetime
import time
import re
import threading
import random
import os
import json
from gtts import gTTS
from dotenv import load_dotenv
import openai
load_dotenv()

OPENAI_API_KEY = os.getenv("your API Key")
ELEVENLABS_API_KEY = "Your Eleven lab api key"


# Memory file
MEMORY_FILE = "memory.json"
if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f:
        json.dump([], f)  # Create an empty list if the file doesn't exist
MEMORY_DURATION = 60  # Number of days to store conversations

def save_to_memory(user_input):
    """Save conversations with timestamps to memory."""
    # Ensure memory file exists
    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w") as f:
            json.dump([], f)  # Create an empty list if the file doesn't exist

    # Load existing memory
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)

    # Append new input with a timestamp
    memory.append({
        "date": str(datetime.datetime.now()),
        "text": user_input
    })

    # Remove old memory beyond MEMORY_DURATION
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=MEMORY_DURATION)
    memory = [entry for entry in memory if datetime.datetime.fromisoformat(entry["date"]) > cutoff_date]

    # Save updated memory
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)


def recall_memory():
    """Retrieve recent memory and return key details."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)

    last_interactions = memory[-5:]  # Get last 5 interactions
    return last_interactions


def analyze_memory():
    """Check past memory and generate follow-up questions."""
    memory = recall_memory()
    follow_up = []

    for entry in memory:
        if "text" in entry:
            text = entry["text"].lower()
        else:
            continue  # Skip entries without "text" key

        if "sad" in text or "not feeling well" in text:
            follow_up.append("Last time you seemed sad. Are you feeling better today?")

        if "buy a bike" in text or "thinking of buying a bike" in text:
            follow_up.append("You mentioned wanting to buy a bike. Have you made any decisions?")

        if "learning python" in text or "want to learn coding" in text:
            follow_up.append("You wanted to learn Python. How is your progress going?")

    return follow_up


def record_audio(filename="speech.wav", duration=5):
    """Records audio from the microphone."""
    import pyaudio
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = 1024

    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, input=True,
                        frames_per_buffer=CHUNK)

    print("Listening...")
    frames = []

    for _ in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)

    print("Recording complete.")
    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))


def transcribe_audio_whisper(filename="speech.wav"):
    """Uses OpenAI's Whisper to transcribe audio with high accuracy."""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    with open(filename, "rb") as f:
        response = requests.post("https://api.openai.com/v1/audio/transcriptions",
                                 headers=headers,
                                 files={"file": f})

    if response.status_code == 200:
        return response.json()["text"].lower()
    else:
        print("Whisper API error:", response.json())
        return None

def speak(text):
    """Convert text to speech using ElevenLabs AI Voice."""
    url = "https://api.elevenlabs.io/v1/text-to-speech/API Key"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    data = {"text": text, "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}

    response = requests.post(url, json=data, headers=headers)

    """Convert text to speech using Google TTS as a backup."""
    tts = gTTS(text=text, lang='en')
    tts.save("elina_voice.mp3")
    print("Audio saved as 'elina_voice.mp3'.")
    os.system("start elina_voice.mp3")  # Use this for Windows

    if response.status_code == 200:
        audio_file = "elina_voice.mp3"
        with open(audio_file, "wb") as f:
            f.write(response.content)

        print("Audio saved as 'elina_voice.mp3'.")

        # Play audio based on OS
        import platform
        os_name = platform.system()
        if os_name == "Windows":
            os.system(f'start {audio_file}')
        elif os_name == "Darwin":
            os.system(f'afplay {audio_file}')
        elif os_name == "Linux":
            os.system(f'mpg321 {audio_file} || aplay {audio_file}')
    else:
        print("Error:", response.json())


def is_called(command):
    """Check if ELINA is mentioned using direct and fuzzy matching."""
    # Direct keyword matching
    keywords = ["elina", "alina", "elena", "elaina"]  # Possible variations
    if any(keyword in command.lower() for keyword in keywords):
        return True

    # Fuzzy matching for names with slight variations
    for keyword in keywords:
        if fuzz.ratio(command.lower(), keyword) > 70:  # Adjust similarity as needed
            return True

    return False

def get_own_nickname():
    """Retrieve ELINA's nickname from memory."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)
    for entry in memory:
        if "elina_nickname" in entry:
            return entry["elina_nickname"]
    return "Elina"  # Default name if no nickname is set

def set_own_nickname(nickname):
    """Store or update ELINA's nickname in memory."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)

    # Remove existing nickname if present
    memory = [entry for entry in memory if "elina_nickname" not in entry]
    memory.append({"elina_nickname": nickname})

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

def handle_nickname_command(command):
    """Process commands related to setting ELINA's nickname."""
    import re

    # Check for setting a nickname
    nickname_match = re.search(r"(call you|your nickname is) ([\w\s]+)", command)
    if nickname_match:
        nickname = nickname_match.group(2).strip()
        set_own_nickname(nickname)
        speak(f"Got it! You can call me {nickname} from now on.")
        return True

    return False

def listen():
    """Capture microphone input and convert to text with high accuracy."""
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("Listening for your input...")
        recognizer.adjust_for_ambient_noise(source, duration=1)  # Adapts to background noise
        try:
            audio = recognizer.listen(source, timeout=10)  # Allows longer speech inputs
            command = recognizer.recognize_google(audio).lower()  # Convert speech to text

            if is_called(command):
                print(f"You said: {command}")
                return command
            else:
                print("Ignoring unrelated conversation.")
                return None


        except sr.WaitTimeoutError:
            print("No speech detected. Try again.")
            return None
        except sr.UnknownValueError:
            print("I couldn't understand. Could you repeat that?")
            return None
        except sr.RequestError:
            print("There was an issue with the speech service.")
            return None


def get_girlfriend_name():
    """Retrieve the girlfriend's name from memory."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)
    for entry in memory:
        if "girlfriend_name" in entry:
            return entry["girlfriend_name"]
    return None


def set_girlfriend_name(name):
    """Store or update the girlfriend's name in memory."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)

    # Remove existing name if present
    memory = [entry for entry in memory if "girlfriend_name" not in entry]
    memory.append({"girlfriend_name": name})

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)


def process_command(command):
    """Handle commands and respond with ELINA's nickname if available."""
    print("Received command:", command)

    if handle_nickname_command(command):
        print("Handled nickname command.")
        return  # If a nickname was set, return early

    if handle_small_talk(command):
        print("Handled small talk.")
        return  # If small talk was handled, return early


    elina_nickname = get_own_nickname() or "Elina"  # Get current nickname
    command = command.lower()  # Convert command to lowercase for case-insensitive matching

    # GREETINGS HANDLING with Nickname
    greetings = [
        "hello", "hi", "hey", "hola", "bonjour", "namaste", "mahal",
        "what's up", "howdy", "greetings", "yo", "sup", "good morning",
        "good evening", "good afternoon"
    ]

    greeting_responses = [
        f"Hey {elina_nickname}! How’s your day going?",
        f"Hello {elina_nickname}! It's always great to hear from you!",
        f"Hey {elina_nickname}! What’s on your mind today?",
        f"Good to hear from you, {elina_nickname}! What's new?",
        f"Hi {elina_nickname}! How can I make your day better?",
        f"Hola {elina_nickname}! What's up?",
        f"Bonjour {elina_nickname}! How's everything?",
        f"Namaste {elina_nickname}! Hope you're doing well."
    ]

    # Improved greeting detection using word boundaries
    if any(re.search(rf"\b{word}\b", command) for word in greetings):
        response = random.choice(greeting_responses)
        print("Greeting detected:", response)
        speak(response)
        return


    # Check for girlfriend introduction
    girlfriend_match = re.search(r"i have a girlfriend named ([\w\s]+)", command)
    if girlfriend_match:
        girlfriend_name = girlfriend_match.group(1).strip()
        set_girlfriend_name(girlfriend_name)  # Save the girlfriend's name
        speak(f"That's great news! It's wonderful to hear that you've got a girlfriend named {girlfriend_name}.")
        return

    # Check for girlfriend follow-up
    girlfriend_name = get_girlfriend_name()
    if girlfriend_name and ("my girlfriend" in command or girlfriend_name in command):
        speak(f"How are things going with {girlfriend_name}?")
        return
    elif girlfriend_name and ("i'm not happy" in command or "i'm not feeling well" in command):
        speak(f"I'm sorry to hear that. What can I do to help you feel better?")
        return
    elif girlfriend_name and ("i'm happy" in command or "i'm feeling well" in command):
        speak(f"That's awesome! I'm glad you're feeling well with {girlfriend_name}.")
        return

def set_relation(relation, name):
    """Store or update a family member or friend's name in memory."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)

    # Remove existing relation if present
    memory = [entry for entry in memory if relation not in entry]
    memory.append({relation: name})

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

def get_relation(relation):
    """Retrieve a family member or friend's name from memory."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)
    for entry in memory:
        if relation in entry:
            return entry[relation]
    return None

def set_event(event_name, event_date):
    """Store or update a special event date in memory."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)

    # Remove existing event if present
    memory = [entry for entry in memory if event_name not in entry]
    memory.append({event_name: event_date})

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

def get_upcoming_events():
    """Retrieve upcoming events within the next 7 days."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)

    upcoming_events = []
    today = datetime.now()
    for entry in memory:
        for event_name, event_date in entry.items():
            try:
                event_date_obj = datetime.strptime(event_date, "%Y-%m-%d")
                if 0 <= (event_date_obj - today).days <= 7:
                    upcoming_events.append((event_name, event_date_obj))
            except ValueError:
                continue  # Skip if date format is incorrect

    return upcoming_events

    """Make ELINA respond dynamically and naturally with family, friends, and events."""

    # Check for family or friend introduction
    family_match = re.search(r"my (father|mother|brother|sister|girlfriend|friend) is named ([\w\s]+)", command)
    if family_match:
        relation = family_match.group(1)
        name = family_match.group(2).strip()
        set_relation(relation, name)
        speak(f"Got it! I'll remember that your {relation} is named {name}.")
        return

    # Check for special event introduction
    event_match = re.search(r"(birthday|anniversary|valentine's day) is on (\d{1,2}(?:st|nd|rd|th)? \w+)", command)
    if event_match:
        event_name = event_match.group(1).lower()
        event_date_str = event_match.group(2)

        # Convert date to "YYYY-MM-DD" format
        try:
            event_date = datetime.strptime(event_date_str, "%d %B").replace(year=datetime.now().year).strftime(
                "%Y-%m-%d")
            set_event(event_name, event_date)
            speak(f"Got it! I'll remember that {event_name} is on {event_date_str}.")
        except ValueError:
            speak("Sorry, I didn't catch that date. Could you repeat it?")
        return

    # Check for upcoming events and remind the user
    upcoming_events = get_upcoming_events()
    if upcoming_events:
        for event_name, event_date in upcoming_events:
            days_left = (event_date - datetime.now()).days
            if event_name == "valentine's day":
                speak(f"Valentine's Day is in {days_left} days! Have you planned anything special?")
            else:
                speak(f"Your {event_name} is coming up in {days_left} days! Got any plans?")
        return


    # HOW ARE YOU? HANDLING
    mood_questions = ["how are you", "are you fine", "how's it going", "how have you been"]
    mood_responses = [
        "I'm just an AI, but I'm doing great! Thanks for asking.",
        "I'm always here, ready to chat! How about you?",
        "Feeling energetic! What's on your mind?",
        "I’m good! Learning new things every day. What about you?"
    ]

    if any(word in command for word in mood_questions):
        follow_ups = analyze_memory()
        if follow_ups:
            for follow_up in follow_ups:
                speak(follow_up)
        else:
            speak(random.choice(mood_responses))
        return

def handle_small_talk(command):
    """Handle small talk with expanded and diverse responses."""

    print("Checking small talk for:", command)  # Add this line

    # EMOTIONS
    if "i am tired" in command or "feeling tired" in command:
        responses = [
            "You should take some rest. Maybe listen to some relaxing music.",
            "Sounds like you could use a break. How about a short nap?",
            "Why not grab a coffee and relax for a bit?"
        ]
        speak(random.choice(responses))
        return True

    if "i am bored" in command or "feeling bored" in command:
        responses = [
            "How about watching a movie or reading a book?",
            "Maybe try learning something new or play a game?",
            "You could try cooking something interesting or go for a walk!"
        ]
        speak(random.choice(responses))
        return True

    if "i am enthusiastic" in command or "feeling enthusiastic" in command:
        responses = [
            "That's awesome! Maybe start that project you've been thinking about!",
            "Sounds great! How about doing something creative or productive?",
            "Why not use that energy to learn something new or work out?"
        ]
        speak(random.choice(responses))
        return True

    if "i need to do something productive" in command:
        responses = [
            "How about organizing your workspace or planning your week?",
            "Maybe start a new hobby or work on a side project?",
            "Reading a book or learning a new skill sounds productive!"
        ]
        speak(random.choice(responses))
        return True

    if "i am sad" in command or "feeling down" in command:
        responses = [
            "I'm here for you. Want to talk about it?",
            "Sometimes expressing yourself helps. I'm listening.",
            "It's okay to feel that way sometimes. Maybe some music might help?"
        ]
        speak(random.choice(responses))
        return True

    if "i am happy" in command or "feeling great" in command:
        responses = [
            "That's awesome! What made your day so good?",
            "Happiness is contagious! Glad to hear it.",
            "Yay! I'm happy to hear that. Anything exciting happened?"
        ]
        speak(random.choice(responses))
        return True

    # NEW SMALL TALKS (Expanded)
    if "i am lonely" in command:
        responses = [
            "I'm here for you. Want to chat for a while?",
            "Loneliness can be tough. How about calling a friend?",
            "Maybe a walk outside might help clear your mind."
        ]
        speak(random.choice(responses))
        return True

    if "i am angry" in command or "feeling frustrated" in command:
        responses = [
            "It's okay to feel that way. Want to vent about it?",
            "Maybe try taking deep breaths or going for a walk.",
            "Listening to some music might help you cool down."
        ]
        speak(random.choice(responses))
        return True

    if "i am confused" in command:
        responses = [
            "Want to talk about what's confusing you?",
            "Sometimes writing things down helps to clear the mind.",
            "Maybe I can help clarify things. What's on your mind?"
        ]
        speak(random.choice(responses))
        return True

    if "i miss someone" in command:
        responses = [
            "It's natural to miss people we care about. Want to talk about them?",
            "Maybe sending them a message could help you feel better.",
            "You could look at some old photos or write them a letter."
        ]
        speak(random.choice(responses))
        return True

    if "i feel guilty" in command:
        responses = [
            "Want to talk about what’s making you feel guilty?",
            "Sometimes, forgiving yourself is the hardest part. Take it easy.",
            "Maybe reflecting on why you feel this way might help."
        ]
        speak(random.choice(responses))
        return True

    if "i am grateful" in command:
        responses = [
            "That's a wonderful feeling! What are you grateful for today?",
            "Gratitude is a great habit. Keeps us grounded!",
            "It's lovely to hear that! Gratitude brings positivity."
        ]
        speak(random.choice(responses))
        return True

    if "tell me a joke" in command:
        jokes = [
            "Why don't skeletons fight each other? They don't have the guts!",
            "How does the ocean say hi? It waves!",
            "Why was the math book sad? It had too many problems."
        ]
        speak(random.choice(jokes))
        return True

    # EMOTIONS
    if "i feel insecure" in command:
        responses = [
            "It's okay to feel that way sometimes. Want to talk about it?",
            "Remember, no one has it all figured out. You're doing great!",
            "Insecurity is just a sign that you're growing and learning."
        ]
        speak(random.choice(responses))
        return True

    if "i am anxious" in command or "feeling anxious" in command:
        responses = [
            "Take a deep breath. I'm here for you.",
            "Want to talk about what's making you anxious?",
            "Sometimes writing things down helps. Want some tips to calm down?"
        ]
        speak(random.choice(responses))
        return True

    if "i feel embarrassed" in command:
        responses = [
            "It happens to everyone. Want to share what happened?",
            "We all have those moments. Laughing it off can help!",
            "Don't worry! People usually forget these things quickly."
        ]
        speak(random.choice(responses))
        return True

    if "i am proud" in command:
        responses = [
            "That's amazing! You should be proud of yourself!",
            "Achievements deserve to be celebrated! Tell me more!",
            "Pride in your progress is the best kind of motivation!"
        ]
        speak(random.choice(responses))
        return True

    if "i am curious" in command:
        responses = [
            "Curiosity is the key to learning! What’s on your mind?",
            "Ask away! I love curious minds!",
            "Curiosity leads to great discoveries. What are you thinking about?"
        ]
        speak(random.choice(responses))
        return True

    if "i am surprised" in command:
        responses = [
            "Sounds like something unexpected happened! Want to share?",
            "Surprises can be fun! What surprised you?",
            "Wow! Tell me more about it!"
        ]
        speak(random.choice(responses))
        return True

    # DAILY LIFE SITUATIONS
    if "i am hungry" in command:
        responses = [
            "How about ordering some food or trying a new recipe?",
            "Maybe a snack will help! Got any cravings?",
            "You could cook something quick and tasty!"
        ]
        speak(random.choice(responses))
        return True

    if "i am thirsty" in command:
        responses = [
            "A glass of water might do the trick!",
            "How about some juice or a cup of tea?",
            "Staying hydrated is important! Grab a drink!"
        ]
        speak(random.choice(responses))
        return True

    if "i can't sleep" in command:
        responses = [
            "How about some soft music or reading a book?",
            "Sometimes, deep breaths help. Want some tips?",
            "Maybe a warm drink might help you relax."
        ]
        speak(random.choice(responses))
        return True

    if "i need motivation" in command:
        responses = [
            "Remember why you started! You’ve got this!",
            "Sometimes a small step is all it takes to build momentum.",
            "I believe in you! Need a motivational quote?"
        ]
        speak(random.choice(responses))
        return True

    if "i feel lost" in command:
        responses = [
            "It’s okay to feel that way. Want to talk it out?",
            "Sometimes, taking a step back helps to see things clearly.",
            "You're not alone. Let's figure it out together."
        ]
        speak(random.choice(responses))
        return True

    # RANDOM THOUGHTS & FUN
    if "tell me a random fact" in command:
        facts = [
            "Did you know octopuses have three hearts?",
            "Bananas are berries, but strawberries aren’t!",
            "A group of flamingos is called a 'flamboyance'."
        ]
        speak(random.choice(facts))
        return True

    if "tell me a conspiracy theory" in command:
        theories = [
            "Some believe the moon landing was faked!",
            "There's a theory that birds are government spies!",
            "Ever heard the one about Area 51 and aliens?"
        ]
        speak(random.choice(theories))
        return True

    if "i miss old times" in command:
        responses = [
            "Nostalgia can be bittersweet. Want to share a memory?",
            "It's nice to look back sometimes. What do you miss the most?",
            "Those were the days, huh? Let's talk about it."
        ]
        speak(random.choice(responses))
        return True

    if "i feel like a failure" in command:
        responses = [
            "You're not a failure. Mistakes are part of growth.",
            "Every success story has struggles behind it. Keep going!",
            "You're doing better than you think. Let's talk it out."
        ]
        speak(random.choice(responses))
        return True

    if "tell me something funny" in command:
        jokes = [
            "Why don’t skeletons fight each other? They don’t have the guts!",
            "I'm reading a book on anti-gravity. It’s impossible to put down!",
            "Parallel lines have so much in common. It’s a shame they’ll never meet."
        ]
        speak(random.choice(jokes))
        return True

    # TIME & DATE
    if "what time is it" in command or "what's the date today" in command:
        from datetime import datetime
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        current_date = now.strftime("%A, %B %d, %Y")
        speak(f"The current time is {current_time}, and today's date is {current_date}.")
        return

    # WEATHER
    if "what's the weather" in command or "how's the weather today" in command:
        speak("I can't check the weather yet, but I can help you with other things!")
        return

    # RANDOM FUN FACTS
    if "tell me a fun fact" in command or "tell me something interesting" in command:
        fun_facts = [
            "Did you know that honey never spoils? Archaeologists found 3000-year-old honey in Egyptian tombs that was still good to eat!",
            "Octopuses have three hearts! Two pump blood to the gills, and one pumps it to the rest of the body.",
            "The Eiffel Tower can grow taller in the summer! Heat causes the metal to expand, making it up to 15 cm taller."
        ]
        speak(random.choice(fun_facts))
        return

    # Default response if no other condition matches
    speak("That’s interesting! Tell me more about it.")

def analyze_memory():
        """Check past memory and generate follow-up questions."""
        memory = recall_memory()
        follow_up = []

        for entry in memory:
            if "text" in entry:  # Check if "text" key exists
                text = entry["text"].lower()
            else:
                continue  # Skip entries without "text" key

            if "sad" in text or "not feeling well" in text:
                follow_up.append("Last time you seemed sad. Are you feeling better today?")

            if "buy a bike" in text or "thinking of buying a bike" in text:
                follow_up.append("You mentioned wanting to buy a bike. Have you made any decisions?")

            if "learning python" in text or "want to learn coding" in text:
                follow_up.append("You wanted to learn Python. How is your progress going?")

        return follow_up


def set_reminder(event, remind_time, repeat=None):
    """Store or update a reminder in memory."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)

    reminder = {
        "event": event,
        "remind_time": remind_time,
        "repeat": repeat
    }
    memory.append({"reminder": reminder})

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)


def get_upcoming_reminders():
    """Retrieve and manage reminders."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)

    now = datetime.now()
    reminders_to_notify = []
    updated_memory = []

    for entry in memory:
        if "reminder" in entry:
            reminder = entry["reminder"]
            remind_time = datetime.strptime(reminder["remind_time"], "%Y-%m-%d %H:%M")

            if now >= remind_time:
                reminders_to_notify.append(reminder)
                # Handle repeating reminders
                if reminder["repeat"]:
                    if reminder["repeat"] == "daily":
                        new_time = remind_time + timedelta(days=1)
                    elif reminder["repeat"] == "weekly":
                        new_time = remind_time + timedelta(weeks=1)
                    reminder["remind_time"] = new_time.strftime("%Y-%m-%d %H:%M")
                    updated_memory.append({"reminder": reminder})
            else:
                updated_memory.append(entry)
        else:
            updated_memory.append(entry)

    with open(MEMORY_FILE, "w") as f:
        json.dump(updated_memory, f, indent=4)

    return reminders_to_notify


def remind_user():
    """Check for upcoming reminders and notify the user."""
    while True:
        reminders = get_upcoming_reminders()
        for reminder in reminders:
            messages = [
                f"Hey! Don't forget: {reminder['event']}.",
                f"Just a heads-up: {reminder['event']} is coming up!",
                f"Remember to: {reminder['event']}!",
                f"Psst! It's time for: {reminder['event']}!"
            ]
            speak(random.choice(messages))
        time.sleep(60)  # Check every minute


# Run reminder checker in the background
reminder_thread = threading.Thread(target=remind_user, daemon=True)
reminder_thread.start()


def handle_reminder_command(command):
    """Process and set reminders based on user input."""
    import re

    # Extract date and time from command
    time_match = re.search(r"(\d{1,2}:\d{2} (?:AM|PM))", command, re.IGNORECASE)
    date_match = re.search(r"(\d{1,2}(?:st|nd|rd|th)? \w+)", command, re.IGNORECASE)
    repeat_match = re.search(r"(every day|daily|weekly)", command, re.IGNORECASE)
    event_match = re.search(r"remind me to (.+?)(?: at| on| every|$)", command, re.IGNORECASE)

    if event_match:
        event = event_match.group(1).strip()
        repeat = repeat_match.group(1).lower() if repeat_match else None

        if date_match and time_match:
            date_str = date_match.group(1).replace("st", "").replace("nd", "").replace("rd", "").replace("th", "")
            time_str = time_match.group(1)
            date = datetime.strptime(f"{date_str} {datetime.now().year}", "%d %B %Y")
            remind_time = datetime.strptime(f"{date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %I:%M %p")
        elif time_match:
            remind_time = datetime.strptime(f"{datetime.now().strftime('%Y-%m-%d')} {time_match.group(1)}",
                                            "%Y-%m-%d %I:%M %p")
        elif date_match:
            date_str = date_match.group(1).replace("st", "").replace("nd", "").replace("rd", "").replace("th", "")
            remind_time = datetime.strptime(f"{date_str} {datetime.now().year} 09:00", "%d %B %Y %H:%M")
        else:
            speak("I didn't get the date or time. Could you repeat that?")
            return

        set_reminder(event, remind_time.strftime("%Y-%m-%d %H:%M"), repeat)
        speak(f"Got it! I'll remind you to {event} at the right time.")
        return True

    return False

def generate_response(prompt):
    """Generate a natural, context-aware response using OpenAI's GPT API."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a friendly and empathetic AI assistant named Elina."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.8  # Adjusts creativity (higher = more creative)
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I'm having trouble responding right now."

def store_long_talk(command):
    """Store long conversations with context in memory."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)

    memory.append({
        "date": str(datetime.now()),
        "type": "long_talk",
        "text": command
    })

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

def get_recent_long_talks():
    """Retrieve recent long conversations for context."""
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)

    # Get the last 5 long talks for context
    long_talks = [entry['text'] for entry in memory if entry.get('type') == 'long_talk']
    return long_talks[-5:]

def handle_long_talk(command):
    """Process and respond to long talks dynamically."""
    store_long_talk(command)  # Save the user's input for context

    # Retrieve recent context
    recent_talks = get_recent_long_talks()
    context = "\n".join(recent_talks)

    # Generate a natural response based on context
    full_prompt = f"Conversation history:\n{context}\n\nUser: {command}"
    response = generate_response(full_prompt)
    speak(response)

# Main Loop
while True:
    user_command = listen()
    if user_command:
        process_command(user_command)
