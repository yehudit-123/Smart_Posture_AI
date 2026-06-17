import urllib.request
import ssl

# ביטול אימות אבטחה מחמיר
ssl._create_default_https_context = ssl._create_unverified_context

# הכתובת החדשה למודל ה-Heavy
url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
filename = "pose_landmarker_heavy.task"

print("Downloading the HEAVY model file, please wait...")
try:
    urllib.request.urlretrieve(url, filename)
    print(f"Success! The file '{filename}' has been downloaded to your folder.")
except Exception as e:
    print(f"An error occurred: {e}")