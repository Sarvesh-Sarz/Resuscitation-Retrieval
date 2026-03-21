# 🚑 Emergency Response & Ambulance Dispatch Management System

A web-based emergency management platform built with **Flask** and **MySQL** that handles ambulance dispatch, driver and hospital management, emergency call registration, and real-time dispatch tracking.

---

##  Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Setup & Installation](#setup--installation)
- [Running the App](#running-the-app)
- [Routes Reference](#routes-reference)
- [Screenshots](#screenshots)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [License](#license)

---

## ✨ Features

- **Location Management** — Add and manage service areas (area, city, pincode)
- **Hospital Management** — Register hospitals with contact details
- **Ambulance Management** — Track vehicles with availability status and capacity
- **Driver Management** — Register drivers with license and contact info
- **Emergency Call Registration** — Log calls with patient details and severity
- **Automatic Dispatch** — Assigns the first available ambulance to an incoming call
- **Dispatch Tracking** — View all active and past dispatch records in a table
- **Responsive UI** — Glassmorphism-styled frontend with a sticky navbar

---

## 🛠 Tech Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Backend    | Python 3.x, Flask                 |
| Database   | MySQL 8.0, mysql-connector-python |
| Frontend   | Jinja2 Templates, HTML5, CSS3     |
| Styling    | Custom CSS with CSS Variables     |

---

## 📁 Project Structure

```
emergency-system/
│
├── app.py                  # Main Flask application & all route handlers
│
├── templates/
│   ├── base.html           # Base layout with navbar (extended by all pages)
│   ├── index.html          # Dashboard homepage
│   ├── add_location.html   # Form: add a service location
│   ├── add_hospital.html   # Form: register a hospital
│   ├── add_ambulance.html  # Form: add an ambulance unit
│   ├── add_driver.html     # Form: register a driver
│   ├── register_call.html  # Form: log an emergency call + patient info
│   └── dispatch_list.html  # Table: view all dispatch records
│
└── static/
    └── style.css           # Global styles, theme variables, form & table styling
```

---

## 🗄 Database Schema

> Database name: `emergency_system_24bds1109`

```sql
CREATE TABLE Location (
    location_id INT AUTO_INCREMENT PRIMARY KEY,
    area        VARCHAR(100),
    city        VARCHAR(100),
    pincode     VARCHAR(10)
);

CREATE TABLE Hospital (
    hospital_id   INT AUTO_INCREMENT PRIMARY KEY,
    hospital_name VARCHAR(150),
    address       VARCHAR(255),
    contact       VARCHAR(20)
);

CREATE TABLE Ambulance (
    ambulance_id        INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_number      VARCHAR(20),
    capacity            INT,
    availability_status ENUM('Available','Busy') DEFAULT 'Available'
);

CREATE TABLE Driver (
    driver_id      INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(100),
    phone          VARCHAR(15),
    license_number VARCHAR(50)
);

CREATE TABLE Emergency_Call (
    call_id        INT AUTO_INCREMENT PRIMARY KEY,
    emergency_type VARCHAR(100),
    status         ENUM('Pending','Dispatched','Resolved') DEFAULT 'Pending',
    location_id    INT,
    FOREIGN KEY (location_id) REFERENCES Location(location_id)
);

CREATE TABLE Patient (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100),
    age        INT,
    gender     ENUM('Male','Female','Other'),
    contact    VARCHAR(15),
    call_id    INT,
    FOREIGN KEY (call_id) REFERENCES Emergency_Call(call_id)
);

CREATE TABLE Dispatch (
    dispatch_id  INT AUTO_INCREMENT PRIMARY KEY,
    call_id      INT,
    ambulance_id INT,
    driver_id    INT,
    hospital_id  INT,
    FOREIGN KEY (call_id)      REFERENCES Emergency_Call(call_id),
    FOREIGN KEY (ambulance_id) REFERENCES Ambulance(ambulance_id),
    FOREIGN KEY (driver_id)    REFERENCES Driver(driver_id),
    FOREIGN KEY (hospital_id)  REFERENCES Hospital(hospital_id)
);
```

---

## ⚙️ Setup & Installation

### Prerequisites

- Python 3.8+
- MySQL 8.0+
- pip

### 1. Clone the repository

```bash
git clone https://github.com/your-username/emergency-dispatch-system.git
cd emergency-dispatch-system
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install flask mysql-connector-python
```

### 4. Set up the database

Log into MySQL and run:

```sql
CREATE DATABASE emergency_system_24bds1109;
USE emergency_system_24bds1109;
-- Then paste and run the CREATE TABLE statements from the schema above
```

### 5. Configure database credentials

Open `app.py` and update the `get_db()` function:

```python
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="your_mysql_user",
        password="your_mysql_password",
        database="emergency_system_24bds1109"
    )
```

> ⚠️ **Never commit real credentials to version control.** Use environment variables or a `.env` file in production.

---

## ▶️ Running the App

```bash
python app.py
```

The app will start at **http://127.0.0.1:5000** in debug mode.

---

## 🗺 Routes Reference

| Method | Route            | Description                              |
|--------|------------------|------------------------------------------|
| GET    | `/`              | Dashboard homepage                       |
| GET/POST | `/add_location` | Add a new service location              |
| GET/POST | `/add_hospital` | Register a new hospital                 |
| GET/POST | `/add_ambulance`| Add a new ambulance unit                |
| GET/POST | `/add_driver`   | Register a new driver                   |
| GET/POST | `/register`     | Log an emergency call, auto-dispatches  |
| GET    | `/dispatches`    | View all dispatch records               |

---

## ⚠️ Known Limitations

- **No authentication** — all routes are publicly accessible
- **Naive dispatch logic** — assigns the first available ambulance regardless of proximity
- **Race condition** — concurrent calls may be assigned the same ambulance
- **No input validation** — form data is not sanitized beyond `required` HTML attributes
- **No pagination** — `/dispatches` loads all records at once
- **Hardcoded DB credentials** — must be moved to environment variables before deployment
- **No timestamps** — calls and dispatches have no `created_at` fields for response time tracking

See `Emergency_System_Enhancement_Roadmap.docx` for the full technical improvement plan.

---

## 🛣 Roadmap

- [ ] Role-based authentication (Admin, Operator, Hospital Staff, Driver)
- [ ] Proximity-based intelligent ambulance allocation
- [ ] Race condition fix with `SELECT FOR UPDATE`
- [ ] Real-time dispatch map with Leaflet.js + Flask-SocketIO
- [ ] Analytics dashboard (response times, busiest areas, revenue)
- [ ] SMS notifications via Twilio on dispatch
- [ ] Driver mobile PWA with GPS tracking
- [ ] Input validation with Marshmallow
- [ ] Production deployment (Gunicorn + Nginx + HTTPS)
- [ ] ML-based demand forecasting for ambulance pre-positioning

---
