from flask import Flask, render_template, request, redirect, url_for, flash, session
from pymongo import MongoClient
from geopy.geocoders import Nominatim
import requests
import bcrypt,random
import pickle
import xgboost as xgb
import numpy as np

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# MongoDB configuration
app.secret_key = "super secret key"
client = MongoClient("mongodb://localhost:27017/")  # Connection to MongoDB, change the URI as needed
db = client["real_estate"]  # Database name
collection = db["users"]

# Geocoding service
geolocator = Nominatim(user_agent="real_estate_app")

# Google Maps Places API key (replace with your own key)
GOOGLE_MAPS_API_KEY = 'AIzaSyB4V5P3yylRtLLyMPsvxKyDZxAQaxhKLVU'

# OSM Nominatim API endpoint
NOMINATIM_ENDPOINT = 'https://nominatim.openstreetmap.org/search'

# Overpass API endpoint
OVERPASS_ENDPOINT = 'https://overpass-api.de/api/interpreter'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/home')
def home():
    return render_template('home.html',username=session.get('username'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the username already exists
        existing_user = collection.find_one({'username': username})
        if existing_user:
            return render_template('signup.html', error='Username already exists. Please choose a different one.')

        # Hash the password before storing
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Store the new user in the database
        new_user = {'username': username, 'password': hashed_password}
        collection.insert_one(new_user)

        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the entered username exists
        existing_user = collection.find_one({'username': username})

        if existing_user and bcrypt.checkpw(password.encode('utf-8'), existing_user['password']):
            session['username'] = username  # Store username in session for authentication
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password. Please try again.')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)  # Remove username from session
    return redirect(url_for('index'))


@app.route('/add_property', methods=['GET', 'POST'])
def add_property():
    if request.method == 'POST':
        property_data = {
            'name': request.form['name'],
            'address': request.form['address'],
            'house_area': float(request.form['house_area']),
            'bedrooms': int(request.form['bedrooms']),
            'kitchen': bool(request.form.get('kitchen')),
            'car_parking': bool(request.form.get('car_parking')),
            'security': bool(request.form.get('security')),
            'maintenance': bool(request.form.get('maintainence'))
        }

        collection.update_one(
            {'username': session['username']},
            {'$set': property_data}
        )

        automatic_geo_locator()
        automatically_check_nearby_places()
        
        
        return redirect('/home')

    return render_template('add_property.html')

@app.route('/geocode_addresses')
def geocode_addresses():
    properties = collection.find({'username': session['username']})
    for property in properties:
        address = property['address']
        location = geolocator.geocode(address)
        
        if location:
            # Update the document with geolocation data
            collection.update_one(
                {'_id': property['_id']},
                {'$set': {'latitude': location.latitude, 'longitude': location.longitude}}
            )

    return redirect('/home')

@app.route('/check_nearby_places')
def check_nearby_places():
    properties = collection.find({'username': session['username']})
    predict_model()
    for property in properties:
        latitude = property.get('latitude')
        longitude = property.get('longitude')
        
        if latitude and longitude:
            # Simulate random values for schools and hospitals
            schools_exist = random.choice([0, 1])
            hospitals_exist = random.choice([0, 1])

            # Update the document with random truth values for schools and hospitals
            collection.update_one(
                {'_id': property['_id']},
                {'$set': {'school_nearby': schools_exist, 'hospital_nearby': hospitals_exist}}
            )

    return redirect('/home')

@app.route('/check_price')
def check_price():
    with open('xgboost_model.pkl', 'rb') as model_file:
        model = pickle.load(model_file)
        # print(dir1(model))
        #np inputs -'area', 'No of Bedrooms', 'MaintanceStaff', 'Latitude', 'Longitude'
        usr_val = collection.find({'username': session['username']})
        for i in usr_val:
            sq_ft = i.get('house_area')
            brd_rm = i.get('bedrooms')
            school = i.get('school_nearby')
            hospital = i.get('hospital_nearby')
            latitude = i.get('latitude')
            longitude = i.get('longitude')
            area = i.get('address')
            car_parking = i.get('car_parking')
            kitchen = i.get('kitchen')
            manitainence_staff = i.get('manitainence')
            security = i.get('security')

            
            new_data = np.array([[sq_ft, brd_rm, float(school), float(hospital), latitude, longitude]])
            get_price = model.predict(new_data)
            print(get_price[0])
            str_price = str(int(get_price[0]))

            if(school == 1):
                school_new = 'yes'
            else:
                school_new = 'no'

            if(hospital == 1):
                hospital_new = 'yes'
            else:
                hospital_new = 'no'

            car_park = 'yes' if car_parking else 'no'
            kitchen_av = 'yes' if kitchen else 'no'
            maint_staff = 'yes' if manitainence_staff else 'no'
            sec = 'yes' if security else 'no'
    
    return render_template('check_price.html', price = str_price , sq_ft = sq_ft, brd_rm = brd_rm,school = school_new,hospital =hospital_new,
                           area = area , car_park = car_park,kitchen = kitchen_av,
                           
                           manitainence_staff = maint_staff, security = sec)


        


def automatic_geo_locator():
    print("Automatically adding cordinates")
    properties = collection.find({'username': session['username']})
    for property in properties:
        address = property['address']
        location = geolocator.geocode(address)
        
        if location:
            # Update the document with geolocation data
            collection.update_one(
                {'_id': property['_id']},
                {'$set': {'latitude': location.latitude, 'longitude': location.longitude}}
            )

def automatically_check_nearby_places():
    properties = collection.find({'username': session['username']})
    for property in properties:
        latitude = property.get('latitude')
        longitude = property.get('longitude')
        
        if latitude and longitude:
            # Simulate random values for schools and hospitals
            schools_exist = random.choice([0, 1])
            hospitals_exist = random.choice([0, 1])

            # Update the document with random truth values for schools and hospitals
            collection.update_one(
                {'_id': property['_id']},
                {'$set': {'school_nearby': schools_exist, 'hospital_nearby': hospitals_exist}}
            )


def predict_model():
    # Load the trained model from the pickle file
    with open('xgboost_model.pkl', 'rb') as model_file:
        model = pickle.load(model_file)
        # print(dir1(model))
        #np inputs -'area', 'No of Bedrooms', 'MaintanceStaff', 'Latitude', 'Longitude'
        usr_val = collection.find({'username': session['username']})
        for i in usr_val:
            sq_ft = i.get('house_area')
            brd_rm = i.get('bedrooms')
            school = i.get('school_nearby')
            hospital = i.get('hospital_nearby')
            latitude = i.get('latitude')
            longitude = i.get('longitude')
            
            
            new_data = np.array([[sq_ft, brd_rm, float(school), float(hospital), latitude, longitude]])
            print(model.predict(new_data))
    
    

if __name__ == '__main__':
    app.run(debug=True)
