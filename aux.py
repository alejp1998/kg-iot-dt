#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" Auxiliary Imports/Variables/Classes/Functions
Definition of auxiliary elements to be used by other modules.
"""
# ---------------------------------------------------------------------------
# Imports
import os
import time
import re
import uuid
from datetime import datetime, timedelta
from json import JSONEncoder, loads, dump, dumps

import pandas as pd
import numpy as np
from numpy import random
from stumpy import mass
from thefuzz import fuzz

from typing import Any, List, Dict, Tuple
from colorama import Fore, Style
from builtins import print as prnt
from joblib import Parallel, delayed
from benedict import benedict

from threading import Thread
from paho.mqtt import client as mqtt_client
from typedb.client import TypeDB, SessionType, TransactionType
# ---------------------------------------------------------------------------

###########################
######## VARIABLES ########
###########################

# Root topics for publishing
prodline_root   = 'productionline'
safetyenv_root  = 'safetyenvironmental'

# Server addresses
kb_addr     =   '0.0.0.0:80'
kb_name     =   'iotdt'
broker_addr =   '0.0.0.0' # broker_addr = 'mosquitto'
broker_port =   8883

# Other variables
arrow_str       =   '     |------> '
arrow_str2      =   '     |          |---> '
sdf_cols = ['thing','thing_desc','obj','obj_desc','prop','prop_desc','prop_type','prop_unit']

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

# TypeDB Client Class
class TypeDBClient():
    """A class for interacting with the TypeDB database.

    Attributes:
        cli (TypeDB.core_client): The TypeDB client object for interacting with the database.
        defined_modules (list): A list of device module names that have been defined in the knowledge graph.
        defined_attribs (list): A list of device attribute names that have been defined in the knowledge graph.
        devices (list): A list of integrated device names in the knowledge graph.

    Methods:
        initialization() -> None: Initializes the knowledge graph by checking if it exists, deleting it if it does, creating it as a new knowledge base, defining the initial schema, and populating it with initial data.
        match_query(query: str, varname: str) -> List[str]: Executes a MATCH query on the knowledge graph and returns the value of varname for each resulting concept map.
        insert_query(query: str) -> None: Executes an INSERT query on the knowledge graph.
        delete_query(query: str) -> None: Executes a DELETE query on the knowledge graph.
        update_query(query: str) -> None: Executes an UPDATE query on the knowledge graph.
        define_query(query: str) -> None: Executes a DEFINE query on the knowledge graph.
        define_device(dev_class: str, uuid: str) -> None: Define a new device in the knowledge graph.
        replicate_relations(integ_uuid: str, noninteg_uuid: str) -> None: Replicate the relations of an integrated device to a non-integrated device.
        disintegrate_device(uuid: str) -> None: Disintegrate a device from the knowledge graph.
        get_integrated_devices() -> Dict[str, Dict[str, Any]]: Get the UUIDs of the integrated devices in the knowledge graph.
    """

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
    def match_query(self, query: str, varname: str) -> List[str] :
        with self.cli.session(kb_name, SessionType.DATA) as data_ssn:
            with data_ssn.transaction(TransactionType.READ) as rtrans:
                concept_maps = rtrans.query().match(query)
                results = [concept_map.get(varname).get_value() for concept_map in concept_maps]
        return results

    def insert_query(self, query: str) -> None :
        with self.cli.session(kb_name, SessionType.DATA) as data_ssn:
            with data_ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().insert(query)
                wtrans.commit()

    def delete_query(self, query: str) -> None :
        with self.cli.session(kb_name, SessionType.DATA) as data_ssn:
            with data_ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().delete(query)
                wtrans.commit()

    def update_query(self, query: str) -> None :
        with self.cli.session(kb_name, SessionType.DATA) as data_ssn:
            with data_ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().update(query)
                wtrans.commit()

    def define_query(self, query: str) -> None :
        with self.cli.session(kb_name, SessionType.SCHEMA) as schema_ssn:
            with schema_ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().define(query)
                wtrans.commit()

    # Define device
    def define_device(self, dev_class: str, uuid: str) -> None :
        """Define a new device in the knowledge graph.

        Args:
            dev_class (str): The class of the device to be defined.
            uuid (str): The unique identifier for the device.
        Returns: 
            None
        """
        # Build and run define / insert queries
        self.define_query(f'define {dev_class.lower()} sub device;')
        self.insert_query(f'insert $dev isa {dev_class.lower()}, has uuid "{uuid}";')

    # Get device relations
    def replicate_relations(self, integ_uuid: str, noninteg_uuid: str) -> None :
        """Replicate the relations of an integrated device to a non-integrated device.

        Args:
            integ_uuid (str): The unique identifier of the integrated device.
            noninteg_uuid (str): The unique identifier of the non-integrated device.
        Returns: 
            None
        """
        # Match closest device and its meaningful relations
        matchq = f'match $integ_dev isa device, has uuid "{integ_uuid}";\n'
        matchq += '$nds1 (task: $tsk, device: $integ_dev) isa needs;\n'
        matchq += f'$noninteg_dev isa device, has uuid "{noninteg_uuid}";\n'
        # Insert those relations on non integrated device
        insertq = 'insert $nds2 (task: $tsk, device: $noninteg_dev) isa needs;\n'
        # Perform query
        #print(matchq + '\n' + insertq)
        self.insert_query(matchq + '\n' + insertq)

    # Disintegrate a device from the KG
    def disintegrate_device(self, uuid: str) -> None :
        """Disintegrate a device from the knowledge graph.

        Args:
            uuid (str): The unique identifier of the device to be disintegrated.
        Returns: 
            None
        """
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
    def get_integrated_devices(self) -> Dict[str, Dict[str, Any]] :
        """Get the UUIDs of the integrated devices in the knowledge graph.

        Returns:
            dict: A dictionary with the UUIDs of the integrated devices as keys and its dictionaries to be filled.
        """
        dev_uuids = self.match_query('match $dev isa device, has uuid $devuuid;','devuuid')
        return {k: {'class': '', 'integrated': True, 'period': 0, 'timestamps': [], 'modules':{}} for k in dev_uuids}
    
# SDF manager to handle devices and modules definitions
class SDFManager() :
    """SDF manager to handle devices and modules definitions.

    Attributes:
        path (str): The path to the folder containing the SDF files.
        sdf_cache (dict): A cache of previously loaded SDF files, with the file names as keys and the SDF content as values.

    Methods:
        __init__(path: str) -> None: Initialization.
        get_all_sdfs() -> Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]: Load all files in the folder.
        build_sdf(dev_class: str) -> Tuple[Dict[str, Any], pd.DataFrame]: Read SDF files completing content through references.
        build_sdf_df(sdf: Dict[str, Any]) -> pd.DataFrame: Add SDF description to a DataFrame.
    """
    # Initialization
    def __init__(self, path='sdf/'):
        self.path = path
        self.sdf_cache = {}
    
    # Load all files in folder
    def get_all_sdfs(self) -> Tuple[Dict[str, Any], Dict[str, pd.DataFrame]] :
        sdfs, sdf_dfs = {}, {}
        for filename in os.listdir(self.path) :
            dev_class = filename.split('.')[0]
            if dev_class == 'sdfData': continue
            sdfs[dev_class], sdf_dfs[dev_class] = self.build_sdf(dev_class)
        return sdfs, sdf_dfs

    # Read SDF files completing content through references
    def build_sdf(self, dev_class: str) -> Tuple[Dict[str, Any], pd.DataFrame] :
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
    def build_sdf_df(self, sdf: Dict[str, Any]) -> pd.DataFrame :
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

# Class to handle datetimes in JSON printing
class ModifiedEncoder(JSONEncoder):
    """Class to handle datetime objects when encoding to JSON.

    Overrides the default method of the JSONEncoder class to convert datetime objects to strings in the desired format before encoding.
    """

    def default(self, obj):
        """Convert datetime objects to strings before encoding.

        Args:
            obj (Any): The object to be encoded.

        Returns:
            str: The string representation of the datetime object in the desired format, or the result of the default method if obj is not a datetime object.
        """
        if isinstance(obj,datetime): return obj.strftime("%Y-%m-%dT%H:%M:%S.%f")
        return JSONEncoder.default(self, obj)

####################################################
######## CLASSES AND TIME SERIES SIMILARITY ########
####################################################

# Compute string edit distance
def calc_str_dist(non_integ_class_row_desc, row):
    """Compute the string edit distance between two strings.

    Parameters
    ----------
    non_integ_class_row_desc (str): The first string.
    row (pandas.Series): A series containing the second string in the 'prop' column and its description in the 'prop_desc' column.

    Returns
    -------
    int: The string edit distance between the two input strings.
    """
    return fuzz.ratio(non_integ_class_row_desc, row['prop'] + ' ' + row['prop_desc'])

# Compute voting results df
def calc_voting_result_df(votes: List[Dict[str, int]]) -> pd.DataFrame:
    """Compute the voting results DataFrame.

    Parameters
    ----------
    votes (List[Dict[str, int]]): A list of dictionaries containing the voting results for each row, with the candidate names as keys and their scores as values.

    Returns
    -------
    pandas.DataFrame: A DataFrame containing the candidate names in the 'candidate' column and their total scores in the 'score' column, sorted in descending order by score.
    """
    total_vote_sdf = {}
    for vote in votes:
        for candidate, score in vote.items() :
            if candidate not in total_vote_sdf :
                total_vote_sdf[candidate] = score
            else :
                total_vote_sdf[candidate] += score

    return pd.DataFrame(total_vote_sdf.items(),columns=['candidate','score']).sort_values(by='score',ascending=False)

# Compute closest classes by comparing SDF descriptions
def get_closest_classes(noninteg_class: pd.DataFrame, integ_classes: pd.DataFrame, i: int, score: int = 3,) -> Dict[str, int] :
    """Compute the closest classes by comparing SDF descriptions.

    Parameters
    ----------
    noninteg_class (pandas.DataFrame): A DataFrame containing the non-integrated class.
    integ_classes (pandas.DataFrame): A DataFrame containing the integrated classes.
    i (int): The index of the row in noninteg_class to compare.
    score (int): The maximum number of points to give to the closest class.

    Returns
    -------
    Dict[str, int]: A dictionary containing the candidate names as keys and their scores as values.
    """
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
def get_closest_devs(noninteg_dev: pd.DataFrame, integ_devs: pd.DataFrame, closest_classes: List[str], i: int, score: int = 1) -> Dict[str, int]:
    """Compute the closest devices searching for closest time series pattern.

    Parameters
    ----------
    noninteg_dev (pandas.DataFrame): A DataFrame containing the non-integrated device.
    integ_devs (pandas.DataFrame): A DataFrame containing the integrated devices.
    closest_classes (List[str]): A list of class names of the closest classes.
    i (int): The index of the row in noninteg_dev to compare.
    score (int): The number of points to give to the closest device.

    Returns
    -------
    Dict[str, int]: A dictionary containing the candidate names as keys and their scores as values.
    """
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

# Sine wave
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

# Get all paths in dict with sdfRef
def get_ref_paths(dic: dict) -> dict:
    """Get all paths in a dictionary to values with a key of 'sdfRef'.
    
    Parameters
    ----------
    dic (dict): The dictionary to search for 'sdfRef' keys.
    
    Returns
    -------
    dict: A dictionary where the keys are the paths to the 'sdfRef' keys and the values are the values of the 'sdfRef' keys.
    """
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
def build_devs_df(devices: dict) -> pd.DataFrame:
    """Build a DataFrame from a dictionary of devices.
    
    Parameters
    ----------
    devices (dict): A dictionary where the keys are device UUIDs and the values are dictionaries containing information about the devices.
    
    Returns
    -------
    pandas.DataFrame: A DataFrame with columns 'uuid', 'class', 'integ', 'period', 'mod', 'attrib', and 'v1' to 'vn', where n is the length of the value buffer for each attribute. Each row represents an attribute of a device module.
    """
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

# Print device tree
def print_device_tree(dev_dict: Dict) -> None:
    """Prints the device tree for a given device dictionary.
    
    Parameters
    ----------
    dev_dict (Dict): A device dictionary.
    
    Returns
    -------
    None
    """
    for mod_name, mod_sdf_dict in dev_dict['sdfObject'].items() :
        print(arrow_str + f'[{mod_name}]',kind='')
        for attrib_name, attrib_sdf_dict in mod_sdf_dict['sdfProperty'].items() :
            tdbtype = types_trans[attrib_sdf_dict['type']]
            print(arrow_str2 + f'({attrib_name})<{tdbtype}>',kind='')

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