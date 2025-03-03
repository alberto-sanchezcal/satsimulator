import random
import datetime
import numpy as np
import json


RADIUS_EARTH = 6371  

num_configurations = 50

f_number_options = [1.4, 2.8, 4.0, 5.6]
sensor_width_options = [6.2208]
sensor_height_options = [3.4992]
cam_res_options = [0.9216]
focal_length_options = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]  

semimajor_axis_range = (RADIUS_EARTH + 400, RADIUS_EARTH + 1000)  
eccentricity_range = (0.0001, 0.01) 
inclination_range = (40, 100)  
ra_of_asc_node_range = (0, 360)  
arg_of_pericenter_range = (0, 360)  
true_anomaly_range = (0, 360)  

time_epoch = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


satellite_configurations = []

for i in range(1, num_configurations + 1):
    configuration = {
        "OBJECT_NAME": f"Event-Sat-{i}",
        "SEMIMAJOR_AXIS": round(random.uniform(*semimajor_axis_range), 2),
        "ECCENTRICITY": round(random.uniform(*eccentricity_range), 6),
        "INCLINATION": round(random.uniform(*inclination_range), 2),
        "RA_OF_ASC_NODE": round(random.uniform(*ra_of_asc_node_range), 2),
        "ARG_OF_PERICENTER": round(random.uniform(*arg_of_pericenter_range), 2),
        "TRUE_ANOMALY": round(random.uniform(*true_anomaly_range), 2),
        "EPOCH": "2024-09-09T10:00:00.00", 
        "f-number": random.choice(f_number_options),
        "Sensor Width": random.choice(sensor_width_options),
        "Sensor Height": random.choice(sensor_height_options),
        "Camera Resolution": random.choice(cam_res_options),
        "Focal Length": random.choice(focal_length_options),
        "Quaternion Vector": [round(random.uniform(-1, 1), 6) for _ in range(3)],
        "Quaternion Angle": round(random.uniform(0, 360), 2)
    }
    
    norm = np.linalg.norm(configuration["Quaternion Vector"])
    configuration["Quaternion Vector"] = str([round(coord / norm, 6) 
                                              for coord in configuration["Quaternion Vector"]])
    
    satellite_configurations.append(configuration)


with open('database/created_sats.json', 'w') as json_file:
    json.dump(satellite_configurations, json_file, indent=4)