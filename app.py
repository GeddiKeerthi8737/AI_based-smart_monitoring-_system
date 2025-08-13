import cv2
import numpy as np
from ultralytics import YOLO
import time
import streamlit as st
import pyttsx3
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


# Simple text summarizer function (no external dependencies)
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


# --- Custom CSS for Professional Look ---
def load_css():
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');

    /* Global Styles */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        font-family: 'Poppins', sans-serif;
    }

    /* Main Header */
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        text-align: center;
    }

    .main-header h1 {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }

    .main-header p {
        color: #e0e7ff;
        font-size: 1.1rem;
        margin-top: 0.5rem;
        font-weight: 300;
    }

    /* Login Container */
    .login-container {
        background: white;
        padding: 3rem;
        border-radius: 20px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        max-width: 400px;
        margin: 2rem auto;
    }

    .login-header {
        text-align: center;
        margin-bottom: 2rem;
    }

    .login-header h2 {
        color: #2d3748;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }

    .login-header p {
        color: #718096;
        font-size: 0.9rem;
    }

    /* Road Cards */
    .road-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        border-left: 5px solid #4299e1;
        transition: transform 0.3s ease;
    }

    .road-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 35px rgba(0,0,0,0.15);
    }

    .road-title {
        color: #2d3748;
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
    }

    .road-title::before {
        content: "🛣️";
        margin-right: 0.5rem;
    }

    /* Metrics Cards */
    .metric-card {
        background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #38b2ac;
    }

    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #2d3748;
    }

    .metric-label {
        font-size: 0.9rem;
        color: #718096;
        font-weight: 500;
    }

    /* Traffic Light Enhanced */
    .traffic-light-container {
        background: linear-gradient(145deg, #2d3748, #4a5568);
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
    }

    /* Emissions Card */
    .emissions-card {
        background: linear-gradient(135deg, #fed7e2 0%, #fbb6ce 100%);
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #d53f8c;
    }

    .emissions-title {
        color: #97266d;
        font-weight: 600;
        margin-bottom: 0.5rem;
        font-size: 1rem;
    }

    /* Plants Card */
    .plants-card {
        background: linear-gradient(135deg, #c6f6d5 0%, #9ae6b4 100%);
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #38a169;
    }

    .plants-title {
        color: #276749;
        font-weight: 600;
        margin-bottom: 0.5rem;
        font-size: 1rem;
    }

    /* Summary Box */
    .summary-box {
        background: linear-gradient(135deg, #fff5f5 0%, #fed7d7 100%);
        padding: 2rem;
        border-radius: 15px;
        margin: 2rem 0;
        border-left: 5px solid #f56565;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }

    .summary-title {
        color: #c53030;
        font-size: 1.4rem;
        font-weight: 600;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
    }

    .summary-title::before {
        content: "📊";
        margin-right: 0.5rem;
    }

    /* Status Indicators */
    .status-good { color: #38a169; font-weight: 600; }
    .status-moderate { color: #d69e2e; font-weight: 600; }
    .status-poor { color: #e53e3e; font-weight: 600; }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(90deg, #4299e1 0%, #3182ce 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s ease;
        width: 100%;
    }

    .stButton > button:hover {
        background: linear-gradient(90deg, #3182ce 0%, #2c5282 100%);
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.2);
    }

    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Sidebar Styling */
    .css-1d391kg {
        background: linear-gradient(180deg, #1a202c 0%, #2d3748 100%);
    }

    /* Success Message */
    .success-message {
        background: linear-gradient(135deg, #c6f6d5 0%, #9ae6b4 100%);
        color: #276749;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)


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
    top_color = "#ff4444" if state == "red" else "#333333"
    middle_color = "#333333"
    bottom_color = "#44ff44" if state == "green" else "#333333"
    text = f"{rem}" if state == "green" and rem is not None else ""

    top_shadow = "0 0 20px #ff4444" if state == "red" else "0 0 5px #333333"
    bottom_shadow = "0 0 20px #44ff44" if state == "green" else "0 0 5px #333333"

    html = f"""
    <div class="traffic-light-container">
      <div style="margin:10px auto;width:50px;height:50px;border-radius:50%;
                  background:{top_color};box-shadow:{top_shadow};
                  transition: all 0.3s ease;"></div>
      <div style="margin:10px auto;width:50px;height:50px;border-radius:50%;
                  background:{middle_color};box-shadow:0 0 5px #333333;"></div>
      <div style="margin:10px auto;width:50px;height:50px;border-radius:50%;
                  background:{bottom_color};color:white;
                  font-weight:bold;display:flex;align-items:center;justify-content:center;
                  box-shadow:{bottom_shadow};font-size:1.2rem;
                  transition: all 0.3s ease;">
        {text}
      </div>
    </div>
    """
    return html


def generate_summary(idx, counts, unused, emis, plants):
    text = (
            f"Road {idx + 1} Report:\n"
            f"- Vehicles: {counts[idx]}\n"
            f"- Unused Area: {unused[idx]:.2f} m²\n"
            f"- Emissions: " + ", ".join([f"{k}: {v}" for k, v in emis[idx].items()]) + "\n"
                                                                                        f"- Suggested Plants: {plants[idx][3]}\n"
    )

    # Create a simple summary without external dependencies
    summary = f"Road {idx + 1}: {counts[idx]} vehicles detected, {unused[idx]:.1f}m² unused area, {plants[idx][1]} air quality. Plants recommended: {plants[idx][3][:50]}..."

    def speak():
        try:
            engine = pyttsx3.init()
            engine.say(summary)
            engine.runAndWait()
        except:
            pass  # Skip if pyttsx3 has issues

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

        # Main header
        st.markdown("""
        <div class="main-header">
            <h1>🚦 Smart Traffic Monitoring System</h1>
            <p>Advanced AI-Powered Traffic Management & Environmental Solutions</p>
        </div>
        """, unsafe_allow_html=True)

        # Login container
        st.markdown("""
        <div class="login-container">
            <div class="login-header">
                <h2>🔐 System Access</h2>
                <p>Please enter your credentials to access the monitoring dashboard</p>
            </div>
        """, unsafe_allow_html=True)

        username = st.text_input("👤 Username", placeholder="Enter your username")
        password = st.text_input("🔒 Password", type='password', placeholder="Enter your password")

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 Login to Dashboard"):
                if username and password:
                    c.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
                    if c.fetchone():
                        st.session_state.logged_in = True
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials. Please try again.")
                else:
                    st.error("⚠️ Please enter both username and password")

        st.markdown("</div>", unsafe_allow_html=True)

        # Add some demo info
        st.markdown("""
        <div style="background: rgba(255,255,255,0.1); padding: 2rem; border-radius: 15px; margin-top: 2rem; text-align: center;">
            <h3 style="color: white; margin-bottom: 1rem;">🏢 MSME Traffic Solutions - Hackathon 2025</h3>
            <p style="color: #e0e7ff; font-size: 1rem; line-height: 1.6;">
                🚀 Advanced AI-Powered Traffic Management System<br>
                🎯 Real-time Vehicle Detection • Dynamic Signal Control • Environmental Monitoring<br>
                🌱 Smart Green Solutions • Emission Analysis • Professional Dashboard
            </p>
            <div style="margin-top: 1.5rem; padding: 1rem; background: rgba(255,255,255,0.1); border-radius: 10px;">
                <p style="color: #cbd5e0; font-size: 0.9rem;">
                    🏆 Built for Smart City Innovation • Professional Grade Solution<br>
                    💡 MSME Ready • Scalable Architecture • Business Intelligence
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        conn.close()
        st.stop()


def main():
    st.set_page_config(
        page_title="Smart Traffic Monitoring | MSME Solutions",
        layout="wide",
        page_icon="🚦",
        initial_sidebar_state="collapsed"
    )

    check_login()

    # Show success message and redirect
    st.markdown("""
    <div class="success-message">
        ✅ Login Successful! Welcome to the Smart Traffic Monitoring Dashboard
    </div>
    """, unsafe_allow_html=True)

    run_dashboard()


def run_dashboard():
    load_css()

    # Dashboard Header
    st.markdown("""
    <div class="main-header">
        <h1>🚦 Smart Traffic Control Center</h1>
        <p>Real-time AI Traffic Monitoring & Environmental Analysis Dashboard</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar for system info
    with st.sidebar:
        st.markdown("### 🏢 System Information")
        st.info("**MSME Traffic Solutions**\n\nAdvanced AI-powered traffic management system")
        st.markdown("### 📊 System Status")
        st.success("🟢 All Systems Online")
        st.markdown("### 🛠️ Features")
        st.write("• Real-time vehicle detection")
        st.write("• Dynamic signal timing")
        st.write("• Environmental monitoring")
        st.write("• Smart plant suggestions")

        if st.button("🔄 Refresh System"):
            st.rerun()

        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()

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
                    <div class="road-title">Road {i + 1} - Junction Alpha-{i + 1}</div>
                """, unsafe_allow_html=True)

                col1, col2, col3, col4 = st.columns([4, 1, 2, 2])

                with col1:
                    st.image(cv2.cvtColor(frames[i], cv2.COLOR_BGR2RGB),
                             channels="RGB", use_container_width=True)

                rem = int(durations[i] - (time.time() - start)) if signal_states[i] == 'green' else None
                with col2:
                    st.markdown(traffic_light_html(signal_states[i], rem), unsafe_allow_html=True)

                with col3:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{counts[i]}</div>
                        <div class="metric-label">🚗 Active Vehicles</div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{unused_list[i]:.1f}</div>
                        <div class="metric-label">📏 Unused Area (m²)</div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Air quality status
                    air_status = plant_info[i][1]
                    status_class = "status-good" if air_status == "Good" else "status-moderate" if air_status == "Moderate" else "status-poor"
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">
                            <span class="{status_class}">{air_status}</span>
                        </div>
                        <div class="metric-label">🌬️ Air Quality</div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Emissions data under air quality
                    st.markdown(f"""
                    <div class="emissions-card">
                        <div class="emissions-title">💨 Emissions Analysis</div>
                        <div style="color: #2d3748; font-size: 0.9rem; font-weight: 500;">
                            <div style="margin: 0.3rem 0;">CO2: <span style="color: #c53030; font-weight: 600;">{emis_list[i]['CO2']:.1f} g/km</span></div>
                            <div style="margin: 0.3rem 0;">NOx: <span style="color: #c53030; font-weight: 600;">{emis_list[i]['NOx']:.2f} g/km</span></div>
                            <div style="margin: 0.3rem 0;">PM2.5: <span style="color: #c53030; font-weight: 600;">{emis_list[i]['PM2.5']:.3f} g/km</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Plant recommendations under emissions
                    st.markdown(f"""
                    <div class="plants-card">
                        <div class="plants-title">🌱 Green Solutions</div>
                        <div style="color: #2d3748; font-size: 0.9rem; font-weight: 500;">
                            <div style="margin: 0.3rem 0;"><strong>Recommended:</strong></div>
                            <div style="margin: 0.3rem 0; color: #276749;">{plant_info[i][3]}</div>
                            <div style="margin: 0.3rem 0;"><strong>Est. Reduction:</strong> <span style="color: #38a169; font-weight: 600;">{plant_info[i][4]}%</span> pollution</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with col4:
                    # System status and additional info
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #e6fffa 0%, #b2f5ea 100%); padding: 1rem; border-radius: 10px; margin: 0.5rem 0;">
                        <div style="color: #234e52; font-weight: 600; margin-bottom: 0.5rem;">📊 System Status</div>
                        <div style="color: #2d3748; font-size: 0.9rem;">
                            <div style="margin: 0.3rem 0;">Signal: <span style="color: {'#38a169' if signal_states[i] == 'green' else '#e53e3e'}; font-weight: 600;">{'ACTIVE' if signal_states[i] == 'green' else 'WAITING'}</span></div>
                            <div style="margin: 0.3rem 0;">Detection: <span style="color: #38a169; font-weight: 600;">ONLINE</span></div>
                            <div style="margin: 0.3rem 0;">AI Model: <span style="color: #3182ce; font-weight: 600;">YOLOv8</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Traffic density indicator
                    density_level = "LOW" if counts[i] <= 3 else "MEDIUM" if counts[i] <= 7 else "HIGH"
                    density_color = "#38a169" if counts[i] <= 3 else "#d69e2e" if counts[i] <= 7 else "#e53e3e"

                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #fff5f5 0%, #fed7d7 100%); padding: 1rem; border-radius: 10px; margin: 0.5rem 0;">
                        <div style="color: #c53030; font-weight: 600; margin-bottom: 0.5rem;">🚦 Traffic Density</div>
                        <div style="color: #2d3748; font-size: 0.9rem;">
                            <div style="margin: 0.3rem 0;">Level: <span style="color: {density_color}; font-weight: 600;">{density_level}</span></div>
                            <div style="margin: 0.3rem 0;">Vehicles: <span style="color: #2d3748; font-weight: 600;">{counts[i]}</span></div>
                            <div style="margin: 0.3rem 0;">Efficiency: <span style="color: #3182ce; font-weight: 600;">{max(0, 100 - counts[i] * 10)}%</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

        if current != last_summary:
            summary = generate_summary(current, counts, unused_list, emis_list, plant_info)
            summary_box.markdown(f"""
            <div class="summary-box">
                <div class="summary-title">Real-time Analysis Report</div>
                <div style="color: #2d3748; line-height: 1.6;">
                    <strong>🎯 Current Focus:</strong> Road {current + 1}<br>
                    <strong>📊 Summary:</strong> {summary}
                </div>
            </div>
            """, unsafe_allow_html=True)
            last_summary = current

        time.sleep(0.1)


if __name__ == "__main__":
    main()