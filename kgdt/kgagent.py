#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" Knowledge Graph Agent
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
class KGAgent(TypeDBClient) :
    # Initialization
    def __init__(self, initialize=True, buffer_th=60):
        TypeDBClient.__init__(self,initialize)
        # Attributes for stats
        self.dev_msg_stats = {}
        self.total_msg_count = 0
        self.msg_proc_time = 0
        self.sdf_manager = SDFManager()
        # Variables for devices management / integration
        self.buffer_th = buffer_th # values within buffer_th last minutes will be stored for each device
        self.sdf_dicts = {}
        self.sdfs_df = pd.DataFrame(columns=sdf_cols)
        
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
                self.consistency_handling(msg)
                toc = time.perf_counter()
                # Data messages statistics
                self.total_msg_count += 1
                self.dev_msg_stats[uuid][0] += 1
                self.msg_proc_time += toc-tic
                self.dev_msg_stats[uuid][1] += toc-tic
                print(arrow_str + f'msg processed <Tp={(toc-tic)*1000:.0f}ms | Avg.Tp={(self.dev_msg_stats[uuid][1]/self.dev_msg_stats[uuid][0])*1000:.0f}ms>\n', kind='info')
                # Data messages summary
                if self.total_msg_count % 500 == 0 :
                    # Print messages processing summary
                    print('-----------------------------------------------------', kind='summary')
                    print(f'MSGs SUMMARY <N={self.total_msg_count} | Avg. Tp={(self.msg_proc_time/self.total_msg_count)*1000:.0f}ms>', kind='summary')
                    print('-----------------------------------------------------\n', kind='summary')
                    # Save devices data to file for analysis
                    with open('devices.json', 'w') as f:
                        dump(self.devices,f,cls=ModifiedEncoder)
            
    # Start MQTT client
    def start(self):
        self.client = mqtt_client.Client('KG') # create new client instance

        self.client.on_log = self.on_log # bind callback fn
        self.client.on_connect = self.on_connect # bind callback fn
        self.client.on_disconnect = self.on_disconnect # bind callback fn
        self.client.on_message = self.on_message # bind callback fn

        self.client.connect(broker_addr, port=broker_port) # connect to the broker
        self.client.loop_forever() # run client loop for callbacks to be processed

    # Define modules and attributes according to SDF description
    def define_modules_attribs(self,name,uuid,timestamp,data) :
        # Build datetime timestamp
        dt_timestamp = datetime.strptime(timestamp,"%Y-%m-%dT%H:%M:%S.%f")
        self.devices[uuid]['timestamps'].append(dt_timestamp)
        # Get device sdf dict
        sdf_dict = self.sdf_dicts[name]
        # Build define query
        defineq = ''
        defineq_attribs = ''
        # Build match-insert query
        matchq = f'match\n$dev isa device, has uuid "{uuid}", has timestamp {timestamp[:-7]};\n\n'
        insertq = f'insert\n'

        # Iterate over modules and its attributes
        for i, (mod_name, mod_sdf_dict) in enumerate(sdf_dict['sdfObject'].items()) :
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

                # Create buffer arrays
                self.devices[uuid]['modules'][mod_uuid]['attribs'][attrib_name] = []

            # Associate module with device
            defineq += ';\n'
            insertq += f';\n$includes{i} (device: $dev, module: $mod{i}) isa includes; \n'

        # Define in KG schema
        tic = time.perf_counter()
        if (defineq != '') or (defineq_attribs != '') :
            #print('define\n' + defineq_attribs + defineq, kind='debug')
            self.define_query('define\n' + defineq_attribs + defineq)
        
        # Initialize in KG schema
        #print(matchq + insertq, kind='debug')
        self.insert_query(matchq + insertq)
        toc = time.perf_counter()
        # Notify of definition in console log
        print(arrow_str + f'modules/attribs defined <Tq={(toc-tic)*1000:.0f}ms>', kind='success')
        print_device_tree(sdf_dict)

    # Update module attributes
    def update_attribs(self,name,uuid,timestamp,data) :
        # Build datetime timestamp
        dt_timestamp = datetime.strptime(timestamp,"%Y-%m-%dT%H:%M:%S.%f")
        # Get device sdf dict
        sdf_dict = self.sdf_dicts[name]
        # Match - Delete - Insert Query
        matchq = f'match\n$dev isa device, has uuid "{uuid}", has timestamp $tmstmp; '
        deleteq = 'delete\n$dev has $tmstmp;\n'
        insertq = f'insert\n$dev has timestamp {timestamp[:-7]}; '

        # Iterate over modules
        for i, (mod_name, mod_dict) in enumerate(data.items()) :
            mod_sdf_dict = sdf_dict['sdfObject'][mod_name]
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
        
        # Remove too old samples from buffer
        if self.devices[uuid]['timestamps'][0] < dt_timestamp - timedelta(seconds=self.buffer_th) :
            self.devices[uuid]['timestamps'].pop(0)
            for mod_uuid, mod_dict in self.devices[uuid]['modules'].items() :
                for attrib_name, attrib_buffer in mod_dict['attribs'].items() :
                    attrib_buffer.pop(0)

        # Update attributes in the knowledge graph
        #print(matchq + '\n' + deleteq + '\n' + insertq, kind='debug')
        tic = time.perf_counter()
        self.update_query(matchq + '\n' + deleteq + '\n' + insertq)
        toc = time.perf_counter()
        # Notify of update in console log
        print(arrow_str + f'attributes updated <Tq={(toc-tic)*1000:.0f}ms>', kind='success')

    def consistency_handling(self,msg) :
        # Decode message components
        name, uuid, timestamp, module_uuids, data = msg['name'], msg['uuid'], msg['timestamp'], msg['module_uuids'], msg['data']
        dt_timestamp = datetime.strptime(timestamp,"%Y-%m-%dT%H:%M:%S.%f")

        # Retrieve and build SDF dict
        if name not in self.sdf_dicts :
            dev_sdf, dev_sdf_df = self.sdf_manager.build_sdf(name)
            self.sdf_dicts[name] = dev_sdf['sdfThing'][name]
            self.sdfs_df = pd.concat([self.sdfs_df,dev_sdf_df]).reset_index(drop=True)

        # If it is the first time the device has been seen 
        if uuid not in self.devices :
            # Add device as not integrated
            self.devices[uuid] = {'name':name, 'integrated':False, 'timestamps':[], 'period':0, 'modules':{}}
            # Define and add device to KG
            self.define_device(name,uuid)

        # Check if all device modules have already been defined
        if set(self.devices[uuid]['modules']) != set(module_uuids) :
            # Add modules and attributes to the knowledge graph
            self.define_modules_attribs(name,uuid,timestamp,data)

        # If the device is defined but yet to be integrated
        if not self.devices[uuid]['integrated'] :
            # Wait till we have at least 20 buffered samples
            if len(self.devices[uuid]['timestamps']) > 20 : 
                self.integrate(name,uuid)

        # Update device attributes
        self.update_attribs(name,uuid,timestamp,data)
        
        # Update other device data
        self.devices[uuid]['name'] = name
        self.devices[uuid]['period'] = (dt_timestamp-self.devices[uuid]['timestamps'][0]).total_seconds()
        self.devices[uuid]['timestamps'].append(dt_timestamp)

    ### INTEGRATION ALGORITHM ###
    def integrate(self,name,uuid) :
        # Create devices DataFrame
        devs_df = build_devs_df(self.devices)

        # Non-integrated class and dev DataFrames
        noninteg_class = self.sdfs_df[self.sdfs_df.thing == name]
        noninteg_dev = devs_df[devs_df.uuid == uuid]

        # Integrated classes and devs DataFrames
        integ_classes = self.sdfs_df[self.sdfs_df.thing != name]
        integ_devs = devs_df[(devs_df.integ == True) & (devs_df.uuid != uuid)]

        # Compute Top 5 closest SDF classes
        tic = time.perf_counter()
        votes = (Parallel(n_jobs=12)(delayed(get_closest_classes)(noninteg_class,integ_classes,i) for i in range(noninteg_class.shape[0])))
        voting_result_df = calc_voting_result_df(votes)
        closest_classes = voting_result_df.candidate.iloc[0:5].tolist()
        toc = time.perf_counter()
        print(arrow_str + f'closest classes computed in {(toc-tic)*1000:.0f}ms>', kind='success')
        print(voting_result_df.to_string(index=False))
        
        # Out of those 5 closest classes, get device that best matches time series pattern
        tic = time.perf_counter()
        votes = (Parallel(n_jobs=12)(delayed(get_closest_devs)(noninteg_dev,integ_devs,closest_classes,i) for i in range(noninteg_dev.shape[0])))
        voting_result_df = calc_voting_result_df(votes)
        toc = time.perf_counter()
        print(arrow_str + f'closest devices computed in {(toc-tic)*1000:.0f}ms>', kind='success')
        print(voting_result_df.to_string(index=False))

        # If the values similarity is high enough, then the device is either a replacement of a previous
        # device or a complementary device to speed up a task. Therefore, we have to integrate the device
        # within the task its most similar device belongs to in the KG.

        # FUTURE WORK: In case similarity is low, a more complex analysis will need to be performed to
        # build a new task or branch in the KG where this new device should be integrated. This could be 
        # powered by a graph of MQTT subscriptions that allows us to have some insight of how devices 
        # interact with each other.

        # Change device integration flag
        self.devices[uuid]['integrated'] = True

######################
######## MAIN ########
######################
def main() :
    # Create Knowledge Graph Agent instance
    kg_agent = KGAgent(initialize=True, buffer_th=180)

    # Start KG operation
    kg_agent.start()

if __name__ == "__main__":
    main()