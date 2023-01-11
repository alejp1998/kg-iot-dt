#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" Knowledge Graph Agent
In this module, a Knowledge Graph Agent class is defined. This class implements an MQTT client,
which is subscribed to all the topics in the MQTT network. This allows the MQTT client to listen 
to all the data being reported by the IoT devices. When the MQTT client receives a message from 
the broker, it processes the message and updates the Knowledge Graph accordingly.

The Knowledge Graph Agent class also inherits the TypeDBClient class, which is responsible for managing
interactions with the TypeDB database using a set of predefined query operations and functions.

When a data message is received, it is processed by the consistency_handler function. 
This function checks whether the device has already been integrated into the Knowledge Graph. 
If it hasn't, the integrate algorithm is triggered to do so. The consistency_handler function also 
updates the values of the device's attributes in the Knowledge Graph and maintains a short memory 
of the device's behavior in the last two minutes, which is useful for integrating new, unforeseen devices.

The integrate algorithm works as follows:

1. Check the existing classes that are closest to the new class, based on the text edit distance.
2. Among the top 5 closest existing classes, check which instance has the closest time series behavior 
in its data. This is done by searching for the attribute with the most similar time series pattern 
to the new device.
3. Once the closest instance is found, if it is very similar (more similar than a threshold) 
to the new device, it is assumed that the new device is either a replacement for or a 
complementary device to the existing one. In this case, the relations of the closest device are 
replicated in the new device.
4. If the closest device hasn't reported data recently, it is assumed to have been replaced by the 
new device and is removed from the Knowledge Graph.

The purpose of this module is to modify the Knowledge Graph in real time based on the data reported by 
the IoT devices, so that the Knowledge Graph accurately reflects the structure of the IoT platform.
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
    """
    A class for managing devices and their data in a knowledge graph.

    Attributes:
        print_queries (bool): A flag for printing queries made to the database.
        dev_msg_stats (dict): A dictionary for storing message statistics for each device.
        total_msg_count (int): The total number of messages received.
        msg_proc_time (int): The total time spent processing messages.
        sdf_manager (SDFManager): An object for managing SDF files.
        buffer_th (int): The number of seconds to store data for each device.
        sdf_dicts (dict): A dictionary for storing SDF information.
        sdfs_df (pandas.DataFrame): A DataFrame for storing SDF information.
    """

    # Initialization
    def __init__(self, initialize=True, print_queries=False, buffer_th=60):
        """
        Initializes the KGAgent and its parent class, TypeDBClient.

        Args:
            initialize (bool): A flag for initializing the database.
            print_queries (bool): A flag for printing queries made to the database.
            buffer_th (int): The number of seconds to store data for each device.
        """
        # State tracking
        self.state = 0 # 0 for IDLE, 1 for PROCESSING, 2 for QUERYING
        self.states_ts = [time.perf_counter()] # times when state changes
        self.states = [0] # values state changes to
        self.state_times = [0,0,0]
        # Parent class initialization
        TypeDBClient.__init__(self,initialize)
        # Debugging / logging
        self.print_queries = print_queries
        # Attributes for stats
        self.dev_msg_stats = {}
        self.total_msg_count = 0
        self.msg_proc_time = 0
        self.sdf_manager = SDFManager()
        # Variables for devices management / integration
        self.buffer_th = buffer_th # values within buffer_th last minutes will be stored for each device
        self.sdf_dicts = {}
        self.sdfs_df = pd.DataFrame(columns=sdf_cols)
    
    # Track state over time as it changes
    def change_state(self, new_state) :
        tic = time.perf_counter()
        self.state_times[self.state] = self.state_times[self.state] + (tic-self.states_ts[-1])
        self.state = new_state
        self.states_ts.append(tic)
        self.states.append(new_state)

    # MQTT Callback Functions
    def on_log(client, userdata, level, buf):
        """Prints a log message."""
        print("log: " + buf, kind='info')

    def on_connect(self, client, userdata, flags, rc):
        """Subscribes to all topics and prints a success message on connection."""
        self.client.subscribe('#', qos=0)
        print("\nKnowledge Graph connected - Waiting for messages...\n", kind='success')

    def on_disconnect(self, client, userdata, rc):
        """Prints a failure message on disconnection."""
        print("\nKnowledge Graph disconnected.\n", kind='fail')

    def on_message(self, client, userdata, msg):
        """Handles messages received from the MQTT broker."""
        # Decode message
        msg = loads(str(msg.payload.decode("utf-8")))
        topic, dev_class, uuid = msg['topic'], msg['class'], msg['uuid']

        # Treat message depending on its category
        match msg['category'] :
            case 'CONNECTED' :
                print(f'({topic}) - {dev_class}[{uuid[0:6]}] connected to broker.', kind='success')

            case 'DISCONNECTED' :
                print(f'({topic}) - {dev_class}[{uuid[0:6]}] disconnected from broker.', kind='fail')

            case 'DATA' :
                if uuid not in self.dev_msg_stats: self.dev_msg_stats[uuid] = [0,0]
                print(f'({topic}) -> {dev_class}[{uuid[0:6]}] msg received <N={self.dev_msg_stats[uuid][0]+1}>', kind='info')
                # Integrate message and time elapsed time
                tic = time.perf_counter()
                self.change_state(1) # PROCESSING
                self.consistency_handler(msg)
                self.change_state(0) # IDLE
                toc = time.perf_counter()
                # Data messages statistics
                self.total_msg_count += 1
                self.dev_msg_stats[uuid][0] += 1
                self.msg_proc_time += toc-tic
                self.dev_msg_stats[uuid][1] += toc-tic
                print(arrow_str + f'msg processed <Tp={(toc-tic)*1000:.0f}ms | Avg.Tp={(self.dev_msg_stats[uuid][1]/self.dev_msg_stats[uuid][0])*1000:.0f}ms>\n', kind='info')
                # Data messages summary
                if self.total_msg_count % 100 == 0 :
                    # Print messages processing summary
                    print('-----------------------------------------------------', kind='summary')
                    print(f'MSGs SUMMARY <N={self.total_msg_count} | Avg. Tp={(self.msg_proc_time/self.total_msg_count)*1000:.0f}ms>', kind='summary')
                    print('-----------------------------------------------------\n', kind='summary')
                    # Save devices data to file for analysis
                    with open('devices.json', 'w') as f:
                        dump(self.devices,f,cls=ModifiedEncoder)
                    # Save state data for visualization
                    with open('states.csv', 'w') as f:
                        writer = csv.writer(f)
                        writer.writerows(zip(['ts']+self.states_ts, ['states']+self.states))
                    # Save state times
                    with open('state_times.csv', 'w') as f:
                        writer = csv.writer(f)
                        writer.writerow(['state_times']+self.state_times)

    # Start MQTT client
    def start(self):
        """Starts the MQTT client and binds the callback functions."""
        self.client = mqtt_client.Client('KG') # create new client

        self.client.on_log = self.on_log
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        self.client.connect(broker_addr, port=broker_port) # connect to the broker
        self.client.loop_forever() # run client loop for callbacks to be processed

    # Define modules and attributes according to SDF description
    def define_modules_attribs(self, dev_class: str, uuid: str, timestamp: str, data: dict) -> None :
        """
        Define modules and attributes for a device in the knowledge graph according to its SDF description.

        Parameters
        ----------
        dev_class (str): The class of the device.
        uuid (str): The unique identifier of the device.
        timestamp (str): The timestamp of the update in ISO-8601 format.
        data (dict): A dictionary containing the updates for the modules and their attributes. The structure should
                     be {'module_name': {'attribute_name': attribute_value, ...}, ...}. The attribute value should
                     have the correct type according to the attribute's definition in the SDF.

        Returns
        -------
        None
        """
        # Build datetime timestamp
        dt_timestamp = datetime.strptime(timestamp,"%Y-%m-%dT%H:%M:%S.%f")
        self.devices[uuid]['timestamps'].append(dt_timestamp)
        # Get device sdf dict
        sdf_dict = self.sdf_dicts[dev_class]
        # Build define query
        defineq = ''
        defineq_attribs = ''
        # Build match-insert query
        matchq = f'match\n$dev isa {dev_class.lower()}, has uuid "{uuid}";\n\n'
        insertq = f'insert\n$dev has timestamp {timestamp[:-4]};\n\n'

        # Iterate over modules and its attributes
        for i, (mod_name, mod_sdf_dict) in enumerate(sdf_dict['sdfObject'].items()) :
            # Add module to device dict
            self.devices[uuid]['modules'][mod_name] = {}
            
            # Check if module has already been defined in KG schema
            if mod_name not in self.defined_modules : 
                defineq += f'{mod_name} sub module; '
                self.defined_modules.append(mod_name)
            
            # Insert module
            insertq += f'$mod{i+1} isa {mod_name}, has uuid "{uuid}"'
            for j, (attrib_name, attrib_sdf_dict) in enumerate(mod_sdf_dict['sdfProperty'].items()) :
                # Define modules and assign default values
                tdbtype = types_trans[attrib_sdf_dict['type']]

                # In case the attribute was not yet defined, define it
                if attrib_name not in self.defined_attribs : 
                    defineq_attribs += f'{attrib_name} sub attribute, value {tdbtype}; \n'
                    self.defined_attribs.append(attrib_name)

                # Make the module own the attribute
                defineq += f'{", " if j>0 else f"{mod_name} "}owns {attrib_name}'

                # Insert attributes in module
                insertq += f', has {attrib_name} {defvalues[tdbtype]}'

                # Create buffer arrays
                self.devices[uuid]['modules'][mod_name][attrib_name] = []

            # Finish queries construction
            defineq += ';\n'
            insertq += ';\n'
        
        # Link all modules to the device
        insertq += '$includes (device: $dev'
        for j in range(i+1): insertq += f', module: $mod{j+1}'
        insertq += ') isa includes; \n'

        # Define in KG schema
        tic = time.perf_counter()
        if (defineq != '') or (defineq_attribs != '') :
            if self.print_queries: print('define\n' + defineq_attribs + defineq, kind='debug')
            self.define_query('define\n' + defineq_attribs + defineq)
        
        # Initialize in KG schema
        if self.print_queries: print(matchq + insertq, kind='debug')
        self.insert_query(matchq + insertq)
        toc = time.perf_counter()

        # Notify of definition in console log
        print(arrow_str + f'modules/attribs defined <Tq={(toc-tic)*1000:.0f}ms>', kind='success')
        print_device_tree(sdf_dict)

    # Update module attributes
    def update_attribs(self,dev_class: str, uuid: str, timestamp: str, data: dict) -> None :
        """
        Update the attributes of the modules of a device in the knowledge graph.

        Parameters
        ----------
        dev_class (str): The class of the device.
        uuid (str): The unique identifier of the device.
        timestamp (str): The timestamp of the update in ISO-8601 format.
        data (dict): A dictionary containing the updates for the modules and their attributes. The structure should
                     be {'module_name': {'attribute_name': attribute_value, ...}, ...}. The attribute value should
                     have the correct type according to the attribute's definition in the SDF.

        Returns
        -------
        None
        """
        # Build datetime timestamp
        dt_timestamp = datetime.strptime(timestamp,"%Y-%m-%dT%H:%M:%S.%f")
        # Get device sdf dict
        sdf_dict = self.sdf_dicts[dev_class]
        # Match - Delete - Insert Query
        matchq = f'match\n$dev isa {dev_class.lower()}, has uuid "{uuid}", has timestamp $tmstmp;\n\n'
        deleteq = 'delete\n$dev has $tmstmp;\n\n'
        insertq = f'insert\n$dev has timestamp {timestamp[:-4]};\n\n'

        # Iterate over modules
        for i, (mod_name, mod_dict) in enumerate(data.items()) :
            mod_sdf_dict = sdf_dict['sdfObject'][mod_name]
            
            # Match module
            matchq += f'$mod{i+1} isa {mod_name}, has uuid "{uuid}"'
            deleteq += f'$mod{i+1} '
            insertq += f'$mod{i+1} '
            for j, (attrib_name, attrib_value) in enumerate(mod_dict.items()) :
                attrib_sdf_dict = mod_sdf_dict['sdfProperty'][attrib_name]
                
                # Value wrapping according to type
                tdbtype = types_trans[attrib_sdf_dict['type']]
                match tdbtype :
                    case 'double' : value = f'{attrib_value:.2f}'
                    case 'string' : value = f'"{attrib_value}"'
                    case 'boolean': value = str(attrib_value).lower()

                # Query construction
                matchq += f', has {attrib_name} $attrib{i+1}{j+1}'
                deleteq += f'{", " if j!=0 else ""}has $attrib{i+1}{j+1}'
                insertq += f'{", " if j!=0 else ""}has {attrib_name} {value}'

                # Add the value to the buffer
                self.devices[uuid]['modules'][mod_name][attrib_name].append(attrib_value)
                
            # Insert line break
            deleteq += ';\n'
            insertq += ';\n'
            matchq += ';\n'
        
        # Remove too old samples from buffer
        if self.devices[uuid]['timestamps'][0] < dt_timestamp - timedelta(seconds=self.buffer_th) :
            self.devices[uuid]['timestamps'].pop(0)
            for mod_name, attribs_dic in self.devices[uuid]['modules'].items() :
                for attrib_name, attrib_buffer in attribs_dic.items() :
                    attrib_buffer.pop(0)
        
        # Update attributes in the knowledge graph
        if self.print_queries: print(matchq + '\n' + deleteq + '\n' + insertq, kind='debug')
        tic = time.perf_counter()
        self.update_query(matchq + '\n' + deleteq + '\n' + insertq)
        toc = time.perf_counter()
        # Notify of update in console log
        print(arrow_str + f'attributes updated <Tq={(toc-tic)*1000:.0f}ms>', kind='success')

    # Consistency handling
    def consistency_handler(self, msg: dict) -> None:
        """
        Handle message consistency by adding new devices, modules and attributes to the knowledge graph
        as well as integrating devices and updating attributes.

        Parameters
        ----------
        msg (dict): Dictionary containing message data.
                    Expected format: {'class': string, 'uuid': string, 'timestamp': string, 'data': dict}
        Returns
        -------
        None
        """
        # Decode message components
        dev_class, uuid, timestamp, data = msg['class'], msg['uuid'], msg['timestamp'], msg['data']
        dt_timestamp = datetime.strptime(timestamp,"%Y-%m-%dT%H:%M:%S.%f")

        # Retrieve and build SDF dict
        if dev_class not in self.sdf_dicts :
            dev_sdf, dev_sdf_df = self.sdf_manager.build_sdf(dev_class)
            self.sdf_dicts[dev_class] = dev_sdf['sdfThing'][dev_class]
            self.sdfs_df = pd.concat([self.sdfs_df,dev_sdf_df]).reset_index(drop=True)

        # If it is the first time the device has been seen 
        if uuid not in self.devices :
            # Add device as not integrated
            self.devices[uuid] = {'class':dev_class, 'integrated':False, 'period':0, 'timestamps':[], 'modules':{}}
            # Define and add device to KG
            self.define_device(dev_class,uuid)
            self.change_state(1) # PROCESSING

        # Check if all device modules have already been defined
        if set(self.devices[uuid]['modules']) != set(data.keys()) :
            # Add modules and attributes to the knowledge graph
            self.define_modules_attribs(dev_class,uuid,timestamp,data)
            self.change_state(1) # PROCESSING
        
        # If the device is defined but yet to be integrated
        if not self.devices[uuid]['integrated'] :
            # Wait till we have at least 20 buffered samples
            if len(self.devices[uuid]['timestamps']) > 20 : 
                self.integrate(dev_class,uuid,dt_timestamp)
                self.change_state(1) # PROCESSING

        # Update device attributes
        self.update_attribs(dev_class,uuid,timestamp,data)
        self.change_state(1) # PROCESSING

        # Update other device data
        self.devices[uuid]['class'] = dev_class
        self.devices[uuid]['period'] = (dt_timestamp - self.devices[uuid]['timestamps'][-1]).total_seconds()
        self.devices[uuid]['timestamps'].append(dt_timestamp)
        

    ### INTEGRATION ALGORITHM ###
    def integrate(self, dev_class: str, uuid: str, dt_timestamp: datetime) -> None:
        """
        Integrate the device with the given uuid and class into the knowledge graph. This is done by finding the most similar
        device or task in the knowledge graph, and either integrating the new device as a replacement or a complementary
        device to the task, or creating a new task if no similar device or task is found.

        Parameters
        ----------
        dev_class (str): The class of the device to be integrated.
        uuid (str): The UUID of the device to be integrated.
        dt_timestamp (datetime): The timestamp of the last received message from the device.

        Returns
        -------
        None
        """
        # Create devices DataFrame
        devs_df = build_devs_df(self.devices)

        # Non-integrated class and dev DataFrames
        noninteg_class = self.sdfs_df[self.sdfs_df.thing == dev_class]
        noninteg_dev = devs_df[devs_df.uuid == uuid]

        # Integrated classes and devs DataFrames
        integ_classes = self.sdfs_df[self.sdfs_df.thing != dev_class]
        integ_devs = devs_df[(devs_df.integ == True) & (devs_df.uuid != uuid)]

        # Compute Top 5 closest SDF classes
        tic = time.perf_counter()
        votes = (Parallel(n_jobs=12)(delayed(get_closest_classes)(noninteg_class,integ_classes,i) for i in range(noninteg_class.shape[0])))
        voting_result_df = calc_voting_result_df(votes)
        closest_classes = voting_result_df.candidate.iloc[0:5].tolist()
        toc = time.perf_counter()
        print(arrow_str + f'closest classes computed in {(toc-tic)*1000:.0f}ms', kind='success')
        print(voting_result_df.to_string(index=False))
        
        # Out of those 5 closest classes, get device that best matches time series pattern
        tic = time.perf_counter()
        votes = (Parallel(n_jobs=12)(delayed(get_closest_devs)(noninteg_dev,integ_devs,closest_classes,i) for i in range(noninteg_dev.shape[0])))
        voting_result_df = calc_voting_result_df(votes)
        integ_class, integ_uuid = voting_result_df.iloc[0].candidate.split('/')
        toc = time.perf_counter()
        print(arrow_str + f'closest devices computed in {(toc-tic)*1000:.0f}ms', kind='success')
        print(voting_result_df.to_string(index=False))

        # If the values similarity is high enough, then the device is either a replacement of a previous
        # device or a complementary device to speed up a task. Therefore, we have to integrate the device
        # within the task its most similar device belongs to in the KG.
        tic = time.perf_counter()
        self.replicate_relations(integ_uuid,uuid)
        self.devices[uuid]['integrated'] = True
        toc = time.perf_counter()
        print(arrow_str + f'device integrated (relations replicated in KG) <Tq={(toc-tic)*1000:.0f}ms>', kind='success')

        # In case the closest integrated device has not reported data lately, we understand it 
        # as a replacement and thus we eliminate the device from the KG
        if self.devices[integ_uuid]['timestamps'][-1] < (dt_timestamp - timedelta(seconds=2*self.devices[integ_uuid]['period'])) :
            tic = time.perf_counter()
            self.disintegrate_device(integ_uuid) # remove device from KG
            del self.devices[integ_uuid] # delete device from memory
            toc = time.perf_counter()
            print(arrow_str + f'old device and its modules disintegrated from KG <Tq={(toc-tic)*1000:.0f}ms>', kind='success')

        # FUTURE WORK: In case similarity is low, a more complex analysis will need to be performed to
        # build a new task or branch in the KG where this new device should be integrated. This could be 
        # powered by a graph of MQTT subscriptions that allows us to have some insight of how devices 
        # interact with each other.

######################
######## MAIN ########
######################
def main() :
    # Create Knowledge Graph Agent instance
    kg_agent = KGAgent(initialize=True, print_queries=False, buffer_th=180)

    # Start KG operation
    kg_agent.start()

if __name__ == "__main__":
    main()