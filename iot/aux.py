# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" Auxiliary Variables/Functions/Imports
Module defining auxiliary elements for the IoT Devices module.
"""
# ---------------------------------------------------------------------------
# Imports
from threading import Thread
from paho.mqtt import client as mqtt_client

from json import dumps
from numpy import random
import numpy as np

from datetime import datetime, timedelta
import time, re, uuid

from colorama import Fore, Style
from builtins import print as prnt
from typing import Any, List, Dict, Tuple
# ---------------------------------------------------------------------------

###########################
######## VARIABLES ########
###########################

# Root topics for publishing
prodline_root   = 'productionline'
safetyenv_root  = 'safetyenvironmental'

# Other variables
arrow_str       = '     |------> '
arrow_str2      = '     |          |---> '

#########################
######## CLASSES ########
#########################

# Class providing ground truth for ambient variables such as temperature, pressure...
class GroundTruth(Thread) :
    """
    A class that provides ground truth values for ambient variables such as temperature, pressure, etc. It is a subclass of the Thread class and updates the ground truth values every 100 milliseconds.

    Attributes:
        ground_truth_vars (dict): a dictionary containing the names and initial values of the ambient variables.

    Methods:
        update_ground_truth_vars(self) -> None: updates the ground truth values.
        get(self, var: str) -> float: returns the current value of the specified variable.
        run(self) -> None: the method called when the thread is started. It updates the ground truth values and sleeps for 100 milliseconds repeatedly.
    """
    # Initialization
    def __init__(self,ground_truth_vars):
        Thread.__init__(self)
        self.ground_truth_vars = {}
        # Initialize each variable
        for name, params in ground_truth_vars.items() :
            mu, sigma = params
            self.ground_truth_vars[name] = sample_normal_mod(mu,sigma)
    
    # New ground truth series samples
    def update_ground_truth_vars(self) -> None :
        for name, last_value in self.ground_truth_vars.items():
            self.ground_truth_vars[name] = get_new_sample(last_value,sigma=0.001)
    
    # Get ground truth var current value
    def get(self, var: str) -> float:
        return self.ground_truth_vars[var]

    # Thread execution
    def run(self) -> None :
        while True : 
            # Update ground truth series values and sleep for 100ms
            self.update_ground_truth_vars()
            time.sleep(0.1)

###########################
######## FUNCTIONS ########
###########################

# Get new random sample of time series based on last one
def get_new_sample(last_sample: float, sigma: float = 0.01) -> float:
    """Returns a new sample by multiplying the last sample by a random number
    drawn from a normal distribution with mean 1 and standard deviation sigma.
    
    Parameters
    ----------
    last_sample (float): The last sample value.
    sigma (float): The standard deviation of the normal distribution. Default value is 0.01.
    
    Returns
    -------
    A new sample value, as a float.
    """
    return last_sample*random.normal(1,sigma)

def sample_sine(offset: float, amp: float, T: float, phi: float) -> float:
    """Returns a new sample of a sine wave at the current time.
    
    Parameters
    ----------
    offset (float): The offset of the sine wave.
    amp (float): The amplitude of the sine wave.
    T (float): The period of the sine wave.
    phi (float): The phase of the sine wave.
    
    Returns
    -------
    A new sample value, as a float.
    """
    t = time.perf_counter()
    return get_new_sample(offset + amp*np.sin((2*np.pi/T)*t + phi))

# Square wave
def sample_square(offset: float, amp: float, T: float, phi: float) -> float:
    """Returns a new sample of a square wave at the current time.
    
    Parameters
    ----------
    offset (float): The offset of the square wave.
    amp (float): The amplitude of the square wave.
    T (float): The period of the square wave.
    phi (float): The phase of the square wave.
    
    Returns
    -------
    A new sample value, as a float.
    """
    t = time.perf_counter()
    return get_new_sample(offset + amp*np.sign(np.sin((2*np.pi/T)*t + phi)))

# Sawtooth wave
def sample_triangular(offset: float, amp: float, T: float, phi: float) -> float:
    """Returns a new sample of a triangular wave at the current time.
    
    Parameters
    ----------
    offset (float): The offset of the sine wave.
    amp (float): The amplitude of the sine wave.
    T (float): The period of the sine wave.
    phi (float): The phase of the sine wave.
    
    Returns
    -------
    A new sample value, as a float.
    """
    t = time.perf_counter() + phi/(2*np.pi/T)
    val = offset + 2*amp*((t%(T/2)/T)-0.5) if t%T  < T/2 else offset - 2*amp*((t%(T/2)/T)-0.5)
    return get_new_sample(val)

# Sawtooth wave
def sample_sawtooth(offset: float, amp: float, T: float, phi: float) -> float:
    """Returns a new sample of a sawtooth wave at the current time.
    
    Parameters
    ----------
    offset (float): The offset of the sawtooth wave.
    amp (float): The amplitude of the sawtooth wave.
    T (float): The period of the sawtooth wave.
    phi (float): The phase of the sawtooth wave.
    
    Returns
    -------
    A new sample value, as a float.
    """
    t = time.perf_counter() + phi/(2*np.pi/T)
    return get_new_sample(offset + amp*(2*((t%T)/T)-0.5))

# Flip a coin (returns True with prob = prob)
def coin(prob: float = 0.5) -> bool:
    """Flips a virtual coin.
    
    Parameters
    ----------
    prob (float): The probability of the coin returning True. Default value is 0.5.
    
    Returns
    -------
    True with probability `prob`, False otherwise.
    """
    return random.uniform() < prob

# Generate data from a normal distribution between a min and a maximum value
def sample_normal_mod(mu: float, sigma: float = 0.05, modifier: float = 0.0) -> float:
    """Generates a random value from a normal distribution between two thresholds.
    
    The thresholds are defined as `mu - sigma` and `mu + sigma`,
    where `mu` is the mean of the normal distribution and `sigma` is its standard deviation.
    The `modifier` argument is applied to both `mu` and `sigma` before the thresholds are calculated.
    
    Parameters
    ----------
    mu (float): The mean of the normal distribution.
    sigma (float): The standard deviation of the normal distribution. Default value is 0.05.
    modifier (float): A factor to modify `mu` and `sigma` by. Default value is 0.0.
    
    Returns
    -------
    A random value from the normal distribution, within the calculated thresholds.
    """
    # Apply modification factor to values
    mu = mu*(1 + modifier)
    sigma = sigma*(1 + modifier)
    th = [mu - sigma, mu + sigma] # threshold within 1 STD

    # Generate random value within thresholds
    val = random.normal(mu,sigma)
    if val > th[0] : return th[0] 
    elif val < th[1] : return th[1]
    else: val

# Generate robot data
def gen_robot_data(offset: float, A: float, T: float, phi: float, actuator_status: bool) -> Dict[str, Dict[str, float]]:
    """Generates data for a robot.
    
    Parameters
    ----------
    offset (float): The offset of the generated data.
    A (float): A scaling factor for the generated data.
    T (float): A period for the generated data.
    phi (float): A phase shift for the generated data.
    actuator_status (bool): The status of the robot's actuator.
    
    Returns
    -------
    A dictionary containing data for the robot's joint and actuator.
    """
    return {
        'joint': {
            'x_position' : sample_sine(offset,A,T,phi),
            'y_position' : sample_sine(offset-1,A*2,T*1.25,phi),  
            'z_position' : sample_sine(offset-2,A/2,T*0.75,phi),
            'roll_orientation' : sample_sawtooth(offset+np.pi/2,A,T,phi), 
            'pitch_orientation' : sample_sawtooth(offset+1*np.pi/4,A*2,T*1.25,phi), 
            'yaw_orientation' : sample_sawtooth(offset+2*np.pi/4,A/2,T*0.75,phi)
        },
        'actuator': {
            'x_position' : sample_triangular(offset,A,T,phi),
            'y_position' : sample_triangular(offset-1,A*2,T*1.5,phi),  
            'z_position' : sample_triangular(offset-2,A/2,T*0.5,phi),
            'roll_orientation' : sample_triangular(offset+np.pi/2,A,T,phi), 
            'pitch_orientation' : sample_triangular(offset+1*np.pi/4,A*2,T*1.5,phi), 
            'yaw_orientation' : sample_triangular(offset+2*np.pi/4,A/2,T*0.75,phi),
            'actuator_status' : actuator_status
        }
    }

# Generate header data
def gen_header(dev_class: str, topic: str, uuid: str, category: str = 'DATA') -> Dict[str, str]:
    """Generates header data for a device.
    
    Parameters
    ----------
    dev_class (str): The class of the device.
    topic (str): The topic of the device.
    uuid (str): The UUID of the device.
    category (str): The category of the data. Default value is 'DATA'.
    
    Returns
    -------
    A dictionary containing the header data.
    """
    return {
        'category' : category,
        'class' : dev_class,
        'topic' : topic,
        'uuid' : uuid,
        'timestamp' : datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")
    }

# Print device data
def print_device_data(timestamp: datetime, data: Dict[str, Dict[str, Any]]) -> None:
    """Print device data.
    
    Parameters
    ----------
    timestamp (str): Datetime object representing the current time.
    data (dict): A dictionary containing device data. The keys are the names of the devices 
                and the values are dictionaries containing the device properties.
            
    Returns
    -------
    None.
    """
    print(arrow_str + f'[timer]',kind='')
    print(arrow_str2 + f'(timestamp)<datetime>={timestamp}',kind='')
    for mname in data :
        print(arrow_str + f'[{mname}]',kind='')
        for mproperty in data[mname] :
            print(arrow_str2 + f'({mproperty})={data[mname][mproperty]}',kind='')

# Colored prints
def print(text: str, kind: str = '') -> None:
    """Prints a text in the console with a specific color.
    
    Parameters
    ----------
    text (str): The text to be printed.
    kind (str): The color of the text.
    
    Returns
    -------
    None
    """
    prnt(cprint_dict[kind] + str(text) + Style.RESET_ALL)


##############################
######## DICTIONARIES ########
##############################

# Colored prints
cprint_dict = {
    'info':     Fore.WHITE,
    'success' : Fore.GREEN,
    'fail':     Fore.RED,
    'summary':  Fore.MAGENTA,
    'debug':    Fore.BLUE,
    '':         Fore.YELLOW 
}
