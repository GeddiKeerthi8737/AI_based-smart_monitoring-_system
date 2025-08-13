import cv2
import numpy as np
from ultralytics import YOLO
import time
import streamlit as st
import pyttsx3
import threading
import sqlite3
import os

# --- Constants ---
PLANT_SUGGESTIONS = {
    "Low": {"plants": "Lavender, Aloe Vera, Snake Plant", "reduction": 5},
    "Moderate": {"plants": "Spider Plant, Peace Lily, Bamboo Palm", "reduction": 10},
    "High": {"plants": "Areca Palm, Boston Fern, Rubber Plant", "reduction": 20},
    "Severe": {"plants": "Areca Palm, Boston Fern, Rubber Plant", "reduction": 30},
}
EMISSION_FACTORS = {"CO2": 120, "NOx": 0.6, "PM2.5": 0.005}
PIXEL_TO_M2_FACTOR = 0.05


def simple_summarizer(text, max_length=100):
    """Simple text summarizer without external dependencies"""
    lines = text.split('\n')
    summary_lines = []
    for line in lines:
        if line.strip() and not line.startswith('-'):
            summary_lines.append(line.strip())
    if summary_lines:
        return summary_lines[0][:max_length] + "..." if len(summary_lines[0]) > max_length else summary_lines[0]
    return "Traffic analysis completed for current road section."


def load_css():
    """Load CSS from external file"""
    try:
        with open("templates/styles.css", "r", encoding='utf-8') as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("CSS file not found. Please ensure templates/styles.css exists.")


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
    top_color = "#ff4444" if state == "red" else "#333333"
    bottom_color = "#44ff44" if state == "green" else "#333333"
    text = f"{rem}" if state == "green" and rem is not None else ""
    top_shadow = "0 0 20px #ff4444" if state == "red" else "0 0 5px #333333"
    bottom_shadow = "0 0 20px #44ff44" if state == "green" else "0 0 5px #333333"

    return f"""
    <div class="traffic-light-container">
      <div style="margin:10px auto;width:50px;height:50px;border-radius:50%;
                  background:{top_color};box-shadow:{top_shadow};
                  transition: all 0.3s ease;"></div>
      <div style="margin:10px auto;width:50px;height:50px;border-radius:50%;
                  background:#333333;box-shadow:0 0 5px #333333;"></div>
      <div style="margin:10px auto;width:50px;height:50px;border-radius:50%;
                  background:{bottom_color};color:white;
                  font-weight:bold;display:flex;align-items:center;justify-content:center;
                  box-shadow:{bottom_shadow};font-size:1.2rem;
                  transition: all 0.3s ease;">
        {text}
      </div>
    </div>
    """


def generate_summary(idx, counts, unused, emis, plants):
    summary = f"Road {idx + 1}: {counts[idx]} vehicles detected, {unused[idx]:.1f}m² unused area, {plants[idx][1]} air quality. Plants recommended: {plants[idx][3][:50]}..."

    def speak():
        try:
            engine = pyttsx3.init()
            engine.say(summary)
            engine.runAndWait()
        except:
            pass

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
        load_css()

        # Header with logo and profile
        st.markdown("""
        <div class="header-container">
            <div class="header-left">
                <h1>🚦 AI Traffic Monitoring System</h1>
                <p>Professional Real-time Traffic Analysis & Control</p>
            </div>
            <div class="header-right">
                <div class="company-logo">TrafficAI Pro</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Login container
        st.markdown("""
        <div class="login-container">
            <div class="login-header">
                <h2>🔐 System Access</h2>
                <p>Enter credentials to access the professional dashboard</p>
            </div>
        """, unsafe_allow_html=True)

        username = st.text_input("👤 Username", placeholder="Enter username")
        password = st.text_input("🔒 Password", type='password', placeholder="Enter password")

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 Access Dashboard"):
                if username and password:
                    c.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
                    if c.fetchone():
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials")
                else:
                    st.error("⚠️ Please enter credentials")

        st.markdown("</div>", unsafe_allow_html=True)
        conn.close()
        st.stop()


def run_dashboard():
    load_css()

    # Professional header with logo and profile
    st.markdown(f"""
    <div class="dashboard-header">
        <div class="header-left">
            <h1>🚦 Real Time Traffic Analysis Report</h1>
            <p>Professional AI-Powered Traffic Management Dashboard</p>
        </div>
        <div class="header-right">
            <div class="company-logo">TrafficAI Pro</div>
           <div class="profile-section">
                <div class="profile-dropdown">
                    <div class="profile-icon" onclick="toggleDropdown()">👤</div>
                    <div class="profile-dropdown-content" id="profileDropdown">
                        <div class="profile-info">
                            <strong>👤 {st.session_state.get('username', 'Admin')}</strong>
                        </div>
                        <div class="dropdown-item" onclick="logout()">🚪 Logout</div>
                    </div>
                </div>
            </div>
            <script>
                function toggleDropdown() {{
                    document.getElementById("profileDropdown").classList.toggle("show");
                }}
                function logout() {{
                    window.location.reload();
                }}
                window.onclick = function(event) {{
                    if (!event.target.matches('.profile-icon')) {{
                        var dropdowns = document.getElementsByClassName("profile-dropdown-content");
                        for (var i = 0; i < dropdowns.length; i++) {{
                            var openDropdown = dropdowns[i];
                            if (openDropdown.classList.contains('show')) {{
                                openDropdown.classList.remove('show');
                            }}
                        }}
                    }}
                }}
            </script>
    """, unsafe_allow_html=True)

    # Success message
    st.markdown("""
    
    <div class="success-message">
        ✅ Dashboard Active - Real-time Traffic Monitoring Enabled
    </div>
    """, unsafe_allow_html=True)

    # Main dashboard functionality
    model = YOLO('yolov8n.pt')
    caps = [cv2.VideoCapture(f'Road_{i + 1}.mp4') for i in range(4)]
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
            frame = cv2.resize(frame, (400, 225))
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
                st.markdown(f"""
                <div class="road-card">
                    <div class="road-title">Road {i + 1} - Traffic Junction Alpha-{i + 1}</div>
                """, unsafe_allow_html=True)

                col1, col2, col3, col4 = st.columns([4, 1, 2, 2])

                with col1:
                    st.image(cv2.cvtColor(frames[i], cv2.COLOR_BGR2RGB), channels="RGB", use_container_width=True)

                rem = int(durations[i] - (time.time() - start)) if signal_states[i] == 'green' else None
                with col2:
                    st.markdown(traffic_light_html(signal_states[i], rem), unsafe_allow_html=True)

                with col3:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{counts[i]}</div>
                        <div class="metric-label">🚗 Active Vehicles</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{unused_list[i]:.1f}</div>
                        <div class="metric-label">📏 Unused Area (m²)</div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Air quality with density
                    air_status = plant_info[i][1]
                    status_class = "status-good" if air_status == "Good" else "status-moderate" if air_status == "Moderate" else "status-poor"
                    density_level = "LOW" if counts[i] <= 3 else "MEDIUM" if counts[i] <= 7 else "HIGH"

                    st.markdown(f"""
                    <div class="air-quality-card">
                        <div class="air-quality-title">🌬️ Air Quality & Density</div>
                        <div class="air-quality-content">
                            <div>Status: <span class="{status_class}">{air_status}</span></div>
                            <div>Density: <span class="density-{density_level.lower()}">{density_level}</span></div>
                            <div>Efficiency: <span class="efficiency">{max(0, 100 - counts[i] * 10)}%</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with col4:
                    # Emissions
                    st.markdown(f"""
                    <div class="emissions-card">
                        <div class="emissions-title">💨 Emissions Analysis</div>
                        <div class="emissions-content">
                            <div>CO2: <span class="emission-value">{emis_list[i]['CO2']:.1f} g/km</span></div>
                            <div>NOx: <span class="emission-value">{emis_list[i]['NOx']:.2f} g/km</span></div>
                            <div>PM2.5: <span class="emission-value">{emis_list[i]['PM2.5']:.3f} g/km</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Plant recommendations
                    st.markdown(f"""
                    <div class="plants-card">
                        <div class="plants-title">🌱 Green Solutions</div>
                        <div class="plants-content">
                            <div><strong>Plants:</strong> {plant_info[i][3]}</div>
                            <div><strong>Reduction:</strong> <span class="reduction-value">{plant_info[i][4]}%</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

        if current != last_summary:
            summary = generate_summary(current, counts, unused_list, emis_list, plant_info)
            summary_box.markdown(f"""
            <div class="summary-box">
                <div class="summary-title">📊 Real-time Analysis Report</div>
                <div class="summary-content">
                    <strong>🎯 Current Focus:</strong> Road {current + 1}<br>
                    <strong>📊 Analysis:</strong> {summary}
                </div>
            </div>
            """, unsafe_allow_html=True)
            last_summary = current

        time.sleep(0.1)


def main():
    st.set_page_config(
        page_title="AI Traffic Monitoring | Professional Dashboard",
        layout="wide",
        page_icon="🚦",
        initial_sidebar_state="collapsed"
    )

    check_login()
    run_dashboard()


if __name__ == "__main__":
    main()