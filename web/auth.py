"""
Session-based authentication for the Twitch Drops Miner web interface.
Uses Flask sessions with secure cookies for authentication.
"""
import os
import json
import secrets
import time
from functools import wraps
from flask import jsonify, redirect, url_for, session
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CREDENTIALS_PATH = os.path.join(DATA_DIR, 'credentials.json')

# Session settings
SESSION_SECRET = None

def get_session_secret():
    global SESSION_SECRET
    if SESSION_SECRET is None:
        SESSION_SECRET = os.environ.get('SESSION_SECRET')
        if not SESSION_SECRET:
            SESSION_SECRET = secrets.token_hex(32)
            env_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

            # Read current .env file
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    env_content = f.read()

                # Check if SESSION_SECRET line exists
                if 'SESSION_SECRET=' in env_content:
                    # Replace existing empty SESSION_SECRET line
                    env_content = env_content.replace('SESSION_SECRET=', f'SESSION_SECRET={SESSION_SECRET}')
                else:
                    # Append SESSION_SECRET to the end of the file
                    env_content += f"\n# Session Authentication Secret\nSESSION_SECRET={SESSION_SECRET}\n"

                # Write updated content back to .env file
                with open(env_path, 'w') as f:
                    f.write(env_content)

                if os.environ.get('TDM_WEBUI_ENABLED'):
                    print(f"Generated and saved session secret to .env file: {SESSION_SECRET[:8]}...{SESSION_SECRET[-8:]}")
            else:
                # .env file doesn't exist, just use the generated secret this time
                # if os.environ.get('TDM_WEBUI_ENABLED'):
                #     print(f"Generated session secret (no .env file): {SESSION_SECRET[:8]}...{SESSION_SECRET[-8:]}")
                pass

        # Set it in environment for Flask
        os.environ['SESSION_SECRET'] = SESSION_SECRET
    return SESSION_SECRET

# Argon2 hasher for password hashing
ph = PasswordHasher()

def init_credentials():
    """Initialize credentials file if it doesn't exist"""
    if not os.path.exists(CREDENTIALS_PATH):
        with open(CREDENTIALS_PATH, 'w') as f:
            json.dump({
                "users": [],
                "setup_complete": False
            }, f)
        return False

    with open(CREDENTIALS_PATH, 'r') as f:
        credentials = json.load(f)

    return credentials.get("setup_complete", False)

def is_setup_needed():
    """Check if initial setup is needed"""
    return not init_credentials()

def create_user(username, password):
    """Create a new user with the given credentials"""
    if not username or not password:
        return False, "Username and password are required"

    # Check if file exists
    init_credentials()

    with open(CREDENTIALS_PATH, 'r') as f:
        credentials = json.load(f)

    # Check if setup is already complete and user is trying to create new account
    if credentials.get("setup_complete", False):
        # Only allow if there are no users yet (special case)
        if credentials.get("users", []):
            return False, "Setup already complete"

    # Check if username exists
    for user in credentials.get("users", []):
        if user["username"] == username:
            return False, "Username already exists"

    # Create user with Argon2 hashed password
    user = {
        "username": username,
        "password": ph.hash(password),  # Using Argon2 for password hashing
        "created_at": time.time()
    }

    credentials["users"] = credentials.get("users", []) + [user]
    credentials["setup_complete"] = True

    with open(CREDENTIALS_PATH, 'w') as f:
        json.dump(credentials, f)

    return True, "User created successfully"

def validate_credentials(username, password):
    """Validate username and password using Argon2"""
    if not os.path.exists(CREDENTIALS_PATH):
        return False, "No users defined"

    with open(CREDENTIALS_PATH, 'r') as f:
        credentials = json.load(f)

    for user in credentials.get("users", []):
        if user["username"] == username:
            try:
                # Verify password hash using Argon2
                ph.verify(user["password"], password)
                return True, "Authentication successful"
            except VerifyMismatchError:
                return False, "Invalid password"

    return False, "User not found"

def login_user(username):
    """Log in a user by setting session data"""
    session['username'] = username
    session['logged_in'] = True
    session['login_time'] = time.time()

def logout_user():
    """Log out a user by clearing session data"""
    session.clear()

def is_logged_in():
    """Check if user is currently logged in"""
    return session.get('logged_in', False)

def get_current_user():
    """Get the current logged-in username"""
    if is_logged_in():
        return session.get('username')
    return None

def auth_required(f):
    """Decorator to require authentication for API routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            return jsonify({'error': 'Authentication required'}), 401

        # Add username to kwargs
        kwargs['username'] = get_current_user()
        return f(*args, **kwargs)

    return decorated

def login_required(f):
    """Decorator to redirect unauthenticated users to login page for web routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for('login'))

        # Add username to kwargs
        kwargs['username'] = get_current_user()
        return f(*args, **kwargs)

    return decorated
