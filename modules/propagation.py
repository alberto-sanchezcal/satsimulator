from astropy import units as u
from poliastro.bodies import Earth, Moon, Sun
from astropy.time import Time, TimeDelta
from poliastro.util import norm, time_range
from datetime import datetime, timedelta

import numpy as np
from poliastro.core.propagation.farnocchia import (
    farnocchia_coe as farnocchia_coe_fast,
    farnocchia_rv as farnocchia_rv_fast,
)
from poliastro.core.propagation import danby
from poliastro.core.propagation import pimienta
from poliastro.twobody.propagation.vallado import vallado

from numba import njit as jit

from scipy.integrate import RK23, RK45, DOP853, solve_ivp 

from poliastro.constants import rho0_earth, H0_earth
from poliastro.ephem import build_ephem_interpolant
from astropy.coordinates import solar_system_ephemeris
from poliastro.core.perturbations import (J2_perturbation,
                                          atmospheric_drag_exponential,
                                          third_body,
                                          radiation_pressure
                                          )

from sgp4.api import Satrec
from sgp4.api import jday

def func_twobody(t0, u_, k):
    """Differential equation for the initial value two body problem.

    Parameters
    ----------
    t0 : float
        Time.
    u_ : numpy.ndarray
        Six component state vector [x, y, z, vx, vy, vz] (km, km/s).
    k : float
        Standard gravitational parameter.

    """
    x, y, z, vx, vy, vz = u_
    r3 = (x**2 + y**2 + z**2) ** 1.5

    du = np.array([vx, vy, vz, -k * x / r3, -k * y / r3, -k * z / r3])
    return du

def func_twobody_w_s_pert(t0, u_, k, A_over_m):

    x, y, z, vx, vy, vz = u_
    r3 = (x**2 + y**2 + z**2) ** 1.5

    du_kep = np.array([vx, vy, vz, -k * x / r3, -k * y / r3, -k * z / r3])

    #J2 perturbation
    ax, ay, az = J2_perturbation(
        t0, u_, k, J2=Earth.J2.value, R=Earth.R.to(u.km).value
    )
    du_ad_J2 = np.array([0, 0, 0, ax, ay, az])

    #Atmospheric drag perturbation
    C_D = 2.2 
    B = C_D * A_over_m
    rho0 = rho0_earth.to(u.kg / u.km**3).value
    H0 = H0_earth.to(u.km).value
    ax, ay, az = atmospheric_drag_exponential(
        t0,
        u_,
        k,
        R=Earth.R.to(u.km).value,
        C_D=C_D,
        A_over_m=A_over_m,
        H0=H0,
        rho0=rho0,
    )
    du_ad_atm = np.array([0, 0, 0, ax, ay, az])
    
    return du_kep + du_ad_J2 + du_ad_atm


def func_twobody_w_pert(t0, u_, k, start_date, prop_time, A_over_m, epoch):

    x, y, z, vx, vy, vz = u_
    r3 = (x**2 + y**2 + z**2) ** 1.5

    du_kep = np.array([vx, vy, vz, -k * x / r3, -k * y / r3, -k * z / r3])

    #J2 perturbation
    ax, ay, az = J2_perturbation(
        t0, u_, k, J2=Earth.J2.value, R=Earth.R.to(u.km).value
    )
    du_ad_J2 = np.array([0, 0, 0, ax, ay, az])

    #Atmospheric drag perturbation
    C_D = 2.2 
    B = C_D * A_over_m
    rho0 = rho0_earth.to(u.kg / u.km**3).value
    H0 = H0_earth.to(u.km).value
    ax, ay, az = atmospheric_drag_exponential(
        t0,
        u_,
        k,
        R=Earth.R.to(u.km).value,
        C_D=C_D,
        A_over_m=A_over_m,
        H0=H0,
        rho0=rho0,
    )
    du_ad_atm = np.array([0, 0, 0, ax, ay, az])

    #3rd body perturbation
    solar_system_ephemeris.set("de432s")
    epochs_moon_sun = time_range(epoch,
                            num_values = 20,  # Match the main step count
                            end = start_date + (prop_time)/1440 * u.day
                            )
    body_r = build_ephem_interpolant(Moon,epochs_moon_sun)
    ax, ay, az = third_body(
        t0,
        u_,
        k,
        k_third= Moon.k.to(u.km**3 / u.s**2).value,
        perturbation_body=body_r,
    )
    du_ad_3rd = np.array([0, 0, 0, ax, ay, az])  

    #radiation pressure perturbation
    body_s = build_ephem_interpolant(Sun,epochs_moon_sun)
    ax, ay, az = radiation_pressure(
        t0,
        u_,
        k,
        R=Earth.R.to(u.km).value,
        C_R = 1.4, #this is a default value
        A_over_m = A_over_m,
        Wdivc_s = 1367/((10*6)*299792),
        star = body_s
    )
    du_ad_rad = np.array([0, 0, 0, ax, ay, az])
    
    return du_kep + du_ad_J2 + du_ad_atm + du_ad_3rd + du_ad_rad

def cowell(k, r, v, tofs, RK_integrator, rtol=1e-11, *, events=None, f=func_twobody):
    x, y, z = r
    vx, vy, vz = v

    u0 = np.array([x, y, z, vx, vy, vz])

    if RK_integrator == "DOP853":
        RK_integrator = DOP853
    elif RK_integrator == "RK45":
        RK_integrator = RK45
    elif RK_integrator == "RK23":
        RK_integrator = RK23    
           

    result = solve_ivp(
        f,
        (0, max(tofs)),
        u0,
        args=(k,),
        rtol=rtol,
        atol=1e-12,
        method=RK_integrator,
        dense_output=True,
        events=events,
    )

    if not result.success:
        raise RuntimeError("Integration failed")

    if events is not None:
        # Collect only the terminal events
        terminal_events = [event for event in events if event.terminal]

        # If there are no terminal events, then the last time of integration is the
        # greatest one from the original array of propagation times
        if not terminal_events:
            last_t = max(tofs)
        else:
            # Filter the event which triggered first
            last_t = min(event._last_t for event in terminal_events)
            # FIXME: Here last_t has units, but tofs don't
            tofs = [tof for tof in tofs if tof < last_t] + [last_t]

    rrs = []
    vvs = []
    for i in range(len(tofs)):
        t = tofs[i]
        y = result.sol(t)
        rrs.append(y[:3])
        vvs.append(y[3:])

    return rrs, vvs

def cowell_w_s_pert(k, r, v, tofs, RK_integrator, span, mass, rtol=1e-11, *, events=None, f=func_twobody_w_s_pert):
    x, y, z = r
    vx, vy, vz = v

    u0 = np.array([x, y, z, vx, vy, vz])

    if RK_integrator == "DOP853":
        RK_integrator = DOP853
    elif RK_integrator == "RK45":
        RK_integrator = RK45
    elif RK_integrator == "RK23":
        RK_integrator = RK23    

    A_over_m = span**2/mass

    result = solve_ivp(
        f,
        (0, max(tofs)),
        u0,
        args=(k,A_over_m),
        rtol=rtol,
        atol=1e-12,
        method=RK_integrator,
        dense_output=True,
        events=events,
    )

    if not result.success:
        raise RuntimeError("Integration failed")

    if events is not None:
        # Collect only the terminal events
        terminal_events = [event for event in events if event.terminal]

        # If there are no terminal events, then the last time of integration is the
        # greatest one from the original array of propagation times
        if not terminal_events:
            last_t = max(tofs)
        else:
            # Filter the event which triggered first
            last_t = min(event._last_t for event in terminal_events)
            # FIXME: Here last_t has units, but tofs don't
            tofs = [tof for tof in tofs if tof < last_t] + [last_t]

    rrs = []
    vvs = []
    for i in range(len(tofs)):
        t = tofs[i]
        y = result.sol(t)
        rrs.append(y[:3])
        vvs.append(y[3:])

    return rrs, vvs


def cowell_w_pert(k, r, v, tofs, RK_integrator, initial_orbit, span, mass, start_date, prop_time, rtol=1e-11, *, events=None, f=func_twobody_w_pert):
    x, y, z = r
    vx, vy, vz = v

    u0 = np.array([x, y, z, vx, vy, vz])

    if RK_integrator == "DOP853":
        RK_integrator = DOP853
    elif RK_integrator == "RK45":
        RK_integrator = RK45
    elif RK_integrator == "RK23":
        RK_integrator = RK23    
           

    A_over_m = span*span/mass
    epoch = Time(initial_orbit.epoch, scale='tdb')

    result = solve_ivp(
        f,
        (0, max(tofs)),
        u0,
        args=(k, start_date, prop_time, A_over_m, epoch),
        rtol=rtol,
        atol=1e-12,
        method=RK_integrator,
        dense_output=True,
        events=events,
    )

    if not result.success:
        raise RuntimeError("Integration failed")

    if events is not None:
        # Collect only the terminal events
        terminal_events = [event for event in events if event.terminal]

        # If there are no terminal events, then the last time of integration is the
        # greatest one from the original array of propagation times
        if not terminal_events:
            last_t = max(tofs)
        else:
            # Filter the event which triggered first
            last_t = min(event._last_t for event in terminal_events)
            # FIXME: Here last_t has units, but tofs don't
            tofs = [tof for tof in tofs if tof < last_t] + [last_t]

    rrs = []
    vvs = []
    for i in range(len(tofs)):
        t = tofs[i]
        y = result.sol(t)
        rrs.append(y[:3])
        vvs.append(y[3:])

    return rrs, vvs

def sgp4_propagator(jd,fr, item):
    s = item['TLE_LINE1']
    t = item['TLE_LINE2']
    satellite = Satrec.twoline2rv(s, t)

    e, rr, vv = satellite.sgp4_array(jd, fr)

    return rr, vv


def propagate (initial_orbit, epochs, tofs, method = 'Farnocchia', item=None, start_date=None, prop_time=None, jd=None, fr =None):

    r0 = initial_orbit.r.to(u.km).value
    v0 = initial_orbit.v.to(u.km / u.s).value

    k = Earth.k.to(u.km**3 / u.s**2).value

    # COWELL
    if method == 'Cowell (wo/perturbations)':
        tofs = tofs.to(u.s).value
        rr_cowell, vv_cowell = cowell(k, r0, v0, tofs, "DOP853")
        rr_cowell = np.array(rr_cowell)
        vv_cowell = np.array(vv_cowell)
        return rr_cowell, vv_cowell
    if method == 'Cowell (w/ some perturbations)':
        tofs = tofs.to(u.s).value
        rr_cowell, vv_cowell = cowell_w_s_pert(k, r0, v0, tofs, "DOP853", item['span'], item['mass'])
        rr_cowell = np.array(rr_cowell)
        vv_cowell = np.array(vv_cowell)
        return rr_cowell, vv_cowell
    if method == 'Cowell (w/ perturbations)':
        tofs = tofs.to(u.s).value
        rr_cowell, vv_cowell = cowell_w_pert(k, r0, v0, tofs, "DOP853", initial_orbit, item['span'], item['mass'], start_date, prop_time)
        rr_cowell = np.array(rr_cowell)
        vv_cowell = np.array(vv_cowell)
        return rr_cowell, vv_cowell

    # FARNOCHIA
    if method == 'Farnocchia':
        results = np.array([farnocchia_rv_fast(k, r0, v0 , tof) for tof in tofs])
        rr_farnocchia = results[:, 0]
        vv_farnocchia = results[:, 1]
        return rr_farnocchia, vv_farnocchia
    
    #DANBY
    if method == 'Danby':
        results = np.array([danby(k, r0, v0 , tof) for tof in tofs])
        rr_danby = results[:, 0]
        vv_danby = results[:, 1]
        return rr_danby, vv_danby

    #PIMIENTA
    if method == 'Pimienta':
        results = np.array([pimienta(k, r0, v0 , tof) for tof in tofs])
        rr_pimienta = results[:, 0]
        vv_pimienta = results[:, 1]
        return rr_pimienta, vv_pimienta
    
    #VALLADO
    if method == 'Vallado':
        numiter = 10
        results = np.array([vallado(k, r0, v0, tof, numiter=numiter) for tof in tofs])
        rr_vallado = results[:, 0]
        vv_vallado = results[:, 1]
        return rr_vallado, vv_vallado

    if method == 'SGP4':
        if item ['OBJECT_ID'] == 'CREATED BY USER':
            results = np.array([farnocchia_rv_fast(k, r0, v0 , tof) for tof in tofs])
            rr_farnocchia = results[:, 0]
            vv_farnocchia = results[:, 1]
            return rr_farnocchia, vv_farnocchia            
        else:
            rr_sgp4, vv_sgp4 = sgp4_propagator(jd, fr, item)
            rr_sgp4 = np.array(rr_sgp4)
            vv_sgp4 = np.array(vv_sgp4)
            return rr_sgp4,vv_sgp4
    



def spherical_to_cartesian(r, ra, dec):

    x = r * np.cos(dec) * np.cos(ra)
    y = r * np.cos(dec) * np.sin(ra)
    z = r * np.sin(dec)
    
    return x, y, z

def to_julian (epochs):
    jd=[]
    fr=[]
    for epoch in epochs:
        year = epoch.datetime.year
        month = epoch.datetime.month
        day = epoch.datetime.day
        hour = epoch.datetime.hour
        minute = epoch.datetime.minute
        second = epoch.datetime.second
        microsecond = epoch.datetime.microsecond
        second_fraction = microsecond / 1_000_000
        second_with_fraction = second + second_fraction
        
        jd_, fr_ = jday(year, month, day, hour, minute, second_with_fraction)
        
        jd.append(jd_)
        fr.append(fr_)
    
    jd = np.array(jd)
    fr = np.array(fr)
    return jd, fr
