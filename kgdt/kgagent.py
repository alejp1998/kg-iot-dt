#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" KG (Type DB) Agent 
In this module a Knowledge Graph class implementing a MQTT client is defined. This client is subscribed to all the topics
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
from aux import *
from typedb.client import *  # import everything from typedb.client
from typedb_ml.networkx.concept_dict_to_networkx import concept_dict_to_networkx as conceptdicttonx
import networkx as nx
# ---------------------------------------------------------------------------

# Server addresses
kb_addr = '0.0.0.0:80'
kb_name = 'iotdt'
broker_addr = '0.0.0.0' # broker_addr = 'mosquitto'
broker_port = 8883
interval = 0.1

#######################################
######## KNOWLEDGE GRAPH AGENT ########
#######################################

# MQTT Agent handling the KG
class KnowledgeGraph() :
    # Initialization
    def __init__(self,topic_root=''):
        # Root topic the MQTT agent is subscribed to
        self.topic_root = topic_root
        self.msg_count = 0
        self.msg_proc_time = 0
        # Dictionary having device_uids in the KG as keys associated with the list
        # of modules ids they include
        self.known_devices = self.initialization()

    # MQTT Callback Functions
    def on_log(client, userdata, level, buf):
        print("log: " + buf, kind='info')
        
    def on_connect(self, client, userdata, flags, rc):
        self.client.subscribe(self.topic_root+'#', qos=0) # subscribe to all topics
        print("\nKnowledge Graph connected.\n", kind='success')

    def on_disconnect(self, client, userdata, rc):
        print("\nKnowledge Graph disconnected.\n", kind='fail')

    def on_message(self, client, userdata, msg):
        # Decode message
        msg = json.loads(str(msg.payload.decode("utf-8")))
        #print(msg, kind='info')
        topic, uid = msg['topic'], msg['uid']

        # Treat message depending on its category
        if msg['category'] == 'CONNECTED' :
            print(f'({self.topic_root}{topic})[{uid[0:6]}] connected to broker.', kind='success')
        elif msg['category'] == 'DISCONNECTED' :
            print(f'({self.topic_root}{topic})[{uid[0:6]}] disconnected from broker.', kind='fail')
        elif msg['category'] == 'DATA' :
            print(f'({self.topic_root}{topic})[{uid[0:6]}] data msg received.', kind='info')
            # Integrate message and time elapsed time
            tic = time.perf_counter()
            self.integration(msg)
            toc = time.perf_counter()
            print(arrow_str + f'msg processed in {toc - tic:.3f}s. \n', kind='info')
            # Data messages summary
            self.msg_count += 1
            self.msg_proc_time += toc-tic
            if self.msg_count % 50 == 0 :
                print('-----------------------------------------------------', kind='summary')
                print(f'MSGs SUMMARY - Count={self.msg_count}, Avg. Proc. Time={self.msg_proc_time/self.msg_count:.3f}s.', kind='summary')
                print('-----------------------------------------------------\n', kind='summary')
                time.sleep(1) # sleep for 1 sec to visualize message
            
    # Start MQTT client
    def start(self):
        self.client = mqtt.Client('KB') # create new client instance

        self.client.on_log = self.on_log # bind callback fn
        self.client.on_connect = self.on_connect # bind callback fn
        self.client.on_disconnect = self.on_disconnect # bind callback fn
        self.client.on_message = self.on_message # bind callback fn

        self.client.connect(broker_addr, port=broker_port) # connect to the broker
        self.client.loop_forever() # run client loop for callbacks to be processed

    # Clear unknown device modules
    def clear_device_modules(self,uid,module_uids):
        known_device_mods_cleared = []
        unknown_device_mods = []
        for mod_uid in self.known_devices[uid] :
            if mod_uid in module_uids :
                known_device_mods_cleared.append(mod_uid)
            else :
                unknown_device_mods.append(mod_uid)
        # Remove unknown modules from KG
        if len(unknown_device_mods) != 0 :
            matchq = 'match '
            deleteq = 'delete '
            i = 0
            for mod_uid in unknown_device_mods :
                i += 1
                matchq += f'$mod{i} isa module, has uid "{mod_uid}";\n$includes{i} (device: $dev, module: $mod{i}) isa includes;\n'
                deleteq += f'$mod{i} isa module;\n$includes{i} isa includes;\n'
            #print(matchq + deleteq)
            delete_query(matchq + deleteq)
            print(arrow_str + f' unknown modules cleared.', kind='success')
            
        return known_device_mods_cleared

    # Define modules and attributes according to SDF description
    def define_modules_attribs(self,sdf,data,uid) :
        # Build define query
        defineq = 'define '
        # Build match-insert query
        matchq = f'match $dev isa device, has uid "{uid}"; \n'
        insertq = f'insert $mod0 isa timer, has uid "{uid}", has timestamp 2022-01-01T00:00:00;'
        insertq += '$includes0 (device: $dev, module: $mod0) isa includes; \n'

        # Iterate over module names
        i = 0
        for mname in sdf['sdfObject'] :
            mod_uid = data[mname]['uid']
            # If the module is not yet in the KG
            if mod_uid not in self.known_devices[uid] :
                i += 1
                # Insert module
                insertq += f'$mod{i} isa {mname}, has uid "{mod_uid}"'
                for mproperty in sdf['sdfObject'][mname]['sdfProperty'] :
                    # Continue to next iteration if the property is the uid
                    if mproperty == 'uid' :
                        continue

                    # Define modules and assign default values
                    tdbtype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['type']
                    if tdbtype != 'array' :
                        defineq += f'{mproperty} sub attribute, value {tdbtype}; \n'
                        defineq += f'{mname} sub module, owns {mproperty}; \n'
                        insertq += f', has {mproperty} {defvalues[tdbtype]}'
                    else :
                        itemstype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['items']['type']
                        arraylen = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['maxItems']
                        for n in range(arraylen) :
                            defineq += f'{mproperty}_{n+1} sub attribute, value {itemstype}; \n'
                            defineq += f'{mname} sub module, owns {mproperty}_{n+1}; \n'
                            insertq += f', has {mproperty}_{n+1} {defvalues[itemstype]}'
                
                # Associate module with device
                insertq += f'; $includes{i} (device: $dev, module: $mod{i}) isa includes; \n'
                # Add module to known devices list
                self.known_devices[uid].append(mod_uid)

        # Define and initialize in the knowledge graph
        if i != 0 :
            #print(defineq, kind='debug')
            define_query(defineq)
            #print(matchq + insertq, kind='debug')
            insert_query(matchq + insertq)

    # Update module properties
    def update_properties(self,sdf,data,uid,timestamp) :
        # Match - Delete - Insert Query
        matchq = f'match $mod0 isa timer, has uid "{uid}", has timestamp $prop0; '
        deleteq = 'delete $mod0 has $prop0; '
        insertq = f'insert $mod0 has timestamp {timestamp}; '

        # Iterate over modules
        i, j = 0, 0
        for mname in data :
            i += 1
            mod_uid = data[mname]['uid']
            matchq += f'$mod{i} isa {mname}, has uid "{mod_uid}"'
            for mproperty in data[mname] :
                # Continue to next iteration if the property is the uid
                if mproperty == 'uid' :
                    continue
                else :
                    j += 1
                
                # Value wrapping according to type
                tdbtype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['type']
                if tdbtype != 'array' :
                    if tdbtype == 'double' :
                        value = f'{data[mname][mproperty]:.5f}'
                    elif tdbtype == 'string' :
                        value = f'"{data[mname][mproperty]}"'
                    elif tdbtype == 'boolean' :
                        value = 'true' if data[mname][mproperty] else 'false'
                    else :
                        value = f'{data[mname][mproperty]}'
                    # Query construction
                    matchq += f', has {mproperty} $prop0{j}'
                    deleteq += f'$mod{i} has $prop0{j}; '
                    insertq += f'$mod{i} has {mproperty} {value}; '
                else : 
                    itemstype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['items']['type']
                    arraylen = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['maxItems']
                    for n in range(arraylen) :
                        if itemstype == 'double' :
                            value = f'{data[mname][mproperty][n]:.5f}'
                        elif itemstype == 'string' :
                            value = f'"{data[mname][mproperty][n]}"'
                        elif itemstype == 'boolean' :
                            value = 'true' if data[mname][mproperty][n] else 'false'
                        else :
                            value = f'{data[mname][mproperty][n]}'
                        # Query construction
                        matchq += f', has {mproperty}_{n+1} $prop{j}{n+1}'
                        deleteq += f'$mod{i} has $prop{j}{n+1}; '
                        insertq += f'$mod{i} has {mproperty}_{n+1} {value}; '
                # Insert line break
                deleteq += ' \n'
                insertq += ' \n'
            matchq += '; \n'
        
        # Update properties in the knowledge graph
        #print(matchq + '\n' + deleteq + '\n' + insertq, kind='debug')
        update_query(matchq + '\n' + deleteq + '\n' + insertq)

    # Initialize Knowledge Base
    def initialization(self) :
        with TypeDB.core_client(kb_addr) as tdb:
            # Check if the knowledge graph exists and delete it
            if tdb.databases().contains(kb_name) :
                tdb.databases().get(kb_name).delete()
            # Create it as a new knowledge base
            tdb.databases().create(kb_name)
            print(f'{kb_name} KB CREATED.', kind='success')
            
            # Open a SCHEMA session to define initial schema
            with open('typedbconfig/schema.tql') as f: # read schema query from file
                query = f.read()
            define_query(query)
            print(f'{kb_name} SCHEMA DEFINED.', kind='success')
                    
            # Open a DATA session to populate kb with initial data
            with open('typedbconfig/data.tql') as f: # read schema query from file
                        query = f.read()
            insert_query(query)
            print(f'{kb_name} DATA POPULATED.', kind='success')

            # Get initial device_uids in the KG
            query = queries['device_uids']
            device_uids = match_query(query,'devuid')
            return {key: [] for key in device_uids}

    ######## INTEGRATION ALGORITHM ########
    def integration(self,msg) :
        # Decode message components
        topic, sdf, uid, timestamp, module_uids, data = msg['topic'], msg['sdf'], msg['uid'], msg['timestamp'], msg['module_uids'], msg['data']
        # See if device is already in the knowledge graph
        exists = uid in self.known_devices

        # If it is already in the knowledge graph
        if exists :
            # Check if all device modules have already been defined
            if set(self.known_devices[uid]) != set(module_uids) :
                # Clear device modules
                self.known_devices[uid] = self.clear_device_modules(uid,module_uids)

                # Add modules and attributes to the knowledge graph
                self.define_modules_attribs(sdf,data,uid)
                print(arrow_str + f'modules/attribs defined.', kind='success')
                print_device_tree(data,sdf)

        # If the device is not in the knowledge graph
        else : 
            pass

        # Otherwise integrate it where it fits the most


        # Once device is already integrated, update its module attributes
        self.update_properties(sdf,data,uid,timestamp)
        print(arrow_str + f'attributes updated.', kind='success')

###########################################
######## TYPEDB AUXILIAR FUNCTIONS ########
###########################################

# Get full-graph knowledge graph
def get_full_graph() :
    with TypeDB.core_client(kb_addr) as tdb:
        with tdb.session(kb_name, SessionType.DATA) as ssn:
            with ssn.transaction(TransactionType.READ) as rtrans:
                ans_iter = rtrans.query().match(queries['current_graph'])
                answers = [ans.get('x') for ans in ans_iter]
    return answers

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

######################
######## MAIN ########
######################

# Create Knowledge Graph instance
kg_agent = KnowledgeGraph(topic_root='')

# Start KG operation
kg_agent.start()