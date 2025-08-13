import cv2
import numpy as np
from ultralytics import YOLO
import time
import streamlit as st
import pyttsx3
from transformers import pipeline
import threading
import sqlite3

# --- Constants ---
PLANT_SUGGESTIONS = {
    "Low": {"plants": "Lavender, Aloe Vera, Snake Plant", "reduction": 5},
    "Moderate": {"plants": "Spider Plant, Peace Lily, Bamboo Palm", "reduction": 10},
    "High": {"plants": "Areca Palm, Boston Fern, Rubber Plant", "reduction": 20},
    "Severe": {"plants": "Areca Palm, Boston Fern, Rubber Plant", "reduction": 30},
}
EMISSION_FACTORS = {"CO2": 120, "NOx": 0.6, "PM2.5": 0.005}
PIXEL_TO_M2_FACTOR = 0.05

# Load summarizer model (lightweight)
summarizer = pipeline("summarization", model="t5-small")

# --- Utility Functions ---
def get_pollution_info(count):
    if count == 0:
        level = "Low"
    elif count <= 5:
        level = "Moderate"
    elif count <= 10:
        level = "High"
    else:
        level = "Severe"
    air = {"Low": "Good", "Moderate": "Moderate", "High": "Poor", "Severe": "Very Poor"}[level]
    return count * 0.2, level, air, PLANT_SUGGESTIONS[level]["plants"], PLANT_SUGGESTIONS[level]["reduction"]

def calculate_unused_area(frame, results):
    h, w, _ = frame.shape
    mask = np.zeros((h, w), np.uint8)
    for r in results[0].boxes:
        if int(r.cls) in [2, 3, 5, 7]:
            x1, y1, x2, y2 = map(int, r.xyxy[0])
            mask[y1:y2, x1:x2] = 1
    return np.sum(mask == 0) * PIXEL_TO_M2_FACTOR

def traffic_light_html(state, rem):
    top_color = "red" if state == "red" else "#2c2c2c"
    middle_color = "#2c2c2c"
    bottom_color = "green" if state == "green" else "#2c2c2c"
    text = f"{rem}" if state == "green" and rem is not None else ""

    html = f"""
    <div style="background:#111;width:60px;padding:10px;text-align:center;border-radius:10px;
                box-shadow: 0 0 10px rgba(0,0,0,0.5);">
      <div style="margin:8px auto;width:40px;height:40px;border-radius:50%;
                  background:{top_color};box-shadow:0 0 5px {top_color};"></div>
      <div style="margin:8px auto;width:40px;height:40px;border-radius:50%;
                  background:{middle_color};"></div>
      <div style="margin:8px auto;width:40px;height:40px;border-radius:50%;
                  background:{bottom_color};color:white;
                  font-weight:bold;display:flex;align-items:center;justify-content:center;
                  box-shadow:0 0 5px {bottom_color};">
        {text}
      </div>
    </div>
    """
    return html

def generate_summary(idx, counts, unused, emis, plants):
    text = (
        f"Road {idx+1} Report:\n"
        f"- Vehicles: {counts[idx]}\n"
        f"- Unused Area: {unused[idx]:.2f} m²\n"
        f"- Emissions: " + ", ".join([f"{k}: {v}" for k, v in emis[idx].items()]) + "\n"
        f"- Suggested Plants: {plants[idx][3]}\n"
    )
    summary = summarizer(text, max_length=100, min_length=30, do_sample=False)[0]['summary_text']
    def speak():
        engine = pyttsx3.init()
        engine.say(summary)
        engine.runAndWait()
    threading.Thread(target=speak).start()
    return summary

def check_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users(username TEXT, password TEXT)')
    conn.commit()

    if not st.session_state.logged_in:
        st.header("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type='password')
        if st.button("Login"):
            c.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
            if c.fetchone():
                st.session_state.logged_in = True
                st.rerun()

            else:
                st.error("Incorrect username or password")
        st.stop()

def main():
    st.set_page_config(page_title="Smart Traffic Monitoring", layout="wide")
    st.title("🚦 Smart Traffic Monitoring System")
    check_login()
    st.success("Login Successful. You are now being redirected to the Dashboard.")
    run_dashboard()

def run_dashboard():
    model = YOLO('yolov8n.pt')
    caps = [cv2.VideoCapture(f'Road_{i+1}.mp4') for i in range(4)]
    signal_states = ['red'] * 4
    durations = [5] * 4
    current = 0
    start = time.time()
    last_summary = None

    placeholders = [st.empty() for _ in range(4)]
    summary_box = st.empty()

    while True:
        frames, counts, emis_list, unused_list, plant_info = [], [], [], [], []

        for i, cap in enumerate(caps):
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
            frame = cv2.resize(frame, (320, 180))
            res = model(frame)
            count = sum(int(r.cls) in [2, 3, 5, 7] for r in res[0].boxes)
            for r in res[0].boxes:
                if int(r.cls) in [2, 3, 5, 7]:
                    x1, y1, x2, y2 = map(int, r.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            emis = {k: count * v for k, v in EMISSION_FACTORS.items()}
            unused = calculate_unused_area(frame, res)
            prate, plevel, air, sug, red = get_pollution_info(count)
            plant_val = (plevel, air, int(unused / 2), sug, red * int(unused / 2))
            frames.append(frame)
            counts.append(count)
            emis_list.append(emis)
            unused_list.append(unused)
            plant_info.append(plant_val)

        if time.time() - start >= durations[current]:
            current = (current + 1) % 4
            durations[current] = max(5, counts[current])
            start = time.time()
            signal_states = ['red'] * 4
            signal_states[current] = 'green'

        for i in range(4):
            with placeholders[i].container():
                st.markdown(f"### Road {i+1}")
                c1, c2, c3, c4 = st.columns([3, 1, 2, 1])
                with c1:
                    st.image(cv2.cvtColor(frames[i], cv2.COLOR_BGR2RGB), channels="RGB")
                rem = int(durations[i] - (time.time() - start)) if signal_states[i] == 'green' else None
                with c2:
                    st.markdown(traffic_light_html(signal_states[i], rem), unsafe_allow_html=True)
                with c3:
                    st.metric("Vehicles", counts[i])
                    st.metric("Unused m²", f"{unused_list[i]:.1f}")
                    st.markdown("Emissions:")
                    for pollutant, value in emis_list[i].items():
                        st.write(f"{pollutant}: {value}")
                with c4:
                    st.write(f"Pollution: {plant_info[i][0]}, Air: {plant_info[i][1]}")
                    st.write(f"Plants: {plant_info[i][3]}")
                    st.write(f"Est. Reduction: {plant_info[i][4]}")

        if current != last_summary:
            summary = generate_summary(current, counts, unused_list, emis_list, plant_info)
            summary_box.markdown(f"### 🚦 Road {current+1} Summary:\n{summary}")
            last_summary = current

        time.sleep(0.1)

if __name__ == "__main__":
    main()
