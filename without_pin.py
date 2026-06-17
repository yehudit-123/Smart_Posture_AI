import cv2
import mediapipe as mp
import time
import collections
import winsound
import keyboard            
import posture_math      
import profile_manager  

toaster = ToastNotifier()

# === התחברות משתמש (Login) ===
print("=======================================")
print("  SmartPosture AI - BACKGROUND MODE    ")
print("=======================================")
current_user = input("Please enter your name to login: ").strip().title()

profile = profile_manager.get_profile(current_user)

POSTURE_TOLERANCE = 8.0     
PITCH_TOLERANCE = 12.0      
ASYMMETRY_THRESHOLD = 7.0   

if profile:
    print(f"\nWelcome back, {current_user}! Profile loaded successfully.")
    personal_baseline = profile["posture_baseline"]
    personal_pitch_baseline = profile["pitch_baseline"]
    dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
    dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE
    is_calibrated = True
else:
    print(f"\nHello {current_user}! You are a new user. Please sit straight and press Ctrl+Alt+C 5 times.")
    personal_baseline = 0.0
    dynamic_threshold = 0.0
    dynamic_pitch_threshold = 0.0
    is_calibrated = False

print("\n--- GLOBAL SHORTCUTS ---")
print("Ctrl + Alt + C : Calibrate posture")
print("Ctrl + Alt + R : Reset profile")
print("Ctrl + Alt + = : Make tolerance EASIER (Plus key)")
print("Ctrl + Alt + - : Make tolerance HARDER (Minus key)")
print("Ctrl + Alt + Q : Quit application")
print("------------------------\n")

# === הגדרות מערכת ומונים ===
SCORE_HISTORY_LENGTH = 15
score_history = collections.deque(maxlen=SCORE_HISTORY_LENGTH)
asymmetry_history = collections.deque(maxlen=SCORE_HISTORY_LENGTH)
pitch_history = collections.deque(maxlen=SCORE_HISTORY_LENGTH)

REQUIRED_CALIBRATION_FRAMES = 5
calibration_scores = []
calibration_pitch = []

BAD_POSTURE_TIME_LIMIT = 10.0  
bad_posture_start_time = None 
last_beep_time = 0            
last_toast_time = 0
TOAST_COOLDOWN = 15.0 

total_monitored_frames = 0
good_posture_frames = 0
last_key_time = 0 

options = mp.tasks.vision.PoseLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path='pose_landmarker_heavy.task'),
    running_mode=mp.tasks.vision.RunningMode.VIDEO,
    num_poses=1,
    min_pose_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

cap = cv2.VideoCapture(0)
if not cap.isOpened(): exit()

print("Camera is active in the background. Monitoring started...\n")

with mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker:
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret: break

        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        timestamp_ms = int((time.time() - start_time) * 1000)
        results = landmarker.detect_for_video(mp_image, timestamp_ms)

        current_raw_score = None
        current_pitch_score = None
        current_time = time.time()

        if results.pose_landmarks:
            for landmarks in results.pose_landmarks:
                nose = landmarks[0]
                right_ear = landmarks[8]
                left_ear = landmarks[7]
                right_shoulder = landmarks[12]
                left_shoulder = landmarks[11]
                
                if nose.visibility > 0.5 and right_ear.visibility > 0.5 and left_ear.visibility > 0.5 and right_shoulder.visibility > 0.5 and left_shoulder.visibility > 0.5:
                    
                    current_raw_score = posture_math.get_forward_head_posture(right_ear, right_shoulder, left_shoulder) * 100
                    score_history.append(current_raw_score)
                    avg_score = sum(score_history) / len(score_history)
                    
                    current_asymmetry = posture_math.get_shoulder_asymmetry(right_shoulder, left_shoulder)
                    asymmetry_history.append(current_asymmetry)
                    avg_asymmetry = sum(asymmetry_history) / len(asymmetry_history)

                    current_pitch_score = posture_math.get_head_pitch(nose, right_ear, left_ear, right_shoulder, left_shoulder) * 100
                    pitch_history.append(current_pitch_score)
                    avg_pitch = sum(pitch_history) / len(pitch_history)

                    if not is_calibrated:
                        pass 
                    else:
                        is_tech_neck = avg_score > dynamic_threshold
                        is_uneven = avg_asymmetry > ASYMMETRY_THRESHOLD
                        is_looking_down = avg_pitch > dynamic_pitch_threshold
                        
                        is_actively_alerting = False
                        
                        if is_tech_neck or is_uneven or is_looking_down:
                            if is_looking_down: status_msg = "Your screen seems too low. Please look up!"
                            elif is_tech_neck: status_msg = "Tech Neck detected. Please sit back!"
                            else: status_msg = "Uneven Shoulders. Try to sit symmetrically."
                            
                            if bad_posture_start_time is None: 
                                bad_posture_start_time = current_time
                                
                            if (current_time - bad_posture_start_time) > BAD_POSTURE_TIME_LIMIT:
                                is_actively_alerting = True
                                
                                if current_time - last_beep_time > 2.0:
                                    winsound.Beep(1000, 200)
                                    last_beep_time = current_time
                                    
                                if current_time - last_toast_time > TOAST_COOLDOWN:
                                    try:
                                        toaster.show_toast("SmartPosture AI Alert", status_msg, duration=4, threaded=True)
                                    except:
                                        pass 
                                    last_toast_time = current_time
                        else:
                            bad_posture_start_time = None

                        total_monitored_frames += 1
                        if not is_actively_alerting:
                            good_posture_frames += 1

        # === ניהול מקשי רקע דרך מקלדת גלובלית ===
        if current_time - last_key_time > 0.4:
            
            # --- התיקון החדש: לוגיקת סיום ויציאה ---
            if keyboard.is_pressed('ctrl+alt+q'):
                print("\nPreparing to quit. Calculating daily summary...")
                
                # חישוב הציון הסופי
                if total_monitored_frames > 0:
                    final_percentage = (good_posture_frames / total_monitored_frames) * 100
                    summary_msg = f"Session complete! You maintained good posture {final_percentage:.1f}% of the time today. Great job!"
                else:
                    summary_msg = "Session ended before enough posture data was collected."
                
                # הקפצת ההודעה (עם threaded=False כדי שהתוכנית תמתין עד שההודעה תרד)
                try:
                    toaster.show_toast("Daily Posture Summary", summary_msg, duration=5, threaded=False)
                except:
                    pass
                
                print("Quitting SmartPosture AI. Have a healthy day!")
                break
                
            elif keyboard.is_pressed('ctrl+alt+c') and not is_calibrated and current_raw_score is not None:
                calibration_scores.append(current_raw_score)
                calibration_pitch.append(current_pitch_score)
                winsound.Beep(1500, 100) 
                print(f"Captured calibration {len(calibration_scores)}/{REQUIRED_CALIBRATION_FRAMES}")
                
                if len(calibration_scores) >= REQUIRED_CALIBRATION_FRAMES:
                    personal_baseline = sum(calibration_scores) / len(calibration_scores)
                    dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
                    personal_pitch_baseline = sum(calibration_pitch) / len(calibration_pitch)
                    dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE
                    
                    is_calibrated = True
                    profile_manager.save_profile(current_user, personal_baseline, personal_pitch_baseline)
                    winsound.Beep(800, 200)
                    winsound.Beep(1200, 400) 
                    print("Calibration Complete! Running silently...")
                last_key_time = current_time
                    
            elif keyboard.is_pressed('ctrl+alt+r') and is_calibrated:
                is_calibrated = False
                calibration_scores.clear()
                calibration_pitch.clear()
                bad_posture_start_time = None
                total_monitored_frames = 0  
                good_posture_frames = 0
                winsound.Beep(500, 300)
                print("\nProfile Reset. Please press Ctrl+Alt+C 5 times to recalibrate.")
                last_key_time = current_time
                
            elif keyboard.is_pressed('ctrl+alt+='):
                if is_calibrated:
                    POSTURE_TOLERANCE += 1.0
                    PITCH_TOLERANCE += 1.0
                    dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
                    dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE
                    winsound.Beep(1500, 50)
                    print(f"Tolerance made EASIER. Current Tolerance: {POSTURE_TOLERANCE}")
                last_key_time = current_time
                    
            elif keyboard.is_pressed('ctrl+alt+-'):
                if is_calibrated:
                    POSTURE_TOLERANCE -= 1.0
                    PITCH_TOLERANCE -= 1.0
                    dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
                    dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE
                    winsound.Beep(1000, 50)
                    print(f"Tolerance made HARDER. Current Tolerance: {POSTURE_TOLERANCE}")
                last_key_time = current_time

cap.release()