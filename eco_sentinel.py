# -*- coding: utf-8 -*-
from ultralytics import YOLO
import cv2
from flask import Flask, Response, render_template_string, jsonify
import threading
import time
import os
import serial
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from collections import defaultdict

os.environ["OMP_NUM_THREADS"] = "4"

app = Flask(__name__)
model = YOLO("/home/securitybusters/eco_friendly/litter12_ncnn_model", task="detect")

# ── EMAIL CONFIG ──────────────────────────────────────────────
SENDER_EMAIL = "rdsmcorp@gmail.com"
SENDER_PASSWORD = "PASTE_YOUR_APP_PASSWORD_HERE"
RECEIVER_EMAIL = "pingpranavb@gmail.com"

REPORTS_DIR = "/home/securitybusters/eco_friendly/error_reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

cap = None
for i in range(5):
    for index in range(5):
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"Camera found at index {index}")
                break
        cap.release()
    if cap and cap.isOpened():
        break
    time.sleep(2)

if not cap or not cap.isOpened():
    print("Camera not working")
    exit()

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
cap.set(cv2.CAP_PROP_FPS, 120)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

arduino = None
try:
    arduino = serial.Serial('/dev/serial0', 9600, timeout=1)
    time.sleep(2)
    print("Arduino connected")
except Exception as e:
    print(f"Arduino not found: {e}")

mq135_value = 0
mq2_value = 0
temperature = 0
humidity = 0

def read_arduino():
    global mq135_value, mq2_value, temperature, humidity
    if arduino is None:
        return
    while True:
        try:
            line = arduino.readline().decode('utf-8').strip()
            if line.startswith("DATA,"):
                parts = line.split(",")
                if len(parts) == 5:
                    mq135_value = int(parts[1])
                    mq2_value   = int(parts[2])
                    temperature = float(parts[3])
                    humidity    = float(parts[4])
        except:
            pass

threading.Thread(target=read_arduino, daemon=True).start()

def send_arduino(cmd):
    if arduino is not None:
        try:
            arduino.write((cmd + "\n").encode())
        except:
            pass

# ── GLOBALS ───────────────────────────────────────────────────
latest_frame = None
lock = threading.Lock()
fps = 0
detection_count = 0
eap_score = 0
priority = "LOW"
recommendation = "Area Clean"
session_active = False
session_start = None
eap_history = []
detection_history = []
final_report = None
waste_summary = {}
session_waste_totals = defaultdict(int)
reported_errors = []

WASTE_COLORS = {
    'cardboard': (139, 69,  19),
    'glass':     (0,   255, 255),
    'metal':     (192, 192, 192),
    'other':     (128, 0,   128),
    'paper':     (255, 165, 0),
    'plastic':   (0,   0,   255),
}

# ── EAP ──────────────────────────────────────────────────────

def get_object_score(count):
    if count == 0:   return 0
    elif count == 1: return 10
    elif count == 2: return 15
    elif count == 3: return 20
    elif count == 4: return 25
    else:            return 30

def get_coverage_score(ground_boxes, frame_w, frame_h):
    if not ground_boxes: return 0
    total_area = 0
    frame_area = frame_w * frame_h
    for (x1, y1, x2, y2) in ground_boxes:
        total_area += (x2 - x1) * (y2 - y1)
    coverage = (total_area / frame_area) * 100
    if coverage < 5:    return 5
    elif coverage < 15: return 10
    elif coverage < 30: return 20
    else:               return 30

def get_air_score(mq135):
    if mq135 < 200:   return 0
    elif mq135 < 400: return 5
    elif mq135 < 600: return 10
    elif mq135 < 800: return 15
    else:             return 20

def get_smoke_score(mq2):
    if mq2 < 200:   return 0
    elif mq2 < 400: return 5
    elif mq2 < 600: return 8
    elif mq2 < 800: return 10
    else:           return 10

def get_priority(score):
    if score >= 70:   return "CRITICAL"
    elif score >= 50: return "HIGH"
    elif score >= 30: return "MEDIUM"
    else:             return "LOW"

def get_recommendation(score):
    if score >= 70:   return "Immediate Cleanup Required"
    elif score >= 50: return "Cleanup Soon"
    elif score >= 30: return "Monitor Area"
    else:             return "Area Clean"

def get_color(p):
    if p == "CRITICAL": return "#ff3b3b"
    elif p == "HIGH":   return "#ff9f1c"
    elif p == "MEDIUM": return "#ffd60a"
    else:               return "#39ff6a"

def get_air_label(mq135):
    if mq135 < 200:   return "Good"
    elif mq135 < 400: return "Moderate"
    elif mq135 < 600: return "Unhealthy"
    elif mq135 < 800: return "Poor"
    else:             return "Hazardous"

def get_smoke_label(mq2):
    if mq2 < 200:   return "Clear"
    elif mq2 < 400: return "Mild"
    elif mq2 < 600: return "Elevated"
    elif mq2 < 800: return "High"
    else:           return "Dangerous"

def generate_report():
    global final_report
    if not eap_history: return
    avg_eap = round(sum(eap_history) / len(eap_history), 1)
    max_eap = max(eap_history)
    min_eap = min(eap_history)
    avg_det = round(sum(detection_history) / len(detection_history), 1)
    max_det = max(detection_history)
    duration = round(time.time() - session_start, 1)
    p = get_priority(avg_eap)
    final_report = {
        'avg_eap': avg_eap, 'max_eap': max_eap, 'min_eap': min_eap,
        'avg_detections': avg_det, 'max_detections': max_det,
        'duration': duration, 'priority': p,
        'recommendation': get_recommendation(avg_eap),
        'color': get_color(p),
        'timestamp': datetime.now().strftime("%d %b %Y, %H:%M:%S"),
        'samples': len(eap_history),
        'waste_totals': dict(session_waste_totals),
        'air_label': get_air_label(mq135_value),
        'smoke_label': get_smoke_label(mq2_value),
        'temperature': temperature,
        'humidity': humidity,
        'mq135': mq135_value,
        'mq2': mq2_value,
        'error_reports': len(reported_errors),
    }

def send_email(report):
    try:
        msg = MIMEMultipart("alternative")
        msg['Subject'] = f"ECO-SENTINEL Area Report — {report['timestamp']}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL

        waste_rows = ""
        for category, count in sorted(report['waste_totals'].items()):
            waste_rows += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #1a2a1a;color:#888;">{category.capitalize()}</td>
                <td style="padding:8px;border-bottom:1px solid #1a2a1a;text-align:right;color:#39ff6a;">{count} item(s)</td>
            </tr>"""

        if not waste_rows:
            waste_rows = '<tr><td colspan="2" style="padding:8px;color:#888;text-align:center;">No waste detected</td></tr>'

        error_section = ""
        if reported_errors:
            error_rows = ""
            for err in reported_errors:
                error_rows += f"<tr><td style='padding:8px;color:#888;border-bottom:1px solid #1a2a1a;'>{err['timestamp']}</td></tr>"
            error_section = f"""
            <div style="background:#0d1117;border:1px solid #1f2730;padding:20px;margin-bottom:20px;">
                <p style="color:#ff9f1c;font-size:0.7em;letter-spacing:3px;margin:0 0 12px;">FLAGGED DETECTION ERRORS ({len(reported_errors)})</p>
                <table style="width:100%;border-collapse:collapse;">{error_rows}</table>
                <p style="color:#5a6472;font-size:0.7em;margin-top:10px;">Snapshots saved locally for review and future model retraining</p>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head></head>
        <body style="background:#0a0a0a;color:#d4d8dd;font-family:Courier New,monospace;padding:30px;">

        <div style="max-width:600px;margin:0 auto;">

        <div style="background:#0d1117;border:1px solid #1f2730;padding:20px;margin-bottom:20px;">
            <h1 style="color:#39ff6a;margin:0;font-size:1.4em;letter-spacing:4px;">🌿 ECO-SENTINEL</h1>
            <p style="color:#5a6472;margin:5px 0 0;font-size:0.8em;letter-spacing:2px;">MUNICIPAL ENVIRONMENTAL ASSISTANCE SYSTEM</p>
        </div>

        <div style="background:#0d1117;border:1px solid {report['color']};padding:20px;margin-bottom:20px;text-align:center;">
            <p style="color:#5a6472;font-size:0.7em;letter-spacing:3px;margin:0 0 10px;">AREA ASSESSMENT REPORT</p>
            <div style="font-size:3.5em;font-weight:bold;color:{report['color']};">{report['avg_eap']}</div>
            <div style="color:#5a6472;font-size:0.8em;">out of 100</div>
            <div style="color:{report['color']};font-size:0.9em;letter-spacing:3px;margin-top:8px;">PRIORITY: {report['priority']}</div>
            <div style="color:#5a6472;font-size:0.8em;margin-top:5px;">{report['recommendation']}</div>
        </div>

        <div style="background:#0d1117;border:1px solid #1f2730;padding:20px;margin-bottom:20px;">
            <p style="color:#39ff6a;font-size:0.7em;letter-spacing:3px;margin:0 0 12px;">WASTE DETECTED BY CATEGORY</p>
            <table style="width:100%;border-collapse:collapse;">
                {waste_rows}
                <tr>
                    <td style="padding:8px;color:#39ff6a;font-weight:bold;">Total items</td>
                    <td style="padding:8px;text-align:right;color:#39ff6a;font-weight:bold;">{sum(report['waste_totals'].values())} item(s)</td>
                </tr>
            </table>
        </div>

        <div style="background:#0d1117;border:1px solid #1f2730;padding:20px;margin-bottom:20px;">
            <p style="color:#39ff6a;font-size:0.7em;letter-spacing:3px;margin:0 0 12px;">ENVIRONMENTAL READINGS</p>
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:8px;border-bottom:1px solid #1a2a1a;color:#888;">Air Quality (MQ-135)</td><td style="padding:8px;border-bottom:1px solid #1a2a1a;text-align:right;color:#d4d8dd;">{report['mq135']} — {report['air_label']}</td></tr>
                <tr><td style="padding:8px;border-bottom:1px solid #1a2a1a;color:#888;">Smoke Level (MQ-2)</td><td style="padding:8px;border-bottom:1px solid #1a2a1a;text-align:right;color:#d4d8dd;">{report['mq2']} — {report['smoke_label']}</td></tr>
                <tr><td style="padding:8px;border-bottom:1px solid #1a2a1a;color:#888;">Temperature</td><td style="padding:8px;border-bottom:1px solid #1a2a1a;text-align:right;color:#d4d8dd;">{report['temperature']}°C</td></tr>
                <tr><td style="padding:8px;color:#888;">Humidity</td><td style="padding:8px;text-align:right;color:#d4d8dd;">{report['humidity']}% RH</td></tr>
            </table>
        </div>

        {error_section}

        <div style="background:#0d1117;border:1px solid #1f2730;padding:20px;margin-bottom:20px;">
            <p style="color:#39ff6a;font-size:0.7em;letter-spacing:3px;margin:0 0 12px;">SESSION DETAILS</p>
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:8px;border-bottom:1px solid #1a2a1a;color:#888;">Timestamp</td><td style="padding:8px;border-bottom:1px solid #1a2a1a;text-align:right;color:#d4d8dd;">{report['timestamp']}</td></tr>
                <tr><td style="padding:8px;border-bottom:1px solid #1a2a1a;color:#888;">Duration</td><td style="padding:8px;border-bottom:1px solid #1a2a1a;text-align:right;color:#d4d8dd;">{report['duration']}s</td></tr>
                <tr><td style="padding:8px;border-bottom:1px solid #1a2a1a;color:#888;">Samples taken</td><td style="padding:8px;border-bottom:1px solid #1a2a1a;text-align:right;color:#d4d8dd;">{report['samples']}</td></tr>
                <tr><td style="padding:8px;border-bottom:1px solid #1a2a1a;color:#888;">Max EAP</td><td style="padding:8px;border-bottom:1px solid #1a2a1a;text-align:right;color:#d4d8dd;">{report['max_eap']}</td></tr>
                <tr><td style="padding:8px;color:#888;">Min EAP</td><td style="padding:8px;text-align:right;color:#d4d8dd;">{report['min_eap']}</td></tr>
            </table>
        </div>

        <div style="border:1px solid #1f2730;padding:12px;text-align:center;">
            <p style="color:#5a6472;font-size:0.75em;margin:0;">Sent automatically by ECO-SENTINEL AI Module</p>
            <p style="color:#5a6472;font-size:0.7em;margin:4px 0 0;">Municipal Environmental Assistance System</p>
        </div>

        </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html, 'html'))
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ── CAMERA ───────────────────────────────────────────────────

def capture_frames():
    global latest_frame
    while True:
        ret, frame = cap.read()
        if ret:
            with lock:
                latest_frame = frame

threading.Thread(target=capture_frames, daemon=True).start()

def generate():
    global fps, detection_count, eap_score, priority, recommendation, waste_summary
    prev_time = time.time()
    while True:
        with lock:
            frame = latest_frame.copy() if latest_frame is not None else None
        if frame is not None:
            h, w = frame.shape[:2]
            results = model.predict(frame, conf=0.25, imgsz=320, verbose=False)
            boxes = results[0].boxes
            annotated = frame.copy()
            ground_boxes = []
            ground_count = 0
            current_waste = {}

            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                label = results[0].names[cls]

                if y1 > h * 0.4:
                    color = WASTE_COLORS.get(label, (0, 0, 255))
                    cv2.rectangle(annotated, (x1,y1), (x2,y2), color, 2)
                    cv2.putText(annotated, f"{label} {conf:.2f}",
                               (x1, y1-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    ground_boxes.append((x1, y1, x2, y2))
                    ground_count += 1
                    current_waste[label] = current_waste.get(label, 0) + 1

                    if session_active:
                        session_waste_totals[label] += 1

            detection_count = ground_count
            waste_summary = current_waste

            O = get_object_score(detection_count)
            C = get_coverage_score(ground_boxes, w, h)
            A = get_air_score(mq135_value)
            S = get_smoke_score(mq2_value)
            eap_score = min(100, O + C + A + S)
            priority = get_priority(eap_score)
            recommendation = get_recommendation(eap_score)

            if session_active:
                eap_history.append(eap_score)
                detection_history.append(detection_count)

            curr_time = time.time()
            fps = 1 / (curr_time - prev_time)
            prev_time = curr_time
            _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 50])
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# ── HTML ──────────────────────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html>
<head>
<title>ECO-SENTINEL</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0b0d10; color: #d4d8dd; font-family: 'Consolas', 'Courier New', monospace; }
.header { background: #11151a; border-bottom: 1px solid #1f2730; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; }
.header h1 { font-size: 1.2em; letter-spacing: 5px; color: #39ff6a; }
.header p { font-size: 0.65em; color: #5a6472; letter-spacing: 2px; margin-top: 3px; }
.header-right { display: flex; align-items: center; gap: 14px; font-size: 0.75em; color: #5a6472; }
.badge { display: flex; align-items: center; gap: 6px; color: #39ff6a; border: 1px solid #1f2730; padding: 4px 10px; border-radius: 3px; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: #39ff6a; }
.main { display: flex; gap: 10px; padding: 10px; }
.camera-section { flex: 2; display: flex; flex-direction: column; gap: 10px; }
.panel { background: #11151a; border: 1px solid #1f2730; border-radius: 3px; }
.panel-header { padding: 8px 14px; border-bottom: 1px solid #1f2730; font-size: 0.65em; letter-spacing: 3px; color: #5a6472; display: flex; justify-content: space-between; align-items: center; }
.live-tag { display: flex; align-items: center; gap: 5px; color: #39ff6a; font-size: 0.9em; }
.camera-feed img { width: 100%; display: block; }
.panel-footer { padding: 7px 14px; border-top: 1px solid #1f2730; font-size: 0.7em; color: #5a6472; display: flex; justify-content: space-between; }
.alert-bar { padding: 10px 14px; font-size: 0.78em; letter-spacing: 2px; font-weight: bold; text-align: center; border-radius: 3px; border: 1px solid; display: none; }
.sensor-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.sensor-card { background: #11151a; border: 1px solid #1f2730; border-radius: 3px; padding: 14px; text-align: center; }
.sensor-label { font-size: 0.6em; letter-spacing: 2px; color: #5a6472; margin-bottom: 8px; }
.sensor-value { font-size: 1.8em; font-weight: bold; color: #39ff6a; }
.sensor-unit { font-size: 0.7em; color: #3a4350; }
.sensor-status { font-size: 0.7em; margin-top: 6px; letter-spacing: 1px; font-weight: bold; }
.waste-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.waste-card { background: #11151a; border: 1px solid #1f2730; border-radius: 3px; padding: 10px; text-align: center; }
.waste-name { font-size: 0.65em; letter-spacing: 2px; color: #5a6472; margin-bottom: 4px; }
.waste-count { font-size: 1.6em; font-weight: bold; }
.sidebar { flex: 1; min-width: 210px; display: flex; flex-direction: column; gap: 10px; }
.eap-panel { background: #11151a; border: 1px solid #1f2730; border-radius: 3px; padding: 16px; text-align: center; }
.eap-label { font-size: 0.62em; letter-spacing: 3px; color: #5a6472; margin-bottom: 8px; }
.eap-num { font-size: 3.4em; font-weight: bold; line-height: 1; color: #39ff6a; }
.eap-of { font-size: 0.78em; color: #3a4350; }
.bar-bg { width: 100%; height: 4px; background: #1a1f26; margin: 10px 0 8px; border-radius: 2px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 2px; transition: width 0.4s, background 0.3s; background: #39ff6a; }
.eap-pri { font-size: 0.78em; letter-spacing: 4px; font-weight: bold; color: #39ff6a; }
.eap-rec { font-size: 0.7em; color: #5a6472; margin-top: 4px; }
.status-panel { background: #11151a; border: 1px solid #1f2730; border-radius: 3px; padding: 12px 14px; }
.status-label { font-size: 0.62em; letter-spacing: 3px; color: #5a6472; margin-bottom: 10px; }
.s-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; font-size: 0.78em; color: #9ba3ad; border-bottom: 1px solid #161a20; }
.s-row:last-child { border-bottom: none; }
.s-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.btn { width: 100%; padding: 11px; font-family: inherit; font-size: 0.72em; letter-spacing: 3px; cursor: pointer; border-radius: 3px; transition: all 0.2s; font-weight: bold; background: transparent; }
.btn-start { border: 1px solid #39ff6a; color: #39ff6a; }
.btn-start:hover { background: #39ff6a; color: #0b0d10; }
.btn-stop { border: 1px solid #ff3b3b; color: #ff3b3b; }
.btn-stop:hover { background: #ff3b3b; color: #0b0d10; }
.btn-redo { border: 1px solid #3ba6ff; color: #3ba6ff; }
.btn-redo:hover { background: #3ba6ff; color: #0b0d10; }
.btn-report { border: 1px solid #ff9f1c; color: #ff9f1c; }
.btn-report:hover { background: #ff9f1c; color: #0b0d10; }
.log-wrap { margin: 0 10px 10px; background: #11151a; border: 1px solid #1f2730; border-radius: 3px; }
.log-hdr { padding: 7px 14px; font-size: 0.62em; letter-spacing: 3px; color: #5a6472; border-bottom: 1px solid #1f2730; }
.log-body { padding: 8px 14px; height: 70px; overflow-y: auto; font-size: 0.72em; }
.l-row { color: #5a6472; padding: 1px 0; }
.l-row span { color: #39ff6a55; margin-right: 8px; }
.report-wrap { margin: 0 10px 10px; background: #11151a; border: 1px solid #1f2730; border-radius: 3px; display: none; }
.report-hdr { padding: 14px; text-align: center; border-bottom: 1px solid #1f2730; }
.report-hdr h2 { font-size: 0.7em; letter-spacing: 4px; color: #5a6472; margin-bottom: 12px; }
.r-score { font-size: 4em; font-weight: bold; line-height: 1; }
.r-of { font-size: 0.78em; color: #3a4350; margin-top: 3px; }
.r-pri { font-size: 0.85em; font-weight: bold; letter-spacing: 4px; margin-top: 8px; }
.r-rec { font-size: 0.72em; color: #5a6472; margin-top: 5px; }
.r-grid { display: grid; grid-template-columns: repeat(4, 1fr); border-bottom: 1px solid #1f2730; }
.r-card { padding: 14px 8px; text-align: center; border-right: 1px solid #1f2730; }
.r-card:last-child { border-right: none; }
.r-card-lbl { font-size: 0.6em; letter-spacing: 2px; color: #5a6472; margin-bottom: 5px; }
.r-card-val { font-size: 1.4em; font-weight: bold; color: #39ff6a; }
.r-table { width: 100%; border-collapse: collapse; font-size: 0.78em; }
.r-table td { padding: 9px 14px; border-bottom: 1px solid #161a20; }
.r-table td:first-child { color: #5a6472; }
.r-table td:last-child { text-align: right; color: #d4d8dd; }
.r-actions { padding: 12px 14px; border-top: 1px solid #1f2730; display: flex; gap: 8px; }
.r-actions .btn { margin: 0; }
.email-st { padding: 8px 14px; font-size: 0.72em; color: #5a6472; text-align: center; border-top: 1px solid #1f2730; }
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: #0b0d10; }
::-webkit-scrollbar-thumb { background: #2a323c; }
</style>
</head>
<body>

<div class="header">
    <div>
        <h1>ECO-SENTINEL</h1>
        <p>MUNICIPAL ENVIRONMENTAL ASSISTANCE SYSTEM</p>
    </div>
    <div class="header-right">
        <span id="clock">--:--:--</span>
        <div class="badge"><div class="dot"></div>ONLINE</div>
    </div>
</div>

<div class="main">
    <div class="camera-section">
        <div class="panel camera-feed">
            <div class="panel-header">
                <span>LIVE AI CAMERA FEED</span>
                <div class="live-tag"><div class="dot"></div>LIVE</div>
            </div>
            <img src="/video">
            <div class="panel-footer">
                <span id="fps">FPS: --</span>
                <span id="waste-footer">WASTE: 0</span>
                <span id="eap-footer">EAP: 0</span>
            </div>
        </div>
        <div class="alert-bar" id="alert-bar">WASTE DETECTED — EAP UPDATING</div>

        <div class="waste-grid">
            <div class="waste-card"><div class="waste-name">PLASTIC</div><div class="waste-count" id="w-plastic" style="color:#ff3b3b">0</div></div>
            <div class="waste-card"><div class="waste-name">PAPER</div><div class="waste-count" id="w-paper" style="color:#ff9f1c">0</div></div>
            <div class="waste-card"><div class="waste-name">METAL</div><div class="waste-count" id="w-metal" style="color:#c0c0c0">0</div></div>
            <div class="waste-card"><div class="waste-name">GLASS</div><div class="waste-count" id="w-glass" style="color:#00ffff">0</div></div>
            <div class="waste-card"><div class="waste-name">CARDBOARD</div><div class="waste-count" id="w-cardboard" style="color:#8b4513">0</div></div>
            <div class="waste-card"><div class="waste-name">OTHER</div><div class="waste-count" id="w-other" style="color:#800080">0</div></div>
        </div>

        <div class="sensor-grid">
            <div class="sensor-card">
                <div class="sensor-label">AIR QUALITY (MQ-135)</div>
                <div class="sensor-value" id="mq135-val">--</div>
                <div class="sensor-unit">raw units</div>
                <div class="sensor-status" id="mq135-status">--</div>
            </div>
            <div class="sensor-card">
                <div class="sensor-label">SMOKE / GAS (MQ-2)</div>
                <div class="sensor-value" id="mq2-val">--</div>
                <div class="sensor-unit">raw units</div>
                <div class="sensor-status" id="mq2-status">--</div>
            </div>
            <div class="sensor-card">
                <div class="sensor-label">TEMP / HUMIDITY</div>
                <div class="sensor-value" id="temp-val">--°C</div>
                <div class="sensor-unit" id="hum-val">-- % RH</div>
                <div class="sensor-status">DHT11</div>
            </div>
        </div>
    </div>

    <div class="sidebar">
        <div class="eap-panel">
            <div class="eap-label">ENVIRONMENTAL ACTION PRIORITY</div>
            <div class="eap-num" id="eap-num">0</div>
            <div class="eap-of">/ 100</div>
            <div class="bar-bg"><div class="bar-fill" id="eap-bar" style="width:0%"></div></div>
            <div class="eap-pri" id="eap-pri">LOW</div>
            <div class="eap-rec" id="eap-rec">Area Clean</div>
        </div>

        <div class="status-panel">
            <div class="status-label">SYSTEM STATUS</div>
            <div class="s-row"><div class="s-dot" style="background:#39ff6a;"></div>Camera Online</div>
            <div class="s-row"><div class="s-dot" style="background:#39ff6a;"></div>AI Module Active</div>
            <div class="s-row"><div class="s-dot" style="background:#39ff6a;"></div>Sensors Active</div>
            <div class="s-row"><div class="s-dot" id="s-dot-radar" style="background:#3a4350;"></div><span id="s-radar">Radar Idle</span></div>
            <div class="s-row"><div class="s-dot" id="s-dot-session" style="background:#3a4350;"></div><span id="s-session">Session Inactive</span></div>
            <div class="s-row"><div class="s-dot" id="s-dot-detect" style="background:#39ff6a;"></div><span id="s-detect">Scanning...</span></div>
        </div>

        <button class="btn btn-start" onclick="startSession()">START SESSION</button>
        <button class="btn btn-stop" onclick="stopSession()">STOP + REPORT</button>
        <button class="btn btn-report" onclick="reportError()">REPORT DETECTION ERROR</button>
    </div>
</div>

<div class="log-wrap">
    <div class="log-hdr">SYSTEM LOG</div>
    <div class="log-body" id="log"></div>
</div>

<div class="report-wrap" id="report">
    <div class="report-hdr">
        <h2>AREA ASSESSMENT REPORT</h2>
        <div class="r-score" id="r-score">--</div>
        <div class="r-of">/ 100</div>
        <div class="r-pri" id="r-pri">--</div>
        <div class="r-rec" id="r-rec">--</div>
    </div>
    <div class="r-grid">
        <div class="r-card"><div class="r-card-lbl">AVG EAP</div><div class="r-card-val" id="r-avg-eap">--</div></div>
        <div class="r-card"><div class="r-card-lbl">MAX EAP</div><div class="r-card-val" id="r-max-eap">--</div></div>
        <div class="r-card"><div class="r-card-lbl">AVG WASTE</div><div class="r-card-val" id="r-avg-det">--</div></div>
        <div class="r-card"><div class="r-card-lbl">MAX WASTE</div><div class="r-card-val" id="r-max-det">--</div></div>
    </div>
    <table class="r-table">
        <tr><td>Timestamp</td><td id="r-time">--</td></tr>
        <tr><td>Duration</td><td id="r-dur">--</td></tr>
        <tr><td>Samples Taken</td><td id="r-samp">--</td></tr>
        <tr><td>Min EAP Score</td><td id="r-min">--</td></tr>
        <tr><td>Plastic detected</td><td id="r-plastic">--</td></tr>
        <tr><td>Paper detected</td><td id="r-paper">--</td></tr>
        <tr><td>Metal detected</td><td id="r-metal">--</td></tr>
        <tr><td>Glass detected</td><td id="r-glass">--</td></tr>
        <tr><td>Cardboard detected</td><td id="r-cardboard">--</td></tr>
        <tr><td>Other detected</td><td id="r-other">--</td></tr>
        <tr><td>Errors reported</td><td id="r-errors">--</td></tr>
    </table>
    <div class="email-st" id="email-st">--</div>
    <div class="r-actions">
        <button class="btn btn-redo" onclick="redoSession()">REDO SCAN</button>
    </div>
</div>

<script>
let logs = [];
let sessionRunning = false;

setInterval(() => {
    const now = new Date();
    document.getElementById('clock').innerHTML =
        String(now.getHours()).padStart(2,'0') + ':' +
        String(now.getMinutes()).padStart(2,'0') + ':' +
        String(now.getSeconds()).padStart(2,'0');
}, 1000);

function addLog(msg) {
    const now = new Date();
    const t = String(now.getHours()).padStart(2,'0') + ':' +
              String(now.getMinutes()).padStart(2,'0') + ':' +
              String(now.getSeconds()).padStart(2,'0');
    logs.unshift(`<div class="l-row"><span>${t}</span>${msg}</div>`);
    if (logs.length > 20) logs.pop();
    document.getElementById('log').innerHTML = logs.join('');
}

function startSession() {
    fetch('/start_session').then(r => r.json()).then(() => {
        sessionRunning = true;
        document.getElementById('s-session').innerHTML = 'Session Active';
        document.getElementById('s-dot-session').style.background = '#39ff6a';
        document.getElementById('s-radar').innerHTML = 'Radar Sweeping';
        document.getElementById('s-dot-radar').style.background = '#39ff6a';
        document.getElementById('report').style.display = 'none';
        addLog('Session started — recording waste data');
    });
}

function stopSession() {
    if (!sessionRunning) { addLog('No active session'); return; }
    fetch('/stop_session').then(r => r.json()).then(data => {
        sessionRunning = false;
        document.getElementById('s-session').innerHTML = 'Session Complete';
        document.getElementById('s-dot-session').style.background = '#ff9f1c';
        document.getElementById('s-radar').innerHTML = 'Radar Idle';
        document.getElementById('s-dot-radar').style.background = '#3a4350';
        addLog('Report generated — EAP ' + data.avg_eap);
        addLog('Sending report to authorities...');
        document.getElementById('email-st').innerHTML = '📧 Sending report to authorities...';
        document.getElementById('email-st').style.color = '#5a6472';
        showReport(data);
        setTimeout(() => {
            document.getElementById('email-st').innerHTML = '📧 Report sent to authorities ✅';
            document.getElementById('email-st').style.color = '#39ff6a';
            addLog('Report emailed to authorities');
        }, 4000);
    });
}

function reportError() {
    fetch('/report_error').then(r => r.json()).then(data => {
        if (data.status === 'reported') {
            addLog('Detection error reported — image saved for review');
        } else {
            addLog('No frame available to report');
        }
    });
}

function redoSession() {
    fetch('/redo_session').then(r => r.json()).then(() => {
        sessionRunning = false;
        document.getElementById('report').style.display = 'none';
        document.getElementById('s-session').innerHTML = 'Session Inactive';
        document.getElementById('s-dot-session').style.background = '#3a4350';
        document.getElementById('s-radar').innerHTML = 'Radar Idle';
        document.getElementById('s-dot-radar').style.background = '#3a4350';
        document.getElementById('eap-num').innerHTML = '0';
        document.getElementById('eap-bar').style.width = '0%';
        document.getElementById('eap-pri').innerHTML = 'LOW';
        document.getElementById('eap-rec').innerHTML = 'Area Clean';
        ['plastic','paper','metal','glass','cardboard','other'].forEach(w => {
            document.getElementById('w-' + w).innerHTML = '0';
        });
        logs = [];
        document.getElementById('log').innerHTML = '';
        addLog('System reset');
        window.scrollTo(0, 0);
    });
}

function showReport(data) {
    document.getElementById('report').style.display = 'block';
    document.getElementById('r-score').innerHTML = data.avg_eap;
    document.getElementById('r-score').style.color = data.color;
    document.getElementById('r-pri').innerHTML = 'PRIORITY: ' + data.priority;
    document.getElementById('r-pri').style.color = data.color;
    document.getElementById('r-rec').innerHTML = data.recommendation;
    document.getElementById('r-avg-eap').innerHTML = data.avg_eap;
    document.getElementById('r-max-eap').innerHTML = data.max_eap;
    document.getElementById('r-avg-det').innerHTML = data.avg_detections;
    document.getElementById('r-max-det').innerHTML = data.max_detections;
    document.getElementById('r-time').innerHTML = data.timestamp;
    document.getElementById('r-dur').innerHTML = data.duration + 's';
    document.getElementById('r-samp').innerHTML = data.samples;
    document.getElementById('r-min').innerHTML = data.min_eap;
    document.getElementById('r-errors').innerHTML = data.error_reports;
    const wt = data.waste_totals || {};
    ['plastic','paper','metal','glass','cardboard','other'].forEach(w => {
        document.getElementById('r-' + w).innerHTML = (wt[w] || 0) + ' item(s)';
    });
    window.scrollTo(0, document.body.scrollHeight);
}

setInterval(() => {
    fetch('/stats').then(r => r.json()).then(data => {
        document.getElementById('fps').innerHTML = 'FPS: ' + data.fps;
        document.getElementById('waste-footer').innerHTML = 'WASTE: ' + data.detections;
        document.getElementById('eap-footer').innerHTML = 'EAP: ' + data.eap;
        document.getElementById('eap-num').innerHTML = data.eap;
        document.getElementById('eap-num').style.color = data.color;
        document.getElementById('eap-bar').style.width = data.eap + '%';
        document.getElementById('eap-bar').style.background = data.color;
        document.getElementById('eap-pri').innerHTML = data.priority;
        document.getElementById('eap-pri').style.color = data.color;
        document.getElementById('eap-rec').innerHTML = data.recommendation;

        document.getElementById('mq135-val').innerHTML = data.mq135;
        document.getElementById('mq135-status').innerHTML = data.air_label;
        document.getElementById('mq135-status').style.color = data.air_color;
        document.getElementById('mq2-val').innerHTML = data.mq2;
        document.getElementById('mq2-status').innerHTML = data.smoke_label;
        document.getElementById('mq2-status').style.color = data.smoke_color;
        document.getElementById('temp-val').innerHTML = data.temperature + '°C';
        document.getElementById('hum-val').innerHTML = data.humidity + ' % RH';

        const ws = data.waste_summary || {};
        ['plastic','paper','metal','glass','cardboard','other'].forEach(w => {
            document.getElementById('w-' + w).innerHTML = ws[w] || 0;
        });

        const alert = document.getElementById('alert-bar');
        if (data.detections > 0) {
            alert.style.display = 'block';
            alert.style.color = data.color;
            alert.style.borderColor = data.color;
            document.getElementById('s-dot-detect').style.background = '#ff3b3b';
            document.getElementById('s-detect').innerHTML = 'Waste: ' + data.detections + ' item(s)';
        } else {
            alert.style.display = 'none';
            document.getElementById('s-dot-detect').style.background = '#39ff6a';
            document.getElementById('s-detect').innerHTML = 'Area Clean';
        }
    });
}, 1000);

addLog('ECO-SENTINEL initialized');
addLog('AI module ready — waste segregation active');
addLog('Sensor link established');
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/video')
def video():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stats')
def stats():
    p = get_priority(eap_score)
    return jsonify({
        'fps': round(fps, 1),
        'detections': detection_count,
        'eap': eap_score,
        'priority': priority,
        'recommendation': recommendation,
        'color': get_color(p),
        'mq135': mq135_value,
        'mq2': mq2_value,
        'temperature': temperature,
        'humidity': humidity,
        'air_label': get_air_label(mq135_value),
        'air_color': get_color(get_priority(get_air_score(mq135_value) * 5)),
        'smoke_label': get_smoke_label(mq2_value),
        'smoke_color': get_color(get_priority(get_smoke_score(mq2_value) * 5)),
        'waste_summary': waste_summary,
    })

@app.route('/report_error')
def report_error():
    global latest_frame, reported_errors
    with lock:
        frame = latest_frame.copy() if latest_frame is not None else None
    if frame is None:
        return jsonify({'status': 'no_frame'})

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_path = f"{REPORTS_DIR}/report_{ts}.jpg"
    cv2.imwrite(img_path, frame)

    reported_errors.append({
        'timestamp': datetime.now().strftime("%d %b %Y, %H:%M:%S"),
        'image_path': img_path
    })

    return jsonify({'status': 'reported', 'timestamp': ts})

@app.route('/start_session')
def start_session():
    global session_active, session_start, eap_history, detection_history, final_report, session_waste_totals, reported_errors
    session_active = True
    session_start = time.time()
    eap_history = []
    detection_history = []
    final_report = None
    session_waste_totals = defaultdict(int)
    reported_errors = []
    send_arduino("RADAR_ON")
    return jsonify({'status': 'started'})

@app.route('/stop_session')
def stop_session():
    global session_active
    session_active = False
    send_arduino("RADAR_OFF")
    generate_report()
    threading.Thread(target=send_email, args=(final_report,), daemon=True).start()
    return jsonify(final_report)

@app.route('/redo_session')
def redo_session():
    global session_active, session_start, eap_history, detection_history, final_report, session_waste_totals, reported_errors
    session_active = False
    session_start = None
    eap_history = []
    detection_history = []
    final_report = None
    session_waste_totals = defaultdict(int)
    reported_errors = []
    send_arduino("RADAR_OFF")
    return jsonify({'status': 'reset'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
