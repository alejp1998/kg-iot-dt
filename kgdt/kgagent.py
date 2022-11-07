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
1. Check if the device reporting data is already present in the KG (look for the device uuid in the graph)
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
# ---------------------------------------------------------------------------

#######################################
######## KNOWLEDGE GRAPH AGENT ########
#######################################

# Knowledge Graph Agent to handle MQTT subscriptions and interaction with TypeDB
class KnowledgeGraph() :
    # Initialization
    def __init__(self, initialize=True, buffer_size=5):
        # Initialize the KG in TypeDB if required
        if initialize :
            self.initialization()
        # Attributes for stats
        self.msg_count = 0
        self.msg_proc_time = 0
        self.sdf_manager = SDFManager() # SDF files manager
        # Variables for devices management / integration
        self.devices = get_integrated_devices()
        self.buffer_size = buffer_size # number of last values to be stored of each device
        self.dev_sdf_dicts = {}
        
    # MQTT Callback Functions
    def on_log(client, userdata, level, buf):
        print("log: " + buf, kind='info')
        
    def on_connect(self, client, userdata, flags, rc):
        self.client.subscribe('#', qos=0) # subscribe to all topics
        print("\nKnowledge Graph connected - Waiting for messages...\n", kind='success')

    def on_disconnect(self, client, userdata, rc):
        print("\nKnowledge Graph disconnected.\n", kind='fail')

    def on_message(self, client, userdata, msg):
        # Decode message
        msg = loads(str(msg.payload.decode("utf-8")))
        #print(msg, kind='info')
        topic, name, uuid = msg['topic'], msg['name'], msg['uuid']

        # Treat message depending on its category
        match msg['category'] :
            case 'CONNECTED' :
                print(f'({topic}) - {name}[{uuid[0:6]}] connected to broker.', kind='success')

            case 'DISCONNECTED' :
                print(f'({topic}) - {name}[{uuid[0:6]}] disconnected from broker.', kind='fail')

            case 'DATA' :
                print(f'({topic}) - {name}[{uuid[0:6]}] data msg received.', kind='info')
                # Integrate message and time elapsed time
                tic = time.perf_counter()
                self.integration(msg)
                toc = time.perf_counter()
                print(arrow_str + f'msg processed in {toc - tic:.3f}s. \n', kind='info')
                # Data messages summary
                self.msg_count += 1
                self.msg_proc_time += toc-tic
                if self.msg_count % 50 == 0 :
                    # Print messages processing summary
                    print('-----------------------------------------------------', kind='summary')
                    print(f'MSGs SUMMARY - Count={self.msg_count}, Avg. Proc. Time={self.msg_proc_time/self.msg_count:.3f}s.', kind='summary')
                    print('-----------------------------------------------------\n', kind='summary')
                    # Save devices data to file for analysis
                    with open('devices.json', 'w') as f:
                        dump(self.devices,f,cls=DequeEncoder)
                    time.sleep(1) # sleep for 1 sec to visualize message
            
    # Start MQTT client
    def start(self):
        self.client = mqtt_client.Client('KG') # create new client instance

        self.client.on_log = self.on_log # bind callback fn
        self.client.on_connect = self.on_connect # bind callback fn
        self.client.on_disconnect = self.on_disconnect # bind callback fn
        self.client.on_message = self.on_message # bind callback fn

        self.client.connect(broker_addr, port=broker_port) # connect to the broker
        self.client.loop_forever() # run client loop for callbacks to be processed

    # Clear device modules
    def clear_device_modules(self,uuid,module_uuids):
        device_mods_cleared = {}
        disappeared_device_mods = []
        for mod_uuid in self.devices[uuid]['modules'] :
            if mod_uuid in module_uuids :
                device_mods_cleared[mod_uuid] = {}
            else :
                disappeared_device_mods.append(mod_uuid)
        
        # Remove disappeared modules from KG
        if len(disappeared_device_mods) != 0 :
            matchq = 'match '
            deleteq = 'delete '
            i = 0
            for mod_uuid in disappeared_device_mods :
                i += 1
                matchq += f'$mod{i} isa module, has uuid "{mod_uuid}";\n$includes{i} (device: $dev, module: $mod{i}) isa includes;\n'
                deleteq += f'$mod{i} isa module;\n$includes{i} isa includes;\n'
            #print(matchq + deleteq)
            delete_query(matchq + deleteq)
            print(arrow_str + f' disappeared modules cleared.', kind='success')
            
        return device_mods_cleared

    # Define device
    def define_device(self,name,uuid) :
        # Build device name on the KG
        tdb_dev_name = name.lower()
        # Build define query
        defineq = f'define {tdb_dev_name} sub device;'
        # Build insert query
        insertq = f'insert $dev isa {tdb_dev_name}, has uuid "{uuid}";'
        # Define device on KG
        define_query(defineq)
        # Insert device instance in KG
        insert_query(insertq)

    # Define modules and attributes according to SDF description
    def define_modules_attribs(self,name,uuid,data) :
        # Get device sdf dict
        dev_sdf_dict = self.dev_sdf_dicts[name]
        # Build define query
        defineq = 'define '
        # Build match-insert query
        matchq = f'match $dev isa device, has uuid "{uuid}", has timestamp 2022-01-01T00:00:00; \n'
        insertq = f'insert '

        # Iterate over modules and its attributes
        i = 0
        for mod_name, mod_sdf_dict in dev_sdf_dict['sdfObject'].items() :
            mod_uuid = data[mod_name]['uuid']

            # Continue to next module if it has been already defined
            if mod_uuid in self.devices[uuid]['modules'] :
                continue

            # Otherwise define module
            self.devices[uuid]['modules'][mod_uuid] = {'name': mod_name,'attribs': {}}

            # Insert module
            i += 1
            insertq += f'$mod{i} isa {mod_name}, has uuid "{mod_uuid}"'
            for attrib_name, attrib_sdf_dict in mod_sdf_dict['sdfProperty'].items() :
                # Continue to next iteration if the attribute is the uuid
                if attrib_name == 'uuid' :
                    continue
                
                # Define modules and assign default values
                tdbtype = types_trans[attrib_sdf_dict['type']]
                defineq += f'{attrib_name} sub attribute, value {tdbtype}; \n'
                defineq += f'{mod_name} sub module, owns {attrib_name}; \n'
                insertq += f', has {attrib_name} {defvalues[tdbtype]}'

                # Add the value to the buffer
                self.devices[uuid]['modules'][mod_uuid]['attribs'][attrib_name] = deque(maxlen=self.buffer_size)

            # Associate module with device
            insertq += f'; $includes{i} (device: $dev, module: $mod{i}) isa includes; \n'

        # Define and initialize in the knowledge graph
        if i != 0 :
            #print(defineq, kind='debug')
            define_query(defineq)
            #print(matchq + insertq, kind='debug')
            insert_query(matchq + insertq)
            # Notify of definition in console log
            print(arrow_str + 'modules/attribs defined.', kind='success')
            print_device_tree(dev_sdf_dict)

    # Update module attributes
    def update_attribs(self,name,uuid,timestamp,data) :
        # Get device sdf dict
        dev_sdf_dict = self.dev_sdf_dicts[name]
        # Match - Delete - Insert Query
        matchq = f'match $dev isa device, has uuid "{uuid}", has timestamp $attrib; '
        deleteq = 'delete $dev has $attrib; '
        insertq = f'insert $dev has timestamp {timestamp}; '

        # Iterate over modules
        i, j = 0, 0
        for mod_name, mod_dict in data.items() :
            mod_sdf_dict = dev_sdf_dict['sdfObject'][mod_name]
            mod_uuid = mod_dict['uuid']
            
            # Match module
            matchq += f'$mod{i} isa {mod_name}, has uuid "{mod_uuid}"'
            for attrib_name, attrib_value in mod_dict.items() :
                attrib_sdf_dict = mod_sdf_dict['sdfProperty'][attrib_name]
                # Continue to next iteration if the attribute is the uuid
                if attrib_name == 'uuid' : continue
                
                # Value wrapping according to type
                tdbtype = types_trans[attrib_sdf_dict['type']]
                match tdbtype :
                    case 'double' :
                        value = f'{attrib_value:.5f}'
                    case 'string' :
                        value = f'"{attrib_value}"'
                    case 'boolean' :
                        value = str(attrib_value).lower()

                # Query construction
                matchq += f', has {attrib_name} $attrib{j}'
                deleteq += f'$mod{i} has $attrib{j}; '
                insertq += f'$mod{i} has {attrib_name} {value}; '

                # Add the value to the buffer
                self.devices[uuid]['modules'][mod_uuid]['attribs'][attrib_name].append(attrib_value)

                # Insert line break
                deleteq += ' \n'
                insertq += ' \n'
                j += 1
            matchq += '; \n'
            i += 1
        
        # Update attributes in the knowledge graph
        #print(matchq + '\n' + deleteq + '\n' + insertq, kind='debug')
        update_query(matchq + '\n' + deleteq + '\n' + insertq)
        # Notify of update in console log
        print(arrow_str + 'attributes updated.', kind='success')

    # Initialize Knowledge Base
    def initialization(self) :
        with TypeDB.core_client(kb_addr) as tdb:
            # Check if the knowledge graph exists and delete it
            if tdb.databases().contains(kb_name) : tdb.databases().get(kb_name).delete()
            
            # Create it as a new knowledge base
            tdb.databases().create(kb_name)
            print(f'{kb_name} KB CREATED.', kind='success')
            
            # Open a SCHEMA session to define initial schema
            with open('typedbconfig/schema.tql') as f: query = f.read()
            define_query(query)
            print(f'{kb_name} SCHEMA DEFINED.', kind='success')
                    
            # Open a DATA session to populate kb with initial data
            with open('typedbconfig/data.tql') as f: query = f.read()
            insert_query(query)
            print(f'{kb_name} DATA POPULATED.', kind='success')

    ######## INTEGRATION ALGORITHM ########
    def integration(self,msg) :
        # Decode message components
        name, uuid, timestamp, module_uuids, data = msg['name'], msg['uuid'], msg['timestamp'], msg['module_uuids'], msg['data']
        dt_timestamp = datetime.strptime(timestamp,"%Y-%m-%dT%H:%M:%S")

        # Retrieve and build SDF dict
        if name not in self.dev_sdf_dicts :
            self.dev_sdf_dicts[name] = self.sdf_manager.build_sdf(name)['sdfThing'][name]

        # If it is the first time the device has been seen 
        if uuid not in self.devices :
            # Add device as not integrated
            self.devices[uuid] = {'name':name, 'integrated':False, 'timestamp':dt_timestamp, 'period':0, 'modules':{}}
            # Define and add device to KG
            self.define_device(name,uuid)

        # Check if all device modules have already been defined
        if set(self.devices[uuid]['modules']) != set(module_uuids) :
            # Clear device modules
            self.devices[uuid]['modules'] = self.clear_device_modules(uuid,module_uuids)
            # Add modules and attributes to the knowledge graph
            self.define_modules_attribs(name,uuid,data)

        # If the device is defined but yet to be integrated
        if not self.devices[uuid]['integrated'] :
            pass
            # Wait till we have enough samples in the buffer
            # Once we have them, perform analysis and integrate the device

        # Update device attributes
        self.update_attribs(name,uuid,timestamp,data)
        
        # Update other device data
        self.devices[uuid]['name'] = name
        self.devices[uuid]['period'] = (dt_timestamp-self.devices[uuid]['timestamp']).total_seconds()
        self.devices[uuid]['timestamp'] = dt_timestamp

######################
######## MAIN ########
######################
def main() :
    # Create Knowledge Graph instance
    kg_agent = KnowledgeGraph(initialize=True, buffer_size=20)

    # Start KG operation
    kg_agent.start()

if __name__ == "__main__":
    main()