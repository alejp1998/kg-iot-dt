#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" Auxiliary Variables/Functions/Imports
Module defining auxiliary elements for the KG agent module.
"""
# ---------------------------------------------------------------------------
# Imports
from typedb.client import *
import paho.mqtt.client as mqtt
from collections import deque

from colorama import Fore, Style
from builtins import print as prnt
from benedict import benedict
import os, json, time
from datetime import datetime, timedelta
from json import JSONEncoder
# ---------------------------------------------------------------------------

###########################
######## VARIABLES ########
###########################

# Server addresses
kb_addr     =   '0.0.0.0:80'
kb_name     =   'iotdt'
broker_addr =   '0.0.0.0' # broker_addr = 'mosquitto'
broker_port =   8883

# Other variables
arrow_str       =   '     |------> '
arrow_str2      =   '     |          |---> '

#########################
######## CLASSES ########
#########################

# SDF manager to handle devices and modules definitions
class SDFManager() :
    # Initialization
    def __init__(self, path='../iot/sdf/'):
        self.path = path
        self.sdf_cache = {}
    
    # Load all files in folder
    def get_all_sdfs(self):
        sdfs = {}
        for filename in os.listdir(self.path) :
            name = filename.split('.')[0]
            sdfs[name] = self.build_sdf(name)
        return sdfs

    # Read SDF files completing content through references
    def build_sdf(self,name):
        # Retrieve original sdf text
        with open(self.path+'/'+name+'.json', 'r') as sdf_file: # open sdf file as a dictionary
            inner_sdf = benedict(json.loads(sdf_file.read()))
        
        # Find dict paths to all sdf references and its associated sdfRef
        paths = get_ref_paths(inner_sdf)
        # Iterate through references replacing them by their referenced value
        for path, sdfRef in paths.items() :
            filename = sdfRef.split('/')[0]
            innerpath = '.'.join(sdfRef.split('/')[1:])
            if filename == '#': # reference to an inner sdf file path
                value = inner_sdf[innerpath]
            else : # reference to an outer sdf file path
                if filename not in self.sdf_cache: # add sdf to cache if not there
                    with open(self.path+filename, 'r') as sdf_file:
                        self.sdf_cache[filename] = benedict(json.loads(sdf_file.read()))
                value = self.sdf_cache[filename][innerpath]
            inner_sdf[path] = value # replace by referenced value
        return inner_sdf

# Class to handle deque lists
class DequeEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, deque):
            return list(obj)
        elif isinstance(obj,datetime):
            return obj.strftime("%Y-%m-%dT%H:%M:%S")
        return JSONEncoder.default(self, obj)

###########################
######## FUNCTIONS ########
###########################

# Get all paths in dict with sdfRef
def get_ref_paths(dic) :
    paths = {}
    # Recursive function
    def get_keys(some_dic, parent=None):
        if isinstance(some_dic, str):
            return
        for key, value in some_dic.items():
            if key == 'sdfRef':
                paths[f'{parent}'[5:]] = value
            if isinstance(value, dict):
                get_keys(value, parent=f'{parent}.{key}')
            else:
                pass
    get_keys(dic) # run recursive function
    return paths
    
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

# Get device_uids in the KG
def get_integrated_devices() :
    device_uuids = match_query('match $dev isa device, has uuid $devuuid;','devuuid')
    return {key: {'name': '', 'integrated': True, 'timestamp': datetime.now(tz=None) + timedelta(hours=2), 'period': 0, 'modules':{}} for key in device_uuids}

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
    'number' :      'double',
    'string' :      'string',
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

