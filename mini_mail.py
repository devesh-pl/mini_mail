# mini_mail.py - full corrected app
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, send_from_directory
import mysql.connector as m
from datetime import datetime
import random
import string
import os
from werkzeug.utils import secure_filename

# -------------------- CONFIG --------------------
# NOTE: Update DB_USER and DB_PASSWORD to match your MySQL setup!
DB_HOST = "localhost"
DB_USER = "thejeswar"
DB_PASSWORD = "student"
ADMIN_DEFAULT_PASSWORD = "root1234"   # used for initial admin row
SECRET_KEY = "".join(random.choices(string.ascii_letters + string.digits, k=24))

app = Flask(__name__)
app.secret_key = SECRET_KEY

# -------------------- UPLOADS --------------------
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4", "mov", "pdf", "txt", "docx"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # filename can be "user_id/filename.ext"
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(file_path):
        # split directory and serve properly
        folder = os.path.dirname(filename)
        fname = os.path.basename(filename)
        if folder:
            return send_from_directory(os.path.join(app.config["UPLOAD_FOLDER"], folder), fname)
        else:
            return send_from_directory(app.config["UPLOAD_FOLDER"], fname)
    return "File not found", 404


# -------------------- DB helpers --------------------
def connect_server():
    return m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD)


def initialize_system():
    """
    Create required databases/tables:
      - mail (userdetails, admins, all_messages, user_activity)
      - per-user DBs are created on signup
    """
    con = connect_server()
    cur = con.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS mail")
    cur.execute("USE mail")

    # user table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS userdetails (
            name VARCHAR(30),
            mobile_no VARCHAR(20),
            user_ID VARCHAR(50) PRIMARY KEY,
            pin INT
        )
    """)

    # admin table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            admin_id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # insert default admin if none
    cur.execute("SELECT COUNT(*) FROM admins")
    cnt = cur.fetchone()[0]
    if cnt == 0:
        cur.execute("INSERT INTO admins (username, password) VALUES (%s, %s)", ("admin", ADMIN_DEFAULT_PASSWORD))

    # global message table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS all_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            sender VARCHAR(50),
            receiver VARCHAR(50),
            direction ENUM('sent','received'),
            message TEXT,
            subject VARCHAR(255),  /* Added subject field */
            attachment VARCHAR(255)
        )
    """)

    # user activity table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_activity (
            id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id VARCHAR(50),
            action ENUM('login','logout','signup','message_sent','message_received'),
            details TEXT
        )
    """)

    con.commit()
    cur.close()
    con.close()


# -------------------- Logging functions --------------------
def log_message_global(sender, receiver, direction, message, subject=None, attachment=None):
    try:
        con = m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database="mail")
        cur = con.cursor()
        cur.execute("""
            INSERT INTO all_messages (sender, receiver, direction, message, subject, attachment)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (sender, receiver, direction, message, subject, attachment))
        con.commit()
        cur.close()
        con.close()
    except Exception as e:
        print("Error logging global message:", e)


def log_user_activity(user_id, action, details=""):
    try:
        con = m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database="mail")
        cur = con.cursor()
        cur.execute("INSERT INTO user_activity (user_id, action, details) VALUES (%s,%s,%s)",
                    (user_id, action, details))
        con.commit()
        cur.close()
        con.close()
    except Exception as e:
        print("Error logging user activity:", e)


# -------------------- Templates & CSS --------------------
BASE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mini Mail</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    :root { 
        /* THEME COLORS (Light Mode Defaults) */
        --page-bg: #050a30; /* Deep Navy Blue (Page Background) */
        --card-bg: #cae8ff; /* Light Blue (Card Background) */
        --theme-text-color: #050a30; /* Dark Text for the card title/content */
        --button-bg: #050a30; /* Deep Navy Blue (Button Background) */
        --button-text: #ffffff; /* White (Button Text) */
        --success: #28a745;
        --danger: #dc3545;
        --border-color: #e9ecef;
    }
    
    /* DARK MODE OVERRIDES */
    body.dark-mode {
        --page-bg: #121212; /* Darker background */
        --card-bg: #2d2d2d; /* Dark card background */
        --theme-text-color: #f0f0f0; /* Light text for the dark card */
        --button-bg: #4a4a4a; /* Dark button background */
        --button-text: #ffffff; /* White button text */
        --border-color: #444444;
    }
    
    body.dark-mode .header-bar {
        background: var(--page-bg); 
        color: var(--card-bg); 
        box-shadow: 0 2px 8px rgba(0,0,0,0.8);
    }
    
    body.dark-mode .header-bar .logo-link {
        color: #bdbdbd; /* Lighter color */
    }
    
    body.dark-mode .menu-icon:hover {
        color: #ffffff;
    }
    
    /* Adjust colors for elements inside dark mode cards/panels */
    body.dark-mode .card, 
    body.dark-mode .dashboard-panel, 
    body.dark-mode .compose-bar, 
    body.dark-mode .composition-panel, 
    body.dark-mode .sent-panel {
        box-shadow: 0 15px 30px rgba(0, 0, 0, 0.7);
    }
    
    /* Input/Textarea in Dark Mode */
    body.dark-mode input, 
    body.dark-mode textarea {
        background: #555555;
        border: 1px solid #777;
        color: #ffffff;
    }
    body.dark-mode input::placeholder, 
    body.dark-mode textarea::placeholder {
        color: rgba(255, 255, 255, 0.5);
    }
    
    /* Specific elements inside dark mode */
    body.dark-mode .drawer {
        background: #2d2d2d;
        box-shadow: -4px 0 15px rgba(0,0,0,0.8);
    }
    body.dark-mode .drawer a {
        color: #bdbdbd;
    }
    body.dark-mode .drawer a:hover {
        background: #4a4a4a;
    }
    body.dark-mode .sent-item {
        background: #3a3a3a;
        color: #f0f0f0;
    }
    body.dark-mode .sent-item-subject {
        color: #bdbdbd;
    }
    body.dark-mode .compose-bar input {
        color: #ffffff;
    }
    body.dark-mode .compose-bar input::placeholder {
        color: rgba(255, 255, 255, 0.5);
    }
    body.dark-mode .message-input-bar {
        background: #555555;
    }
    body.dark-mode .message-input-bar textarea {
        color: #ffffff;
    }
    body.dark-mode table {
        background: #3a3a3a;
        box-shadow: 0 2px 5px rgba(0,0,0,0.5);
    }
    body.dark-mode th {
        background: #555555;
        color: #f0f0f0;
    }
    body.dark-mode td {
        color: #bdbdbd;
        border-bottom: 1px solid #4a4a4a;
    }
    body.dark-mode td:before {
        color: #bdbdbd;
    }

    body {
        font-family: 'Inter', Arial, sans-serif; 
        background: var(--page-bg); 
        margin: 0;
        color: var(--theme-text-color); 
        line-height: 1.6;
        display: flex;
        flex-direction: column;
        min-height: 100vh;
    }
    
    /* --- Main Nav Bar (New Layout) --- */
    .header-bar {
        background: var(--page-bg); 
        color: var(--card-bg); 
        padding: 15px 20px; 
        display: flex;
        justify-content: space-between;
        align-items: center; 
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        position: sticky;
        top: 0;
        z-index: 100;
    }
    .header-bar .logo-link {
        font-size: 1.6rem;
        font-weight: 700;
        text-decoration: none;
        color: var(--card-bg);
        transition: opacity 0.2s;
    }
    .header-bar .logo-link:hover {
        opacity: 0.8;
    }
    .header-controls {
        display: flex;
        align-items: center;
    }
    .menu-icon {
        cursor: pointer;
        font-size: 1.8rem;
        padding: 5px;
        line-height: 1;
        transition: color 0.2s;
    }
    .menu-icon:hover {
        color: #a9d4ff;
    }
    
    /* Theme Toggle Button Style */
    .theme-toggle {
        background: none;
        border: none;
        color: var(--card-bg); /* Use light color from theme */
        font-size: 1.4rem;
        cursor: pointer;
        margin-right: 15px; /* Spacing before menu icon */
        transition: color 0.2s;
        line-height: 1;
    }
    .theme-toggle:hover {
        color: #a9d4ff;
    }


    /* --- Side Drawer Menu --- */
    .drawer {
        position: fixed;
        top: 0;
        right: 0;
        height: 100%;
        width: 280px;
        background: var(--card-bg);
        color: var(--theme-text-color);
        box-shadow: -4px 0 15px rgba(0,0,0,0.4);
        transform: translateX(100%);
        transition: transform 0.3s ease-in-out;
        z-index: 200;
        padding: 20px;
        box-sizing: border-box;
        overflow-y: auto;
    }
    .drawer.open {
        transform: translateX(0);
    }
    .drawer-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 30px;
    }
    .drawer-header h3 {
        margin: 0;
        color: var(--button-bg);
    }
    .close-btn {
        font-size: 2rem;
        cursor: pointer;
        line-height: 1;
        opacity: 0.6;
    }
    .drawer a {
        display: block;
        text-decoration: none;
        color: var(--button-bg);
        padding: 15px 10px;
        border-radius: 8px;
        margin-bottom: 10px;
        font-weight: 600;
        transition: background-color 0.2s;
    }
    .drawer a:hover {
        background: #bce3ff; /* Lighter shade of card background on hover */
    }
    .divider {
        height: 1px;
        background: var(--theme-text-color);
        opacity: 0.1;
        margin: 20px 0;
    }
    .drawer-status {
        font-size: 0.9rem;
        padding: 10px;
        color: var(--button-bg);
        opacity: 0.7;
    }

    /* --- Layout & Card --- */
    .wrap {
        max-width:1100px; 
        margin: auto; 
        padding: 0 20px;
        flex-grow: 1;
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
    }
    .card {
        background:var(--card-bg);
        color: var(--theme-text-color);
        width: 100%;
        max-width: 400px; 
        padding: 30px; 
        border-radius: 20px; 
        box-shadow: 0 15px 30px rgba(0, 0, 0, 0.3);
        border: none;
        text-align: center;
    }
    .index-page-wrap .card {
        width: 300px; 
        height: 400px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 30px;
    }
    
    /* --- Dashboard Card Layout (Three Columns + Footer) --- */
    .dashboard-card {
        max-width: 100%;
        padding: 0;
        box-shadow: none; /* Let the internal panels define the shadow/style */
        background: transparent;
        color: var(--card-bg); /* Use light color for the overall text here */
        display: flex;
        flex-direction: column;
        gap: 20px;
    }

    .dashboard-card h1 {
        font-size: 3rem;
        font-weight: 700;
        color: var(--card-bg);
        margin-bottom: 0;
        align-self: flex-start;
        text-transform: capitalize;
    }

    .dashboard-grid {
        display: grid;
        grid-template-columns: 1.5fr 1fr 1fr; /* Feed wider than inbox/received */
        gap: 20px;
    }
    
    .dashboard-panel {
        background: var(--card-bg);
        color: var(--theme-text-color);
        padding: 20px;
        border-radius: 20px;
        min-height: 400px;
        display: flex;
        flex-direction: column;
    }
    
    .dashboard-panel h4 {
        margin-top: 0;
        font-size: 1.4rem;
        font-weight: 600;
    }
    
    .compose-bar {
        grid-column: 2 / 4; /* Span across inbox and received columns */
        display: flex;
        align-items: center;
        background: var(--card-bg);
        padding: 10px 20px;
        border-radius: 20px;
        margin-top: -10px; /* Overlap slightly with the panels above */
    }
    .compose-bar input {
        flex-grow: 1;
        padding: 10px;
        border: none;
        background: transparent;
        color: var(--button-bg);
        font-weight: 500;
        text-align: left;
        margin: 0; /* Override default input margins */
    }
    .compose-bar input::placeholder {
        color: rgba(5, 10, 48, 0.5); /* Theme text color, slightly transparent */
    }
    .compose-bar .attachment-icon {
        cursor: pointer;
        font-size: 1.5rem;
        color: var(--button-bg);
        padding: 5px;
        transition: opacity 0.2s;
    }
    .compose-bar .attachment-icon:hover {
        opacity: 0.7;
    }

    /* --- Two-Column Layout for Send Page (New Design) --- */
    /* Override standard card wrapper to allow for custom two-column layout */
    .send-page-wrapper {
        max-width: 100%;
        padding: 0;
        box-shadow: none;
        background: transparent;
        display: flex;
        flex-direction: column;
        gap: 20px;
    }
    .send-page-wrapper h1 {
        font-size: 3rem;
        font-weight: 700;
        color: var(--card-bg);
        margin-bottom: 0;
        align-self: flex-start;
    }
    .send-page-content {
        display: grid;
        grid-template-columns: 1.5fr 1fr; /* Composition wider than Sent */
        gap: 20px;
        width: 100%;
    }

    .composition-panel {
        grid-column: 1 / 2;
        background: var(--card-bg);
        color: var(--theme-text-color);
        padding: 30px;
        border-radius: 20px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .sent-panel {
        grid-column: 2 / 3;
        background: var(--card-bg);
        color: var(--theme-text-color);
        padding: 30px;
        border-radius: 20px;
        min-height: 400px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
    }
    .sent-panel h2 {
        font-size: 3rem;
        font-weight: 800;
        color: var(--theme-text-color);
        margin-top: 0;
        margin-bottom: 20px;
    }
    .sent-list {
        width: 100%;
        overflow-y: auto;
        flex-grow: 1;
    }

    /* Message Input Bar (Replaced the textarea + button group) */
    .message-input-bar {
        display: flex;
        align-items: center;
        background: var(--button-bg); /* Dark background */
        padding: 10px 20px;
        border-radius: 20px;
        margin-top: 20px;
        width: 100%;
        box-sizing: border-box;
    }
    .message-input-bar textarea {
        flex-grow: 1;
        border: none;
        background: transparent;
        color: var(--button-text);
        font-weight: 500;
        text-align: left;
        margin: 0;
        padding: 10px 0;
        resize: none;
        min-height: 40px;
        max-height: 150px;
    }
    .message-input-bar textarea::placeholder {
        color: rgba(255, 255, 255, 0.7);
    }
    .message-input-bar .attachment-icon {
        cursor: pointer;
        font-size: 1.5rem;
        color: var(--button-text);
        padding: 5px;
        transition: opacity 0.2s;
    }
    .message-input-bar .attachment-icon:hover {
        opacity: 0.8;
    }

    /* Form inputs inside the composition panel */
    .composition-panel form {
        display: flex;
        flex-direction: column;
        height: 100%;
        justify-content: space-between;
    }
    .composition-panel input {
        width: 100%;
        padding: 15px 20px;
        border-radius: 20px;
        margin: 10px 0;
        background: var(--button-bg);
        color: var(--button-text);
        font-weight: 600;
        text-align: left;
    }
    .composition-panel input::placeholder {
        color: rgba(255, 255, 255, 0.7);
        text-align: left;
    }


    /* Messages in the sent list */
    .sent-item {
        padding: 15px;
        background: #eaf4ff; /* Lighter background for items */
        border-radius: 10px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        cursor: pointer;
        transition: transform 0.1s;
    }
    .sent-item:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .sent-item-header {
        display: flex;
        justify-content: space-between;
        font-size: 0.9rem;
        margin-bottom: 5px;
    }
    .sent-item-subject {
        font-weight: 600;
        color: var(--button-bg);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .sent-item-date {
        opacity: 0.7;
        font-size: 0.8rem;
    }
    
    h1, h2, h3 { 
        color: var(--theme-text-color); 
        font-weight: 700; 
        margin-top: 0;
    }
    
    /* --- Form Elements --- */
    form { margin-top: 20px; }
    label { display: none; } 
    input, textarea {
        width:100%; 
        padding: 12px; 
        border-radius: 10px; 
        border: 1px solid var(--theme-text-color);
        box-shadow: none;
        box-sizing: border-box;
        margin: 15px 0; 
        background: var(--button-bg); 
        color: var(--button-text); 
        font-weight: 600;
        text-align: center;
        transition: background-color 0.2s, color 0.2s;
    }
    input::placeholder, textarea::placeholder {
        color: rgba(255, 255, 255, 0.7);
    }
    input[type="file"] {
        background: transparent;
        color: var(--theme-text-color);
        border: 1px dashed var(--theme-text-color);
        padding: 15px;
    }

    /* --- Buttons (Themed) --- */
    button, .button {
        background: var(--button-bg); 
        color: var(--button-text); 
        border:none; 
        padding: 15px 40px; 
        border-radius: 10px; 
        cursor:pointer; 
        font-weight: 600;
        font-size: 1.1rem;
        text-decoration: none; 
        display: block; 
        width: 100%;
        box-sizing: border-box;
        margin: 15px 0;
        transition: background-color 0.3s ease-in-out, transform 0.2s ease-out, box-shadow 0.3s ease-in-out; 
    }
    
    /* Primary Button Hover */
    button:hover, .button:hover {
        background: #1a438b; 
        transform: translateY(-2px);
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
    }
    
    /* Secondary Button Styling */
    .button-secondary {
        background: #cae8ff; 
        color: var(--theme-text-color); 
        border: 1px solid var(--theme-text-color);
        box-shadow: none; 
    }
    
    /* Secondary Button Hover */
    .button-secondary:hover {
        background: #a9d4ff; 
        transform: translateY(0); 
        box-shadow: none;
    }
    
    .actions {
        display:flex; 
        gap:15px; 
        margin-top: 20px; 
        flex-wrap: wrap;
    }
    .actions .button {
        width: auto;
        display: inline-block;
        flex: 1; 
    }

    /* --- Utility --- */
    .small {
        font-size: 0.85rem; 
        color: var(--theme-text-color);
        opacity: 0.7;
    }
    .alert {
        background:#eaf4ff; 
        padding: 15px; 
        border-left: 5px solid var(--theme-text-color); 
        margin-bottom: 20px; 
        border-radius: 6px;
        color: var(--theme-text-color);
        text-align: left;
    }
    .text-success { color: var(--success); }
    .text-danger { color: var(--danger); }
    
    /* --- Table Styles (General) --- */
    table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 20px;
        background: #f8f9fa; /* Light background for tables */
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    th, td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid #dee2e6;
        font-size: 0.9rem;
        color: #343a40;
    }
    th {
        background: #e9ecef;
        font-weight: 700;
        text-transform: uppercase;
        color: var(--theme-text-color);
    }
    tr:last-child td {
        border-bottom: none;
    }


    /* --- Responsive --- */
    @media (min-width: 1000px) {
        .dashboard-card {
            max-width: 1100px;
            width: 100%;
        }
    }

    @media (max-width: 768px) {
        .wrap {margin: 20px auto; padding: 0 15px; align-items: flex-start;} /* Adjust alignment for smaller screens */
        .card {padding: 20px; max-width: 90%;}
        
        /* Mobile: Convert two-column card to stacked */
        .two-column-card {
            flex-direction: column;
            max-width: 100%;
            box-shadow: none; /* Remove card shadow on mobile as it's split */
        }
        .two-column-card > div {
             border-radius: 15px;
             margin-bottom: 15px; /* Spacing between stacked panels */
        }
        .left-panel, .right-panel {
            border-radius: 15px !important;
        }

        /* Mobile Dashboard: Stack everything */
        .dashboard-card {
             width: 100%;
        }
        .dashboard-grid {
            grid-template-columns: 1fr; /* Single column on mobile */
            gap: 15px;
        }
        .compose-bar {
            grid-column: 1 / 2; /* Span full width */
            order: 4; /* Move compose bar to the end of the stack */
            margin-top: 0;
        }
        .dashboard-panel {
            min-height: 250px;
        }
        
        /* Mobile Send Page: Stack columns */
        .send-page-wrapper {
             width: 100%;
        }
        .send-page-content {
            grid-template-columns: 1fr;
        }
        .composition-panel, .sent-panel {
            grid-column: 1 / 2;
            min-height: auto;
        }
        .sent-panel {
            order: 2; /* Ensure sent history is below composition panel */
            padding-top: 20px;
        }
        .composition-panel {
            order: 1;
            padding-bottom: 10px;
        }
        .send-page-wrapper h1 {
            font-size: 2.5rem;
            align-self: center;
        }

        /* Table responsiveness (Standard table style) */
        table, thead, tbody, th, td, tr {
            display: block;
        }
        thead tr {
            position: absolute;
            top: -9999px;
            left: -9999px;
        }
        td {
            border: none;
            border-bottom: 1px solid var(--border-color);
            position: relative;
            padding-left: 50%;
            text-align: right;
        }
        td:before {
            position: absolute;
            top: 12px;
            left: 6px;
            width: 45%;
            padding-right: 10px;
            white-space: nowrap;
            text-align: left;
            font-weight: 600;
            color: #495057;
        }
        /* Label the data */
        .admin-messages td:nth-of-type(1):before { content: "ID"; }
        .admin-messages td:nth-of-type(2):before { content: "Date"; }
        .admin-messages td:nth-of-type(3):before { content: "Sender"; }
        .admin-messages td:nth-of-type(4):before { content: "Receiver"; }
        .admin-messages td:nth-of-type(5):before { content: "Dir"; }
        .admin-messages td:nth-of-type(6):before { content: "Subject"; } /* Corrected index for mobile table */
        .admin-messages td:nth-of-type(7):before { content: "Message"; }
        .admin-messages td:nth-of-type(8):before { content: "Attach"; }
        
        .user-messages td:nth-of-type(1):before { content: "Date"; }
        .user-messages td:nth-of-type(2):before { content: "From/To"; }
        .user-messages td:nth-of-type(3):before { content: "Subject"; }
        .user-messages td:nth-of-type(4):before { content: "Message"; }
        .user-messages td:nth-of-type(5):before { content: "Attach"; }
        .user-messages td:nth-of-type(6):before { content: "Action"; } /* Added for mobile table */
        
        .admin-users td:nth-of-type(1):before { content: "Name"; }
        .admin-users td:nth-of-type(2):before { content: "Mobile"; }
        .admin-users td:nth-of-type(3):before { content: "User ID"; }
        .admin-users td:nth-of-type(4):before { content: "PIN"; }
        
        .admin-activity td:nth-of-type(1):before { content: "When"; }
        .admin-activity td:nth-of-type(2):before { content: "User"; }
        .admin-activity td:nth-of-type(3):before { content: "Action"; }
        .admin-activity td:nth-of-type(4):before { content: "Details"; }
    }
    
  </style>
</head>
<body>
  
  <div class="header-bar">
    <a href="{{ url_for('index') }}" class="logo-link">Mini Mail</a>
    <div class="header-controls">
        <button id="theme-toggle-btn" class="theme-toggle" onclick="toggleTheme()" title="Toggle Dark/Light Mode">
            ☀️
        </button>
        <div class="menu-icon" onclick="toggleDrawer()">☰</div>
    </div>
  </div>

  <div class="drawer" id="drawer">
    <div class="drawer-header">
      <h3>Navigation</h3>
      <span class="close-btn" onclick="toggleDrawer()">&times;</span>
    </div>

    {% if 'user_id' in session %}
      <div class="drawer-status">
        Logged in as: <strong>{{ session['user_name'] or session['user_id'] }}</strong>
      </div>
      <div class="divider"></div>
      <a href="{{ url_for('dashboard') }}">📬 Dashboard</a>
      <a href="{{ url_for('send_message') }}">✉️ Send Message</a>
      <a href="{{ url_for('view_messages') }}">📥 Messages</a>
      <a href="{{ url_for('trash_mailbox') }}">🗑️ Deleted Mail</a>
      <a href="{{ url_for('logout') }}">🚪 Logout</a>
    {% else %}
      <div class="drawer-status">
        Not logged in.
      </div>
      <div class="divider"></div>
      <a href="{{ url_for('login') }}">🔑 User Login</a>
      <a href="{{ url_for('signup') }}">🧾 Sign Up</a>
    {% endif %}

    <div class="divider"></div>
    <a href="{{ url_for('admin_login') }}">🛠 Admin Panel</a>
    <a href="{{ url_for('creators') }}">⭐ Creators</a>
    <a href="{{ url_for('index') }}">🏠 Home</a>

    <div class="divider"></div>
    <div class="drawer-status">
        <p>Mini Mail — local dev</p>
    </div>
  </div>


  <div class="wrap {% if request.path == '/' %}index-page-wrap{% endif %}">
    <!-- Check if the path is '/send' to apply the new wrapper class -->
    <div class="card {% if request.path == '/send' %}send-page-wrapper{% elif request.path == '/dashboard' %}dashboard-card{% endif %}">
      {% with messages = get_flashed_messages() %}
        {% if messages %}
          {% for msg in messages %}<div class="alert">{{ msg }}</div>{% endfor %}
        {% endif %}
      {% endwith %}
      {{ content|safe }}
    </div>
  </div>

  <script>
    // --- Theme Toggle Logic ---
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const body = document.body;

    function setTheme(mode) {
        if (mode === 'dark') {
            body.classList.add('dark-mode');
            themeToggleBtn.textContent = '🌙'; // Moon icon for dark mode
            localStorage.setItem('theme', 'dark');
        } else {
            body.classList.remove('dark-mode');
            themeToggleBtn.textContent = '☀️'; // Sun icon for light mode
            localStorage.setItem('theme', 'light');
        }
    }

    function toggleTheme() {
        if (body.classList.contains('dark-mode')) {
            setTheme('light');
        } else {
            setTheme('dark');
        }
    }

    // Initialize theme on load
    (function() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            setTheme('dark');
        } else if (savedTheme === 'light') {
             // Do nothing (default is light mode, already handled by CSS variables)
        } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            // Check OS preference if no setting is saved
             setTheme('dark');
        } else {
             setTheme('light');
        }
    })();
    // --- End Theme Toggle Logic ---
    
    function toggleDrawer() {
      const drawer = document.getElementById('drawer');
      drawer.classList.toggle('open');
    }

    // Close drawer if user clicks outside of it
    document.addEventListener('click', function(event) {
        const drawer = document.getElementById('drawer');
        const menuIcon = document.querySelector('.menu-icon');
        const themeToggle = document.getElementById('theme-toggle-btn');
        
        // If the drawer is open, and the click target is not the drawer itself
        // or the menu icon or the theme toggle, close the drawer.
        if (drawer.classList.contains('open') && !drawer.contains(event.target) && !menuIcon.contains(event.target) && !themeToggle.contains(event.target)) {
            toggleDrawer();
        }
    });

    function triggerFileSelect() {
        document.getElementById('attachment-input').click();
    }

    function updateAttachmentDisplay() {
        const fileInput = document.getElementById('attachment-input');
        const fileNameDisplay = document.getElementById('file-name-display');
        
        // Use the placeholder text input to display the file name 
        const messageTextarea = document.getElementById('message-textarea');

        if (fileInput.files.length > 0) {
            // Update the display below the composition bar
            fileNameDisplay.textContent = 'Attached: ' + fileInput.files[0].name;
            fileNameDisplay.style.display = 'block';
        } else {
            fileNameDisplay.textContent = '';
            fileNameDisplay.style.display = 'none';
        }
    }
    
    function navigateToSend() {
        // Simple way to navigate to the send page (to be replaced with actual form submission if required)
        window.location.href = "{{ url_for('send_message') }}";
    }

  </script>

</body>
</html>
"""

INDEX_PAGE = """
<div style="text-align: center; padding: 40px 20px;">
    <h1 style="font-size: 3rem; color: var(--theme-text-color); margin-bottom: 50px;">Mini Mail</h1>
    <div style="flex-direction: column; align-items: center; gap: 20px; margin-top: 30px;">
        <a href="{{ url_for('login') }}" class="button">LOGIN</a>
        <a href="{{ url_for('signup') }}" class="button">SIGN UP</a>
    </div>
</div>
"""

CREATORS_PAGE = """
<div style="text-align: center; padding: 20px 0;">
    <h3>About the Mini Mail Project</h3>
    <p>Mini Mail was developed as a demonstration project focusing on secure user authentication and basic messaging functionality with file attachment capabilities.</p>
    
    <div style="margin-top: 40px; text-align: left;">
        <h4 style="color: var(--button-bg); border-bottom: 2px solid var(--button-bg); padding-bottom: 5px;">The Creators</h4>
        <ul style="list-style: none; padding: 0;">
            <li style="font-size: 1.2rem; font-weight: 600; margin-bottom: 10px;">👤 ARMAN</li>
            <li style="font-size: 1.2rem; font-weight: 600; margin-bottom: 10px;">👤 DEVESH</li>
            <li style="font-size: 1.2rem; font-weight: 600; margin-bottom: 10px;">👤 THEJESWAR</li>
        </ul>
    </div>
    
    <div style="margin-top: 40px;">
        <a href="{{ url_for('index') }}" class="button button-secondary">GO HOME</a>
    </div>
</div>
"""

SIGNUP_PAGE = """
<h3>Create Account</h3>
<form method="post">
  <input name="name" required placeholder="Name">
  <input name="phone" required placeholder="Phone No.">
  <input name="user_id" required placeholder="User ID">
  <input name="pin" type="password" required maxlength="4" placeholder="PIN (4 digits)">
  <input name="confirm" type="password" required maxlength="4" placeholder="Confirm PIN">
  <button type="submit">SIGN UP</button>
</form>
"""

LOGIN_PAGE = """
<h3>User Login</h3>
<form method="post">
  <input name="user_id" required placeholder="User ID">
  <input name="pin" type="password" required maxlength="4" placeholder="PIN">
  <button type="submit">LOGIN</button>
  <button type="button" class="button-secondary" onclick="alert('Please contact an admin to reset your PIN.')">FORGOT PIN</button>
</form>
"""

DASHBOARD_PAGE = """
<!-- The main wrapper handles the dashboard layout -->
<h1 style="color: var(--card-bg);">dashboard</h1>

<div class="dashboard-grid">
    <!-- Panel 1: Feed (Wider column) -->
    <div class="dashboard-panel" style="grid-column: 1 / 2;">
        <h4>feed</h4>
        <div style="overflow-y: auto; flex-grow: 1;">
            <p class="small" style="opacity: 0.9; text-align: center;">Recent activity and important updates will appear here.</p>
            <!-- Mock feed content -->
            <div class="sent-item">
                <div class="sent-item-subject">System Update: New UI deployed!</div>
                <div class="sent-item-date">Just now</div>
            </div>
            <div class="sent-item">
                <div class="sent-item-subject">Welcome {{ name }}!</div>
                <div class="sent-item-date">Dec 15</div>
            </div>
        </div>
    </div>

    <!-- Panel 2: Inbox -->
    <div class="dashboard-panel" style="grid-column: 2 / 3;">
        <h4>inbox</h4>
        <div style="overflow-y: auto; flex-grow: 1;">
            {% if received %}
                {% for r in received %}
                    <div class="sent-item" onclick="window.location.href='{{ url_for('view_messages') }}'">
                        <div class="sent-item-header">
                            <span class="small">From: {{ r[1] }}</span>
                            <span class="sent-item-date">{{ r[0].strftime('%b %d') }}</span>
                        </div>
                        <div class="sent-item-subject">{{ r[4] or 'No Subject' }}</div>
                    </div>
                {% endfor %}
            {% else %}
                <p class="small" style="opacity: 0.9; text-align: center;">Your inbox is empty.</p>
            {% endif %}
        </div>
        <a href="{{ url_for('view_messages') }}" class="button button-secondary" style="margin-top: 20px;">View All ({{ received|length }})</a>
    </div>

    <!-- Panel 3: Sent/Recent Received (Named 'received' in image, used for Sent in our logic) -->
    <div class="dashboard-panel" style="grid-column: 3 / 4;">
        <h4>sent</h4>
        <div style="overflow-y: auto; flex-grow: 1;">
            {% if sent %}
                {% for s in sent %}
                    <div class="sent-item" onclick="window.location.href='{{ url_for('view_messages') }}'">
                        <div class="sent-item-header">
                            <span class="small">To: {{ s[1] }}</span>
                            <span class="sent-item-date">{{ s[0].strftime('%b %d') }}</span>
                        </div>
                        <div class="sent-item-subject">{{ s[4] or 'No Subject' }}</div>
                    </div>
                {% endfor %}
            {% else %}
                <p class="small" style="opacity: 0.9; text-align: center;">You haven't sent any messages.</p>
            {% endif %}
        </div>
        <a href="{{ url_for('view_messages') }}" class="button button-secondary" style="margin-top: 20px;">View All ({{ sent|length }})</a>
    </div>
    
    <!-- Compose Bar (Spans the bottom two columns) -->
    <div class="compose-bar" onclick="navigateToSend()">
        <input type="text" placeholder="type here" readonly>
        <div class="attachment-icon">&#128206;</div> <!-- Paperclip icon -->
    </div>
</div>
"""

SEND_PAGE = """
<h1 style="color: var(--card-bg);">Send New Message</h1>

<div class="send-page-content">
    
    <!-- Left Panel: Composition -->
    <div class="composition-panel">
        <form method="post" enctype="multipart/form-data">
            <div>
                <input name="to_id" required placeholder="receiver id">
                <input name="subject" required placeholder="subject">
            </div>

            <!-- Message Input Bar (Replaces the standard textarea) -->
            <div style="flex-grow: 1; display: flex; flex-direction: column; justify-content: flex-end;">
                <input type="file" name="attachment" id="attachment-input" style="display: none;" onchange="updateAttachmentDisplay()">
                <div class="message-input-bar">
                    <textarea name="message" id="message-textarea" rows="2" required maxlength="1000" placeholder="type here"></textarea>
                    <div class="attachment-icon" onclick="triggerFileSelect()" title="Attach File">&#128206;</div> <!-- Paperclip icon -->
                </div>
                <p id="file-name-display" class="small text-success" style="display: none; text-align: left; margin: 5px 0 0 0;"></p>
                
                <button type="submit" style="margin-top: 20px;">SEND MESSAGE</button>
            </div>
        </form>
    </div>

    <!-- Right Panel: Sent History -->
    <div class="sent-panel">
        <h2>sent</h2>
        <div class="sent-list">
            {% if sent %}
                {% for s in sent %}
                    <div class="sent-item" title="{{ s[2] }}">
                        <div class="sent-item-header">
                            <span class="small">To: {{ s[0] }}</span>
                            <span class="sent-item-date">{{ s[1].strftime('%H:%M, %b %d') }}</span>
                        </div>
                        <div class="sent-item-subject">{{ s[3] or "No Subject" }}</div>
                    </div>
                {% endfor %}
            {% else %}
                <p class="small" style="text-align: center; padding: 40px 0; opacity: 0.9;">No sent messages yet. Start a conversation!</p>
            {% endif %}
        </div>
    </div>
</div>
"""

VIEW_PAGE = """
<h3>Message Inbox (User: {{ uid }})</h3>
{% if not received and not sent %}
    <div style="text-align: center; padding: 30px; border: 1px dashed var(--theme-text-color); border-radius: 8px;">
        <p style="font-size: 1.1rem; color: var(--theme-text-color);">You have no messages yet.</p>
        <a href="{{ url_for('send_message') }}" class="button">Start New Conversation</a>
    </div>
{% endif %}

<h4 style="margin-top: 30px;">📥 Received Messages</h4>
<table class="user-messages">
<thead>
<tr><th>Date</th><th>From</th><th>Subject</th><th>Message</th><th>Attachment</th><th>Action</th></tr>
</thead>
<tbody>
{% for r in received %}
<tr>
  <td>{{ r[1].strftime('%Y-%m-%d %H:%M') }}</td>
  <td><strong>{{ r[2] }}</strong></td>
  <td>{{ r[5] or '-' }}</td>
  <td>{{ r[3] | truncate(100) }}</td>
  <td>{% if r[4] %}<a href="{{ url_for('uploaded_file', filename=r[4]) }}" target="_blank">📎 View File</a>{% else %}-{% endif %}</td>
  <td>
    <form method="post" action="{{ url_for('delete_message_soft', type='received', message_id=r[0]) }}" style="margin: 0;">
        <button type="submit" class="button small" style="padding: 5px 10px; font-size: 0.8rem; background: var(--danger); width: auto;">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody>
</table>

<h4 style="margin-top: 40px;">✉️ Sent Messages</h4>
<table class="user-messages">
<thead>
<tr><th>Date</th><th>To</th><th>Subject</th><th>Message</th><th>Attachment</th><th>Action</th></tr>
</thead>
<tbody>
{% for s in sent %}
<tr>
  <td>{{ s[1].strftime('%Y-%m-%d %H:%M') }}</td>
  <td><strong>{{ s[2] }}</strong></td>
  <td>{{ s[5] or '-' }}</td>
  <td>{{ s[3] | truncate(100) }}</td>
  <td>{% if s[4] %}<a href="{{ url_for('uploaded_file', filename=s[4]) }}" target="_blank">📎 View File</a>{% else %}-{% endif %}</td>
  <td>
    <form method="post" action="{{ url_for('delete_message_soft', type='sent', message_id=s[0]) }}" style="margin: 0;">
        <button type="submit" class="button small" style="padding: 5px 10px; font-size: 0.8rem; background: var(--danger); width: auto;">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody>
</table>
"""

TRASH_PAGE = """
<h3>Deleted Messages (User: {{ uid }})</h3>
{% if not deleted_received and not deleted_sent %}
    <div style="text-align: center; padding: 30px; border: 1px dashed var(--theme-text-color); border-radius: 8px;">
        <p style="font-size: 1.1rem; color: var(--theme-text-color);">Your trash is empty. Nothing deleted yet!</p>
    </div>
{% endif %}

<h4 style="margin-top: 30px;">📥 Deleted Received Messages</h4>
<table class="user-messages">
<thead>
<tr><th>ID</th><th>Date</th><th>From</th><th>Subject</th><th>Action</th></tr>
</thead>
<tbody>
{% for r in deleted_received %}
<tr>
  <td>{{ r[0] }}</td>
  <td>{{ r[1].strftime('%Y-%m-%d %H:%M') }}</td>
  <td><strong>{{ r[2] }}</strong></td>
  <td>{{ r[5] or '-' }}</td>
  <td>
    <div class="actions" style="margin: 0; display: flex; gap: 5px;">
        <!-- Using a form here for proper DELETE/POST request -->
        <form method="post" action="{{ url_for('delete_message_permanent', type='received', message_id=r[0]) }}" style="margin: 0;">
            <button type="submit" class="button small" style="padding: 5px 10px; font-size: 0.8rem; background: var(--danger); width: auto;">Purge</button>
        </form>
        <form method="post" action="{{ url_for('restore_message', type='received', message_id=r[0]) }}" style="margin: 0;">
            <button type="submit" class="button button-secondary small" style="padding: 5px 10px; font-size: 0.8rem; width: auto; background: var(--success);">Restore</button>
        </form>
    </div>
  </td>
</tr>
{% endfor %}
</tbody>
</table>

<h4 style="margin-top: 40px;">✉️ Deleted Sent Messages</h4>
<table class="user-messages">
<thead>
<tr><th>ID</th><th>Date</th><th>To</th><th>Subject</th><th>Action</th></tr>
</thead>
<tbody>
{% for s in deleted_sent %}
<tr>
  <td>{{ s[0] }}</td>
  <td>{{ s[1].strftime('%Y-%m-%d %H:%M') }}</td>
  <td><strong>{{ s[2] }}</strong></td>
  <td>{{ s[5] or '-' }}</td>
  <td>
    <div class="actions" style="margin: 0; display: flex; gap: 5px;">
        <!-- Using a form here for proper DELETE/POST request -->
        <form method="post" action="{{ url_for('delete_message_permanent', type='sent', message_id=s[0]) }}" style="margin: 0;">
            <button type="submit" class="button small" style="padding: 5px 10px; font-size: 0.8rem; background: var(--danger); width: auto;">Purge</button>
        </form>
        <form method="post" action="{{ url_for('restore_message', type='sent', message_id=s[0]) }}" style="margin: 0;">
            <button type="submit" class="button button-secondary small" style="padding: 5px 10px; font-size: 0.8rem; width: auto; background: var(--success);">Restore</button>
        </form>
    </div>
  </td>
</tr>
{% endfor %}
</tbody>
</table>
"""

ADMIN_LOGIN_PAGE = """
<h3>Admin Login</h3>
<form method="post">
  <input name="username" required placeholder="Admin ID">
  <input name="password" type="password" required placeholder="PIN">
  <button type="submit">LOGIN</button>
  <button type="button" class="button-secondary" onclick="alert('Please contact the primary system administrator to reset the admin PIN.')">FORGOT PIN</button>
</form>
"""

ADMIN_DASH_PAGE = """
<h3>Admin Dashboard ({{ admin }})</h3>
<p class="small">Full system oversight including user data, global messages, and activity logs.</p>

<h4 style="margin-top: 30px;">Registered Users (Total: {{ users | length }})</h4>
<table class="admin-users">
<thead>
<tr><th>Name</th><th>Mobile</th><th>User ID</th><th>PIN</th></tr>
</thead>
<tbody>
{% for u in users %}
<tr><td>{{ u[0] }}</td><td>{{ u[1] }}</td><td>{{ u[2] }}</td><td>{{ u[3] }}</td></tr>
{% endfor %}
</tbody>
</table>

<h4 style="margin-top: 40px;">Global Messages (Last 500)</h4>
<table class="admin-messages">
<thead>
<tr><th>ID</th><th>Date</th><th>Sender</th><th>Receiver</th><th>Dir</th><th>Subject</th><th>Message</th><th>Attachment</th></tr>
</thead>
<tbody>
{% for m in messages %}
<tr>
  <td>{{ m[0] }}</td>
  <td>{{ m[1].strftime('%Y-%m-%d %H:%M') }}</td>
  <td>{{ m[2] }}</td>
  <td>{{ m[3] }}</td>
  <td><span class="text-{{ 'success' if m[4] == 'sent' else 'secondary' }}">{{ m[4] }}</span></td>
  <td>{{ m[6] or '-' }}</td> <!-- Subject field -->
  <td style="max-width:300px; font-size:12px;">{{ m[5] | truncate(80) }}</td>
  <td>{% if m[7] %}<a href="{{ url_for('uploaded_file', filename=m[7]) }}" target="_blank">📎</a>{% else %}-{% endif %}</td>
</tr>
{% endfor %}
</tbody>
</table>

<h4 style="margin-top: 40px;">User Activity (Last 500)</h4>
<table class="admin-activity">
<thead>
<tr><th>When</th><th>User</th><th>Action</th><th>Details</th></tr>
</thead>
<tbody>
{% for a in activity %}
<tr>
  <td>{{ a[1].strftime('%Y-%m-%d %H:%M') }}</td>
  <td>{{ a[2] }}</td>
  <td><strong>{{ a[3] }}</strong></td>
  <td><span class="small">{{ a[4] }}</span></td>
</tr>
{% endfor %}
</tbody>
</table>
"""

# -------------------- render helper --------------------
def render(content, **kwargs):
    # Added logic to check if a wide layout is needed based on the rendered content
    return render_template_string(BASE, content=render_template_string(content, **kwargs), is_wide=kwargs.get('is_wide', False))


# -------------------- ROUTES --------------------
@app.route('/')
def index():
    return render(INDEX_PAGE)

@app.route('/creators')
def creators():
    return render(CREATORS_PAGE)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        user_id = request.form.get('user_id', '').strip()
        pin = request.form.get('pin', '').strip()
        confirm = request.form.get('confirm', '').strip()

        if not all([name, phone, user_id, pin, confirm]):
            flash("All fields required")
            return redirect(url_for('signup'))
        if not pin.isdigit() or len(pin) != 4 or pin != confirm:
            flash("PIN must be 4 digits and match confirmation")
            return redirect(url_for('signup'))

        con = connect_server()
        cur = con.cursor()
        cur.execute("USE mail")
        cur.execute("SELECT user_ID FROM userdetails WHERE user_ID=%s", (user_id,))
        if cur.fetchone():
            cur.close()
            con.close()
            flash("User ID already exists")
            return redirect(url_for('signup'))

        cur.execute("INSERT INTO userdetails (name, mobile_no, user_ID, pin) VALUES (%s,%s,%s,%s)",
                    (name, phone, user_id, int(pin)))
        con.commit()

        # create per-user DB and tables
        db_name = f"`{user_id}`"
        try:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            cur.execute(f"USE {db_name}")
            # Updated table schema to include subject and is_deleted
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages_sent(
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    date DATETIME,
                    sent_to VARCHAR(50),
                    sent_message TEXT,
                    subject VARCHAR(255),
                    attachment VARCHAR(255),
                    is_deleted TINYINT DEFAULT 0 /* NEW COLUMN */
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages_received(
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    date DATETIME,
                    received_from VARCHAR(50),
                    received_message TEXT,
                    subject VARCHAR(255),
                    attachment VARCHAR(255),
                    is_deleted TINYINT DEFAULT 0 /* NEW COLUMN */
                )
            """)
            con.commit()
        except m.Error as err:
            flash(f"Error creating user database: {err}. Please contact admin.")
            # Note: We continue execution here to allow the process to finish cleanly.
            print(f"Error creating user database for {user_id}: {err}")
            
        cur.close()
        con.close()

        # log signup
        log_user_activity(user_id, "signup", f"Account created for {name}")
        flash("Account created — you may now log in")
        return redirect(url_for('login'))

    return render(SIGNUP_PAGE)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id', '').strip()
        pin = request.form.get('pin', '').strip()
        con = connect_server()
        cur = con.cursor()
        cur.execute("USE mail")
        cur.execute("SELECT name, pin FROM userdetails WHERE user_ID=%s", (user_id,))
        row = cur.fetchone()
        cur.close()
        con.close()
        if not row:
            flash("User not found")
            return redirect(url_for('login'))
        if str(row[1]) != str(pin):
            flash("Incorrect PIN")
            return redirect(url_for('login'))

        session['user_id'] = user_id
        session['user_name'] = row[0]
        log_user_activity(user_id, "login", f"{user_id} logged in")
        flash("Logged in successfully!")
        return redirect(url_for('dashboard'))
    return render(LOGIN_PAGE)


@app.route('/logout')
def logout():
    if 'user_id' in session:
        uid = session['user_id']
        log_user_activity(uid, "logout", f"{uid} logged out")
    session.clear()
    flash("Logged out")
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please login to view your dashboard")
        return redirect(url_for('login'))
    
    uid = session['user_id']
    received = []
    sent = []
    
    try:
        # Fetch up to 5 received messages, excluding deleted ones
        con = m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=uid)
        cur = con.cursor()
        # Fetching date, received_from, received_message, attachment, subject
        cur.execute("SELECT date, received_from, received_message, attachment, subject FROM messages_received WHERE is_deleted = 0 ORDER BY date DESC LIMIT 5")
        received = cur.fetchall()
        # Fetching date, sent_to, sent_message, attachment, subject
        cur.execute("SELECT date, sent_to, sent_message, attachment, subject FROM messages_sent WHERE is_deleted = 0 ORDER BY date DESC LIMIT 5")
        sent = cur.fetchall()
        cur.close()
        con.close()
    except m.Error as err:
        flash(f"Error accessing your messages for the dashboard: {err}.")
    
    return render(DASHBOARD_PAGE, 
                  name=session.get('user_name', session['user_id']),
                  received=received,
                  sent=sent)


@app.route('/send', methods=['GET', 'POST'])
def send_message():
    if 'user_id' not in session:
        flash("Please login to send a message")
        return redirect(url_for('login'))

    uid = session['user_id']
    
    # Logic for POST (Sending message)
    if request.method == 'POST':
        sender = uid
        receiver = request.form.get('to_id', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        file = request.files.get('attachment')

        if not receiver or not message or not subject:
            flash("Receiver, Subject, and message required")
            return redirect(url_for('send_message'))

        # verify receiver exists
        try:
            con = connect_server()
            cur = con.cursor()
            cur.execute("USE mail")
            cur.execute("SELECT user_ID FROM userdetails WHERE user_ID=%s", (receiver,))
            if not cur.fetchone():
                cur.close()
                con.close()
                flash(f"Receiver '{receiver}' not found in the system.")
                return redirect(url_for('send_message'))
            cur.close()
            con.close()
        except m.Error as err:
            flash(f"Database error during receiver verification: {err}")
            return redirect(url_for('send_message'))

        # handle file
        filename_rel = None
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("File type not allowed")
                return redirect(url_for('send_message'))
            safe = secure_filename(file.filename)
            user_dir = os.path.join(app.config["UPLOAD_FOLDER"], sender)
            os.makedirs(user_dir, exist_ok=True)
            path = os.path.join(user_dir, safe)
            file.save(path)
            filename_rel = f"{sender}/{safe}"

        now = datetime.now()

        try:
            # insert into sender DB
            con1 = m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=sender)
            cur1 = con1.cursor()
            # Updated INSERT query to include subject
            cur1.execute("INSERT INTO messages_sent (date, sent_to, sent_message, subject, attachment) VALUES (%s,%s,%s,%s,%s)",
                         (now, receiver, message, subject, filename_rel))
            con1.commit()
            cur1.close()
            con1.close()

            # insert into receiver DB
            con2 = m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=receiver)
            cur2 = con2.cursor()
            # Updated INSERT query to include subject
            cur2.execute("INSERT INTO messages_received (date, received_from, received_message, subject, attachment) VALUES (%s,%s,%s,%s,%s)",
                         (now, sender, message, subject, filename_rel))
            con2.commit()
            cur2.close()
            con2.close()

            # add global logs
            log_message_global(sender, receiver, "sent", message, subject, filename_rel)
            log_user_activity(sender, "message_sent", f"sent to {receiver} (Sub: {subject})")
            log_user_activity(receiver, "message_received", f"from {sender} (Sub: {subject})")

            flash("Message sent successfully!")
            return redirect(url_for('send_message'))
        
        except m.Error as err:
            flash(f"A database error occurred while sending the message: {err}")
            return redirect(url_for('send_message'))

    # Logic for GET (Displaying form and sent messages)
    sent_messages = []
    try:
        con = m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=uid)
        cur = con.cursor()
        # Fetching sent_to, date, sent_message (for tooltip), subject, excluding deleted
        cur.execute("SELECT sent_to, date, sent_message, subject FROM messages_sent WHERE is_deleted = 0 ORDER BY date DESC")
        sent_messages = cur.fetchall()
        cur.close()
        con.close()
    except m.Error as err:
        flash(f"Error accessing your sent messages history: {err}.")
    
    # The 'send-page-wrapper' class in BASE handles the wide layout
    return render(SEND_PAGE, sent=sent_messages, is_wide=True)


@app.route('/view')
def view_messages():
    if 'user_id' not in session:
        flash("Please login to view your messages")
        return redirect(url_for('login'))

    uid = session['user_id']
    received = []
    sent = []
    try:
        con = m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=uid)
        cur = con.cursor()
        # Fetching id, date, received_from, received_message, attachment, subject, excluding deleted
        cur.execute("SELECT id, date, received_from, received_message, attachment, subject FROM messages_received WHERE is_deleted = 0 ORDER BY date DESC")
        received = cur.fetchall()
        # Fetching id, date, sent_to, sent_message, attachment, subject, excluding deleted
        cur.execute("SELECT id, date, sent_to, sent_message, attachment, subject FROM messages_sent WHERE is_deleted = 0 ORDER BY date DESC")
        sent = cur.fetchall()
        cur.close()
        con.close()
    except m.Error as err:
        flash(f"Error accessing your messages: {err}. Please contact admin.")
        
    return render(VIEW_PAGE, received=received, sent=sent, uid=uid)

# -------------------- TRASH/DELETE ROUTES --------------------

# Helper function to perform DB action
def perform_message_action(uid, msg_type, msg_id, action):
    try:
        con = m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=uid)
        cur = con.cursor()
        
        table = f"messages_{msg_type}" # messages_received or messages_sent
        
        if action == 'soft_delete':
            cur.execute(f"UPDATE {table} SET is_deleted = 1 WHERE id = %s", (msg_id,))
            msg = "moved to trash"
        elif action == 'restore':
            cur.execute(f"UPDATE {table} SET is_deleted = 0 WHERE id = %s", (msg_id,))
            msg = "restored"
        elif action == 'purge':
            # WARNING: This is permanent deletion!
            # Fetch attachment path first to delete the file
            cur.execute(f"SELECT attachment FROM {table} WHERE id = %s", (msg_id,))
            attachment_rel_path = cur.fetchone()
            if attachment_rel_path and attachment_rel_path[0]:
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], attachment_rel_path[0])
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            cur.execute(f"DELETE FROM {table} WHERE id = %s", (msg_id,))
            msg = "permanently deleted"
        else:
            con.close()
            return False, "Invalid action"
            
        con.commit()
        cur.close()
        con.close()
        return True, f"Message {msg_id} ({msg_type}) {msg} successfully."
        
    except m.Error as err:
        return False, f"Database error during message action: {err}"
    except Exception as e:
        return False, f"Error during file deletion/database action: {e}"


@app.route('/delete_message_soft/<string:type>/<int:message_id>', methods=['POST'])
def delete_message_soft(type, message_id):
    if 'user_id' not in session:
        flash("Please login to manage messages")
        return redirect(url_for('login'))
        
    uid = session['user_id']
    success, message = perform_message_action(uid, type, message_id, 'soft_delete')
    
    if success:
        flash(message, 'success')
        log_user_activity(uid, "message_deleted", f"Soft deleted message {message_id} ({type})")
    else:
        flash(message, 'danger')
        
    return redirect(url_for('view_messages'))


@app.route('/delete_message_permanent/<string:type>/<int:message_id>', methods=['POST'])
def delete_message_permanent(type, message_id):
    if 'user_id' not in session:
        flash("Please login to manage messages")
        return redirect(url_for('login'))
        
    uid = session['user_id']
    success, message = perform_message_action(uid, type, message_id, 'purge')
    
    if success:
        flash(message, 'success')
        log_user_activity(uid, "message_purged", f"Permanently deleted message {message_id} ({type})")
    else:
        flash(message, 'danger')
        
    return redirect(url_for('trash_mailbox'))


@app.route('/restore_message/<string:type>/<int:message_id>', methods=['POST'])
def restore_message(type, message_id):
    if 'user_id' not in session:
        flash("Please login to manage messages")
        return redirect(url_for('login'))
        
    uid = session['user_id']
    success, message = perform_message_action(uid, type, message_id, 'restore')
    
    if success:
        flash(message, 'success')
        log_user_activity(uid, "message_restored", f"Restored message {message_id} ({type})")
    else:
        flash(message, 'danger')
        
    return redirect(url_for('trash_mailbox'))


@app.route('/trash')
def trash_mailbox():
    if 'user_id' not in session:
        flash("Please login to view your deleted mail")
        return redirect(url_for('login'))

    uid = session['user_id']
    deleted_received = []
    deleted_sent = []
    try:
        con = m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=uid)
        cur = con.cursor()
        
        # id, date, received_from, received_message, attachment, subject (is_deleted = 1)
        cur.execute("SELECT id, date, received_from, received_message, attachment, subject FROM messages_received WHERE is_deleted = 1 ORDER BY date DESC")
        deleted_received = cur.fetchall()
        
        # id, date, sent_to, sent_message, attachment, subject (is_deleted = 1)
        cur.execute("SELECT id, date, sent_to, sent_message, attachment, subject FROM messages_sent WHERE is_deleted = 1 ORDER BY date DESC")
        deleted_sent = cur.fetchall()
        
        cur.close()
        con.close()
    except m.Error as err:
        flash(f"Error accessing your deleted messages: {err}. Please contact admin.")
        
    return render(TRASH_PAGE, deleted_received=deleted_received, deleted_sent=deleted_sent, uid=uid)


# -------------------- ADMIN ROUTES --------------------
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        con = connect_server()
        cur = con.cursor()
        cur.execute("USE mail")
        cur.execute("SELECT admin_id FROM admins WHERE username=%s AND password=%s", (username, password))
        row = cur.fetchone()
        cur.close()
        con.close()
        if row:
            session['is_admin'] = True
            session['admin_username'] = username
            flash("Admin logged in successfully!")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid admin credentials")
            return redirect(url_for('admin_login'))
    return render(ADMIN_LOGIN_PAGE)


@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        flash("Admin login required")
        return redirect(url_for('admin_login'))

    con = connect_server()
    cur = con.cursor()
    cur.execute("USE mail")
    cur.execute("SELECT name, mobile_no, user_ID, pin FROM userdetails")
    users = cur.fetchall()

    # Updated query to retrieve subject (column index 6)
    cur.execute("SELECT * FROM all_messages ORDER BY message_date DESC LIMIT 500")
    messages = cur.fetchall()

    cur.execute("SELECT * FROM user_activity ORDER BY timestamp DESC LIMIT 500")
    activity = cur.fetchall()

    cur.close()
    con.close()
    return render(ADMIN_DASH_PAGE, admin=session.get('admin_username', 'admin'), users=users, messages=messages, activity=activity)


# -------------------- START --------------------
if __name__ == "__main__":
    initialize_system()
    # run app
    app.run(host="0.0.0.0", port=5001, debug=True)