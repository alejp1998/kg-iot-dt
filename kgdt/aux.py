#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" Auxiliary Imports/Variables/Classes/Functions
Definition of auxiliary elements for the knowledge graph agent (kgagent) module.
"""
# ---------------------------------------------------------------------------
# Imports
from typedb.client import TypeDB, SessionType, TransactionType
from paho.mqtt import client as mqtt_client

import pandas as pd
import numpy as np
from stumpy import mass
from thefuzz import fuzz

from json import JSONEncoder, loads, dump
from datetime import datetime, timedelta
from collections import deque
from benedict import benedict
import os, time

from joblib import Parallel, delayed
from colorama import Fore, Style
from builtins import print as prnt
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
sdf_cols = ['thing','thing_desc','obj','obj_desc','prop','prop_desc','prop_type','prop_unit']
dev_cols = []

#########################
######## CLASSES ########
#########################

# TypeDB Client Class
class TypeDBClient():
    # Initialization
    def __init__(self, initialize):
        # Instantiate TypeDB Client
        self.cli = TypeDB.core_client(kb_addr,4)
        # Initialize the KG in TypeDB if required
        if initialize : self.initialization()
        # Variables for devices management / integration
        self.defined_modules = []
        self.defined_attribs = []
        self.devices = self.get_integrated_devices()

    # TypeDB DB Initialization
    def initialization(self) :
        # Check if the knowledge graph exists and delete it
        if self.cli.databases().contains(kb_name) : self.cli.databases().get(kb_name).delete()
        
        # Create it as a new knowledge base
        self.cli.databases().create(kb_name)
        print(f'{kb_name} KB CREATED.', kind='success')
        
        # Open a SCHEMA session to define initial schema
        with open('typedbconfig/schema.tql') as f: self.define_query(f.read())
        print(f'{kb_name} SCHEMA DEFINED.', kind='success')
                
        # Open a DATA session to populate kb with initial data
        with open('typedbconfig/data.tql') as f: self.insert_query(f.read())
        print(f'{kb_name} DATA POPULATED.', kind='success')
    
    # TypeDB Queries
    def match_query(self,query,varname) :
        with self.cli.session(kb_name, SessionType.DATA) as data_ssn:
            with data_ssn.transaction(TransactionType.READ) as rtrans:
                concept_maps = rtrans.query().match(query)
                results = [concept_map.get(varname).get_value() for concept_map in concept_maps]
        return results

    def insert_query(self,query) :
        with self.cli.session(kb_name, SessionType.DATA) as data_ssn:
            with data_ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().insert(query)
                wtrans.commit()

    def delete_query(self,query) :
        with self.cli.session(kb_name, SessionType.DATA) as data_ssn:
            with data_ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().delete(query)
                wtrans.commit()

    def update_query(self,query) :
        with self.cli.session(kb_name, SessionType.DATA) as data_ssn:
            with data_ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().update(query)
                wtrans.commit()

    def define_query(self,query) :
        with self.cli.session(kb_name, SessionType.SCHEMA) as schema_ssn:
            with schema_ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().define(query)
                wtrans.commit()

    # Define device
    def define_device(self,name,uuid) :
        # Build and run define / insert queries
        self.define_query(f'define {name.lower()} sub device;')
        self.insert_query(f'insert $dev isa {name.lower()}, has uuid "{uuid}";')

    # Get device UUIDs present in the KG
    def get_integrated_devices(self) :
        dev_uuids = self.match_query('match $dev isa device, has uuid $devuuid;','devuuid')
        return {k: {'name': '', 'integrated': True, 'timestamps': [], 'period': 0, 'modules':{}} for k in dev_uuids}
    
# SDF manager to handle devices and modules definitions
class SDFManager() :
    # Initialization
    def __init__(self, path='../iot/sdf/'):
        self.path = path
        self.sdf_cache = {}
    
    # Load all files in folder
    def get_all_sdfs(self):
        sdfs, sdf_dfs = {}, {}
        for filename in os.listdir(self.path) :
            name = filename.split('.')[0]
            if name == 'Auxiliary': continue
            sdfs[name], sdf_dfs[name] = self.build_sdf(name)
        return sdfs, sdf_dfs

    # Read SDF files completing content through references
    def build_sdf(self,name):
        # Retrieve original sdf text
        with open(self.path+'/'+name+'.json', 'r') as sdf_file: inner_sdf = benedict(loads(sdf_file.read()))
        
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
                        self.sdf_cache[filename] = benedict(loads(sdf_file.read()))
                value = self.sdf_cache[filename][innerpath]
            inner_sdf[path] = value # replace by referenced value
        
        # Build sdf DataFrame
        inner_sdf_df = self.build_sdf_df(inner_sdf.copy())
        return inner_sdf, inner_sdf_df
    
    # Add sdf description to DataFrame
    def build_sdf_df(self, sdf) :
        rows = []
        for sdfThing, thing_dic in sdf['sdfThing'].items():
            thing_desc = thing_dic['description']
            for sdfObject, object_dic in thing_dic['sdfObject'].items():
                object_desc = object_dic['description']
                for sdfProperty, prop_dic in object_dic['sdfProperty'].items():
                    if sdfProperty == 'uuid': continue
                    prop_desc = prop_dic['description']
                    prop_type = prop_dic['type']
                    prop_unit = prop_dic['unit'] if 'unit' in prop_dic else None
                    rows.append((sdfThing,thing_desc,sdfObject,object_desc,sdfProperty,prop_desc,prop_type,prop_unit))

        return pd.DataFrame(columns=sdf_cols,data=rows)

# Class to handle deque lists and datetimes
class ModifiedEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, deque): return list(obj)
        elif isinstance(obj,datetime): return obj.strftime("%Y-%m-%dT%H:%M:%S.%f")
        return JSONEncoder.default(self, obj)

###########################
######## FUNCTIONS ########
###########################

# Get all paths in dict with sdfRef
def get_ref_paths(dic) :
    paths = {}
    # Recursive function
    def get_keys(some_dic, parent=None):
        if isinstance(some_dic, str): return
        for key, value in some_dic.items():
            if key == 'sdfRef':
                paths[f'{parent}'[5:]] = value
            if isinstance(value, dict):
                get_keys(value, parent=f'{parent}.{key}')
            else: pass
    get_keys(dic) # run recursive function
    return paths

# Build devices DataFrame
def build_devs_df(devices) :
    rows = []
    for dev_uuid, dev in devices.items() :
        # Dev row initialization
        row = { 'uuid': dev_uuid,           'dev' : dev['name'],
                'integ': dev['integrated'], 'period': dev['period']}
        # Create a row for each module attribute with a column for each value in the buffer
        for mod_uuid, mod in dev['modules'].items() :
            row['mod'] = mod['name']
            for prop_name, values in mod['attribs'].items() :
                row['attrib'] = prop_name
                for i, val in enumerate(values) : row[f'v{i+1}'] = val
                rows.append(row.copy())

    return pd.DataFrame(rows)

# Print device tree
def print_device_tree(dev_dict) :
    for mod_name, mod_sdf_dict in dev_dict['sdfObject'].items() :
        print(arrow_str + f'[{mod_name}]',kind='')
        for attrib_name, attrib_sdf_dict in mod_sdf_dict['sdfProperty'].items() :
            tdbtype = types_trans[attrib_sdf_dict['type']]
            print(arrow_str2 + f'({attrib_name})<{tdbtype}>',kind='')
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

