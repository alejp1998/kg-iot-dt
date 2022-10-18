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

# Get full-graph knowledge graph
def get_full_graph() :
    entity_attribs_dict = {}
    relations = []
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.READ) as rtrans:
                # Gather entities and their owned attributes
                entity_attrib_maps = rtrans.query().match('match $ent isa entity, has $attrib;')
                # Gather relationships between entities
                relation_maps = rtrans.query().match('match $rel isa relation;')

                # Create entities dictionary storing owned attributes as keys
                for concept_map in entity_attrib_maps :
                    entity, attrib = concept_map.get('ent'), concept_map.get('attrib')
                    # Create dictionary key
                    if entity.get_iid() not in entity_attribs_dict :
                        entity_attribs_dict[entity.get_iid()] = {'entity': entity, 'attribs': []}
                    # Add attribute to dictionary
                    entity_attribs_dict[entity.get_iid()]['attribs'].append(attrib)
                    
                # Extract the role players in the relations
                for concept_map in relation_maps :
                    relation = concept_map.get('rel')
                    roleplayers = relation.as_remote(rtrans).get_players_by_role_type()
                    # Dictionary having roles as keys and roleplayers (entities or relations) as values
                    print(roleplayers)

# Get device_uids in the KG
def get_known_devices() :
    concept_maps = match_query('match $dev isa device, has uuid $devuuid;')
    device_uuids = [concept_map.get('devuuid').get_value() for concept_map in concept_maps]
    return {key: [] for key in device_uuids}

# Match Query
def match_query(query) :
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.READ) as rtrans:
                concept_maps = rtrans.query().match(query)
    return concept_maps

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
    N = G.number_of_nodes()
    V = G.number_of_edges()

    pos=nx.spring_layout(G)

    Xv=[pos[k][0] for k in G.nodes()]
    Yv=[pos[k][1] for k in G.nodes()]
    Xed,Yed=[],[]
    for edge in G.edges():
        Xed+=[pos[edge[0]][0],pos[edge[1]][0], None]
        Yed+=[pos[edge[0]][1],pos[edge[1]][1], None]

    trace3=go.Scatter(
        x=Xed,
        y=Yed,
        mode='lines',
        line=dict(
            color=colors[2],
            width=1.5
        ),
        opacity=0.5,
        hoverinfo='none'
    )
    trace4=go.Scatter(
        x=Xv,
        y=Yv,
        mode='markers',
        name='net',
        marker=dict(
            symbol='circle-dot',
            size=[G.degree[node] for node in G.nodes()],
            color=colors[0],
            line=dict(
                color='black',
                width=1
            ),
            opacity=0.9
        ),
        text=[str(node) + ' #degree: ' + str(G.degree[node]) for node in G.nodes()],
        hoverinfo='text'
    )
    layout2d = go.Layout(
        title="Current Knowledge Graph",
        showlegend=False,
        margin=dict(r=0, l=0, t=0, b=0),
        xaxis = {
            'showgrid':False,
            'visible':False
        },
        yaxis = {
            'showgrid':False,
            'showline':False,
            'zeroline':False,
            'autorange':'reversed',
            'visible':False
        }
    )

    data1=[trace3, trace4]
    graph_fig = go.Figure(data=data1, layout=layout2d)
    graph_fig.write_html("graph_fig.html")
    return graph_fig

# Build concepts dictionary from concepts map
def networkxgraph_from_concepts_list(concepts_list):
    print(concepts_list)
    
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

