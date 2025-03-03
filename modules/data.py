import json
import requests
import os
import datetime
import numpy as np
import csv

def read_last_query_time(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            data = json.load(file)
            return datetime.datetime.fromisoformat(data["last_query_time"])
    return None


def write_last_query_time(file_path, query_time):
    with open(file_path, "w") as file:
        data = {"last_query_time": query_time.isoformat()}
        json.dump(data, file)


def should_query_api(last_query_time):
    if last_query_time is None:
        return True
    return (datetime.datetime.now() - last_query_time).total_seconds() >= 24 * 3600


def get_gcat_data():
    url = 'https://planet4589.org/space/gcat/tsv/cat/satcat.tsv'

    file_path = 'database/satcat.tsv'

    try:
        response = requests.get(url)
        response.raise_for_status()
        
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(f"File downloaded and saved as {file_path}")

        additional_data = {}
        with open(file_path, 'r', newline='') as tsvfile:
            reader = csv.reader(tsvfile, delimiter='\t')
            next(reader)
            next(reader)
            
            for row in reader:
                norad_id = int(row[0][1:])
                additional_data[norad_id] = {
                    'NORAD_CAT_ID': norad_id,
                    'length': float(row[25])/1000 if row[25]!='-' else 0.0,
                    'diameter': float(row[27])/1000 if row[27]!='-' else 0.0,
                    'span': float(row[29])/1000 if row[29]!='-' else 0.0,
                    'mass': float(row[19]) if row[19]!='-' else 0.0,
                    'shape': row[31],  
                }

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")
        
    return additional_data


def update_sat_data(sat_data, gcat_data):
    updated_sat_data = []
    for sat in sat_data:
        norad_id = int(sat.get("NORAD_CAT_ID"))
        if norad_id in gcat_data:
            sat.update(gcat_data[norad_id])
            updated_sat_data.append(sat)
    return updated_sat_data

def update_sat_data_shapes_and_params (updated_sat_data):
    for item in updated_sat_data:
        parts = (item["shape"].split('+'))
        new_parts = []
        for part in parts:
            part = part.strip().lower()
            if 'sphere' in part:
                new_parts.append('sphere')
            elif any(word in part for word in ['cyl', 'poly', 'hex', 'oct', 'disk', 'annulus']):
                new_parts.append('cyl')
            elif any(word in part for word in ['box', 'cube']):
                new_parts.append('box')
            elif any(word in part for word in ['cone', 'conical', 'dcone', 'dome']):
                new_parts.append('cone')
            elif '-' in part:
                new_parts.append('sphere')
            else:
                new_parts.append('cyl')
        
        new_parts_main = new_parts[0]
        if 'sphere' in new_parts_main:
            item["shape"] = 'sphere'
        elif 'cyl' in new_parts_main:
            item["shape"] = 'cyl'
        elif 'box' in new_parts_main:
            item["shape"] = 'box'
        elif 'cone' in new_parts_main:
            item["shape"] = 'cone'


        if float (item ["length"]) == 0: 
            if item ["OBJECT_TYPE"].lower() == 'debris':
                item ["length"] = 0.1/1000
            else:
                item ["length"] = 1/1000
        
        item["DECAY_DATE"] = "NO DECAY"


        mean_anomaly = np.radians(float(item['MEAN_ANOMALY']))
        eccentricity = float(item['ECCENTRICITY'])
        true_anomaly = from_mean_to_true_anomaly(mean_anomaly, eccentricity)
        item['TRUE_ANOMALY'] = round(true_anomaly, 4)

    return updated_sat_data


def get_sat_data():
    api_url = "https://www.space-track.org/basicspacedata/query/class/gp/DECAY_DATE/null-val/orderby/NORAD_CAT_ID/"
    username = "20asc01@gmail.com"
    password = "XCVVcJAjKd3WNASC"
    json_file_name = "all_sat"

    #session to persist the authentication
    session = requests.Session()
    
    login_data = {
        "identity": username,
        "password": password
    }
    login_response = session.post("https://www.space-track.org/ajaxauth/login", json=login_data)
    
    if login_response.status_code != 200:
        print("Failed to login. Status code:", login_response.status_code)
        return None
    
    # Fetch JSON data after successful login
    response = session.get(api_url)
    if response.status_code == 200:
        json_data = response.json()
        with open(f"database/{json_file_name}.json", "w") as json_file:
            json.dump(json_data, json_file, indent=2)
        print(f"JSON data saved to database/{json_file_name}.json file.")        
    else:
        print("Error fetching data from the API. Status code:", response.status_code)
        return None

    json_file_path = f"database/{json_file_name}.json"
    with open(json_file_path, "r") as json_file:
        sat_data = json.load(json_file)

    gcat_data = get_gcat_data()
    updated_sat_data = update_sat_data(sat_data, gcat_data)
    updated_sat_data_shapes_and_params = update_sat_data_shapes_and_params(updated_sat_data)
    

    with open(f"database/updated_all_sat.json", "w") as json_file:
        json.dump(updated_sat_data_shapes_and_params, json_file, indent=2)




def from_mean_to_true_anomaly(M, e, tol=1e-10):
    """
    Solves Kepler's equation M = E - e*sin(E) for E using the Newton-Raphson method.
    """    
    # Initial guess
    E = M if e < 0.8 else np.pi
    
    # Newton-Raphson iteration
    while True:
        f = E - e * np.sin(E) - M
        E_next = E - f / (1 - e * np.cos(E))
        if abs(E_next - E) < tol:
            break
        E = E_next
    
    nu = 2 * np.arctan2(np.sqrt(1 + e) * np.sin(E / 2),
                               np.sqrt(1 - e) * np.cos(E / 2))
    
    if nu < 0:
        nu += 2 * np.pi

    nu = np.degrees(nu)    

    return nu

