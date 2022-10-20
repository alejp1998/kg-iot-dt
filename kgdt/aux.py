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
from collections import deque

from typedb_ml.typedb.thing import build_thing

import plotly.graph_objects as go

from colorama import Fore, Back, Style
from builtins import print as prnt
import time, json
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
def print_device_tree(data,sdf) :
    for mname in data :
        print(arrow_str + f'[{mname}]',kind='')
        for mproperty in data[mname] :
            tdbtype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['type']
            print(arrow_str2 + f'({mproperty})<{tdbtype}>',kind='')

# Colored prints
def print(text,kind='') :
    prnt(cprint_dict[kind] + str(text) + Style.RESET_ALL)

# Generate interactive graph visualization
def gen_graph_vis(G):
    # Generate nodes position according to spring layout
    pos=nx.spring_layout(G) 
    Xv=[pos[k][0] for k in G.nodes()]
    Yv=[pos[k][1] for k in G.nodes()]

    # Gather edges info
    Xed,Yed,EdgeTypes,EdgeColors=[],[],[],[]
    for edge in G.edges(data=True):
        Xed+=[pos[edge[0]][0],pos[edge[1]][0], None]
        Yed+=[pos[edge[0]][1],pos[edge[1]][1], None]
        EdgeTypes+=edge[2]['type']

    # Gather nodes info
    NodeSizes, NodeTexts = [],[]
    for node in G.nodes() :
        NodeSizes.append(G.degree[node])
        NodeTexts.append(str(node) + ' #degree: ' + str(G.degree[node]))

    edges_trace=go.Scatter(x=Xed, y=Yed,
        opacity=0.5,
        text=EdgeTypes,
        hoverinfo='text',
        mode='lines',
        line=dict(
            width=1,
            color=colors[2]
        )
    )

    nodes_traze=go.Scatter(name='net',x=Xv,y=Yv,
        text=NodeTexts,
        hoverinfo='text',
        mode='markers',
        marker=dict(
            symbol='circle-dot',
            size=NodeSizes,
            color=colors[0],
            line=dict(
                color='black',
                width=1
            ),
            opacity=0.9
        )
    )
    layout2d = go.Layout(title="Current Knowledge Graph",
        showlegend=False,
        margin=dict(r=0, l=0, t=0, b=0),
        xaxis = {'showgrid':False,'visible':False},
        yaxis = {'showgrid':False,'showline':False,'zeroline':False,'autorange':'reversed','visible':False}
    )

    data=[edges_trace, nodes_traze]
    graph_fig = go.Figure(data=data, layout=layout2d)
    graph_fig.write_html("graph_fig.html")
    return graph_fig
    
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

defvalues = {
    'string' :      '""',
    'long' :        0,
    'double' :      0.0,
    'boolean' :     'false',
    'datetime' :    '2022-01-01T00:00:00'
}

