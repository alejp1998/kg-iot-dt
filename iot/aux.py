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

from datetime import datetime, timedelta
import time, re, uuid

from colorama import Fore, Style
from builtins import print as prnt
# ---------------------------------------------------------------------------

###########################
######## VARIABLES ########
###########################

# Numpy random generator
rng = random.default_rng()

# Root topics for publishing
prodline_root   = 'productionline'
safetyenv_root  = 'safetyenvironmental'

# Other variables
arrow_str       = '     |------> '
arrow_str2      = '     |          |---> '

###########################
######## FUNCTIONS ########
###########################

# Get new sample of time series based on last one
def get_new_sample(last_sample,sigma=0.002):
    return last_sample*(1 + rng.normal(0,sigma))

# Flip a coin (returns True with prob = prob)
def coin(prob=0.5) :
    return rng.uniform() < prob

# Generate data from a normal distribution between a min and a maximum value
def sample_normal_mod(mu,sigma=0.1,modifier=0.0) :
    # Apply modification factor to values
    mu += mu*modifier
    sigma += sigma*modifier
    th = [mu - sigma, mu + sigma] # threshold within 1 STD

    # Generate random value within thresholds
    val = rng.normal(mu,sigma)
    if val > th[0] and val < th[1] : return val
    if val < th[0] : return th[0]
    else: return th[1]

# Generate initial joint data
def init_joint_data(mu1,mu2,sigma):
    joint_dic = {}
    for i_pos in ['x_position','y_position','z_position']:
        joint_dic[i_pos] = sample_normal_mod(mu1,sigma)
    for i_ori in ['roll_orientation','pitch_orientation','yaw_orientation']:
        joint_dic[i_ori] = sample_normal_mod(mu2,sigma)
    return joint_dic

# Generate header data
def fill_header_data(device_name,topic,uuid):
    return {
        'name' : device_name,
        'topic' : topic,
        'uuid' : uuid,
        'timestamp' : datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    }

# Fill module uuids
def fill_module_uuids(data,module_uuids):
    i = 0
    dev_module_uuids = []
    for mname in data :
        data[mname]['uuid'] = module_uuids[i]
        dev_module_uuids.append(module_uuids[i])
        i += 1
    return data, dev_module_uuids

# Print device data
def print_device_data(timestamp,data) :
    print(arrow_str + f'[timer]',kind='')
    print(arrow_str2 + f'(timestamp)<datetime>={timestamp}',kind='')
    for mname in data :
        print(arrow_str + f'[{mname}]',kind='')
        for mproperty in data[mname] :
            print(arrow_str2 + f'({mproperty})={data[mname][mproperty]}',kind='')

# Colored prints
def print(text,kind='') :
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
