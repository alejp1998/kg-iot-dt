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
from numpy import random
from datetime import datetime
from colorama import Fore, Back, Style
from builtins import print as prnt
import paho.mqtt.client as mqtt
import time, json, re, uuid
# ---------------------------------------------------------------------------

###########################
######## VARIABLES ########
###########################

# Root topics for publishing
prodline_root = 'productionline/'
safetyenv_root = 'safetyenvironmental/'

###########################
######## FUNCTIONS ########
###########################

# Print device tree
def print_device_tree(data,sdf) :
    for mname in data :
        print(f'     |-----> [{mname}]',kind='')
        for mproperty in data[mname] :
            tdbtype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['type']
            print(f'     |          |-----> ({mproperty})<{tdbtype}>',kind='')

# Print device data
def print_device_data(data,sdf) :
    for mname in data :
        print(f'     |-----> [{mname}]',kind='')
        for mproperty in data[mname] :
            tdbtype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['type']
            print(f'     |          |-----> ({mproperty})<{tdbtype}>={data[mname][mproperty]}',kind='')

# Colored prints
def print(text,kind='') :
    prnt(cprint_dict[kind] + text + Style.RESET_ALL)


##############################
######## DICTIONARIES ########
##############################

# Colored prints
cprint_dict = {
    'info': Fore.CYAN,
    'success' : Fore.GREEN,
    'fail': Fore.RED,
    'summary': Fore.MAGENTA,
    'debug': Fore.BLUE,
    '': '' 
}

defvalues = {
    'string' : '""',
    'long' : 0,
    'double' : 0.0,
    'boolean' : 'false',
    'datetime' : '2022-01-01T00:00:00'
    ''
}

queries = {
    'device_uids':"""
        match 
            $dev isa device, has uid $devuid;
        get
            $devuid;
    """,
    'modules_check' : """
        match
            $dev isa device, has uid $uiddev; $uiddev "{}";
            $includes (device: $dev, module: $mod) isa includes;
            $mod isa module, has uid $moduid;
        get 
            $moduid;
    """,
    'properties_check' : """
        match 
            $mod isa {}, has {} $prop_value;
        get
            $prop_value;
    """
}

