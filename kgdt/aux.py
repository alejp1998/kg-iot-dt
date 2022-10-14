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
from typedb.client import *  # import everything from typedb.client
import paho.mqtt.client as mqtt
import networkx as nx

from typedb_ml.networkx.queries_to_networkx import build_graph_from_queries
from typedb_ml.networkx.query_graph import Query

from colorama import Fore, Back, Style
from builtins import print as prnt
import time, json
# ---------------------------------------------------------------------------

###########################
######## VARIABLES ########
###########################

# Server addresses
kb_addr = '0.0.0.0:80'
kb_name = 'iotdt'
broker_addr = '0.0.0.0' # broker_addr = 'mosquitto'
broker_port = 8883
interval = 0.1

# Root topics for publishing
prodline_root = 'productionline/'
safetyenv_root = 'safetyenvironmental/'
arrow_str = '     |------> '
arrow_str2 = '     |          |---> '

###########################
######## FUNCTIONS ########
###########################

variable_graph = nx.MultiDiGraph()
# Entities
variable_graph.add_node('tsk')
variable_graph.add_node('dev')
variable_graph.add_node('mod')
# Relations
variable_graph.add_node('nds')
variable_graph.add_edge('nds', 'tsk', type='task')
variable_graph.add_edge('nds', 'dev', type='device')
variable_graph.add_node('inc')
variable_graph.add_edge('inc', 'dev', type='device')
variable_graph.add_edge('inc', 'mod', type='module')

# Get full-graph knowledge graph
def get_full_graph() :
    queries = [Query(variable_graph,queries_dict['current_graph'])]
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.READ) as rtrans:
                concept_graph = build_graph_from_queries(queries,rtrans)

    return concept_graph

# Get device_uids in the KG
def get_known_devices() :
    query = queries_dict['device_uids']
    device_uids = match_query(query,'devuid')
    return {key: [] for key in device_uids}

# Match Query
def match_query(query,name) :
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.READ) as rtrans:
                ans_iter = rtrans.query().match(query)
                answers = [ans.get(name) for ans in ans_iter]
                result = [answer.get_value() for answer in answers]
    return result

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
def print_device_tree(data,sdf) :
    for mname in data :
        print(arrow_str + f'[{mname}]',kind='')
        for mproperty in data[mname] :
            tdbtype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['type']
            print(arrow_str2 + f'({mproperty})<{tdbtype}>',kind='')

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

defvalues = {
    'string' : '""',
    'long' : 0,
    'double' : 0.0,
    'boolean' : 'false',
    'datetime' : '2022-01-01T00:00:00'
    ''
}

queries_dict = {
    'device_uids':"""
        match 
            $dev isa device, has uid $devuid;
        get
            $devuid;
    """,
    'current_graph':"""
        match 
        $tsk isa task;
        $nds (task: $tsk, device: $dev) isa needs;
        $dev isa device;
        $inc (device: $dev, module: $mod) isa includes;
        $mod isa module;
    """
}

