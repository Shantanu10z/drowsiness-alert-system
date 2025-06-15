import cv2
import numpy as np
import dlib
import time
import argparse
import pygame
import serial
from imutils import face_utils
from scipy.spatial import distance as dist
from tkinter import Tk, Label, StringVar, Button, Frame
from PIL import Image, ImageTk

# Alarm setup
pygame.mixer.init()
ALARM_ACTIVE = False

def play_alarm(path):
    global ALARM_ACTIVE
    if not ALARM_ACTIVE:
        pygame.mixer.music.load(path)
        pygame.mixer.music.play(-1)
        ALARM_ACTIVE = True

def stop_alarm():
    global ALARM_ACTIVE
    if ALARM_ACTIVE:
        pygame.mixer.music.stop()
        ALARM_ACTIVE = False

def eye_aspect_ratio(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

def final_ear(shape):
    (lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
    leftEye = shape[lStart:lEnd]
    rightEye = shape[rStart:rEnd]
    return (eye_aspect_ratio(leftEye) + eye_aspect_ratio(rightEye)) / 2.0, leftEye, rightEye

def lip_distance(shape):
    top = np.concatenate((shape[50:53], shape[61:64]))
    bottom = np.concatenate((shape[56:59], shape[65:68]))
    return abs(np.mean(top, axis=0)[1] - np.mean(bottom, axis=0)[1])

# Args
ap = argparse.ArgumentParser()
ap.add_argument("-a", "--alarm", type=str, default="Alert.wav")
args = vars(ap.parse_args())

# Connect Arduino
try:
    arduino = serial.Serial('COM5', 9600, timeout=1)
    time.sleep(2)  # Wait for Arduino to initialize
except Exception as e:
    print(f"[ERROR] Arduino not connected: {e}")
    arduino = None

# Constants
EYE_AR_THRESH = 0.3
YAWN_THRESH = 18.5
GRACE_PERIOD = 2
ARDUINO_TRIGGER_DELAY = 3

# State variables
eye_timer_start = None
no_face_timer_start = None
arduino_trigger_time = None
drowsy = False
drowsiness_count = 0
detection_active = False
alert_triggered = False

# Detector setup
cap = cv2.VideoCapture(0)
detector = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")

# GUI
root = Tk()
root.title("Drowsiness Detection")

frame_label = Label(root)
frame_label.pack()

ear_text = StringVar(value="EAR: --")
yawn_text = StringVar(value="YAWN: --")
status_text = StringVar()
drowsy_text = StringVar(value="Drowsiness Detected: 0")

Label(root, textvariable=ear_text, font=("Helvetica", 12)).pack()
Label(root, textvariable=yawn_text, font=("Helvetica", 12)).pack()
Label(root, textvariable=drowsy_text, font=("Helvetica", 12)).pack()
Label(root, textvariable=status_text, font=("Helvetica", 14, "bold"), fg="red").pack()

button_frame = Frame(root)
button_frame.pack(pady=12)

def start_detection():
    global detection_active
    detection_active = True
    status_text.set("")

def stop_detection():
    global detection_active, drowsy, alert_triggered
    detection_active = False
    drowsy = False
    alert_triggered = False
    stop_alarm()
    if arduino:
        arduino.write(b"stop\n")
    status_text.set("Detection Paused")

Button(button_frame, text="▶ Start Detection", command=start_detection, width=18).pack(side="left", padx=10)
Button(button_frame, text="⏹ Stop Detection", command=stop_detection, width=18).pack(side="left", padx=10)

def update():
    global eye_timer_start, no_face_timer_start, arduino_trigger_time
    global drowsiness_count, drowsy, alert_triggered

    ret, frame = cap.read()
    if not ret:
        root.after(10, update)
        return

    frame = cv2.resize(frame, (640, 480))
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rects = detector.detectMultiScale(gray, 1.1, 5)
    current_time = time.time()
    ear, distance = 0, 0
    face_detected = len(rects) > 0

    if detection_active:
        if face_detected:
            no_face_timer_start = None
            x, y, w, h = rects[0]
            rect = dlib.rectangle(int(x), int(y), int(x + w), int(y + h))
            shape = predictor(gray, rect)
            shape = face_utils.shape_to_np(shape)

            ear, leftEye, rightEye = final_ear(shape)
            distance = lip_distance(shape)

            cv2.drawContours(frame, [cv2.convexHull(leftEye)], -1, (0, 255, 0), 1)
            cv2.drawContours(frame, [cv2.convexHull(rightEye)], -1, (0, 255, 0), 1)
            cv2.drawContours(frame, [shape[48:60]], -1, (0, 255, 0), 1)

            if ear < EYE_AR_THRESH or distance > YAWN_THRESH:
                if eye_timer_start is None:
                    eye_timer_start = current_time
                elif current_time - eye_timer_start >= GRACE_PERIOD:
                    drowsy = True
                    if arduino_trigger_time is None:
                        arduino_trigger_time = current_time
            else:
                if drowsy and ear >= EYE_AR_THRESH:
                    stop_alarm()
                    if arduino:
                        arduino.write(b"stop\n")
                    drowsy = False
                    alert_triggered = False
                eye_timer_start = None
        else:
            if no_face_timer_start is None:
                no_face_timer_start = current_time
            elif current_time - no_face_timer_start >= GRACE_PERIOD:
                drowsy = True
                if arduino_trigger_time is None:
                    arduino_trigger_time = current_time

        if drowsy:
            if not alert_triggered:
                drowsiness_count += 1
                alert_triggered = True
            play_alarm(args["alarm"])
            if arduino and arduino_trigger_time and time.time() - arduino_trigger_time >= ARDUINO_TRIGGER_DELAY:
                arduino.write(b"start\n")
            status_text.set("No Face Detected!" if not face_detected else "DROWSINESS ALERT!")
        else:
            arduino_trigger_time = None
            status_text.set("")

        ear_text.set(f"EAR: {ear:.2f}" if face_detected else "EAR: --")
        yawn_text.set(f"YAWN: {distance:.2f}" if face_detected else "YAWN: --")
        drowsy_text.set(f"Drowsiness Detected: {drowsiness_count}")

    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(img)
    imgtk = ImageTk.PhotoImage(image=img)
    frame_label.imgtk = imgtk
    frame_label.configure(image=imgtk)
    root.after(10, update)

update()
root.mainloop()
cap.release()
cv2.destroyAllWindows()
if arduino:
    arduino.close()
