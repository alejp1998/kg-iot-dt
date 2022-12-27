#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" Auxiliary Imports/Variables/Classes/Functions
Definition of auxiliary elements for the Knowledge Graph Agent (kgagent) module.
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

    # Get device relations
    def replicate_relations(self,integ_uuid,noninteg_uuid) :
        # Match closest device and its meaningful relations
        matchq = f'match $integ_dev isa device, has uuid "{integ_uuid}";\n'
        matchq += '$nds1 (task: $tsk, device: $integ_dev) isa needs;\n'
        matchq += '$flt1 (service: $srv, device: $integ_dev) isa fulfillment;\n'
        matchq += f'$noninteg_dev isa device, has uuid "{noninteg_uuid}";\n'
        # Insert those relations on non integrated device
        insertq = 'insert $nds2 (task: $tsk, device: $noninteg_dev) isa needs;\n'
        insertq += '$flt2 (service: $srv, device: $noninteg_dev) isa fulfillment;\n'
        # Perform query
        #print(matchq + '\n' + insertq)
        self.insert_query(matchq + '\n' + insertq)

    # Disintegrate a device from the KG
    def disintegrate_device(self,uuid) :
        # Match and delete the device modules and its relations / attribute ownerships
        matchq = 'match '
        deleteq = 'delete '
        for i, mod_uuid in enumerate(self.devices[uuid]['modules']) :
            matchq += f'$mod{i} isa module, has uuid "{mod_uuid}";\n'
            deleteq += f'$mod{i} isa module;\n'
        #print(matchq + '\n' + deleteq)
        self.delete_query(matchq + '\n' + deleteq)

        # Match and delete a device and its relations / attribute ownerships
        matchq = f'match $dev isa device, has uuid "{uuid}";\n'
        deleteq = f'delete $dev isa device;\n'
        #print(matchq + '\n' + deleteq)
        self.delete_query(matchq + '\n' + deleteq)
        
    # Get device UUIDs present in the KG
    def get_integrated_devices(self) :
        dev_uuids = self.match_query('match $dev isa device, has uuid $devuuid;','devuuid')
        return {k: {'class': '', 'integrated': True, 'period': 0, 'timestamps': [], 'modules':{}} for k in dev_uuids}
    
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
            dev_class = filename.split('.')[0]
            if dev_class == 'sdfData': continue
            sdfs[dev_class], sdf_dfs[dev_class] = self.build_sdf(dev_class)
        return sdfs, sdf_dfs

    # Read SDF files completing content through references
    def build_sdf(self,dev_class):
        # Retrieve original sdf text
        with open(self.path+'/'+dev_class+'.sdf.json', 'r') as sdf_file: inner_sdf = benedict(loads(sdf_file.read()))
        
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
                    with open(self.path+filename+'.sdf.json', 'r') as sdf_file:
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

# Class to handle datetimes
class ModifiedEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj,datetime): return obj.strftime("%Y-%m-%dT%H:%M:%S.%f")
        return JSONEncoder.default(self, obj)

####################################################
######## CLASSES AND TIME SERIES SIMILARITY ########
####################################################
# Compute string edit distance
def calc_str_dist(non_integ_class_row_desc, row):
    return fuzz.ratio(non_integ_class_row_desc, row['prop'] + ' ' + row['prop_desc'])

# Compute voting results df
def calc_voting_result_df(votes) :
    total_vote_sdf = {}
    for vote in votes:
        for candidate, score in vote.items() :
            if candidate not in total_vote_sdf :
                total_vote_sdf[candidate] = score
            else :
                total_vote_sdf[candidate] += score

    return pd.DataFrame(total_vote_sdf.items(),columns=['candidate','score']).sort_values(by='score',ascending=False)

# Compute closest classes by comparing SDF descriptions
def get_closest_classes(noninteg_class,integ_classes,i,score=3) :
    # Create local copies and compare only rows with same data type
    noninteg_class_row = noninteg_class.iloc[i].copy()
    integ_classes = integ_classes[integ_classes.prop_type==noninteg_class_row['prop_type']].copy()

    # Build non integrated row text description
    non_integ_class_row_desc = noninteg_class_row['prop'] + ' ' + noninteg_class_row['prop_desc']

    # Calc string distances to each other integrated row text description
    integ_classes['str_dist'] = integ_classes.apply(lambda x: calc_str_dist(non_integ_class_row_desc,x), axis=1)
    closest_things = integ_classes[['thing','obj','prop','str_dist']].sort_values(by='str_dist',ascending=False)

    # Give points based on closeness
    vote = {}
    for row in closest_things.itertuples() :
        if score == 0 : break
        if row.thing in vote : continue
        vote[row.thing] = score
        score -= 1

    return vote

# Compute closest devices searching for closest time series pattern
def get_closest_devs(noninteg_dev,integ_devs,closest_classes,i,score=1) :
    # Create local copies
    noninteg_dev_row = noninteg_dev.iloc[i].copy()
    closest_classes.append(noninteg_dev_row['class'])
    integ_devs = integ_devs[integ_devs['class'].isin(closest_classes)].copy()
    val_cols = integ_devs.columns[6:]

    # Compute device with closest time series pattern
    min_dist_profile = np.Inf
    query_series = noninteg_dev_row[val_cols[:20]].astype(float).to_numpy()
    for i, integ_dev_row in integ_devs.iterrows() :
        inspected_series = integ_dev_row[val_cols].dropna().astype(float).to_numpy()
        if inspected_series.size < query_series.size : continue
        # MASS Distance Profile
        dist_profile = mass(query_series, inspected_series, normalize=False)
        if np.min(dist_profile) < min_dist_profile :
            min_dist_profile = np.min(dist_profile)
            candidate = integ_dev_row['class'] + '/' + integ_dev_row.uuid
    
    # The winner is the one with lower distance
    return {candidate: score}
    
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
        row = { 'uuid': dev_uuid,           'class' : dev['class'],
                'integ': dev['integrated'], 'period': dev['period']}
        # Create a row for each module attribute with a column for each value in the buffer
        for mod_name, attribs_dic in dev['modules'].items() :
            row['mod'] = mod_name
            for attrib_name, values in attribs_dic.items() :
                row['attrib'] = attrib_name
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

