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
from email.mime import base
from weakref import ref
from typedb.client import *  # import everything from typedb.client
import paho.mqtt.client as mqtt
import networkx as nx
from collections import deque

from typedb_ml.typedb.thing import build_thing

import plotly.graph_objects as go

from colorama import Fore, Back, Style
from builtins import print as prnt
import os
import time, json, re
# ---------------------------------------------------------------------------

###########################
######## VARIABLES ########
###########################

# Server addresses
kb_addr     =   '0.0.0.0:80'
kb_name     =   'iotdt'
broker_addr =   '0.0.0.0' # broker_addr = 'mosquitto'
broker_port =   8883
interval    =   0.1

# Root topics for publishing
prodline_root   =   'productionline/'
safetyenv_root  =   'safetyenvironmental/'
arrow_str       =   '     |------> '
arrow_str2      =   '     |          |---> '

# Available colors
colors = [
    '#1f77b4',  # muted blue
    '#ff7f0e',  # safety orange
    '#2ca02c',  # cooked asparagus green
    '#d62728',  # brick red
    '#9467bd',  # muted purple
    '#8c564b',  # chestnut brown
    '#e377c2',  # raspberry yogurt pink
    '#7f7f7f',  # middle gray
    '#bcbd22',  # curry yellow-green
    '#17becf'   # blue-teal
]

#########################
######## CLASSES ########
#########################

# SDF manager to handle devices and modules definitions
class SDFManager() :
    # Initialization
    def __init__(self, path='../iot/sdf/'):
        self.path = path
    
    # Read SDF files completing content through references
    def retrieve_sdf(self,name):
        # Retrieve original sdf text
        with open(self.path+'/'+name+'.json', 'r') as sdf_file: # open sdf file as a dictionary
            sdf_text = sdf_file.read()
            init_sdf = json.loads(sdf_text)
        # Iterate through appearances of the word sdfRef and replace them by their value
        while 'sdfRef' in sdf_text:
            match_result = re.search('\{"sdfRef": ".*"\}',sdf_text).group()
            sdfRef = match_result.split(': ')[1][1:-2]
            value = json.dumps(self.retrieve_ref(init_sdf,sdfRef))
            sdf_text = sdf_text.replace(match_result,value)

        sdf = json.loads(sdf_text)
        return sdf

    # Handle SDF references
    def retrieve_ref(self,sdf,sdfRef):
        print(sdfRef)
        split_ref = sdfRef.split('/')
        if split_ref[0] == '#': # reference to an inner sdf file path
            return nested_get(sdf,split_ref[1:])
        else: # reference to an outer sdf file path
            with open(self.path+'/'+split_ref[0], 'r') as sdf_file: # open sdf file as a dictionary
                sdf = json.loads(sdf_file.read())
            return nested_get(sdf,split_ref[1:])

###########################
######## FUNCTIONS ########
###########################

# Get device_uids in the KG
def get_known_devices() :
    device_uuids = match_query('match $dev isa device, has uuid $devuuid;','devuuid')
    return {key: [] for key in device_uuids}

# Match Query
def match_query(query,varname) :
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.READ) as rtrans:
                concept_maps = rtrans.query().match(query)
                results = [concept_map.get(varname).get_value() for concept_map in concept_maps]
    return results

# Insert Query
def insert_query(query) :
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().insert(query)
                wtrans.commit()

# Delete Query
def delete_query(query) :
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().delete(query)
                wtrans.commit()

# Update Query
def update_query(query) :
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().update(query)
                wtrans.commit()

# Define Query
def define_query(query) :
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.SCHEMA) as ssn:
            with ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().define(query)
                wtrans.commit()

# Print device tree
def print_device_tree(name,sdf,data) :
    for mname in data :
        print(arrow_str + f'[{mname}]',kind='')
        for mproperty in data[mname] :
            jsontype = sdf['sdfThing'][name]['sdfObject'][mname]['sdfProperty'][mproperty]['type']
            tdbtype = types_trans[jsontype] if jsontype!="array" else "array"
            print(arrow_str2 + f'({mproperty})<{tdbtype}>',kind='')

# Colored prints
def print(text,kind='') :
    prnt(cprint_dict[kind] + str(text) + Style.RESET_ALL)

# Access nested dictionary through list of keys
def nested_get(dic, keys):  
    print(keys)
    for key in keys:
        dic = dic[key]
    return dic

    
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

# Types translation between SDF (JSON data types) and TypeDB
types_trans = {
    'string' :      'string',
    'number' :      'double',
    'boolean' :     'boolean'
}

# Default values for each type
defvalues = {
    'string' :      '""',
    'long' :        0,
    'double' :      0.0,
    'boolean' :     'false',
    'datetime' :    '2022-01-01T00:00:00'
}

