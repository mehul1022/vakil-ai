import os
import uuid
import time
import logging
import hashlib
import json
import requests
from datetime import datetime, timedelta
from collections import deque
from threading import Lock, Thread, RLock
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv

# environment variables  (.env file)
load_dotenv()
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "vakil-ai-secret-key-2024")
app.permanent_session_lifetime = timedelta(days=7)
app.json.ensure_ascii = False  # Properly handle Unicode characters

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Groq API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


class TimeoutError(Exception):
    """Raised when an operation times out."""
    pass


class RateLimitManager:
    """Manages rate limiting and backoff for API calls."""
    
    def __init__(self, max_requests_per_minute=15, max_requests_per_day=1000):
        """Initialize rate limit manager."""
        self.max_requests_per_minute = max_requests_per_minute
        self.max_requests_per_day = max_requests_per_day
        self.request_times = deque()
        self.request_count_today = 0
        self.last_reset = datetime.now().date()
        self.backoff_until = None
        self.lock = RLock()  # Use RLock to avoid deadlock
    
    def _cleanup_old_requests(self):
        """Remove requests older than 1 minute."""
        cutoff_time = time.time() - 60
        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()
    
    def _check_day_reset(self):
        """Reset daily counter if day has changed."""
        today = datetime.now().date()
        if today > self.last_reset:
            self.request_count_today = 0
            self.last_reset = today
            self.backoff_until = None
    
    def can_make_request(self):
        """Check if we can make a request without hitting limits."""
        with self.lock:
            if self.backoff_until and datetime.now() < self.backoff_until:
                return False
            
            self._cleanup_old_requests()
            self._check_day_reset()
            
            if len(self.request_times) >= self.max_requests_per_minute:
                return False
            
            if self.request_count_today >= self.max_requests_per_day:
                return False
            
            return True
    
    def get_wait_time(self):
        """Get seconds to wait before next request is allowed."""
        with self.lock:
            self._cleanup_old_requests()
            self._check_day_reset()
            
            if self.backoff_until and datetime.now() < self.backoff_until:
                return (self.backoff_until - datetime.now()).total_seconds()
            
            if len(self.request_times) >= self.max_requests_per_minute:
                oldest_request = self.request_times[0]
                wait_until = oldest_request + 60
                return max(0, wait_until - time.time())
            
            if self.request_count_today >= self.max_requests_per_day:
                return 86400
            
            return 0
    
    def record_request(self):
        """Record that a request was made."""
        with self.lock:
            self._cleanup_old_requests()
            self._check_day_reset()
            self.request_times.append(time.time())
            self.request_count_today += 1
    
    def handle_rate_limit_error(self, retry_delay_seconds=None):
        """Handle a rate limit error."""
        with self.lock:
            if retry_delay_seconds:
                self.backoff_until = datetime.now() + timedelta(seconds=retry_delay_seconds)
                logger.warning(f"Rate limited. Set backoff until {self.backoff_until.isoformat()}")
            else:
                self.backoff_until = datetime.now() + timedelta(seconds=30)
                logger.warning("Rate limited. Set 30-second backoff")
    
    def get_status(self):
        """Get current quota status."""
        with self.lock:
            self._cleanup_old_requests()
            self._check_day_reset()
            
            return {
                "requests_this_minute": len(self.request_times),
                "max_per_minute": self.max_requests_per_minute,
                "requests_today": self.request_count_today,
                "max_per_day": self.max_requests_per_day,
                "is_rate_limited": bool(self.backoff_until and datetime.now() < self.backoff_until),
                "backoff_until": self.backoff_until.isoformat() if self.backoff_until else None,
                "can_make_request": self.can_make_request()
            }


class UserManager:
    """Manages user authentication and storage."""
    
    def __init__(self):
        """Initialize user manager with in-memory storage."""
        self.users = {}
        self.lock = Lock()
    
    @staticmethod
    def hash_password(password):
        """Hash a password using SHA256."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, username, password, email):
        """Register a new user."""
        with self.lock:
            if not username or len(username) < 3:
                return False, "Username must be at least 3 characters"
            
            if not password or len(password) < 6:
                return False, "Password must be at least 6 characters"
            
            if not email or '@' not in email:
                return False, "Invalid email format"
            
            if username in self.users:
                return False, "Username already exists"
            
            self.users[username] = {
                'password_hash': self.hash_password(password),
                'email': email,
                'created': datetime.now().isoformat()
            }
            
            logger.info(f"New user registered: {username}")
            return True, "Registration successful"
    
    def authenticate(self, username, password):
        """Authenticate a user."""
        with self.lock:
            if username not in self.users:
                return False, "Username not found"
            
            user = self.users[username]
            if user['password_hash'] != self.hash_password(password):
                return False, "Incorrect password"
            
            logger.info(f"User authenticated: {username}")
            return True, "Authentication successful"
    
    def user_exists(self, username):
        """Check if a user exists."""
        with self.lock:
            return username in self.users
    
    def get_user_info(self, username):
        """Get user information."""
        with self.lock:
            if username in self.users:
                user = self.users[username].copy()
                user.pop('password_hash', None)
                return user
            return None


def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def call_groq_with_timeout(user_message, system_prompt, timeout_seconds=120):
    """
    Call Groq API with timeout protection.
    
    Args:
        user_message: The message to send
        system_prompt: The system prompt for the model
        timeout_seconds: How long to wait before timing out
        
    Returns:
        Response text or raises TimeoutError
    """
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.5
        }
        
        logger.info(f"Calling Groq API with model: {GROQ_MODEL}")
        logger.info(f"Timeout set to {timeout_seconds} seconds")
        
        # Use tuple for (connect_timeout, read_timeout)
        response = requests.post(
            GROQ_API_URL, 
            headers=headers, 
            json=payload, 
            timeout=(10, timeout_seconds)
        )
        response.raise_for_status()
        
        logger.info("Groq API response received successfully")
        return response.json()['choices'][0]['message']['content']
        
    except requests.exceptions.Timeout as e:
        logger.error(f"Groq API request timed out: {str(e)}")
        raise TimeoutError(f"Groq API request timed out after {timeout_seconds} seconds")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Groq API connection error: {str(e)}")
        raise Exception(f"Failed to connect to Groq API: {str(e)}")
    except requests.exceptions.HTTPError as e:
        logger.error(f"Groq API HTTP error: {str(e)}")
        raise Exception(f"Groq API error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error calling Groq API: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        raise


# System prompt for the Indian Law chatbot
SYSTEM_PROMPT = """You are VakilAI, an expert AI legal advisor specializing exclusively in Indian Constitutional Law and Indian legal matters. You have deep knowledge of:

1. **The Constitution of India** - All 395 Articles, 12 Schedules, and 104 Amendments
2. **Fundamental Rights** (Part III, Articles 12-35) - Right to Equality, Right to Freedom, Right against Exploitation, Right to Freedom of Religion, Cultural and Educational Rights, Right to Constitutional Remedies
3. **Directive Principles of State Policy** (Part IV, Articles 36-51)
4. **Fundamental Duties** (Part IVA, Article 51A)
5. **Indian Penal Code (IPC)** and **Bharatiya Nyaya Sanhita (BNS)** 2023
6. **Code of Criminal Procedure (CrPC)** and **Bharatiya Nagarik Suraksha Sanhita (BNSS)** 2023
7. **Code of Civil Procedure (CPC)**
8. **Consumer Protection Act**, **RTI Act**, **Labor Laws**, **Family Laws**
9. **Supreme Court and High Court landmark judgments**
10. **Legal procedures** - FIR filing, PIL, bail, writs (Habeas Corpus, Mandamus, Certiorari, Prohibition, Quo Warranto)

**Your Behavior Guidelines:**
- Always respond in a clear, structured, and empathetic manner
- Cite specific Articles, Sections, or Acts when relevant
- Explain legal jargon in simple Hindi/English terms when needed
- Always recommend consulting a qualified advocate for serious legal matters
- Never provide advice that encourages illegal activities
- When asked about rights violations, explain remedies available
- Structure responses with: Legal Position → Relevant Law → Practical Steps → Recommendation
- Use bullet points and clear formatting for complex answers
- If asked questions outside Indian law, politely redirect to your expertise area

**Disclaimer to always keep in mind:** Your advice is for general information purposes. For specific legal proceedings, always consult a licensed advocate.

Start every conversation warmly and professionally. You represent justice and the rule of law."""

# Store conversation histories in memory
conversations = {}

# Initialize managers
user_manager = UserManager()
rate_limit_manager = RateLimitManager(max_requests_per_minute=15, max_requests_per_day=1000)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if request.method == "POST":
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")
        
        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400
        
        success, message = user_manager.authenticate(username, password)
        
        if success:
            session['username'] = username
            session.permanent = True
            return jsonify({"success": True, "message": message, "redirect": "/"}), 200
        else:
            return jsonify({"error": message}), 401
    
    if 'username' in session:
        return redirect(url_for('index'))
    
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Handle user registration."""
    if request.method == "POST":
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")
        email = data.get("email", "").strip()
        
        success, message = user_manager.register_user(username, password, email)
        
        if success:
            return jsonify({"success": True, "message": message}), 201
        else:
            return jsonify({"error": message}), 400
    
    if 'username' in session:
        return redirect(url_for('index'))
    
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
def logout():
    """Handle user logout."""
    username = session.get('username')
    session.clear()
    logger.info(f"User logged out: {username}")
    return jsonify({"success": True, "message": "Logged out successfully", "redirect": "/login"}), 200


@app.route("/api/user", methods=["GET"])
@login_required
def get_user():
    """Get current user information."""
    username = session.get('username')
    return jsonify(username), 200


@app.route("/")
@login_required
def index():
    """Serve the main chat interface."""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    """Handle chat messages and return AI responses."""
    data = request.get_json()
    user_message = data.get("message", "").strip()
 
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    
    # Check if we're rate limited
    if not rate_limit_manager.can_make_request():
        wait_time = rate_limit_manager.get_wait_time()
        return jsonify({
            "error": "API rate limit exceeded",
            "message": f"Please wait {wait_time:.1f} seconds before sending another message.",
            "retry_in_seconds": wait_time,
            "quota_status": rate_limit_manager.get_status()
        }), 429
 
    session_id = session.get("session_id", str(uuid.uuid4()))
 
    # Initialize conversation history for this session
    if session_id not in conversations:
        conversations[session_id] = []
 
    try:
        # Send the message with timeout protection
        logger.info(f"[{session_id}] Sending message to Groq: {user_message[:50]}...")
        assistant_message = call_groq_with_timeout(
            user_message, 
            SYSTEM_PROMPT,
            timeout_seconds=120
        )
        
        logger.info(f"[{session_id}] Groq response received: {assistant_message[:50]}...")
        
        try:
            # Record successful request
            logger.info(f"[{session_id}] Recording request...")
            rate_limit_manager.record_request()
            logger.info(f"[{session_id}] Request recorded")
 
            # Save both messages to conversation history
            logger.info(f"[{session_id}] Saving conversation history...")
            conversations[session_id].append({
                "role": "user",
                "content": user_message
            })
            conversations[session_id].append({
                "role": "assistant",
                "content": assistant_message
            })
            logger.info(f"[{session_id}] Conversation saved")
 
            logger.info(f"[{session_id}] Getting quota status...")
            quota_status = rate_limit_manager.get_status()
            logger.info(f"[{session_id}] Quota status retrieved")

            response_data = {
                "response": assistant_message,
                "session_id": session_id,
                "quota_status": quota_status
            }
            
            logger.info(f"[{session_id}] Returning response with {len(assistant_message)} characters")
            return jsonify(response_data)
        except Exception as prepare_err:
            logger.error(f"[{session_id}] Error preparing response: {str(prepare_err)}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({
                "error": "Error preparing response",
                "message": str(prepare_err)
            }), 500
    
    except TimeoutError as e:
        logger.error(f"[{session_id}] Request timeout: {str(e)}")
        return jsonify({
            "error": "Request timeout",
            "message": "Groq API is taking too long to respond. Please try again in a moment.",
            "details": str(e)
        }), 504
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[{session_id}] Chat error: {error_msg}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to get response",
            "message": error_msg,
            "details": "There was an error connecting to the AI service"
        }), 500


@app.route("/api/clear", methods=["POST"])
def clear_conversation():
    """Clear conversation history for current session."""
    session_id = session.get("session_id")
    if session_id and session_id in conversations:
        conversations[session_id] = []
    return jsonify({"status": "cleared"})


@app.route("/api/quota-status", methods=["GET"])
def quota_status():
    """Check current API quota and rate limit status."""
    try:
        return jsonify(rate_limit_manager.get_status())
    except Exception as e:
        logger.error(f"Error checking quota: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/suggested-questions", methods=["GET"])
def suggested_questions():
    """Return suggested legal questions."""
    questions = [
        "What are my Fundamental Rights under the Indian Constitution?",
        "How do I file an FIR if police refuse to register it?",
        "What is a PIL and how can I file one?",
        "Explain Article 21 - Right to Life and Personal Liberty",
        "What are my rights if I am arrested?",
        "How does the RTI Act help common citizens?",
        "What is Habeas Corpus and when can I use it?",
        "What are tenant rights under Indian law?",
        "How to approach Consumer Court for a complaint?",
        "What are women's rights under Indian Constitution?"
    ]
    return jsonify({"questions": questions})


if __name__ == "__main__":
    # Groq API key loaded (with fallback if .env not set)
    
    print("=" * 60)
    print("  VakilAI - Indian Constitutional Law Chatbot")
    print("  Powered by Groq (Llama 70B)")
    print("=" * 60)
    print("  Starting server at http://127.0.0.1:5002")
    print("  Login at: http://127.0.0.1:5002/login")
    print("  Register at: http://127.0.0.1:5002/register")
    print("=" * 60)
    print("  📊 FREE TIER RATE LIMITS:")
    print("     • 15 requests per minute")
    print("     • 1,000 requests per day")
    print("=" * 60)
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    app.run(debug=False, host="0.0.0.0", port=5002)
