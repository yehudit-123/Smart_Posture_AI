# ==========================================
# יבוא ספריות (Imports)
# ==========================================
import cv2                 # ספריית הראייה הממוחשבת (עיבוד תמונה ווידאו)
import mediapipe as mp     # הספרייה של גוגל לזיהוי שלד ונקודות ציון על הגוף
import time                # לניהול זמנים (טיימרים להשהיה)
import collections         # לשימוש בתור (deque) כדי לשמור היסטוריית ציונים ולחשב ממוצעים
import winsound            # להשמעת צפצופים (דרך מערכת ההפעלה של ווינדוס)
import keyboard            # לקליטת לחיצות מקלדת ברקע (גם כשהתוכנה ממוזערת)
from plyer import notification  # להקפצת הודעות רשמיות של מערכת ההפעלה ווינדוס בצד המסך
import threading           # כדי להריץ פעולות במקביל (כמו צפצוף) בלי לעצור את שאר התוכנית

# ספריות לניהול ממשק משתמש וגרפיקה (עבור חלון הפינגווין)
import tkinter as tk
from PIL import Image, ImageTk
import os

# יבוא קבצי הלוגיקה החיצוניים שכתבנו כדי לשמור על קוד נקי
import posture_math      
import profile_manager  

# ==========================================
# שלב 1: התחברות משתמש (Login & Profile)
# ==========================================
print("=======================================")
print("  SmartPosture AI - BACKGROUND MODE    ")
print("=======================================")
# קליטת שם המשתמש והפיכתו לאות רישית (Capitalized)
current_user = input("Please enter your name to login: ").strip().title()

# בדיקה מול קובץ ה-JSON האם המשתמש כבר קיים במערכת
profile = profile_manager.get_profile(current_user)

# הגדרות סובלנות - כמה מותר לחרוג מהיציבה האידיאלית לפני שמקבלים אזהרה
POSTURE_TOLERANCE = 8.0     # חריגה מותרת לצוואר (Tech Neck)
PITCH_TOLERANCE = 12.0      # חריגה מותרת לזווית ראש (מבט למטה)
ASYMMETRY_THRESHOLD = 7.0   # חריגה מותרת לנטיית כתפיים (במעלות)

if profile:
    # המשתמש מוכר -> טוענים את נתוני הכיול האישיים שלו
    print(f"\nWelcome back, {current_user}! Profile loaded successfully.")
    personal_baseline = profile["posture_baseline"]
    personal_pitch_baseline = profile["pitch_baseline"]
    
    # חישוב סף ההתראה הדינמי: קו הבסיס האישי + הסובלנות המותרת
    dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
    dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE
    is_calibrated = True
else:
    # משתמש חדש -> מאפסים נתונים וממתינים לכיול
    print(f"\nHello {current_user}! You are a new user. Please sit straight and press Ctrl+Alt+C 5 times.")
    personal_baseline = 0.0
    dynamic_threshold = 0.0
    dynamic_pitch_threshold = 0.0
    is_calibrated = False

# הדפסת קיצורי המקלדת למשתמש
print("\n--- GLOBAL SHORTCUTS ---")
print("Ctrl + Alt + C : Calibrate posture")
print("Ctrl + Alt + R : Reset profile")
print("Ctrl + Alt + = : Make tolerance EASIER (Plus key)")
print("Ctrl + Alt + - : Make tolerance HARDER (Minus key)")
print("Ctrl + Alt + Q : Quit application")
print("------------------------\n")

# ==========================================
# שלב 2: הגדרת חיית המחמד הווירטואלית (הפינגווין הצף)
# ==========================================
root = tk.Tk()
root.overrideredirect(True)                      # הסרת מסגרת החלון (כפתורי סגירה, הגדלה וכו')
root.wm_attributes("-topmost", True)             # הגדרה שהחלון ירחף תמיד מעל כל שאר החלונות
root.wm_attributes("-transparentcolor", "black") # הופך את הרקע השחור לשקוף לחלוטין
root.configure(bg='black')

screen_width = root.winfo_screenwidth()          # קבלת רוחב מסך המחשב
screen_height = root.winfo_screenheight()        # קבלת גובה מסך המחשב

penguin_width = 120    # רוחב תמונת הפינגווין
penguin_height = 160   # גובה תמונת הפינגווין

penguin_x = 0
penguin_y = screen_height - (penguin_height + 60) # מיקום בציר Y: תחתית המסך מינוס גובה שורת המשימות
penguin_speed = 8                                 # מהירות התנועה של הפינגווין

# טעינת התמונה מקובץ במידה והוא קיים
if os.path.exists("penguin.png"):
    img = Image.open("penguin.png")
    img = img.resize((penguin_width, penguin_height), Image.Resampling.LANCZOS) # שינוי גודל איכותי
    penguin_photo = ImageTk.PhotoImage(img)
    label = tk.Label(root, image=penguin_photo, bg='black')
    label.pack()
else:
    print("\n[WARNING] 'penguin.png' not found in the folder. The virtual pet won't appear!")

root.withdraw() # מסתירים את חלון הפינגווין עד שהמשתמש יושב לא טוב

# ==========================================
# שלב 3: אתחול מונים והגדרות מערכת למעקב
# ==========================================
# תורים לשמירת היסטוריית הציונים האחרונים כדי לעשות ממוצע (מונע "קפיצות" ורעשים)
SCORE_HISTORY_LENGTH = 15
score_history = collections.deque(maxlen=SCORE_HISTORY_LENGTH)
asymmetry_history = collections.deque(maxlen=SCORE_HISTORY_LENGTH)
pitch_history = collections.deque(maxlen=SCORE_HISTORY_LENGTH)

REQUIRED_CALIBRATION_FRAMES = 5 # מספר הדגימות הנדרשות לכיול
calibration_scores = []
calibration_pitch = []

BAD_POSTURE_TIME_LIMIT = 10.0 # כמה שניות מותר לשבת עקום לפני שמצפצפים
bad_posture_start_time = None 
last_beep_time = 0            
has_shown_toast = False       # מונע הקפצת הודעות כפולות בווינדוס

total_monitored_frames = 0    # סך כל פריימי הווידאו שנבדקו היום
good_posture_frames = 0       # מתוכם: כמה פריימים המשתמש ישב נכון
last_key_time = 0             # השהייה לקליטת מקלדת כדי לא לקלוט לחיצה בודדת כמה פעמים ברצף

# ==========================================
# שלב 4: הגדרת מודל ה-AI הכבד והפעלת המצלמה
# ==========================================
options = mp.tasks.vision.PoseLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path='pose_landmarker_heavy.task'),
    running_mode=mp.tasks.vision.RunningMode.VIDEO, # אומרים למודל שאנחנו מעבדים וידאו ולא תמונה בודדת
    num_poses=1, # מחפשים רק אדם אחד בפריים
    min_pose_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

cap = cv2.VideoCapture(0) # פתיחת מצלמת הרשת הראשונה (0)
if not cap.isOpened(): exit()

print("Camera is active in the background. Monitoring started...\n")

# פתיחת תהליך המודל
with mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker:
    start_time = time.time()

    # ==========================================
    # שלב 5: לולאת הוידאו המרכזית (רצה כל הזמן)
    # ==========================================
    while True:
        ret, frame = cap.read() # קריאת פריים בודד מהמצלמה
        if not ret: break

        # היפוך מראה של הפריים והמרת צבעים מ-BGR ל-RGB (כי mediapipe דורש RGB)
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # העברת הפריים למודל וקבלת מיקומי השלד חזרה
        timestamp_ms = int((time.time() - start_time) * 1000)
        results = landmarker.detect_for_video(mp_image, timestamp_ms)

        current_raw_score = None
        current_pitch_score = None
        current_time = time.time()

        # אם המודל מצא גוף בתמונה
        if results.pose_landmarks:
            for landmarks in results.pose_landmarks:
                # שליפת הנקודות הרלוונטיות (אף, אוזניים, כתפיים)
                nose = landmarks[0]
                right_ear = landmarks[8]
                left_ear = landmarks[7]
                right_shoulder = landmarks[12]
                left_shoulder = landmarks[11]
                
                # מוודאים שכל הנקודות הדרושות נמצאות בבירור בתוך המסגרת
                if nose.visibility > 0.5 and right_ear.visibility > 0.5 and left_ear.visibility > 0.5 and right_shoulder.visibility > 0.5 and left_shoulder.visibility > 0.5:
                    
                    # קריאה לקבצי המתמטיקה שלנו כדי לחשב ציונים
                    current_raw_score = posture_math.get_forward_head_posture(right_ear, right_shoulder, left_shoulder) * 100
                    score_history.append(current_raw_score)
                    avg_score = sum(score_history) / len(score_history) # ממוצע צוואר קדימה
                    
                    current_asymmetry = posture_math.get_shoulder_asymmetry(right_shoulder, left_shoulder)
                    asymmetry_history.append(current_asymmetry)
                    avg_asymmetry = sum(asymmetry_history) / len(asymmetry_history) # ממוצע נטיית כתפיים
                    
                    current_pitch_score = posture_math.get_head_pitch(nose, right_ear, left_ear, right_shoulder, left_shoulder) * 100
                    pitch_history.append(current_pitch_score)
                    avg_pitch = sum(pitch_history) / len(pitch_history) # ממוצע זווית ראש מטה

                    # אם המשתמש מוגדר ומכויל, מתחילים לנטר
                    if is_calibrated:
                        # בדיקה האם יש חריגה באחד המדדים
                        is_tech_neck = avg_score > dynamic_threshold
                        is_uneven = avg_asymmetry > ASYMMETRY_THRESHOLD
                        is_looking_down = avg_pitch > dynamic_pitch_threshold
                        
                        is_actively_alerting = False
                        
                        # --- טיפול ביציבה שגויה ---
                        if is_tech_neck or is_uneven or is_looking_down:
                            # קביעת טקסט ההודעה לפי הבעיה שנמצאה
                            if is_looking_down: status_msg = "Your screen seems too low. Please look up!"
                            elif is_tech_neck: status_msg = "Tech Neck detected. Please sit back!"
                            else: status_msg = "Uneven Shoulders. Try to sit symmetrically."
                            
                            if bad_posture_start_time is None: 
                                bad_posture_start_time = current_time # התחלת מדידת ה"טיימר הרע"
                                
                            # אם הזמן "הרע" חצה את הסף המותר (10 שניות)
                            if (current_time - bad_posture_start_time) > BAD_POSTURE_TIME_LIMIT:
                                is_actively_alerting = True
                                
                                # מציגים את הפינגווין
                                root.deiconify() 
                                penguin_x += penguin_speed
                                
                                # החלפת כיוון הפינגווין כשהוא פוגע בקצוות המסך
                                if penguin_x > screen_width - penguin_width or penguin_x < 0:
                                    penguin_speed *= -1 
                                
                                # עדכון הפינגווין על המסך
                                root.geometry(f"{penguin_width}x{penguin_height}+{penguin_x}+{penguin_y}")
                                
                                # השמעת צפצוף בתהליכון נפרד (Thread) כדי לא לתקוע את התוכנית
                                if current_time - last_beep_time > 2.0:
                                    threading.Thread(target=lambda: winsound.Beep(1000, 200), daemon=True).start()
                                    last_beep_time = current_time
                                    
                                # הקפצת התראת מערכת הפעלה (פעם אחת בלבד)
                                if not has_shown_toast:
                                    try:
                                        notification.notify(
                                            title="SmartPosture AI Alert",
                                            message=status_msg,
                                            app_name="SmartPosture",
                                            timeout=4
                                        )
                                    except:
                                        pass 
                                    has_shown_toast = True
                        # --- טיפול ביציבה תקינה ---
                        else:
                            bad_posture_start_time = None
                            has_shown_toast = False
                            root.withdraw() # העלמת הפינגווין

                        # עדכון הסטטיסטיקה היומית לגיימיפיקציה (החלקת רעשים)
                        total_monitored_frames += 1
                        if not is_actively_alerting:
                            good_posture_frames += 1

        root.update() # עדכון ממשק חלון הפינגווין כדי למנוע קפיאה של החלון

        # ==========================================
        # שלב 6: ניהול קיצורי מקלדת (Hotkeys)
        # ==========================================
        if current_time - last_key_time > 0.4:
            
            # יציאה מהתוכנה וסיכום
            if keyboard.is_pressed('ctrl+alt+q'):
                print("\nPreparing to quit. Calculating daily summary...")
                
                if total_monitored_frames > 0:
                    final_percentage = (good_posture_frames / total_monitored_frames) * 100
                    summary_msg = f"Session complete! You maintained good posture {final_percentage:.1f}% of the time today. Great job!"
                else:
                    summary_msg = "Session ended before enough posture data was collected."
                
                try:
                    notification.notify(title="Daily Posture Summary", message=summary_msg, app_name="SmartPosture", timeout=5)
                    time.sleep(5) 
                except:
                    pass
                
                print("Quitting SmartPosture AI. Have a healthy day!")
                break
                
            # כיול ראשוני
            elif keyboard.is_pressed('ctrl+alt+c') and not is_calibrated and current_raw_score is not None:
                calibration_scores.append(current_raw_score)
                calibration_pitch.append(current_pitch_score)
                threading.Thread(target=lambda: winsound.Beep(1500, 100), daemon=True).start() 
                print(f"Captured calibration {len(calibration_scores)}/{REQUIRED_CALIBRATION_FRAMES}")
                
                # אם אספנו מספיק דגימות, מחשבים קו בסיס ממוצע ושומרים במסד הנתונים
                if len(calibration_scores) >= REQUIRED_CALIBRATION_FRAMES:
                    personal_baseline = sum(calibration_scores) / len(calibration_scores)
                    dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
                    personal_pitch_baseline = sum(calibration_pitch) / len(calibration_pitch)
                    dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE
                    
                    is_calibrated = True
                    profile_manager.save_profile(current_user, personal_baseline, personal_pitch_baseline)
                    threading.Thread(target=lambda: (winsound.Beep(800, 200), winsound.Beep(1200, 400)), daemon=True).start()
                    print("Calibration Complete! Running silently...")
                last_key_time = current_time
                    
            # מחיקת נתוני משתמש וכיול מחדש
            elif keyboard.is_pressed('ctrl+alt+r') and is_calibrated:
                is_calibrated = False
                calibration_scores.clear()
                calibration_pitch.clear()
                bad_posture_start_time = None
                has_shown_toast = False
                total_monitored_frames = 0  
                good_posture_frames = 0
                threading.Thread(target=lambda: winsound.Beep(500, 300), daemon=True).start()
                print("\nProfile Reset. Please press Ctrl+Alt+C 5 times to recalibrate.")
                last_key_time = current_time
                
            # הגדלת סובלנות - הופך את המערכת לפחות קפדנית
            elif keyboard.is_pressed('ctrl+alt+='):
                if is_calibrated:
                    POSTURE_TOLERANCE += 1.0
                    PITCH_TOLERANCE += 1.0
                    dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
                    dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE
                    threading.Thread(target=lambda: winsound.Beep(1500, 50), daemon=True).start()
                    print(f"Tolerance made EASIER. Current Tolerance: {POSTURE_TOLERANCE}")
                last_key_time = current_time
                    
            # הקטנת סובלנות - הופך את המערכת ליותר נוקשה
            elif keyboard.is_pressed('ctrl+alt+-'):
                if is_calibrated:
                    POSTURE_TOLERANCE -= 1.0
                    PITCH_TOLERANCE -= 1.0
                    dynamic_threshold = personal_baseline + POSTURE_TOLERANCE
                    dynamic_pitch_threshold = personal_pitch_baseline + PITCH_TOLERANCE
                    threading.Thread(target=lambda: winsound.Beep(1000, 50), daemon=True).start()
                    print(f"Tolerance made HARDER. Current Tolerance: {POSTURE_TOLERANCE}")
                last_key_time = current_time

# סגירת המצלמה והורדת החלונות לפני יציאה סופית מהתוכנית
cap.release()
root.destroy()