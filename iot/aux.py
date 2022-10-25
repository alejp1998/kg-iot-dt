#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" Auxiliar Variables/Functions/Imports
Module defining auxiliary elements for the IoT Devices module.
"""
# ---------------------------------------------------------------------------
# Imports
from threading import Thread
from numpy import random
from datetime import datetime, timedelta
from colorama import Fore, Back, Style
from builtins import print as prnt
import paho.mqtt.client as mqtt
import time, json, re, uuid
# ---------------------------------------------------------------------------

###########################
######## VARIABLES ########
###########################

# Root topics for publishing
prodline_root   = 'productionline/'
safetyenv_root  = 'safetyenvironmental/'
arrow_str       = '     |------> '
arrow_str2      = '     |          |---> '

###########################
######## FUNCTIONS ########
###########################

# Generate data from a normal distribution between a min and a maximum value
def normal_th(mu,sigma,th) :
    value = random.normal(mu,sigma)
    if value < th[0] :
        return th[0]
    elif value > th[1] :
        return th[1]
    else :
        return round(value,5)

# Generate random position data within a defined zone
def random_position() :
    return [0.0, 0.0, 0.0]

# Generate random orientation data within a given zone
def random_orientation() :
    return [0.0, 0.0, 0.0]

# Generate robot data dictionary
def robot_data(pos,ori,actuator_status) :
    data = {}
    for i in range(6): 
        data[f'joint{i+1}'] = {'position':pos[i], 'orientation':ori[i]}
    data['actuator'] = {'position':pos[-1], 'orientation':ori[-1], actuator_status: actuator_status}
    return data

# Generate header data
def fill_header_data(device_name,topic,uuid):
    return {
        'name' : device_name,
        'topic' : topic,
        'uuid' : uuid,
        'timestamp' : (datetime.now(tz=None) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
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
