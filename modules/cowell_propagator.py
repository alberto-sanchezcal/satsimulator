from astropy import units as u
from poliastro.bodies import Earth, Moon, Sun
from astropy.time import Time

import numpy as np

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


### COWELL'S PROPAGATOR ###
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


def func_twobody_w_pert(t0, u_, k, epoch, orbital_period, A_over_m):

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
    body_r = build_ephem_interpolant(
        Moon,
        28 * u.day,
        (epoch.value * u.day, epoch.value * u.day + orbital_period * u.day),
        rtol=1e-2,
        attractor=Earth,
    )    
    ax, ay, az = third_body(
        t0,
        u_,
        k,
        k_third= Moon.k.to(u.km**3 / u.s**2).value,
        perturbation_body=body_r,
    )
    du_ad_3rd = np.array([0, 0, 0, ax, ay, az])    

    #radiation pressure perturbation
    body_s = build_ephem_interpolant(
        Sun,
        24 * u.h,
        (epoch.value * u.day, epoch.value * u.day + orbital_period * u.day),
        rtol=1e-2,
        attractor=Sun,
    )    
    ax, ay, az = radiation_pressure(
        t0, 
        u_, 
        k, 
        R=Earth.R.to(u.km).value, 
        C_R = 1.4, #this is a default value
        A_over_m = A_over_m, 
        Wdivc_s = 1367/((10*6)*299792), 
        star = body_s)
    du_ad_rad = np.array([0, 0, 0, ax, ay, az])      
    

    return du_kep + du_ad_J2 + du_ad_atm + du_ad_3rd + du_ad_rad


def cowell(k, r, v, tofs, RK_integrator, initial_orbit, span, mass, rtol=1e-11, *, events=None, f=func_twobody_w_pert):
    x, y, z = r
    vx, vy, vz = v

    u0 = np.array([x, y, z, vx, vy, vz])

    if RK_integrator == "DOP853":
        RK_integrator = DOP853
    elif RK_integrator == "RK45":
        RK_integrator = RK45
    elif RK_integrator == "RK23":
        RK_integrator = RK23    

    epoch = Time(initial_orbit.epoch, scale='utc').to_value('jd') * u.day
    orbital_period = initial_orbit.period.to(u.day).value

    A_over_m = span*span/mass


    result = solve_ivp(
        f,
        (0, max(tofs)),
        u0,
        args=(k,epoch, orbital_period, A_over_m),
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
