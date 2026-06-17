import math

def get_forward_head_posture(ear, right_shoulder, left_shoulder):
    """חישוב רכינת צוואר קדימה מנורמל לרוחב כתפיים"""
    shoulder_width = abs(left_shoulder.x - right_shoulder.x)
    if shoulder_width < 0.01: shoulder_width = 0.01
    depth_difference = right_shoulder.z - ear.z
    return depth_difference / shoulder_width

def get_shoulder_asymmetry(right_shoulder, left_shoulder):
    """חישוב חוסר סימטריה בכתפיים במעלות"""
    dy = left_shoulder.y - right_shoulder.y
    dx = left_shoulder.x - right_shoulder.x
    return math.degrees(math.atan2(abs(dy), abs(dx)))

def get_head_pitch(nose, right_ear, left_ear, right_shoulder, left_shoulder):
    """חישוב זווית מבט מטה מנורמל לרוחב כתפיים"""
    shoulder_width = abs(left_shoulder.x - right_shoulder.x)
    if shoulder_width < 0.01: shoulder_width = 0.01
    mid_ear_y = (right_ear.y + left_ear.y) / 2.0
    pitch_difference = nose.y - mid_ear_y
    return pitch_difference / shoulder_width