import json
import os

PROFILES_FILE = 'user_profiles.json'

def load_profiles():
    """טוען את כל הפרופילים מהקובץ. אם לא קיים, מחזיר מילון ריק."""
    if os.path.exists(PROFILES_FILE):
        with open(PROFILES_FILE, 'r') as file:
            return json.load(file)
    return {}

def save_profile(username, posture_baseline, pitch_baseline):
    """שומר או מעדכן משתמש במסד הנתונים"""
    profiles = load_profiles()
    profiles[username] = {
        "posture_baseline": posture_baseline,
        "pitch_baseline": pitch_baseline
    }
    with open(PROFILES_FILE, 'w') as file:
        json.dump(profiles, file, indent=4)
    print(f"\n[SUCCESS] Profile for '{username}' has been securely saved!")

def get_profile(username):
    """שולף פרופיל של משתמש. מחזיר None אם המשתמש לא קיים."""
    profiles = load_profiles()
    return profiles.get(username)