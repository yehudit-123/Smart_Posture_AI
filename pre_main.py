import cv2
import mediapipe as mp
import time
import collections
import winsound
import posture_math      
import profile_manager  

# === התחברות משתמש(Login) ===
print("=======================================")
print("     Welcome to SmartPosture AI!       ")
print("=======================================")
current_user = input("Please enter your name to login: ").strip().title()

profile = profile_manager.get_profile(current_user)

# הגדרות סובלנות למערכת(כעת ניתן לשנות אותן תוך כדי ריצה!)
POSTURE_TOLERANCE = 8.0
PITCH_TOLERANCE = 12.0
ASYMMETRY_THRESHOLD = 7.0

if profile:
    print(f"Welcome back, {current_user}! Loading your personal calibration data...")
    personal_baseline = profile["posture_baseline"]
    personal_pitch_baseline = profile["pitch_baseline"]
    dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
    dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE
    is_calibrated = True
else:
    print(f"Hello {current_user}! You are a new user. We need to calibrate your posture.")
    personal_baseline = 0.0
    dynamic_threshold = 0.0
    dynamic_pitch_threshold = 0.0
    is_calibrated = False

# === הגדרות מערכת וציור ===
POSE_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10), (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
    (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (27, 29), (27, 31), (29, 31),
    (24, 26), (26, 28), (28, 30), (28, 32), (30, 32)
]

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

# מונים חדשים לסטטיסטיקה יומיות
total_monitored_frames = 0
good_posture_frames = 0

def draw_pose(frame, result):
    if not result.pose_landmarks: return frame
    h, w = frame.shape[:2]
    for landmarks in result.pose_landmarks:
        for connection in POSE_CONNECTIONS:
            start_idx, end_idx = connection
            if start_idx < len(landmarks) and end_idx < len(landmarks):
                cv2.line(frame,
                    (int(landmarks[start_idx].x * w), int(landmarks[start_idx].y * h)),
                    (int(landmarks[end_idx].x * w), int(landmarks[end_idx].y * h)),
                    (0, 200, 0), 2)
        for lm in landmarks:
            cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 4, (255, 128, 0), -1)
    return frame

options = mp.tasks.vision.PoseLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path='pose_landmarker_heavy.task'),
    running_mode=mp.tasks.vision.RunningMode.VIDEO,
    num_poses=1,
    min_pose_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

cap = cv2.VideoCapture(0)
if not cap.isOpened(): exit()

print("\nStarting Camera... Press 'q' to exit.")

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

        frame = draw_pose(frame, results)
        current_raw_score = None
        current_pitch_score = None

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

                    current_time = time.time()

                    if not is_calibrated:
                        cv2.putText(frame, f"NEW USER: {current_user}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 200, 0), 3)
                        cv2.putText(frame, "Sit straight, look at screen, press 'c' 5 times", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                        cv2.putText(frame, f"Captured: {len(calibration_scores)}/{REQUIRED_CALIBRATION_FRAMES}", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    else:
                        is_tech_neck = avg_score > dynamic_threshold
                        is_uneven = avg_asymmetry > ASYMMETRY_THRESHOLD
                        is_looking_down = avg_pitch > dynamic_pitch_threshold

                        is_actively_alerting = False

                        if is_tech_neck or is_uneven or is_looking_down:
                            color = (0, 0, 255)
                            if is_looking_down: 
                                status = "SCREEN TOO LOW: Look up!"
                            elif is_tech_neck: 
                                status = "BAD POSTURE: Tech Neck"
                            else: 
                                status = "BAD POSTURE: Uneven Shoulders"

                            if bad_posture_start_time is None:
                                bad_posture_start_time = current_time

                            if (current_time - bad_posture_start_time) > BAD_POSTURE_TIME_LIMIT:
                                is_actively_alerting = True
                                cv2.putText(frame, "PLEASE FIX POSTURE!", (20, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
                                if current_time - last_beep_time > 2.0:
                                    winsound.Beep(1000, 200)
                                    last_beep_time = current_time
                        else:
                            status = "GOOD POSTURE"
                            color = (0, 255, 0)
                            bad_posture_start_time = None

                        total_monitored_frames += 1
                        if not is_actively_alerting:
                            good_posture_frames += 1

                        # הגנה מפני חלוקה באפס לפני שהצטברו פריימים
                        daily_success_percentage = (good_posture_frames / total_monitored_frames) * 100 if total_monitored_frames > 0 else 0.0

                        cv2.putText(frame, f"User: {current_user} | Neck: {avg_score:.1f}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                        cv2.putText(frame, status, (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
                        cv2.putText(frame, f"Daily Score: {daily_success_percentage:.1f}% Good", (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)
                        
                        # הוספת תצוגת הרגישות הנוכחית על המסך
                        cv2.putText(frame, f"Tolerance: {POSTURE_TOLERANCE:.1f} (Press '+' to make it easier, '-' to make it harder)", (20, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow('SmartPosture AI', frame)

        # === ניהול מקלדת מתקדם ===
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
            
        # מקש C לכיול
        elif key == ord('c') and not is_calibrated and current_raw_score is not None and current_pitch_score is not None:
            calibration_scores.append(current_raw_score)
            calibration_pitch.append(current_pitch_score)
            winsound.Beep(1500, 100)

            if len(calibration_scores) >= REQUIRED_CALIBRATION_FRAMES:
                personal_baseline = sum(calibration_scores) / len(calibration_scores)
                dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
                personal_pitch_baseline = sum(calibration_pitch) / len(calibration_pitch)
                dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE

                is_calibrated = True
                profile_manager.save_profile(current_user, personal_baseline, personal_pitch_baseline)
                winsound.Beep(800, 200)
                winsound.Beep(1200, 400) 
                
        # מקש R לאיפוס פרופיל(לכייל מחדש)
        elif key == ord('r') and is_calibrated:
            is_calibrated = False
            calibration_scores.clear()
            calibration_pitch.clear()
            bad_posture_start_time = None
            total_monitored_frames = 0
            good_posture_frames = 0
            
        # התיקון החדש: מקש '+' להגדלת הסובלנות(סלחני יותר)
        elif key == ord('+') or key == ord('='):
            if is_calibrated:
                POSTURE_TOLERANCE += 1.0
                PITCH_TOLERANCE += 1.0
                dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
                dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE
                winsound.Beep(1500, 50)
                
        # התיקון החדש: מקש '-' להקטנת הסובלנות(קשוח יותר)
        elif key == ord('-'):
            if is_calibrated:
                POSTURE_TOLERANCE -= 1.0
                PITCH_TOLERANCE -= 1.0
                dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
                dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE
                winsound.Beep(1000, 50)

cap.release()
cv2.destroyAllWindows()