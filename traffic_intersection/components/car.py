# Kinematic Car Class
# Tung M. Phan
# California Institute of Technology
# May 3, 2018

import os
import sys
sys.path.append("..")
import scipy.io
import numpy as np
from primitives.prim_car import prim_state_dot
from components.auxiliary.tire_data import get_tire_data
from scipy.integrate import odeint
from numpy import cos, sin, tan, arctan2, sqrt, sign, diag
main_dir = os.path.dirname(os.path.dirname(os.path.realpath("__file__")))
primitive_data = main_dir + '/primitives/MA3.mat'
from prepare.queue import Queue
from primitives.load_primitives import get_prim_data
from PIL import Image
from assumes.disturbance import get_disturbance
import assumes.params as params
from math import pi
from scipy.optimize import newton_krylov, fsolve, anderson, broyden1, broyden2

dir_path = os.path.dirname(os.path.realpath("__file__"))
car_colors = {'blue', 'gray', 'white', 'yellow', 'brown',
        'white1','green', 'white_cross', 'cyan', 'red1', 'orange'}
#car_colors = {'blue', 'gray', 'black', 'white', 'yellow', 'brown', 'white1','green', 'white_cross', 'cyan', 'red1', 'orange', 'white2'}
car_figs = dict()
for color in car_colors:
    car_figs[color] = main_dir + '/components/imglib/cars/' + color + '_car.png'

mat = scipy.io.loadmat(primitive_data)


def saturation_filter(u, u_min, u_max):
    ''' saturation_filter Helper Function

        the output is equal to u_max if u >= u_max, u_min if u <= u_min, and u otherwise
    '''
    return max(min(u, u_max), u_min)

# for convenience if a bunch of primitive data is requested
def get_bunch_prim_data(prim_id, data_fields):
    data = dict()
    for data_field in data_fields:
        data[data_field] = mat['MA3'][prim_id,0][data_field][0,0]
    return list(data.values())

class KinematicCar():
    '''Kinematic car class

    init_state is [vee, theta, x, y], where vee, theta, x, y are the velocity, orientation, and
    coordinates of the car respectively
    '''
    def __init__(self, 
                 init_state=[0, 0, 0, 0],
                 length = 50,  # length of vehicle in pixels
                 acc_max = 9.81,  # maximum acceleration of vehicle
                 acc_min = -9.81,  # maximum deceleration of vehicle
                 steer_max = 0.5,  # maximum steering input in radians
                 steer_min = -0.5,  # minimum steering input in radians
                 vee_max = 100,  # maximum velocity
                 is_honking = False,  # the car is honking
                 color = 'blue',  # color of the car
                 plate_number = None,  # license plate number
                 # queue of primitives, each item in the queue has the form (prim_id, prim_progress) where prim_id is the primitive ID and prim_progress is the progress of the primitive)
                 prim_queue = None,
                 fuel_level = float('inf')):  # TODO: fuel level of the car
        if color not in car_colors:
            raise Exception("This car color doesn't exist!")
        self._length = length
        self._vee_max = vee_max
        self.acc_range = (acc_min, acc_max)
        self.steer_range = (steer_min, steer_max)
        self.alive_time = 0
        self.plate_number = plate_number
        #self.init_state = np.array(init_state, dtype='float')
        self.state = np.array(init_state, dtype='float')
        self.color = color
#        self.new_unpause = False
#        self.new_pause = False
        # extended state required for Bastian's primitive computation
        self.extended_state = None
        self.is_honking = is_honking
        if prim_queue == None:
            self.prim_queue = Queue()
        else:
            self.prim_queue = prim_queue
        self.fuel_level = fuel_level
        self.fig = Image.open(car_figs[color])

    def state_dot(self, state, time, acc, steer):
        """
        This function defines the system dynamics
        
        Inputs
        acc: acceleration input
        steer: steering input
        """
        # if already at maximum speed, can't no longer accelerate
        if abs(state[0]) >= self._vee_max and sign(acc) == sign(state[0]):
            vee_dot = 0
        else:
            vee_dot = saturation_filter(acc, self.acc_range[0], self.acc_range[1])    
        theta_dot = state[0] / self._length * tan(saturation_filter(steer, self.steer_range[0], self.steer_range[1]))
        x_dot = state[0] * cos(state[1]) 
        y_dot = state[0] * sin(state[1]) 
        dstate = [vee_dot, theta_dot, x_dot, y_dot]
        return dstate

    def toggle_honk(self):
        self.is_honking = not self.is_honking

    def next(self, inputs, dt):
        """
        next is a function that updates the current position of the car when inputs are applied for a duration of dt
        
        Inputs:
        inputs: acceleration and steering inputs
        dt: integration time

        Outputs:
        None - the states of the car will get updated
        """
        acc, steer = inputs
        # take only the real part of the solution
        self.state = odeint(self.state_dot, self.state, t=(0, dt), args=(acc, steer))[1]
        self.fuel_level -= abs(acc) * dt # fuel decreases linearly with acceleration
        self.alive_time += dt

        # fix floating
        if abs(acc) < 0.1:
            self.state[0] = 0
            
    def extract_primitive(self):
        """
        This function updates the primitive queue and picks the next primitive to be applied. When there is no more primitive in the queue, it will
        return False

        """
        while self.prim_queue.len() > 0:
            # if the top primitive hasn't been exhausted
            if self.prim_queue.top()[1] < 1:
                prim_id, prim_progress = self.prim_queue.top()  # extract it
                return prim_id, prim_progress
            else:
                self.prim_queue.pop()  # pop it
        return False

    def prim_next(self, dt):
        """
        updates with primitive, if no primitive available, update with next with zero inputs
        Inputs:
        dt: integration time

        Outputs:
        None - the states of the car will get updated
        """
        if self.extract_primitive() == False:  # if there is no primitive to use
            self.next((0, 0), dt)
        else:
            prim_id, prim_progress = self.extract_primitive()
            # TODO: make this portion of the code more automated
            if prim_id > -1:
                # load primitive data 
                list_of_key = ['x0', 'x_ref', 'u_ref', 'alpha', 'K']
                x0, x_ref, u_ref, alpha, K = get_bunch_prim_data(prim_id, list_of_key)
                
                if prim_progress == 0:  # compute initial extended state
                    x_real = self.state.reshape((-1, 1))                   
                    x1 = x_real - x0
                    x2 = np.matmul(np.linalg.inv(diag([4, 0.02, 4, 4])), x1)
                    # initial state, consisting of actual and virtual states for the controller
                    self.extended_state = (np.vstack((x_real, x0, x1, x2)))[:, 0] 
                
                num_of_inputs = 2 
                G_u = np.diag([175, 1.29]) # this diagonal matrix encodes the size of input set (a constraint)
                dist = get_disturbance()
                k = int(prim_progress * params.num_subprims)  # calculate primitive waypoint
                q1 = K[k, 0].reshape((-1, 1), order='F')
                q2 = 0.5 * (x_ref[:, k+1] + x_ref[:, k]).reshape(-1, 1)
                q3 = u_ref[:, k].reshape(-1, 1)
                q4 = u_ref[:, k].reshape(-1, 1)
                q5 = np.matmul(G_u, alpha[k*num_of_inputs: (k+1)*num_of_inputs]).reshape((-1, 1), order='F')
                # parameters for the controller
                q = np.vstack((q1, q2, q3, q4, q5))
                
                self.extended_state = odeint(func=prim_state_dot, y0=self.extended_state, t=[0, dt], args=(dist, q))[-1, :]
                self.state = self.extended_state[0: len(self.state)]
                self.alive_time += dt
                prim_progress = prim_progress + dt / get_prim_data(prim_id, 't_end')[0]
                self.prim_queue.replace_top((prim_id, prim_progress))
            else:  # if is stopping primitive
                self.next((0, 0), dt)

class DynamicCar(KinematicCar): # bicycle 5 DOF model
    def __init__(self,
                m = 2000, # mass of the vehicle in kilograms
                m_w = 15, # mass of one tire
                L_r = 2, # distance in meters from rear axle to center of mass
                L_f = 2, # distance in meters from front axle to center of mass
                h = 1, # height of center of mass in meters
                tire_designation = '155SRS13', # tire specifications
                init_dyn_state = np.zeros(8), # initial dynamical state of vehicle
                car_width = 2.,  # car width
                R_w = 0.3): # the radius of the vehicle's wheel
        KinematicCar.__init__(self)
        self.m = m
        self.L_r = L_r
        self.L_f = L_f
        self.L = self.L_r + self.L_f
        self.h = h
        self.R_w = R_w
        self.m_w = m_w
        self.tire_data = get_tire_data(tire_designation)
        self.dyn_state = init_dyn_state
        self.car_width = car_width
        self.I_w = 1/2. * m_w * R_w**2 # approximated as the moment of inertia around z-axis of a thin disk / cylinder of any length with radius R_w and mass m
        self.I_z = 1/12. * m * (self.L**2 + self.car_width**2)

    def state_dot(self, init_dyn_state, t, delta_f, delta_r, T_af, T_ar, T_bf, T_br):
        # state = [v_x, v_y, r, psi, w_f, w_r, X, Y]

        state = init_dyn_state
        v_x = state[0]
        v_y = state[1]
        r = state[2]
        psi = state[3]
        w_f = state[4]
        w_r = state[5]
        X = state[6]
        Y = state[7]
        m = self.m
        L_r = self.L_r
        L_f = self.L_f
        h = self.h
        R_w = self.R_w
        I_w = self.I_w
        I_z = self.I_z
        g = params.g

        alpha_f = arctan2(v_y + L_f * r, v_x) - delta_f # equation 11
        alpha_r = arctan2(v_y - L_r * r, v_x) - delta_r # equation 12
        V_tf = sqrt((v_y + L_f * r)**2 + v_x**2) # equation 13
        V_tr = sqrt((v_y - L_r * r)**2 + v_x**2) # equation 14
        v_wxf = V_tf * cos(alpha_f) # equation 15
        v_wxr = V_tr * cos(alpha_r) # equation 16
        S_af = self.get_longitudinal_slip(v_wxf, w_f) # equation 17
        S_ar = self.get_longitudinal_slip(v_wxr, w_r) # equation 18

        def algebra(var):
            vdot_x, F_xf, F_xr, F_yf, F_yr = var
            rhs = -F_xf * cos(delta_f) - F_yf * sin(delta_f) - F_xr * cos(delta_r) - F_yr * sin(delta_r)
            eq1 = vdot_x - rhs / m + v_y * r # equation 1
            # substitutions
            a_x = vdot_x # instantaneous longitudinal acceleration
            F_zf = (m * g * L_r - m * a_x * h) / (L_f + L_r) # equation 9
            F_zr = (m * g * L_f - m * a_x * h) / (L_f + L_r) # equation 10
            F_xf_guess, F_yf_guess = self.get_traction(F_xf, F_zf, S_af, alpha_f)
            F_xr_guess, F_yr_guess = self.get_traction(F_xr, F_zr, S_ar, alpha_r)
            eq19 = F_xf - F_xf_guess # equation 19
            eq20 = F_yf - F_yf_guess # equation 20
            eq21 = F_xr - F_xr_guess # equation 21
            eq22 = F_yf - F_yf_guess # equation 22
            return eq1, eq19, eq20, eq21, eq22

        # resolve interdependency with nonlinear solver
        init_guess = [0,0,0,0,0]
        vdot_x, F_xf, F_xr, F_yf, F_yr = anderson(algebra, init_guess)
        rhs = F_yf * cos(delta_f) - F_xf * sin(delta_f) + F_yr * cos(delta_r) - F_xr * sin(delta_r)
        vdot_y = rhs / m  - v_x * r # equation 2
        rhs = L_f * (F_yf * cos(delta_f) - F_xf * sin(delta_f)) - L_r * (F_yr * cos(delta_r) - F_xr * sin(delta_r))
        r_dot = rhs / I_z # equation 3
        rhs = F_xf * R_w - T_bf + T_af
        wdot_f =  rhs / I_w # equation 4
        rhs = F_xr * R_w - T_br + T_ar
        wdot_r =  rhs / I_w # equation 5
        psi_dot = r # equation 6
        v_X = v_x * cos(psi) - v_y * sin(psi) # equation 7
        v_Y = v_x * sin(psi) + v_y * cos(psi) # equation 8

        dstate_dt = [vdot_x, vdot_y, r_dot, psi_dot, wdot_f, wdot_r, v_X, v_Y]
        return dstate_dt

    def next(self, inputs, dt):
        """
        next is a function that updates the current position of the car when inputs are applied for a duration of dt
        Inputs:
        dt: integration time

        Outputs:
        None - the states of the car will get updated
        """
        delta_f, delta_r, T_af, T_ar, T_bf, T_br = inputs

        # take only the real part of the solution
        self.dyn_state = odeint(self.state_dot, self.dyn_state, t=(0, dt), args=inputs)[1]
        # update alive time
        self.alive_time += dt

    def get_longitudinal_slip(self, u, w):
        R = self.R_w
        if u > R*w:
            return (u-R*w)/u
        else:
            return (R*w-u)/R*w

    def get_traction(self, F_x, F_z, S, alpha): # longitudinal slip, slip angle, F_x, normal load
        tire_data = self.tire_data
        T_w = tire_data['T_w']
        T_p = tire_data['T_p']
        F_ZT = tire_data['F_ZT']
        C_1 = tire_data['C_1']
        C_2 = tire_data['C_2']
        C_3 = tire_data['C_3']
        C_4 = tire_data['C_4']
        A_0 = tire_data['A_0']
        A_1 = tire_data['A_1']
        A_2 = tire_data['A_2']
        A_3 = tire_data['A_3']
        A_4 = tire_data['A_4']
        K_a = tire_data['K_a']
        K_1 = tire_data['K_1']
        CS_FZ = tire_data['CS_FZ']
        mu_o = tire_data['mu_o']

        K_mu = 0.124
        K_gamma_camber = 0 # camber angle

        # equation 11 & 12, tire contact patch length
        a_po = (0.0768 * sqrt(F_z * F_ZT)) / (T_w * (T_p + 5))
        a_p = a_po * (1 - K_a * F_x / F_z)

        # equation 13, 14 lateral and longitudianl stiffness coeffs 
        K_s = (2 / a_po**2) * (A_0 + A_1 * F_z - (A_1 / A_2) * F_z**2)
        K_c = (2 / a_po**2) * F_z * CS_FZ

        # equation 15, composite slip calculation
        sigma = (pi * a_p**2) / (8 * mu_o * F_z) * sqrt(K_s**2 * (tan(alpha))**2 + K_c**2 * (S / (1 - S))**2)

        # equation 10 composite force, saturation function
        f_of_sigma = (C_1 * sigma**3 + C_2 * sigma**2 + 4 / pi * sigma) / (C_1 * sigma**3 + C_3 * sigma**2 + C_4 * sigma + 1)

        # equation 18 & 19 modified Long. Stiff Coeff and Tire/Rd coeff friction
        K_c_prime = K_c + (K_s - K_c) * sqrt((sin(alpha))**2 + S**2 * (cos(alpha))**2)
        mu = mu_o * (1 - K_mu * sqrt((sin(alpha))**2 + S**2 * (cos(alpha))**2) )

        # equation 16 & 17 Normalized Lateral and Long Force
        F_y = (f_of_sigma * K_s * tan(alpha) / sqrt(K_s**2 * (tan(alpha))**2 + K_c_prime**2 * S**2) + K_gamma_camber) * mu * F_z
        F_x = (f_of_sigma * K_c_prime * S / sqrt(K_s**2 * (tan(alpha))**2 + K_c_prime**2 * S**2)) * mu * F_z

        return F_x, F_y

# TESTING
v_x = 1
v_y = 0
r = 0
psi = 0
w_f = 0.1
w_r = 0.1
X = 100
Y = 100
init_dyn_state = np.array([v_x, v_y, r, psi, w_f, w_r, X, Y])
dyn_car = DynamicCar(init_dyn_state = init_dyn_state)
delta_f = 0
delta_r = 0
T_af = 5
T_ar = 0
T_bf = 0
T_br = 0
inputs = (delta_f, delta_r, T_af, T_ar, T_bf, T_br)
dt = 0.1
t_end = 10
t_start = 0
t_current = t_start
X = []
Y = []
psi = []
while t_current < t_end:
    dyn_car.next(inputs, 0.1)
    t_current += dt
    state = dyn_car.dyn_state
    X.append(state[-2])
    Y.append(state[-1])
    print(state)

# state = [v_x, v_y, r, psi, w_f, w_r, X, Y]
import matplotlib.pyplot as plt
plt.plot(X,Y)
plt.show()
