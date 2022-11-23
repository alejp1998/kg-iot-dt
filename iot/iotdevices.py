# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" IoT Devices Definition
In this module a IoT Device Class implementing a MQTT Client is defined. 
This class is then inherited by several device subclasses such as robotic arms or scanners, that publish their simulated data
updates to the MQTT network. The network messages have a JSON format, that includes an the device name, which is linked to 
the device SDF description, that can be checked by the KG agent in case the device is unknown.
"""
# ---------------------------------------------------------------------------
# Imports
from aux import *
# ---------------------------------------------------------------------------

# Server addresses
broker_addr = '0.0.0.0' # broker_addr = 'mosquitto'
broker_port = 8883

# Control messaging frequency
speedup_factor = 4

###################################
######## IOT DEVICES CLASS ########
###################################

# IoT Device Class to Inherit
class IoTDevice(Thread) :
    # Initialization
    def __init__(self,topic,devuuid,interval,modifier,print_logs):
        Thread.__init__(self)
        # Topic, publishing interval and log printing
        self.topic = topic
        self.interval = interval/speedup_factor
        self.modifier = modifier
        self.print_logs = print_logs
        # UUIDs
        self.uuid = re.sub(r'(\S{8})(\S{4})(\S{4})(\S{4})(.*)',r'\1-\2-\3-\4-\5',uuid.uuid4().hex) if devuuid=='' else devuuid  # assign unique identifier
        self.mod_uuids = [re.sub(r'(\S{8})(\S{4})(\S{4})(\S{4})(.*)',r'\1-\2-\3-\4-\5',uuid.uuid4().hex) for i in range(10)] # modules unique identifiers
        # Activation flag
        self.active = True
        
    # MQTT Callback Functions
    def on_log(client, userdata, level, buf):
        print("log: " + buf, kind='info')
        
    def on_connect(self, client, userdata, flags, rc):
        print(f'{self.name}[{self.uuid[0:6]}] connected.', kind='success')
        msg = fill_header_data(self.name,self.topic,self.uuid)
        msg['category'] = 'CONNECTED'
        self.client.publish(self.topic,dumps(msg, indent=4))

    def on_disconnect(self, client, userdata, rc):
        print(f'{self.name}[{self.uuid[0:6]}] disconnected.', kind='fail')
        msg = fill_header_data(self.name,self.topic,self.uuid)
        msg['category'] = 'DISCONNECTED'
        self.client.publish(self.topic,dumps(msg, indent=4))

    # Message generation function
    def gen_msg(self):
        msg = fill_header_data(self.name,self.topic,self.uuid)
        msg['data'], msg['module_uuids'] = fill_module_uuids(self.gen_new_data(),self.mod_uuids)
        msg['category'] = 'DATA'
        return msg
    
    # Define tic behavior
    def tic_behavior(self):
        # Wait a random amount of time (up to 10secs) before starting
        time.sleep(random.uniform(0,10))
        # Periodically publish data when connected
        self.msg_count = 0
        tic = time.perf_counter()
        while True :
            if not self.active :
                print(f'{self.name}[{self.uuid[0:6]}] inactive <N={self.msg_count} | T={tic-last_tic:.3f}s>', kind='') # print info
                while not self.active : time.sleep(5)
            self.msg_count += 1
            last_tic = tic
            tic = time.perf_counter()
            msg = self.gen_msg() # generate message with random data
            self.client.publish(self.topic,dumps(msg, indent=4)) # publish it
            print(f'({self.topic}) <- {self.name}[{self.uuid[0:6]}] msg published <N={self.msg_count} | T={tic-last_tic:.3f}s>', kind='info') # print info
            if self.print_logs : print_device_data(msg['timestamp'],msg['data'])
            print('')
            self.client.loop() # run client loop for callbacks to be processed
            time.sleep(self.interval) # wait till next execution
        
    # Thread execution
    def run(self):
        self.client = mqtt_client.Client(self.uuid) # create new client instance

        self.client.on_log = self.on_log # bind callback fn
        self.client.on_connect = self.on_connect # bind callback fn
        self.client.on_disconnect = self.on_disconnect # bind callback fn

        self.client.connect(broker_addr, port=broker_port) # connect to the broker
        self.client.loop() # run client loop for callbacks to be processed
        
        self.tic_behavior() # start tic behavior

#########################################
######## PRODUCTION LINE DEVICES ########
#########################################

# CONVEYOR BELT
class ConveyorBelt(IoTDevice):
    # Initialization
    def __init__ (self,params,topic=prodline_root,devuuid='',interval=2,modifier=0.0,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'ConveyorBelt'
        # Params for data generation
        mean, std = params['conv_belt']
        # Initial values
        self.conveyor_belt = {
            'status': True, 
            'linear_speed': sample_normal_mod(mean,std,self.modifier), 
            'rotational_speed': sample_normal_mod(mean*3,std,self.modifier), 
            'weight': sample_normal_mod(mean*100,std,self.modifier)
        }
    
    # THE DEVICES SHOULD ALSO BE CONSTRUCTED DETERMINING THE LIST OF OTHER DEVICES OR TOPICS THEY 
    # ARE SUBSCRIBED TO, AND WHICH DEVICES ARE SUBSCRIBED TO THE TOPICS THE DEVICE PUBLISHES

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # CONVEYOR BELT MODULE
        self.conveyor_belt['status'] = coin(0.95) if self.conveyor_belt['status'] else coin(0.2)
        self.conveyor_belt['linear_speed'] = get_new_sample(self.conveyor_belt['linear_speed'])
        self.conveyor_belt['rotational_speed'] = get_new_sample(self.conveyor_belt['rotational_speed'])
        self.conveyor_belt['weight'] = get_new_sample(self.conveyor_belt['weight'])
        
        # Modifications based on status value
        conveyor_belt_copy = self.conveyor_belt.copy()
        conveyor_belt_copy['linear_speed'] = self.conveyor_belt['linear_speed'] if self.conveyor_belt['status'] else 0.0
        conveyor_belt_copy['rotational_speed'] = self.conveyor_belt['rotational_speed'] if self.conveyor_belt['status'] else 0.0
        
        # Return updated data dictionary
        return {'conveyor_belt' : conveyor_belt_copy}

# TAG SCANNER
class TagScanner(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=60, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'TagScanner'
        # Initial values
        self.rfid_scanner = {
            'product_id' : random.randint(0,10),
            'process_id' : random.randint(0,10)
        }

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # RFID SCANNER MODULE
        self.rfid_scanner['product_id'] = self.rfid_scanner['product_id'] if coin(0.7) else random.randint(0,10)
        self.rfid_scanner['process_id'] = self.rfid_scanner['process_id'] if coin(0.7) else random.randint(0,10)
        
        # Return updated data dictionary
        return {'rfid_scanner' : self.rfid_scanner}

# PRODUCTION CONTROL
class ProductionControl(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=60, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'ProductionControl'
        # Initial values
        self.production_control = {'production_status' : True}

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # PRODUCTION CONTROL MODULE
        self.production_control['production_status'] = coin(0.95) if self.production_control['production_status'] else coin(0.2)
        
        # Return updated data dictionary
        return {'production_control' : self.production_control}

# REPAIR CONTROL
class RepairControl(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=40, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'RepairControl'
        # Initial values
        self.repair_control = {'repair_status': 2}
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # REPAIR CONTROL MODULE
        self.repair_control['repair_status'] = self.repair_control['repair_status'] if coin(0.8) else (self.repair_control['repair_status'] + 1)%2
        
        # Return updated data dictionary
        return {'repair_control' : self.repair_control}
                  
# PRODUCT CONFIG SCANNER
class ConfigurationScanner(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'ConfigurationScanner'
        # No initial values since this device requires no memory for data generation

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {
            'left_cam': {'config_status' : coin(0.975)},
            'right_cam': {'config_status' : coin(0.975)},
            'front_cam': {'config_status' : coin(0.975)},
            'back_cam': {'config_status' : coin(0.975)},
            'top_cam': {'config_status' : coin(0.975)},
            'bottom_cam': {'config_status' : coin(0.975)}
        }

# PRODUCT QUALITY SCANNER
class QualityScanner(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'QualityScanner'
        # No initial values since this device requires no memory for data generation

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {
            'left_cam': {'quality_status' : coin(0.975)},
            'right_cam': {'quality_status' : coin(0.975)},
            'front_cam': {'quality_status' : coin(0.975)},
            'back_cam': {'quality_status' : coin(0.975)},
            'top_cam': {'quality_status' : coin(0.975)},
            'bottom_cam': {'quality_status' : coin(0.975)}
        }

# FAULT NOTIFIER
class FaultNotifier(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'FaultNotifier'
        # Initial data
        self.fault_notifier = {'alarm': False}

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # FAULT NOTIFIER MODULE
        self.fault_notifier['alarm'] = coin(0.05) if not self.fault_notifier['alarm'] else coin(0.7)
        
        # Return updated data dictionary
        return {'fault_notifier': self.fault_notifier}

######################################
# INTRODUCE SINES IN DATA GENERATION #
######################################

# POSE DETECTOR
class PoseDetector(IoTDevice):
    # Initialization
    def __init__(self,params,topic=prodline_root,devuuid='',interval=3, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'PoseDetector'
        # Params for data generation
        self.params = params['pose_det']

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # Unpack params and sample time
        offset, A, T, phi = self.params
        # Return updated data dictionary
        return {
            'pose_detection_cam':{
                'x_position' : sample_triangular(offset,A,T,phi),
                'y_position' : sample_triangular(offset+1,A*2,T/2,phi),  
                'z_position' : sample_triangular(offset-1,A/2,T*2,phi),
                'roll_orientation' : sample_triangular(offset+np.pi/2,A,T,phi), 
                'pitch_orientation' : sample_triangular(offset+6*np.pi/4,A*2,T/2,phi), 
                'yaw_orientation' : sample_triangular(offset-6*np.pi/4,A/2,T*2,phi)
            }
        }

# PIECE DETECTOR
class PieceDetector(IoTDevice):
    # Initialization
    def __init__(self,params,topic=prodline_root,devuuid='',interval=3, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'PieceDetector'
        # Params for data generation
        self.params = params['piece_det']
        self.piece_id = random.randint(0,6)

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # Unpack params and sample time
        offset, A, T, phi = self.params
        # Return updated data dictionary
        return {
            'piece_detection_cam':{
                'piece_id' : self.piece_id if coin(0.7) else random.randint(0,6),
                'x_position' : sample_sawtooth(offset,A,T,phi),
                'y_position' : sample_sawtooth(offset+1,A*2,T/2,phi),  
                'z_position' : sample_sawtooth(offset-1,A/2,T*2,phi),
                'roll_orientation' : sample_sawtooth(offset+np.pi/2,A,T,phi), 
                'pitch_orientation' : sample_sawtooth(offset+6*np.pi/4,A*2,T/2,phi), 
                'yaw_orientation' : sample_sawtooth(offset-6*np.pi/4,A/2,T*2,phi)
            }
        }

# PICK UP ROBOT
class PickUpRobot(IoTDevice):
    # Initialization
    def __init__(self,params,topic=prodline_root,devuuid='',interval=3, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'PickUpRobot'
        # Params for data generation
        self.params = params['pickup']
        self.actuator_status = False

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        self.actuator_status = coin(0.2) if not self.actuator_status else coin(0.7)
        # Unpack params and sample time
        offset, A, T, phi = self.params
        # Return updated data dictionary
        return gen_robot_data(offset,A,T,phi+random.normal(),self.actuator_status)

# CLAMPING ROBOT
class ClampingRobot(IoTDevice):
    # Initialization
    def __init__(self,params,topic=prodline_root,devuuid='',interval=3, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'ClampingRobot'
        # Params for data generation
        self.params = params['clamping']
        self.actuator_status = False

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        self.actuator_status = coin(0.2) if not self.actuator_status else coin(0.7)
        # Unpack params and sample time
        offset, A, T, phi = self.params
        # Return updated data dictionary
        return gen_robot_data(offset,A,T,phi+random.normal(),self.actuator_status)

# DRILLING ROBOT
class DrillingRobot(IoTDevice):
    # Initialization
    def __init__(self,params,topic=prodline_root,devuuid='',interval=3, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'DrillingRobot'
        # Params for data generation
        self.params = params['drilling']
        self.actuator_status = False

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        self.actuator_status = coin(0.2) if not self.actuator_status else coin(0.7)
        # Unpack params and sample time
        offset, A, T, phi = self.params
        t = time.perf_counter()
        # Return updated data dictionary
        return gen_robot_data(offset,A,T,phi+random.normal(),self.actuator_status)

# MILLING ROBOT
class MillingRobot(IoTDevice):
    # Initialization
    def __init__(self,params,topic=prodline_root,devuuid='',interval=3, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'MillingRobot'
        # Params for data generation
        self.params = params['pickup']
        self.actuator_status = False

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        self.actuator_status = coin(0.2) if not self.actuator_status else coin(0.7)
        # Unpack params and sample time
        offset, A, T, phi = self.params
        t = time.perf_counter()
        # Return updated data dictionary
        return gen_robot_data(offset,A,T,phi+random.normal(),self.actuator_status)


################################################
######## SAFETY / ENVIRONMENTAL DEVICES ########
################################################

# AIR QUALITY
class AirQuality(IoTDevice):
    # Initialization
    def __init__(self,ground_truth,topic=safetyenv_root,devuuid='',interval=2,modifier=0.0,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'AirQuality'
        # Variables for data generation
        self.gt = ground_truth
        
    # New measurement around ground truth values
    def gen_new_data(self) :
        return {
            'temperature_sensor' : {'temperature': sample_normal_mod(self.gt.get('temperature'),modifier=self.modifier)},
            'humidity_sensor' : {'humidity': sample_normal_mod(self.gt.get('humidity'),modifier=self.modifier)},
            'pressure_sensor' : {'pressure': sample_normal_mod(self.gt.get('pressure'),modifier=self.modifier)},
            'air_quality_sensor' : {
                'pm1': sample_normal_mod(self.gt.get('pm1'),modifier=self.modifier), 
                'pm25': sample_normal_mod(self.gt.get('pm25'),modifier=self.modifier), 
                'pm10': sample_normal_mod(self.gt.get('pm10'),modifier=self.modifier)
            }
        }

# AIR QUALITY MODIFIED
class AirQualityModified(IoTDevice):
    # Initialization
    def __init__(self,ground_truth,topic=safetyenv_root,devuuid='',interval=2, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'AirQualityModified'
        # Variables for data generation
        self.gt = ground_truth

    # New measurement around ground truth values
    def gen_new_data(self) :
        return {
            'temperature_humidity_sensor' : {
                'temperature' : sample_normal_mod(self.gt.get('temperature'),modifier=self.modifier),
                'humidity' : sample_normal_mod(self.gt.get('humidity'),modifier=self.modifier)
            },
            'air_quality_sensor' : {
                'pm25' : sample_normal_mod(self.gt.get('pm25'),modifier=self.modifier),
                'pm10' : sample_normal_mod(self.gt.get('pm10'),modifier=self.modifier)
            }
        }

# NOISE SENSOR
class NoiseSensor(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=5, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'NoiseSensor'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {'noise_sensor' : {'noise' : sample_normal_mod(70,2,self.modifier)}}

# SMOKE SENSOR
class SmokeSensor(IoTDevice):
    ## Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=5, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'SmokeSensor'
        # Initial values
        self.smoke_sensor = {'smoke': False}
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        self.smoke_sensor['smoke'] = coin(0.05) if self.smoke_sensor['smoke'] else coin(0.7)
        return {'smoke_sensor' : self.smoke_sensor}

# SEISMIC SENSOR
class SeismicSensor(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=5, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'SeismicSensor'
        # Initial values
        self.seismic_sensor = {'intensity': random.randint(0,1)}
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        self.seismic_sensor['intensity'] = random.randint(0,1) if coin(0.95) else random.randint(2,8)
        return {'seismic_sensor' : self.seismic_sensor}

# RAIN SENSOR
class RainSensor(IoTDevice):
    # Initialization
    def __init__(self,ground_truth,topic=safetyenv_root,devuuid='',interval=5, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'RainSensor'
        # Variables for data generation
        self.gt = ground_truth
        
    # New measurement around ground truth values
    def gen_new_data(self) :
        return {'rain_sensor' : {'cumdepth' : sample_normal_mod(self.gt.get('rain_cumdepth'),modifier=self.modifier)}}

# WIND SENSOR
class WindSensor(IoTDevice):
    # Initialization
    def __init__(self,ground_truth,topic=safetyenv_root,devuuid='',interval=5, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'WindSensor'
        # Variables for data generation
        self.gt = ground_truth
        
    # New measurement around ground truth values
    def gen_new_data(self) :
        return {
            'wind_sensor' : {
                'speed' : sample_normal_mod(self.gt.get('wind_speed'),modifier=self.modifier),
                'direction' : sample_normal_mod(self.gt.get('wind_direction'),modifier=self.modifier)
            }
        }

# INDOORS ALARM
class IndoorsAlarm(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=5, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'IndoorsAlarm'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {
            'air_quality_alarm' : {'status' : coin(0.005)},
            'temperature_alarm' : {'status' : coin(0.005)},
            'humidity_alarm' : {'status' : coin(0.005)},
            'fire_alarm' : {'status' : coin(0.005)},
            'seismic_alarm' : {'status' : coin(0.005)}
        }

# OUTDOORS ALARM
class OutdoorsAlarm(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=5, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'OutdoorsAlarm'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {
            'air_quality_alarm' : {'status' : coin(0.005)},
            'temperature_alarm' : {'status' : coin(0.005)},
            'humidity_alarm' : {'status' : coin(0.005)},
            'rain_alarm' : {'status' : coin(0.005)},
            'wind_alarm' : {'status' : coin(0.005)}
        }
