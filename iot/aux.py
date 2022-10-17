#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" Auxiliar Variables/Functions/Imports
Module defining auxiliar content to be used by the main modules.
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
from pygments import highlight
from pygments.formatters.terminal256 import Terminal256Formatter
from pygments.lexers.web import JsonLexer
# ---------------------------------------------------------------------------

###########################
######## VARIABLES ########
###########################

# Root topics for publishing
prodline_root = 'productionline/'
safetyenv_root = 'safetyenvironmental/'
arrow_str = '     |------> '
arrow_str2 = '     |          |---> '

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
def robot_data(pos,ori,actuator_name,actuator_status) :
    return {
        'joint1' : {
            'position' : pos[0],
            'orientation' : ori[0]
        },
        'joint2' : {
            'position' : pos[1],
            'orientation' : ori[1]
        },
        'joint3' : {
            'position' : pos[2],
            'orientation' : ori[2]
        },
        'joint4' : {
            'position' : pos[3],
            'orientation' : ori[3]
        },
        'joint5' : {
            'position' : pos[4],
            'orientation' : ori[4]
        },
        'joint6' : {
            'position' : pos[5],
            'orientation' : ori[5]
        },
        actuator_name : {
            'status' : actuator_status,
            'position' : pos[6],
            'orientation' : ori[6]
        }
    }

# Generate header data
def fill_header_data(device_name,device_desc,topic,uuid):
    return {
        'device_name' : device_name,
        'sdf': device_desc,
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
def print_device_data(timestamp,data,sdf) :
    print(arrow_str + f'[timer]',kind='')
    print(arrow_str2 + f'(timestamp)<datetime>={timestamp}',kind='')
    for mname in data :
        print(arrow_str + f'[{mname}]',kind='')
        for mproperty in data[mname] :
            tdbtype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['type']
            print(arrow_str2 + f'({mproperty})<{tdbtype}>={data[mname][mproperty]}',kind='')

# Colored prints
def print(text,kind='') :
    prnt(cprint_dict[kind] + str(text) + Style.RESET_ALL)


##############################
######## DICTIONARIES ########
##############################

# Colored prints
cprint_dict = {
    'info': Fore.WHITE,
    'success' : Fore.GREEN,
    'fail': Fore.RED,
    'summary': Fore.MAGENTA,
    'debug': Fore.BLUE,
    '': Fore.YELLOW 
}
