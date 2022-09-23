#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" KB (Type DB) Client 
In this module a Knowledge Base class implementing a MQTT client is defined. This client is subscribed to all the topics
in the MQTT network in order to listen to all the data being reported by the IoT devices. Once it receives a message from the 
MQTT broker, it processes it and modifies the content in the Knowledge Graph according to it.

The integration of the message content into the Knowledge Graph is done by the integration algorithm, through the following steps: 
1. Check if the device reporting data is already present in the KG (look for the device uid in the graph)
2. In case it is not, find the branch or location in the graph structure where this device would fit best. Additionally, check the 
SDF description of the device and, in case a module / attribute is not defined in the schema, define it. 
3. Once the device is already located in the graph structure, update its module attributes according to the data specified in the message.

Hence, the objective of this module is to interact with the KG according to what it listens to in the MQTT network, with the purpose of making 
the information in the KG as accurate as possible with respect to the real structure, being able to handle difficult situations such as new devices 
or ambiguity/existence of similar devices with different characteristics.
"""
# ---------------------------------------------------------------------------
# Imports 
from threading import Thread
from typedb.client import * # import everything from typedb.client
from auxdicts import queries, transtypes, defvalues
import paho.mqtt.client as mqtt
import time
import json
# ---------------------------------------------------------------------------


# Root topics for publishing
prodline_root = 'productionline/'
safetyenv_root = 'safetyenvironmental/'

# Server addresses
kb_addr = '0.0.0.0:80'
kb_name = 'iotdt'
broker_addr = '0.0.0.0' # broker_addr = 'mosquitto'
broker_port = 8883
interval = 0.1

#######################################
######## KNOWLEDGE BASE CLIENT ########
#######################################

# MQTT Client handling database
class KnowledgeBase() :
    # Initialization
    def __init__(self,topic_root=''):
        Thread.__init__(self)
        self.topic_root = topic_root

    # MQTT Callback Functions
    def on_log(client, userdata, level, buf):
        print("log: " + buf)
        
    def on_connect(self, client, userdata, flags, rc):
        self.client.subscribe(self.topic_root+'#', qos=0) # subscribe to all topics
        print("Knowledge Base connected.")

    def on_disconnect(self, client, userdata, rc):
        print("Knowledge Base disconnected.")

    def on_message(self, client, userdata, msg):
        msg = json.loads(str(msg.payload.decode("utf-8")))
        print("({}{}) msg received -> {}.".format(self.topic_root,msg['topic'],'{...}'))
        kb_integration(msg)
        print('({}{}) msg processed.'.format(self.topic_root,msg['topic']))
            
    # Thread execution
    def start(self):
        self.client = mqtt.Client('KB') # create new client instance

        self.client.on_log = self.on_log # bind callback fn
        self.client.on_connect = self.on_connect # bind callback fn
        self.client.on_disconnect = self.on_disconnect # bind callback fn
        self.client.on_message = self.on_message # bind callback fn

        self.client.connect(broker_addr, port=broker_port) # connect to the broker
        self.client.loop_forever() # run client loop for callbacks to be processed

###########################################
######## INTEGRATION ALGORITHM ############
###########################################

def kb_integration(msg) :
    # Decode the message
    sdf = msg['sdf']
    uid = msg['uid']
    data = msg['data']

    # See if device is already in the knowledge graph
    answers = match_query(queries['uid_check'].format(uid),'dev')
    exists = len(answers) != 0

    # If it is already in the knowledge graph
    if exists :
        # Check if its modules have been also included
        answers = match_query(queries['modules_check'].format(uid),'mod')
        exists = len(answers) != 0
        if not exists : 
            # Add modules and attributes to the knowledge graph
            add_modules_attribs(sdf,uid)

    # If the device is not in the knowledge graph
    else : 
        pass

    # Otherwise integrate it where it fits the most
    

    # Once device is already integrated, update its module attributes
    update_properties(sdf,data,uid)

###########################################
######## TYPEDB AUXILIAR FUNCTIONS ########
###########################################

# Initialize Knowledge Base
def typedb_initialization() :
    with TypeDB.core_client(kb_addr) as tdb:
        # Check if the knowledge base exists and delete it
        if tdb.databases().contains(kb_name) :
            tdb.databases().get(kb_name).delete()
        # Create it as a new knowledge base
        tdb.databases().create(kb_name)
        print('{} KB CREATED.'.format(kb_name))
        
        # Open a SCHEMA session to define initial schema
        with tdb.session(kb_name, SessionType.SCHEMA) as ssn:
            with ssn.transaction(TransactionType.WRITE) as wtrans: # creating a write transaction
                with open('typedbconfig/schema.tql') as f: # read schema query from file
                    query = f.read()
                wtrans.query().define(query) # execute query
                wtrans.commit() # write transaction must always be committed (closed)
                print('{} SCHEMA DEFINED.'.format(kb_name))

        # Open a DATA session to populate kb with initial data
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.WRITE) as wtrans: # creating a write transaction
                with open('typedbconfig/data.tql') as f: # read schema query from file
                    query = f.read()
                wtrans.query().insert(query) # execute query
                wtrans.commit() # write transaction must always be committed (closed)
                print('{} DATA POPULATED.'.format(kb_name))

# Add modules and attributes according to SDF description
def add_modules_attribs(sdf,uid) :
    mnames = list(sdf['sdfObject'].keys())
    # Define query
    defineq = 'define '
    for mname in mnames :
        # Get list of properties
        mproperties = list(sdf['sdfObject'][mname]['sdfProperty'].keys())
        for mproperty in mproperties[1:] :
            # Get list of non-yet-defined attribs
            try : 
                answers = match_query(queries['properties_check'].format(mname,mproperty),'prop_value')
            except :
                tdbtype = transtypes[sdf['sdfObject'][mname]['sdfProperty'][mproperty]['type']] if mproperty != 'timestamp' else 'datetime'
                if tdbtype != 'array' :
                    defineq += f'{mproperty} sub attribute, value {tdbtype}; \n'
                    defineq += f'{mname} sub module, owns {mproperty}; \n'
                else :
                    itemstype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['items']['type']
                    arraylen = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['maxItems']
                    for n in range(arraylen) :
                        defineq += f'{mproperty}_{n+1} sub attribute, value {transtypes[itemstype]}; \n'
                        defineq += f'{mname} sub module, owns {mproperty}_{n+1}; \n'

    # Define in the knowledge graph
    if defineq != 'define ' :
        define_query(defineq)
        print(defineq)
    
    # Create module instances
    matchq = f'match $dev isa device, has uid "{uid}"; \n'
    insertq = 'insert '
    i = 0
    for mname in mnames :
        i += 1
        insertq += f'$mod{i} isa {mname}'
        mproperties = list(sdf['sdfObject'][mname]['sdfProperty'].keys())
        for mproperty in mproperties :
            tdbtype = transtypes[sdf['sdfObject'][mname]['sdfProperty'][mproperty]['type']] if mproperty != 'timestamp' else 'datetime'
            if tdbtype != 'array' :
                insertq += f', has {mproperty} {defvalues[tdbtype]}'
            else : 
                itemstype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['items']['type']
                arraylen = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['maxItems']
                for n in range(arraylen) :
                    insertq += f', has {mproperty}_{n+1} {defvalues[transtypes[itemstype]]}'
        insertq += f'; $includes{i} (device: $dev, module: $mod{i}) isa includes; \n'
    # Insert in the knowledge graph
    query = matchq + insertq
    #print(query)
    insert_query(query)
    

# Update module properties
def update_properties(sdf,data,uid) :
    mnames = list(data.keys())
    # Match - Delete - Insert Query
    matchq = f'match $dev isa device, has uid "{uid}"; \n'
    deleteq = 'delete '
    insertq = 'insert '
    i, j = 0, 0
    for mname in mnames :
        i += 1
        mod_uid = data[mname]['uid']
        mproperties = list(data[mname].keys())
        matchq += f'$includes{i} (device: $dev, module: $mod{i}) isa includes; \n$mod{i} isa {mname}, has uid "{mod_uid}"'
        for mproperty in mproperties[1:] :
            j += 1
            # Value wrapping according to type
            tdbtype = transtypes[sdf['sdfObject'][mname]['sdfProperty'][mproperty]['type']] if mproperty != 'timestamp' else 'datetime'
            if tdbtype != 'array' :
                if tdbtype == 'boolean' :
                    value = 'true' if data[mname][mproperty] else 'false'
                elif tdbtype == 'string' :
                    value = f'"{data[mname][mproperty]}"'
                else :
                    value = f'{data[mname][mproperty]}'
                # Query construction
                matchq += f', has {mproperty} $prop0{j}'
                deleteq += f'$mod{i} has $prop0{j}; \n'
                insertq += f'$mod{i} has {mproperty} {value}; \n'
            else : 
                itemstype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['items']['type']
                arraylen = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['maxItems']
                for n in range(arraylen) :
                    if itemstype == 'boolean' :
                        value = 'true' if data[mname][mproperty][n] else 'false'
                    elif itemstype == 'string' :
                        value = f'"{data[mname][mproperty][n]}"'
                    else :
                        value = f'{data[mname][mproperty][n]}'
                    # Query construction
                    matchq += f', has {mproperty}_{n+1} $prop{j}{n+1}'
                    deleteq += f'$mod{i} has $prop{j}{n+1}; \n'
                    insertq += f'$mod{i} has {mproperty}_{n+1} {value}; \n'
        matchq += '; \n'
    # Build Complete Query
    query = matchq + deleteq + insertq
    print(query)
    # Update properties in the knowledge graph
    update_query(query)


# Match Query
def match_query(query,name) :
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.READ) as rtrans:
                ans_iter = rtrans.query().match(query)
                answers = [ans.get(name) for ans in ans_iter]
    return answers

# Insert Query
def insert_query(query) :
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.WRITE) as wtrans:
                wtrans.query().insert(query)
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

######################
######## MAIN ########
######################

# Initialize TypeDB
typedb_initialization()

# Start Knowledge Base Controller Thread
KnowledgeBase(topic_root='').start()