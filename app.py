from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
import mysql.connector
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-in-production")

#  DB CONNECTION
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root"),
        database=os.getenv("DB_NAME", "emergency_system_24bds1109")
    )


def try_assign_pending(cursor):
    cursor.execute("""
        SELECT ec.call_id FROM Emergency_Call ec
        LEFT JOIN Dispatch d ON ec.call_id = d.call_id
        WHERE ec.status = 'Pending'
          AND d.dispatch_id IS NULL
        ORDER BY ec.created_at ASC
        LIMIT 1
    """)
    pending_call = cursor.fetchone()
    if not pending_call:
        return False

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

    if ambulance and driver and hospital:
        call_id = pending_call['call_id']
        cursor.execute("""
            INSERT INTO Dispatch (call_id, ambulance_id, driver_id, hospital_id, dispatch_time)
            VALUES (%s, %s, %s, %s, NOW())
        """, (call_id, ambulance['ambulance_id'], driver['driver_id'], hospital['hospital_id']))

        cursor.execute("""
            UPDATE Ambulance SET availability_status = 'Busy'
            WHERE ambulance_id = %s
        """, (ambulance['ambulance_id'],))

        cursor.execute("""
            UPDATE Emergency_Call SET status = 'Dispatched'
            WHERE call_id = %s
        """, (call_id,))
        return True
    return False


@app.before_request
def auto_cleanup():
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            INSERT IGNORE INTO Dispatch_Archive (
                dispatch_id, ambulance_id, driver_id, hospital_id, call_id,
                dispatch_time, arrival_time, completion_time,
                emergency_type, call_created_at,
                patient_name, patient_age, patient_gender, patient_contact,
                vehicle_number, driver_name, hospital_name
            )
            SELECT d.dispatch_id, d.ambulance_id, d.driver_id, d.hospital_id, d.call_id,
                   d.dispatch_time, d.arrival_time, d.completion_time,
                   ec.emergency_type, ec.created_at,
                   p.name, p.age, p.gender, p.contact,
                   a.vehicle_number, dr.name, h.hospital_name
            FROM Dispatch d
            JOIN Emergency_Call ec ON d.call_id      = ec.call_id
            JOIN Patient        p  ON ec.call_id     = p.call_id
            JOIN Ambulance      a  ON d.ambulance_id = a.ambulance_id
            JOIN Driver         dr ON d.driver_id    = dr.driver_id
            JOIN Hospital       h  ON d.hospital_id  = h.hospital_id
            WHERE DATE(ec.created_at) < CURDATE()
        """)

        cursor.execute("""
            UPDATE Ambulance SET availability_status = 'Available'
            WHERE ambulance_id IN (
                SELECT d.ambulance_id FROM Dispatch d
                JOIN Emergency_Call ec ON d.call_id = ec.call_id
                WHERE DATE(ec.created_at) < CURDATE()
            )
        """)

        cursor.execute("""
            DELETE FROM Payment WHERE dispatch_id IN (
                SELECT d.dispatch_id FROM Dispatch d
                JOIN Emergency_Call ec ON d.call_id = ec.call_id
                WHERE DATE(ec.created_at) < CURDATE()
            )
        """)
        cursor.execute("""
            DELETE FROM Dispatch WHERE call_id IN (
                SELECT call_id FROM Emergency_Call WHERE DATE(created_at) < CURDATE()
            )
        """)
        cursor.execute("""
            DELETE FROM Patient WHERE call_id IN (
                SELECT call_id FROM Emergency_Call WHERE DATE(created_at) < CURDATE()
            )
        """)
        cursor.execute("DELETE FROM Emergency_Call WHERE DATE(created_at) < CURDATE()")

        db.commit()
        db.close()
    except Exception:
        pass


#  DASHBOARD
@app.route('/')
def index():
    stats = {
        'active_calls': 0, 'available_ambulances': 0, 'busy_ambulances': 0,
        'todays_dispatches': 0, 'total_hospitals': 0, 'pending_calls': 0,
        'avg_response': 0, 'resolved_today': 0
    }
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS v FROM Emergency_Call WHERE DATE(created_at)=CURDATE()")
        stats['active_calls'] = cursor.fetchone()['v']

        cursor.execute("SELECT COUNT(*) AS v FROM Ambulance WHERE availability_status='Available'")
        stats['available_ambulances'] = cursor.fetchone()['v']

        cursor.execute("SELECT COUNT(*) AS v FROM Ambulance WHERE availability_status='Busy'")
        stats['busy_ambulances'] = cursor.fetchone()['v']

        cursor.execute("SELECT COUNT(*) AS v FROM Dispatch WHERE DATE(dispatch_time)=CURDATE()")
        stats['todays_dispatches'] = cursor.fetchone()['v']

        cursor.execute("SELECT COUNT(*) AS v FROM Hospital")
        stats['total_hospitals'] = cursor.fetchone()['v']

        cursor.execute("""
            SELECT COUNT(*) AS v FROM Emergency_Call ec
            LEFT JOIN Dispatch d ON ec.call_id = d.call_id
            WHERE ec.status='Pending' AND d.dispatch_id IS NULL
              AND DATE(ec.created_at)=CURDATE()
        """)
        stats['pending_calls'] = cursor.fetchone()['v']

        cursor.execute("""
            SELECT ROUND(AVG(TIMESTAMPDIFF(MINUTE, ec.created_at, d.dispatch_time)),1) AS v
            FROM Dispatch d
            JOIN Emergency_Call ec ON d.call_id=ec.call_id
            WHERE DATE(ec.created_at)=CURDATE()
        """)
        stats['avg_response'] = cursor.fetchone()['v'] or 0

        cursor.execute("""
            SELECT COUNT(*) AS v FROM Emergency_Call
            WHERE status='Resolved' AND DATE(created_at)=CURDATE()
        """)
        stats['resolved_today'] = cursor.fetchone()['v']

        db.close()
    except Exception:
        pass

    return render_template('index.html', **stats)

#  ADD LOCATION
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
            cursor.execute("INSERT INTO Location (area,city,pincode) VALUES (%s,%s,%s)",
                           (area, city, pincode))
            db.commit()
            db.close()
            flash(f"Location '{area}, {city}' added!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    return render_template('add_location.html')

#  ADD HOSPITAL
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
            cursor.execute("INSERT INTO Hospital (hospital_name,address,contact) VALUES (%s,%s,%s)",
                           (name, address, contact))
            db.commit()
            db.close()
            flash(f"Hospital '{name}' added!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    return render_template('add_hospital.html')

#  ADD AMBULANCE
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
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT ambulance_id FROM Ambulance WHERE vehicle_number=%s", (vehicle,))
            if cursor.fetchone():
                flash("That vehicle number already exists.", "error")
                db.close()
                return render_template('add_ambulance.html')
            cursor.execute("INSERT INTO Ambulance (vehicle_number,capacity) VALUES (%s,%s)",
                           (vehicle, int(capacity)))
            db.commit()
            db.close()
            flash(f"Ambulance '{vehicle}' added!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    return render_template('add_ambulance.html')

#  ADD DRIVER
@app.route('/add_driver', methods=['GET', 'POST'])
def add_driver():
    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        phone       = request.form.get('phone', '').strip()
        license_num = request.form.get('license', '').strip().upper()

        if not name or not phone or not license_num:
            flash("All fields are required.", "error")
            return render_template('add_driver.html')
        if not phone.isdigit() or len(phone) != 10:
            flash("Phone must be exactly 10 digits.", "error")
            return render_template('add_driver.html')
        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT driver_id FROM Driver WHERE license_number=%s", (license_num,))
            if cursor.fetchone():
                flash("That license number already exists.", "error")
                db.close()
                return render_template('add_driver.html')
            cursor.execute("INSERT INTO Driver (name,phone,license_number) VALUES (%s,%s,%s)",
                           (name, phone, license_num))
            db.commit()
            db.close()
            flash(f"Driver '{name}' added!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    return render_template('add_driver.html')

#  REGISTER EMERGENCY CALL
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

        errors = []
        if not emergency_type:           errors.append("Emergency type is required.")
        if not location_id:              errors.append("Select a location.")
        if not name or len(name) < 2:   errors.append("Patient name must be at least 2 chars.")
        if not age.isdigit() or not (0 < int(age) < 120): errors.append("Invalid age.")
        if gender not in ('Male','Female','Other'): errors.append("Select a gender.")
        if not contact.isdigit() or len(contact) != 10: errors.append("Contact must be 10 digits.")

        if errors:
            for e in errors: flash(e, "error")
            db.close()
            return render_template('register_call.html', locations=locations)

        try:
            cursor.execute("""
                SELECT ambulance_id FROM Ambulance
                WHERE availability_status='Available'
                ORDER BY ambulance_id ASC LIMIT 1 FOR UPDATE
            """)
            ambulance = cursor.fetchone()

            cursor.execute("SELECT driver_id FROM Driver LIMIT 1")
            driver = cursor.fetchone()

            cursor.execute("SELECT hospital_id FROM Hospital LIMIT 1")
            hospital = cursor.fetchone()

            cursor.execute("""
                INSERT INTO Emergency_Call (emergency_type, status, location_id, created_at)
                VALUES (%s, 'Pending', %s, NOW())
            """, (emergency_type, int(location_id)))
            call_id = cursor.lastrowid

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
                    UPDATE Ambulance SET availability_status='Busy' WHERE ambulance_id=%s
                """, (ambulance['ambulance_id'],))
                cursor.execute("""
                    UPDATE Emergency_Call SET status='Dispatched' WHERE call_id=%s
                """, (call_id,))
                db.commit()
                db.close()
                flash(" Ambulance dispatched successfully!", "success")
            else:
                db.commit()
                db.close()
                flash(" Call logged. No ambulance available now — will auto-assign when one is free.", "warning")

            return redirect(url_for('dispatches'))

        except Exception as e:
            db.rollback()
            db.close()
            flash(f"Failed to register: {str(e)}", "error")
            return render_template('register_call.html', locations=locations)

    db.close()
    return render_template('register_call.html', locations=locations)

#  VIEW DISPATCHES
@app.route('/dispatches')
def dispatches():
    dispatches_data = []
    pending_data = []
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT d.dispatch_id, d.dispatch_time, d.arrival_time, d.completion_time,
                   ec.call_id, ec.emergency_type, ec.status AS call_status, ec.created_at,
                   l.area, l.city,
                   p.name AS patient_name, p.age, p.gender, p.contact,
                   a.vehicle_number, a.capacity,
                   dr.name AS driver_name, dr.phone AS driver_phone,
                   h.hospital_name,
                   pay.amount AS payment_amount,
                   pay.payment_method, pay.payment_status
            FROM Dispatch d
            JOIN Emergency_Call ec ON d.call_id      = ec.call_id
            JOIN Patient        p  ON ec.call_id     = p.call_id
            JOIN Ambulance      a  ON d.ambulance_id = a.ambulance_id
            JOIN Driver         dr ON d.driver_id    = dr.driver_id
            JOIN Hospital       h  ON d.hospital_id  = h.hospital_id
            JOIN Location       l  ON ec.location_id = l.location_id
            LEFT JOIN Payment   pay ON d.dispatch_id = pay.dispatch_id
            WHERE DATE(ec.created_at) = CURDATE()
            ORDER BY d.dispatch_time DESC
        """)
        dispatches_data = cursor.fetchall()

        cursor.execute("""
            SELECT ec.call_id, ec.emergency_type, ec.created_at,
                   l.area, l.city,
                   p.name AS patient_name, p.age, p.gender, p.contact
            FROM Emergency_Call ec
            LEFT JOIN Dispatch d ON ec.call_id = d.call_id
            JOIN Patient  p ON ec.call_id  = p.call_id
            JOIN Location l ON ec.location_id = l.location_id
            WHERE ec.status='Pending' AND d.dispatch_id IS NULL
              AND DATE(ec.created_at) = CURDATE()
            ORDER BY ec.created_at ASC
        """)
        pending_data = cursor.fetchall()
        db.close()
    except Exception as e:
        flash(f"Could not load dispatches: {str(e)}", "error")

    return render_template('dispatch_list.html',
                           data=dispatches_data,
                           pending=pending_data)

#  MARK ARRIVED
@app.route('/dispatch/arrived/<int:dispatch_id>', methods=['POST'])
def mark_arrived(dispatch_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE Dispatch SET arrival_time=NOW()
            WHERE dispatch_id=%s AND arrival_time IS NULL
        """, (dispatch_id,))
        db.commit()
        db.close()
        flash("✅ Marked as Arrived at patient location.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for('dispatches'))

#  MARK COMPLETED
@app.route('/dispatch/complete/<int:dispatch_id>', methods=['POST'])
def mark_completed(dispatch_id):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT ambulance_id, call_id FROM Dispatch WHERE dispatch_id=%s
        """, (dispatch_id,))
        row = cursor.fetchone()

        if row:
            cursor.execute("UPDATE Dispatch SET completion_time=NOW() WHERE dispatch_id=%s",
                           (dispatch_id,))
            cursor.execute("UPDATE Emergency_Call SET status='Resolved' WHERE call_id=%s",
                           (row['call_id'],))
            cursor.execute("UPDATE Ambulance SET availability_status='Available' WHERE ambulance_id=%s",
                           (row['ambulance_id'],))
            try_assign_pending(cursor)
            db.commit()
            db.close()
            flash(" Dispatch completed! Please record payment.", "success")
            return redirect(url_for('add_payment', dispatch_id=dispatch_id))

        db.close()
        flash("Dispatch not found.", "error")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for('dispatches'))

#  PAYMENT
@app.route('/payment/<int:dispatch_id>', methods=['GET', 'POST'])
def add_payment(dispatch_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT d.dispatch_id, d.dispatch_time, d.arrival_time, d.completion_time,
               p.name AS patient_name, p.contact,
               ec.emergency_type,
               h.hospital_name, a.vehicle_number, dr.name AS driver_name
        FROM Dispatch d
        JOIN Emergency_Call ec ON d.call_id      = ec.call_id
        JOIN Patient        p  ON ec.call_id     = p.call_id
        JOIN Hospital       h  ON d.hospital_id  = h.hospital_id
        JOIN Ambulance      a  ON d.ambulance_id = a.ambulance_id
        JOIN Driver         dr ON d.driver_id    = dr.driver_id
        WHERE d.dispatch_id=%s
    """, (dispatch_id,))
    dispatch = cursor.fetchone()

    cursor.execute("SELECT * FROM Payment WHERE dispatch_id=%s", (dispatch_id,))
    existing = cursor.fetchone()

    if request.method == 'POST':
        amount         = request.form.get('amount', '').strip()
        payment_method = request.form.get('payment_method', '').strip()
        payment_status = request.form.get('payment_status', 'Paid').strip()

        if not amount or not payment_method:
            flash("Amount and payment method are required.", "error")
            db.close()
            return render_template('payment.html', dispatch=dispatch, existing=existing)
        try:
            amount = float(amount)
            if amount < 0: raise ValueError()
        except ValueError:
            flash("Enter a valid positive amount.", "error")
            db.close()
            return render_template('payment.html', dispatch=dispatch, existing=existing)

        try:
            if existing:
                cursor.execute("""
                    UPDATE Payment SET amount=%s, payment_method=%s,
                    payment_status=%s, payment_date=NOW()
                    WHERE dispatch_id=%s
                """, (amount, payment_method, payment_status, dispatch_id))
            else:
                cursor.execute("""
                    INSERT INTO Payment (dispatch_id, amount, payment_date, payment_method, payment_status)
                    VALUES (%s, %s, NOW(), %s, %s)
                """, (dispatch_id, amount, payment_method, payment_status))
            db.commit()
            db.close()
            flash(f"💰 Payment of ₹{amount:.2f} recorded!", "success")
            return redirect(url_for('dispatches'))
        except Exception as e:
            flash(f"Error saving payment: {str(e)}", "error")

    db.close()
    return render_template('payment.html', dispatch=dispatch, existing=existing)

#  HISTORY
@app.route('/history')
def history():
    records = []
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM Dispatch_Archive ORDER BY archived_at DESC LIMIT 200
        """)
        records = cursor.fetchall()
        db.close()
    except Exception as e:
        flash(f"Could not load history: {str(e)}", "error")
    return render_template('history.html', records=records)


if __name__ == '__main__':
    app.run(debug=False)
