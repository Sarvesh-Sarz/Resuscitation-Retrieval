from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
import mysql.connector
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-in-production")

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="USER",
        password="PASSWORD",
        database="DATABASE NAME"
    )

@app.before_request
def auto_cleanup():
    try:
        db = get_db()
        cursor = db.cursor()
        # Archive old dispatches before deleting
        cursor.execute("""
            INSERT INTO Dispatch_Archive 
            SELECT d.*, ec.emergency_type, ec.created_at,
            p.name, p.age, p.gender, p.contact,
            a.vehicle_number, dr.name, h.hospital_name
            FROM Dispatch d
            JOIN Emergency_Call ec ON d.call_id = ec.call_id
            JOIN Patient p ON ec.call_id = p.call_id
            JOIN Ambulance a ON d.ambulance_id = a.ambulance_id
            JOIN Driver dr ON d.driver_id = dr.driver_id
            JOIN Hospital h ON d.hospital_id = h.hospital_id
            WHERE DATE(ec.created_at) < CURDATE()
        """)
        # Delete dispatches whose call is older than today
        cursor.execute("""
            DELETE FROM Dispatch
            WHERE call_id IN (
                SELECT call_id FROM Emergency_Call
                WHERE DATE(created_at) < CURDATE()
            )
        """)
        # Delete patients linked to old calls
        cursor.execute("""
            DELETE FROM Patient
            WHERE call_id IN (
                SELECT call_id FROM Emergency_Call
                WHERE DATE(created_at) < CURDATE()
            )
        """)
        # Free up ambulances whose old dispatches were just deleted
        cursor.execute("""
            UPDATE Ambulance
            SET availability_status = 'Available'
            WHERE ambulance_id NOT IN (
                SELECT ambulance_id FROM Dispatch
            )
            AND availability_status = 'Busy'
        """)
        # Finally delete the old calls themselves
        cursor.execute("""
            DELETE FROM Emergency_Call
            WHERE DATE(created_at) < CURDATE()
        """)
        db.commit()
        db.close()
    except Exception:
        pass  # Never crash the app due to cleanup failure


# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────
@app.route('/')
def index():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM Emergency_Call WHERE DATE(created_at) = CURDATE()")
        active_calls = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) AS total FROM Ambulance WHERE availability_status = 'Available'")
        available_ambulances = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) AS total FROM Dispatch WHERE DATE(dispatch_time) = CURDATE()")
        todays_dispatches = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) AS total FROM Hospital")
        total_hospitals = cursor.fetchone()['total']

        db.close()
    except Exception:
        active_calls = available_ambulances = todays_dispatches = total_hospitals = 0

    return render_template('index.html',
                           active_calls=active_calls,
                           available_ambulances=available_ambulances,
                           todays_dispatches=todays_dispatches,
                           total_hospitals=total_hospitals)


# ─────────────────────────────────────────────
#  ADD LOCATION
# ─────────────────────────────────────────────
@app.route('/add_location', methods=['GET', 'POST'])
def add_location():
    if request.method == 'POST':
        area    = request.form.get('area', '').strip()
        city    = request.form.get('city', '').strip()
        pincode = request.form.get('pincode', '').strip()

        if not area or not city or not pincode:
            flash("All fields are required.", "error")
            return render_template('add_location.html')

        if not pincode.isdigit() or len(pincode) != 6:
            flash("Pincode must be exactly 6 digits.", "error")
            return render_template('add_location.html')

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO Location (area, city, pincode) VALUES (%s, %s, %s)",
                (area, city, pincode)
            )
            db.commit()
            db.close()
            flash("Location added successfully!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Database error: {str(e)}", "error")

    return render_template('add_location.html')


# ─────────────────────────────────────────────
#  ADD HOSPITAL
# ─────────────────────────────────────────────
@app.route('/add_hospital', methods=['GET', 'POST'])
def add_hospital():
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        contact = request.form.get('contact', '').strip()

        if not name or not address or not contact:
            flash("All fields are required.", "error")
            return render_template('add_hospital.html')

        if not contact.isdigit() or len(contact) < 10:
            flash("Contact must be at least 10 digits.", "error")
            return render_template('add_hospital.html')

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO Hospital (hospital_name, address, contact) VALUES (%s, %s, %s)",
                (name, address, contact)
            )
            db.commit()
            db.close()
            flash("Hospital added successfully!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Database error: {str(e)}", "error")

    return render_template('add_hospital.html')


# ─────────────────────────────────────────────
#  ADD AMBULANCE
# ─────────────────────────────────────────────
@app.route('/add_ambulance', methods=['GET', 'POST'])
def add_ambulance():
    if request.method == 'POST':
        vehicle  = request.form.get('vehicle', '').strip().upper()
        capacity = request.form.get('capacity', '').strip()

        if not vehicle or not capacity:
            flash("All fields are required.", "error")
            return render_template('add_ambulance.html')

        if not capacity.isdigit() or int(capacity) < 1:
            flash("Capacity must be a positive number.", "error")
            return render_template('add_ambulance.html')

        try:
            db = get_db()
            cursor = db.cursor()
            # Check for duplicate vehicle number
            cursor.execute("SELECT ambulance_id FROM Ambulance WHERE vehicle_number = %s", (vehicle,))
            if cursor.fetchone():
                flash("An ambulance with that vehicle number already exists.", "error")
                db.close()
                return render_template('add_ambulance.html')

            cursor.execute(
                "INSERT INTO Ambulance (vehicle_number, capacity) VALUES (%s, %s)",
                (vehicle, int(capacity))
            )
            db.commit()
            db.close()
            flash("Ambulance added successfully!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Database error: {str(e)}", "error")

    return render_template('add_ambulance.html')


# ─────────────────────────────────────────────
#  ADD DRIVER
# ─────────────────────────────────────────────
@app.route('/add_driver', methods=['GET', 'POST'])
def add_driver():
    if request.method == 'POST':
        name       = request.form.get('name', '').strip()
        phone      = request.form.get('phone', '').strip()
        license_num = request.form.get('license', '').strip().upper()

        if not name or not phone or not license_num:
            flash("All fields are required.", "error")
            return render_template('add_driver.html')

        if not phone.isdigit() or len(phone) != 10:
            flash("Phone must be exactly 10 digits.", "error")
            return render_template('add_driver.html')

        try:
            db = get_db()
            cursor = db.cursor()
            # Check for duplicate license
            cursor.execute("SELECT driver_id FROM Driver WHERE license_number = %s", (license_num,))
            if cursor.fetchone():
                flash("A driver with that license number already exists.", "error")
                db.close()
                return render_template('add_driver.html')

            cursor.execute(
                "INSERT INTO Driver (name, phone, license_number) VALUES (%s, %s, %s)",
                (name, phone, license_num)
            )
            db.commit()
            db.close()
            flash("Driver added successfully!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Database error: {str(e)}", "error")

    return render_template('add_driver.html')


# ─────────────────────────────────────────────
#  REGISTER EMERGENCY CALL
# ─────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register_call():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Location ORDER BY city, area")
    locations = cursor.fetchall()

    if request.method == 'POST':
        emergency_type = request.form.get('emergency_type', '').strip()
        location_id    = request.form.get('location_id', '').strip()
        name           = request.form.get('name', '').strip()
        age            = request.form.get('age', '').strip()
        gender         = request.form.get('gender', '').strip()
        contact        = request.form.get('contact', '').strip()

        # ── Validation ──
        errors = []
        if not emergency_type:
            errors.append("Emergency type is required.")
        if not location_id or not location_id.isdigit():
            errors.append("Please select a valid location.")
        if not name or len(name) < 2:
            errors.append("Patient name must be at least 2 characters.")
        if not age.isdigit() or not (0 < int(age) < 120):
            errors.append("Age must be a number between 1 and 119.")
        if gender not in ('Male', 'Female', 'Other'):
            errors.append("Please select a valid gender.")
        if not contact.isdigit() or len(contact) != 10:
            errors.append("Contact must be exactly 10 digits.")

        if errors:
            for e in errors:
                flash(e, "error")
            db.close()
            return render_template('register_call.html', locations=locations)

        # ── Atomic dispatch transaction ──
        try:
            # Lock the best available ambulance so no other request grabs it
            cursor.execute("""
                SELECT ambulance_id FROM Ambulance
                WHERE availability_status = 'Available'
                ORDER BY ambulance_id ASC
                LIMIT 1
                FOR UPDATE
            """)
            ambulance = cursor.fetchone()

            cursor.execute("SELECT driver_id FROM Driver LIMIT 1")
            driver = cursor.fetchone()

            cursor.execute("SELECT hospital_id FROM Hospital LIMIT 1")
            hospital = cursor.fetchone()

            # Insert the emergency call (always saved, even if no ambulance)
            cursor.execute("""
                INSERT INTO Emergency_Call (emergency_type, status, location_id, created_at)
                VALUES (%s, 'Pending', %s, NOW())
            """, (emergency_type, int(location_id)))
            call_id = cursor.lastrowid

            # Insert patient record
            cursor.execute("""
                INSERT INTO Patient (name, age, gender, contact, call_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, int(age), gender, contact, call_id))

            if ambulance and driver and hospital:
                cursor.execute("""
                    INSERT INTO Dispatch (call_id, ambulance_id, driver_id, hospital_id, dispatch_time)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (call_id, ambulance['ambulance_id'], driver['driver_id'], hospital['hospital_id']))

                cursor.execute("""
                    UPDATE Ambulance SET availability_status = 'Busy'
                    WHERE ambulance_id = %s
                """, (ambulance['ambulance_id'],))

                db.commit()
                db.close()
                flash("Emergency call registered and ambulance dispatched!", "success")
            else:
                db.commit()
                db.close()
                flash("Call logged but no ambulance/driver/hospital is currently available.", "warning")

            return redirect(url_for('dispatches'))

        except Exception as e:
            db.rollback()
            db.close()
            flash(f"Failed to register call: {str(e)}", "error")
            return render_template('register_call.html', locations=locations)

    db.close()
    return render_template('register_call.html', locations=locations)


# ─────────────────────────────────────────────
#  VIEW DISPATCHES  (today only)
# ─────────────────────────────────────────────
@app.route('/dispatches')
def dispatches():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                d.dispatch_id,
                p.name            AS patient_name,
                p.age,
                p.gender,
                p.contact,
                ec.emergency_type,
                ec.status,
                l.area,
                l.city,
                a.vehicle_number,
                a.capacity,
                dr.name           AS driver_name,
                dr.phone          AS driver_phone,
                h.hospital_name,
                d.dispatch_time,
                ec.created_at
            FROM Dispatch d
            JOIN Emergency_Call ec ON d.call_id   = ec.call_id
            JOIN Patient        p  ON ec.call_id  = p.call_id
            JOIN Ambulance      a  ON d.ambulance_id = a.ambulance_id
            JOIN Driver         dr ON d.driver_id = dr.driver_id
            JOIN Hospital       h  ON d.hospital_id = h.hospital_id
            JOIN Location       l  ON ec.location_id = l.location_id
            WHERE DATE(ec.created_at) = CURDATE()
            ORDER BY d.dispatch_time DESC
        """)
        data = cursor.fetchall()
        db.close()
    except Exception as e:
        flash(f"Could not load dispatches: {str(e)}", "error")
        data = []

    return render_template('dispatch_list.html', data=data)


if __name__ == '__main__':
    app.run(debug=False)
