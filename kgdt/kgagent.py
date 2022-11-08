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
        self.dev_msg_stats = {}
        self.total_msg_count = 0
        self.msg_proc_time = 0
        self.sdf_manager = SDFManager() # SDF files manager
        # Variables for devices management / integration
        self.defined_modules = []
        self.defined_attribs = []
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
                if uuid not in self.dev_msg_stats: self.dev_msg_stats[uuid] = [0,0]
                print(f'({topic}) -> {name}[{uuid[0:6]}] msg received <N={self.dev_msg_stats[uuid][0]+1}>', kind='info')
                # Integrate message and time elapsed time
                tic = time.perf_counter()
                self.integration(msg)
                toc = time.perf_counter()
                # Data messages statistics
                self.total_msg_count += 1
                self.dev_msg_stats[uuid][0] += 1
                self.msg_proc_time += toc-tic
                self.dev_msg_stats[uuid][1] += toc-tic
                print(arrow_str + f'msg processed <Tp={toc-tic:.3f}s | Avg.Tp={self.dev_msg_stats[uuid][1]/self.dev_msg_stats[uuid][0]:.3f}s>\n', kind='info')
                # Data messages summary
                if self.total_msg_count % 500 == 0 :
                    # Print messages processing summary
                    print('-----------------------------------------------------', kind='summary')
                    print(f'MSGs SUMMARY <N={self.total_msg_count} | Avg. Tp={self.msg_proc_time/self.total_msg_count:.3f}s>', kind='summary')
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
        defineq = ''
        defineq_attribs = ''
        # Build match-insert query
        matchq = f'match\n$dev isa device, has uuid "{uuid}", has timestamp 2022-01-01T00:00:00;\n\n'
        insertq = f'insert\n'

        # Iterate over modules and its attributes
        for i, (mod_name, mod_sdf_dict) in enumerate(dev_sdf_dict['sdfObject'].items()) :
            mod_uuid = data[mod_name]['uuid']

            # Continue to next module if it has been already defined
            if mod_uuid in self.devices[uuid]['modules'] :
                continue

            # Otherwise add module to devices dict and insert it
            self.devices[uuid]['modules'][mod_uuid] = {'name': mod_name,'attribs': {}}
            
            # Check if module has already been defined in KG schema
            if mod_name not in self.defined_modules : 
                defineq += f'{mod_name} sub module; '
                self.defined_modules.append(mod_name)
            
            # Insert module
            defineq += f'{mod_name} '
            insertq += f'$mod{i} isa {mod_name}, has uuid "{mod_uuid}"'
            for j, (attrib_name, attrib_sdf_dict) in enumerate(mod_sdf_dict['sdfProperty'].items()) :
                # Continue to next iteration if the attribute is the uuid
                if attrib_name == 'uuid' :
                    continue
                
                # Define modules and assign default values
                tdbtype = types_trans[attrib_sdf_dict['type']]
                if attrib_name not in self.defined_attribs : 
                    defineq_attribs += f'{attrib_name} sub attribute, value {tdbtype}; \n'
                    self.defined_attribs.append(attrib_name)
                defineq += f'{", " if j>1 else ""}owns {attrib_name}'
                insertq += f', has {attrib_name} {defvalues[tdbtype]}'

                # Add the value to the buffer
                self.devices[uuid]['modules'][mod_uuid]['attribs'][attrib_name] = deque(maxlen=self.buffer_size)

            # Associate module with device
            defineq += ';\n'
            insertq += f';\n$includes{i} (device: $dev, module: $mod{i}) isa includes; \n'

        # Define in KG schema
        tic = time.perf_counter()
        if (defineq != '') or (defineq_attribs != '') :
            #print('define\n' + defineq_attribs + defineq, kind='debug')
            define_query('define\n' + defineq_attribs + defineq)
        
        # Initialize in KG schema
        #print(matchq + insertq, kind='debug')
        insert_query(matchq + insertq)
        toc = time.perf_counter()
        # Notify of definition in console log
        print(arrow_str + f'modules/attribs defined <Tq={toc-tic:.3f}s>', kind='success')
        print_device_tree(dev_sdf_dict)

    # Update module attributes
    def update_attribs(self,name,uuid,timestamp,data) :
        # Get device sdf dict
        dev_sdf_dict = self.dev_sdf_dicts[name]
        # Match - Delete - Insert Query
        matchq = f'match\n$dev isa device, has uuid "{uuid}", has timestamp $tmstmp; '
        deleteq = 'delete\n$dev has $tmstmp;\n'
        insertq = f'insert\n$dev has timestamp {timestamp}; '

        # Iterate over modules
        for i, (mod_name, mod_dict) in enumerate(data.items()) :
            mod_sdf_dict = dev_sdf_dict['sdfObject'][mod_name]
            mod_uuid = mod_dict['uuid']
            
            # Match module
            matchq += f'$mod{i} isa {mod_name}, has uuid "{mod_uuid}"'
            deleteq += f'$mod{i} '
            insertq += f'$mod{i} '
            for j, (attrib_name, attrib_value) in enumerate(mod_dict.items()) :
                attrib_sdf_dict = mod_sdf_dict['sdfProperty'][attrib_name]
                # Continue to next iteration if the attribute is the uuid
                if attrib_name == 'uuid' : continue
                
                # Value wrapping according to type
                tdbtype = types_trans[attrib_sdf_dict['type']]
                match tdbtype :
                    case 'double' : value = f'{attrib_value:.5f}'
                    case 'string' : value = f'"{attrib_value}"'
                    case 'boolean': value = str(attrib_value).lower()

                # Query construction
                matchq += f', has {attrib_name} $attrib{i}{j}'
                deleteq += f'{", " if j!=0 else ""}has $attrib{i}{j}'
                insertq += f'{", " if j!=0 else ""}has {attrib_name} {value}'

                # Add the value to the buffer
                self.devices[uuid]['modules'][mod_uuid]['attribs'][attrib_name].append(attrib_value)

            # Insert line break
            deleteq += ';\n'
            insertq += ';\n'
            matchq += ';\n'
        
        # Update attributes in the knowledge graph
        #print(matchq + '\n' + deleteq + '\n' + insertq, kind='debug')
        tic = time.perf_counter()
        update_query(matchq + '\n' + deleteq + '\n' + insertq)
        toc = time.perf_counter()
        # Notify of update in console log
        print(arrow_str + f'attributes updated <Tq={toc-tic:.3f}s>', kind='success')

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
    kg_agent = KnowledgeGraph(initialize=True, buffer_size=50)

    # Start KG operation
    kg_agent.start()

if __name__ == "__main__":
    main()