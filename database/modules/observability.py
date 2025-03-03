import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.propagation import propagate, to_julian
from modules.coord_frames import get_coord_sys

import numpy as np
from astropy.time import Time
import datetime
from datetime import datetime, timedelta
from poliastro.bodies import Earth
from poliastro.twobody import Orbit
from poliastro.util import time_range
from astropy import units as u
import ast


def get_observable_objects(created_data, ephem_catalog_sat_data, sun_data):
    epochs_array = np.array(sun_data["epochs"])
    observant_coords = np.array(created_data['coords'])

    observations = []
    for observed_data in ephem_catalog_sat_data:
        observed_coords = np.array(observed_data['coords'])
        object_size = (float(observed_data['length']) +
                       float(observed_data['diameter'])
                       )/2*1000

        mean_lambda = 550 *10**(-9)
        f_number = created_data['f-number']
        sensor_width = created_data['Sensor Width'] * 10**(-3)
        sensor_height = created_data['Sensor Height'] *10**(-3)
        cam_res = created_data['Camera Resolution'] * 10**6
        focal_length = created_data['Focal Length']*10**(-3)

        distances = np.linalg.norm(observant_coords - observed_coords, axis=1)
        aspect_ratio = sensor_width / sensor_height
        resolution_width = np.sqrt(cam_res * aspect_ratio)
        resolution_height = cam_res / resolution_width
        pixel_size_w = sensor_width / resolution_width
        pixel_size_h = sensor_height / resolution_height
        pixel_size = pixel_size_w

        D_airy_disk = 2.44*mean_lambda*f_number

        index_observable = []
        epoch_finer_ =[None]*len(epochs_array)
        prev_observed_pos_cam = None
        for index, distance in enumerate(distances):
            min_object_size_observable = max(D_airy_disk,pixel_size)*distance*1000/focal_length

            object_in_FOV = False
            object_intersects_FOV = False
            observed_pos_cam = None 

            if object_size >= min_object_size_observable:
                vertical_FOV = 2 * np.arctan((sensor_height/2) / focal_length)
                horizontal_FOV = 2 * np.arctan((sensor_width/2) / focal_length)
                r_observed_observant = (observed_coords[index] - 
                                        observant_coords[index]
                                        )*1000
                cam_frame = np.array(created_data['bodyaxis'][index]) 
                R_ECI_cam = np.array([cam_frame[0].T,cam_frame[1].T,cam_frame[2].T])
                observed_pos_cam = np.dot(R_ECI_cam, r_observed_observant)
                proy_y = observed_pos_cam[0]*np.tan(horizontal_FOV / 2)
                proy_z = observed_pos_cam[0]*np.tan(vertical_FOV / 2)

                if (-proy_y <= observed_pos_cam[1] <= proy_y and -proy_z <= observed_pos_cam[2] <= proy_z):
                    object_in_FOV = True
                elif index > 0 and abs(observed_pos_cam[1])> proy_y and abs(observed_pos_cam[2])> proy_z:
                    if prev_observed_pos_cam is not None: 
                        object_intersects_FOV = check_line_intersects_fov(vertical_FOV, 
                                                                        horizontal_FOV, 
                                                                        prev_observed_pos_cam, 
                                                                        observed_pos_cam
                                                                        )                            
                else: 
                    object_in_FOV = False
                    object_intersects_FOV = False

                if object_in_FOV or object_intersects_FOV:
                    sun_coords = np.array(sun_data['coords'])
                    sun_coords_min_dist = sun_coords[index]
                    r_sun_observed = (observed_coords[index]-sun_coords_min_dist)*1000
                    r_sun_observed_norm = np.linalg.norm(r_sun_observed)
                    r_sun_Earth = -(sun_coords_min_dist)*1000
                    r_sun_Earth_norm = np.linalg.norm(r_sun_Earth)
                    angle_gamma = np.arccos(np.dot(r_sun_observed/r_sun_observed_norm,
                                                r_sun_Earth/r_sun_Earth_norm)
                                            )
                    h = np.sin(angle_gamma)*r_sun_observed_norm
                    b = np.dot(r_sun_observed, r_sun_Earth/r_sun_Earth_norm)

                    if h >= float(Earth.R.value) or (h < float(Earth.R.value) and b < r_sun_Earth_norm):
                        
                        if object_intersects_FOV:
                            def check_intersection_with_higher_resolution(start_epoch, end_epoch, resolution=100):
                                start_time = Time(datetime.strptime(start_epoch, "%Y-%m-%d %H:%M:%S.%f"), 
                                                scale="utc", format="datetime")
                                end_time = Time(datetime.strptime(end_epoch, "%Y-%m-%d %H:%M:%S.%f"), 
                                                scale="utc", format="datetime")
                                prop_time = (end_time - start_time).to(u.min)
                                epochs_fine = time_range(start_time, num_values=resolution, end=end_time)
                                jd, fr = to_julian(epochs_fine)
                                
                                item_observed = observed_data
                                item_observant = created_data
                                orb_sat_observed = Orbit.from_classical(Earth,
                                                                        float(item_observed["SEMIMAJOR_AXIS"]) * u.km,
                                                                        float(item_observed["ECCENTRICITY"]) * u.one,
                                                                        float(item_observed["INCLINATION"]) * u.deg,
                                                                        float(item_observed["RA_OF_ASC_NODE"]) * u.deg,
                                                                        float(item_observed["ARG_OF_PERICENTER"]) * u.deg,
                                                                        float(item_observed["TRUE_ANOMALY"]) * u.deg,
                                                                        Time(item_observed["EPOCH"], scale='utc')
                                                                        )
                                orb_sat_observant = Orbit.from_classical(Earth,
                                                                        float(item_observant["SEMIMAJOR_AXIS"]) * u.km,
                                                                        float(item_observant["ECCENTRICITY"]) * u.one,
                                                                        float(item_observant["INCLINATION"]) * u.deg,
                                                                        float(item_observant["RA_OF_ASC_NODE"]) * u.deg,
                                                                        float(item_observant["ARG_OF_PERICENTER"]) * u.deg,
                                                                        float(item_observant["TRUE_ANOMALY"]) * u.deg,
                                                                        Time(item_observant["EPOCH"], scale='utc')
                                                                        )
                                tofs_observed = (epochs_fine - orb_sat_observed.epoch).to(u.s)
                                tofs_obsevant = (epochs_fine - orb_sat_observant.epoch).to(u.s)
                                rr_observed, vv_observed = propagate (orb_sat_observed,epochs_fine,tofs_observed, method='SGP4', item=item_observed, start_date=start_time, prop_time=prop_time, jd=jd, fr=fr)
                                rr_observant, vv_observant = propagate (orb_sat_observant,epochs_fine,tofs_obsevant, method='Fanocchia', item=item_observant, start_date=start_time, prop_time=prop_time, jd=jd, fr=fr)
                                quater_angle_observant = float(item_observant['Quaternion Angle'])
                                quater_axis_obsevant = ast.literal_eval(item_observant['Quaternion Vector'])
                                orbit_axis_sys_observant, body_axis_sys_observant = get_coord_sys (rr_observant,vv_observant,quater_angle_observant,quater_axis_obsevant)
                                
                                prev_observed_pos_cam_finer = None
                                for i, epoch_fine in enumerate(epochs_fine):
                                    r_observed_observant_finer = (rr_observed[i] - 
                                        rr_observant[i]
                                        )*1000
                                    cam_frame_finer = np.array(body_axis_sys_observant[index]) 
                                    R_ECI_cam_finer = np.array([cam_frame_finer[0].T,cam_frame_finer[1].T,cam_frame_finer[2].T])
                                    observed_pos_cam_finer = np.dot(R_ECI_cam_finer, r_observed_observant_finer)
                                    proy_y_finer = observed_pos_cam_finer[0]*np.tan(horizontal_FOV / 2)
                                    proy_z_finer = observed_pos_cam_finer[0]*np.tan(vertical_FOV / 2)

                                    if (-proy_y_finer <= observed_pos_cam_finer[1] <= proy_y_finer and -proy_z_finer <= observed_pos_cam_finer[2] <= proy_z_finer):
                                        return True, epoch_fine.utc.iso
                                    elif i > 0 and check_line_intersects_fov(vertical_FOV, 
                                                                            horizontal_FOV, 
                                                                            prev_observed_pos_cam_finer, 
                                                                            observed_pos_cam_finer
                                                                            ):
                                        result, epoch = check_intersection_with_higher_resolution(
                                            epochs_fine[i-1].utc.iso, 
                                            epoch_fine.utc.iso,
                                            resolution)
                                        if result:
                                            return True, epoch
                                        
                                    prev_observed_pos_cam_finer = observed_pos_cam_finer
                                return False, None
                            
                            found_intersection, intersection_epoch = check_intersection_with_higher_resolution(
                                epochs_array[index-1], 
                                epochs_array[index])
                            
                            if found_intersection:
                                object_in_FOV = True
                                index_observable.append(index)                            
                                epoch_finer_[index] = intersection_epoch
                                            
                        else:                         
                            observable = True
                            index_observable.append(index)                    
                    else:
                        observable = False
                else:
                    observable = False
            else:
                observable = False

            prev_observed_pos_cam = observed_pos_cam

        if len(index_observable) > 0:
            min_distance = float('inf')
            min_index = None
            for i in index_observable:
                if distances[i] < min_distance:
                    min_distance = distances[i]
                    min_index = i 

            observations.append({
                "To Object ID": observed_data['OBJECT_ID'],
                "Index_observable": index_observable,
                "NORAD_CAT_ID_observed": observed_data['NORAD_CAT_ID'],
                "NORAD_CAT_ID_observant": created_data['NORAD_CAT_ID'],
                "Closest Distance (km)": min_distance,
                "Time of Closest Approach": epochs_array[min_index] if epoch_finer_[min_index] is None else epoch_finer_[min_index],
                "Index_closest": min_index,
                "object_intersects_FOV": object_intersects_FOV
            }) 

    num_observations = len(observations)
  
    return observations, num_observations


def check_line_intersects_fov(fov_v, fov_h, point1, point2):
    # Calculate the four corner vectors of the FOV
    up = np.array([0, 0, 1])
    right = np.array([0, 1, 0])
    camera_dir = np.array([1, 0, 0])
    camera_pos = np.array([0, 0, 0])

    half_height = np.tan(fov_v / 2)
    half_width = np.tan(fov_h / 2)
    
    top_left = camera_dir + half_height * up - half_width * right
    top_right = camera_dir + half_height * up + half_width * right
    bottom_left = camera_dir - half_height * up - half_width * right
    bottom_right = camera_dir - half_height * up + half_width * right
    
    # Planes of the FOV pyramid
    planes = [
        (camera_pos, np.cross(top_left, top_right)),
        (camera_pos, np.cross(top_right, bottom_right)),
        (camera_pos, np.cross(bottom_right, bottom_left)),
        (camera_pos, np.cross(bottom_left, top_left))
    ]
    
    line_vec = np.array(point2) - np.array(point1)
    for plane_point, plane_normal in planes:
        denominator = np.dot(plane_normal, line_vec)
        if abs(denominator) < 1e-6:
            continue  
        t = np.dot(plane_normal, (plane_point - point1)) / denominator
        if 0 <= t <= 1:
            intersection_point = point1 + t * line_vec
            if np.dot(camera_dir, intersection_point) > 0:
                vertical_angle = np.arctan2(np.dot(intersection_point, up), np.dot(intersection_point, camera_dir))
                horizontal_angle = np.arctan2(np.dot(intersection_point, right), np.dot(intersection_point, camera_dir))
                if abs(vertical_angle) <= fov_v/2 and abs(horizontal_angle) <= fov_h/2:
                    return True
    
    return False