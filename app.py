from flask import Flask, render_template, request, redirect
import mysql.connector

app = Flask(__name__)

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="emergency_system_24bds1109"
    )

@app.route('/')
def index():
    return render_template('index.html')

# ---------------- ADD LOCATION ----------------
@app.route('/add_location', methods=['GET', 'POST'])
def add_location():
    if request.method == 'POST':
        area = request.form['area']
        city = request.form['city']
        pincode = request.form['pincode']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Location (area, city, pincode) VALUES (%s,%s,%s)",
                       (area, city, pincode))
        db.commit()
        db.close()
        return redirect('/')
    return render_template('add_location.html')

# ---------------- ADD HOSPITAL ----------------
@app.route('/add_hospital', methods=['GET', 'POST'])
def add_hospital():
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        contact = request.form['contact']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Hospital (hospital_name,address,contact) VALUES (%s,%s,%s)",
                       (name, address, contact))
        db.commit()
        db.close()
        return redirect('/')
    return render_template('add_hospital.html')

# ---------------- ADD AMBULANCE ----------------
@app.route('/add_ambulance', methods=['GET', 'POST'])
def add_ambulance():
    if request.method == 'POST':
        vehicle = request.form['vehicle']
        capacity = request.form['capacity']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Ambulance (vehicle_number,capacity) VALUES (%s,%s)",
                       (vehicle, capacity))
        db.commit()
        db.close()
        return redirect('/')
    return render_template('add_ambulance.html')

# ---------------- ADD DRIVER ----------------
@app.route('/add_driver', methods=['GET', 'POST'])
def add_driver():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        license = request.form['license']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Driver (name,phone,license_number) VALUES (%s,%s,%s)",
                       (name, phone, license))
        db.commit()
        db.close()
        return redirect('/')
    return render_template('add_driver.html')

# ---------------- REGISTER CALL ----------------
@app.route('/register', methods=['GET', 'POST'])
def register_call():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Location")
    locations = cursor.fetchall()

    if request.method == 'POST':
        emergency_type = request.form['emergency_type']
        location_id = request.form['location_id']
        name = request.form['name']
        age = request.form['age']
        gender = request.form['gender']
        contact = request.form['contact']

        cursor.execute("INSERT INTO Emergency_Call (emergency_type,status,location_id) VALUES (%s,'Pending',%s)",
                       (emergency_type, location_id))
        call_id = cursor.lastrowid

        cursor.execute("INSERT INTO Patient (name,age,gender,contact,call_id) VALUES (%s,%s,%s,%s,%s)",
                       (name, age, gender, contact, call_id))

        cursor.execute("SELECT ambulance_id FROM Ambulance WHERE availability_status='Available' LIMIT 1")
        ambulance = cursor.fetchone()

        cursor.execute("SELECT driver_id FROM Driver LIMIT 1")
        driver = cursor.fetchone()

        cursor.execute("SELECT hospital_id FROM Hospital LIMIT 1")
        hospital = cursor.fetchone()

        if ambulance:
            cursor.execute("INSERT INTO Dispatch (call_id,ambulance_id,driver_id,hospital_id) VALUES (%s,%s,%s,%s)",
                           (call_id, ambulance['ambulance_id'], driver['driver_id'], hospital['hospital_id']))
            cursor.execute("UPDATE Ambulance SET availability_status='Busy' WHERE ambulance_id=%s",
                           (ambulance['ambulance_id'],))

        db.commit()
        db.close()
        return redirect('/dispatches')

    return render_template('register_call.html', locations=locations)

# ---------------- VIEW DISPATCHES ----------------
@app.route('/dispatches')
def dispatches():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT d.dispatch_id, p.name, a.vehicle_number,
               dr.name AS driver_name, h.hospital_name
        FROM Dispatch d
        JOIN Emergency_Call ec ON d.call_id = ec.call_id
        JOIN Patient p ON ec.call_id = p.call_id
        JOIN Ambulance a ON d.ambulance_id = a.ambulance_id
        JOIN Driver dr ON d.driver_id = dr.driver_id
        JOIN Hospital h ON d.hospital_id = h.hospital_id
    """)

    data = cursor.fetchall()
    db.close()

    return render_template('dispatch_list.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
