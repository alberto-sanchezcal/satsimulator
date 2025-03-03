import numpy as np
import quaternion

def get_coord_sys (rr,vv, angle_quat, axis_quat): 
    angle = np.radians(angle_quat)
    axis_orb = axis_quat/np.linalg.norm(axis_quat)

    z_axis_orb_coord = np.array([-coord/np.linalg.norm(coord) for coord in rr])
    y_axis_orb_coord = -np.cross(rr[1], vv[1])/np.linalg.norm(np.cross(rr[1], vv[1]))
    x_axis_orb_coord = [np.cross(y_axis_orb_coord,z_axis_orb_coord_step) for 
                        z_axis_orb_coord_step in z_axis_orb_coord]
    orbit_axis_sys = []
    for i, z in enumerate(z_axis_orb_coord):
        orbit_frame_step = [x_axis_orb_coord[i], y_axis_orb_coord, z]
        orbit_axis_sys.append(orbit_frame_step)

    #COMPUTATION OF THE BODY FRAME
    body_axis_sys = []
    for orbit_frame_step in orbit_axis_sys:
        x_orb = orbit_frame_step[0]
        y_orb = orbit_frame_step[1]
        z_orb = orbit_frame_step[2]
        R_ECEF_orb= np.array([x_orb.T, y_orb.T, z_orb.T])
        R_orb_ECEF = R_ECEF_orb.T
        axis_ECEF = np.dot (R_orb_ECEF, axis_orb)
        q = quaternion.from_rotation_vector(angle * axis_ECEF)

        p_x = np.quaternion(0,x_orb[0],x_orb[1],x_orb[2]) 
        rotated_p_x = q * p_x * q.conjugate()
        x_body = rotated_p_x.vec/np.linalg.norm(rotated_p_x.vec)

        p_y = np.quaternion(0,y_orb[0],y_orb[1],y_orb[2]) 
        rotated_p_y = q * p_y * q.conjugate()
        y_body = rotated_p_y.vec/np.linalg.norm(rotated_p_y.vec)

        p_z = np.quaternion(0,z_orb[0],z_orb[1],z_orb[2])
        rotated_p_z = q * p_z * q.conjugate()
        z_body = rotated_p_z.vec/np.linalg.norm(rotated_p_z.vec)
        
        body_system_step = [x_body, y_body, z_body]
        body_axis_sys.append(body_system_step)    

    return orbit_axis_sys, body_axis_sys