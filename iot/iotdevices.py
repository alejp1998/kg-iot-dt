#!/usr/bin/env python3
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

# Auxiliary vars
car_parts = ['door','window','wheel','seat','mirror']
car_underpans = ['S60','S80','V60','XC60','XC70']

# Server addresses
broker_addr = '0.0.0.0' # broker_addr = 'mosquitto'
broker_port = 8883

###################################
######## IOT DEVICES CLASS ########
###################################

# IoT Device Class to Inherit
class IoTDevice(Thread) :
    # Initialization
    def __init__(self,topic,devuuid,interval,print_logs):
        Thread.__init__(self)
        # Topic, publishing interval and log printing
        self.topic = topic
        self.interval = interval
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
        self.client.publish(self.topic,json.dumps(msg, indent=4))

    def on_disconnect(self, client, userdata, rc):
        print(f'{self.name}[{self.uuid[0:6]}] disconnected.', kind='fail')
        msg = fill_header_data(self.name,self.topic,self.uuid)
        msg['category'] = 'DISCONNECTED'
        self.client.publish(self.topic,json.dumps(msg, indent=4))

    # Message generation function
    def gen_msg(self):
        msg = fill_header_data(self.name,self.topic,self.uuid)
        msg['data'], dev_mod_uuids = fill_module_uuids(self.gen_data(),self.mod_uuids)
        msg['module_uuids'] = dev_mod_uuids
        msg['category'] = 'DATA'
        return msg

    # Define periodic behavior
    def periodic_behavior(self):
        # Wait a random amount of time (up to 5secs) before starting
        time.sleep(random.randint(0,5))
        # Periodically publish data when connected
        msg_count = 0
        tic = time.perf_counter()
        while True :
            if not self.active :
                print(f'{self.name}[{self.uuid[0:6]}] inactive - Count={msg_count}, Last msg {tic-last_tic:.3f}s ago.', kind='') # print info
                while not self.active :
                    time.sleep(5)
            msg_count += 1
            last_tic = tic
            tic = time.perf_counter()
            msg = self.gen_msg() # generate message with random data
            self.client.publish(self.topic,json.dumps(msg, indent=4)) # publish it
            print(f'{self.name}[{self.uuid[0:6]}] msg to ({self.topic}) - Count={msg_count}, Last msg {tic-last_tic:.3f}s ago.', kind='info') # print info
            if self.print_logs :
                if msg_count == 1 :
                    print_device_data(msg['timestamp'],msg['data'])
            self.client.loop() # run client loop for callbacks to be processed
            time.sleep(self.interval) # wait till next execution
        
    # Thread execution
    def run(self):
        self.client = mqtt.Client(self.uuid) # create new client instance

        self.client.on_log = self.on_log # bind callback fn
        self.client.on_connect = self.on_connect # bind callback fn
        self.client.on_disconnect = self.on_disconnect # bind callback fn

        self.client.connect(broker_addr, port=broker_port) # connect to the broker
        self.client.loop() # run client loop for callbacks to be processed
        
        self.periodic_behavior() # start periodic behavior

#########################################
######## PRODUCTION LINE DEVICES ########
#########################################

# CONVEYOR BELT
class ConveyorBelt(IoTDevice):
    # Initialization
    def __init__ (self, topic=prodline_root, devuuid='', interval=5, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'ConveyorBelt'

    # Simulate data generation
    def gen_data(self) :
        status = True if random.uniform() < 0.9 else False

        return {
            'conveyor_belt' : {
                'status' : status,
                'linear_speed' : normal_th(3.5,0.5,[3,4]) if status else 0.0,
                'rotational_speed' : normal_th(24,0.5,[22,26]) if status else 0.0,
                'weight' : normal_th(10,0.5,[8,12])
            }
        }       

# TAG SCANNER
class TagScanner(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=60*3,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'TagScanner'
        
    # Simulate data generation
    def gen_data(self) :
        product_id = random.randint(0,10)

        return {
            'rfid_scanner' : {
                'product_id' : product_id,
                'process_id' : product_id
            }
        }

# PRODUCTION CONTROL
class ProductionControl(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=60*3,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'ProductionControl'

    # Simulate data generation
    def gen_data(self) :
        # Random status
        rand_val = random.uniform()
        if rand_val < 0.7 :
            status = True #'active'
        else :
            status = False #'paused'

        return {'production_control' : {'production_status' : status}}

# REPAIR CONTROL
class RepairControl(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=60*2,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'RepairControl'
        

    # Simulate data generation
    def gen_data(self) :
        # Random status
        rand_val = random.uniform()
        if rand_val < 0.1 :
            status = 0 #'done'
        elif rand_val < 0.6 :
            status = 1 #'ongoing' 
        else :
            status = 2 #'idle'

        return {'repair_control' : {'repair_status' : status}}
                  
# PRODUCT CONFIG SCANNER
class ConfigurationScanner(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=30,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'ConfigurationScanner'

    # Simulate data generation
    def gen_data(self) :
        return {
            'left_cam': {'config_status' : True if random.uniform() < 0.975 else False},
            'right_cam': {'config_status' : True if random.uniform() < 0.975 else False},
            'front_cam': {'config_status' : True if random.uniform() < 0.975 else False},
            'back_cam': {'config_status' : True if random.uniform() < 0.975 else False},
            'top_cam': {'config_status' : True if random.uniform() < 0.975 else False},
            'bottom_cam': {'config_status' : True if random.uniform() < 0.975 else False}
        }

# PRODUCT QUALITY SCANNER
class QualityScanner(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=30,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'QualityScanner'

    # Simulate data generation
    def gen_data(self) :
        return {
            'left_cam': {'quality_status' : True if random.uniform() < 0.975 else False},
            'right_cam': {'quality_status' : True if random.uniform() < 0.975 else False},
            'front_cam': {'quality_status' : True if random.uniform() < 0.975 else False},
            'back_cam': {'quality_status' : True if random.uniform() < 0.975 else False},
            'top_cam': {'quality_status' : True if random.uniform() < 0.975 else False},
            'bottom_cam': {'quality_status' : True if random.uniform() < 0.975 else False}
        }

# FAULT NOTIFIER
class FaultNotifier(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=30,focus='configuration',print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'FaultNotifier'
        # Data generation attributes
        self.focus = 0 if focus=='configuration' else 1

    # Simulate data generation
    def gen_data(self) :
        return {
            'fault_notifier': {
                'focus' : self.focus,
                'alarm' : False if random.uniform() < 0.975 else True
            }
        }

# POSE DETECTOR
class PoseDetector(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'PoseDetector'
        # Data generation attributes
        self.n_calls = 0
        self.last_pos = [0.0,0.0,0.0]
        self.last_ori = [0.0,0.0,0.0]

    # Simulate data generation
    def gen_data(self) :
        self.n_calls += 1
        # Every one minute focus on position of a different object
        if self.n_calls%60 == 0 :
            self.n_calls = 1
            self.last_pos = [normal_th(0,2,[-0.5,0.5]) for i in range(3)]
            self.last_ori = [normal_th(0,10,[-180,180]) for i in range(3)]
        else :
            self.last_pos = [normal_th(self.last_pos[i],0.01,[-0.5,0.5]) for i in range(3)]
            self.last_ori = [normal_th(self.last_ori[i],0.01,[-180,180]) for i in range(3)]

        return {
            'pose_detection_cam' : {
                'x_position' : self.last_pos[0], 'y_position' : self.last_pos[1], 'z_position' : self.last_pos[2],
                'roll_orientation' : self.last_ori[0], 'pitch_orientation' : self.last_ori[1], 'yaw_orientation' : self.last_ori[2]
            }
        }

# PIECE DETECTOR
class PieceDetector(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10,focus='parts',print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'PieceDetector'
        # Data generation attributes
        self.focus = 0 if focus == 'parts' else 1
        self.pieces = car_parts if self.focus == 0 else car_underpans
        self.n_calls = 0
        self.last_pos = [0.0,0.0,0.0]
        self.last_ori = [0.0,0.0,0.0]
        self.piece = self.pieces[random.randint(0,len(self.pieces))]

    # Simulate data generation
    def gen_data(self) :
        # Every one minute focus on position of a different object
        if self.n_calls%60 == 0 :
            self.n_calls = 1
            self.last_pos = [normal_th(0,2,[-0.5,0.5]) for i in range(3)]
            self.last_ori = [normal_th(0,10,[-180,180]) for i in range(3)]
            self.piece = random.randint(0,len(self.pieces))
        else :
            self.last_pos = [normal_th(self.last_pos[i],0.01,[-0.5,0.5]) for i in range(3)]
            self.last_ori = [normal_th(self.last_ori[i],0.01,[-180,180]) for i in range(3)]

        return {
            'piece_detection_cam' : {
                'focus' : self.focus,
                'piece_id' : self.piece,
                'x_position' : self.last_pos[0], 'y_position' : self.last_pos[1], 'z_position' : self.last_pos[2],
                'roll_orientation' : self.last_ori[0], 'pitch_orientation' : self.last_ori[1], 'yaw_orientation' : self.last_ori[2]
            }
        }

# PICK UP ROBOT
class PickUpRobot(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'PickUpRobot'
        # Data generation attributes
        self.n_actuator = 0
        self.actuator_status = False
        self.pos = [[0.0,0.0,0.0] for j in range(7)]
        self.ori = [[0.0,0.0,0.0] for j in range(7)]

    # Simulate data generation
    def gen_data(self) :
        self.pos = [[normal_th(self.pos[j][i],0.01,[-0.5,0.5]) for i in range(3)] for j in range(7)]
        self.ori = [[normal_th(self.ori[j][i],0.01,[-180,180]) for i in range(3)] for j in range(7)]

        if self.n_actuator%2 == 0 & self.n_actuator != 0 :
            self.n_actuator = 0
            self.actuator_status = False if random.uniform() < 0.6 else True
        elif self.actuator_status :
            self.n_actuator +=1

        return robot_data(self.pos,self.ori,self.actuator_status)

# CLAMPING ROBOT
class ClampingRobot(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'ClampingRobot'
        # Data generation attributes
        self.n_actuator = 0
        self.actuator_status = False
        self.pos = [[0.0,0.0,0.0] for j in range(7)]
        self.ori = [[0.0,0.0,0.0] for j in range(7)]

    # Simulate data generation
    def gen_data(self) :
        self.pos = [[normal_th(self.pos[j][i],0.01,[-0.5,0.5]) for i in range(3)] for j in range(7)]
        self.ori = [[normal_th(self.ori[j][i],0.01,[-180,180]) for i in range(3)] for j in range(7)]

        if self.n_actuator%2 == 0 & self.n_actuator != 0 :
            self.n_actuator = 0
            self.actuator_status = False if random.uniform() < 0.6 else True
        elif self.actuator_status :
            self.n_actuator +=1

        return robot_data(self.pos,self.ori,self.actuator_status)

# DRILLING ROBOT
class DrillingRobot(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'DrillingRobot'
        # Data generation attributes
        self.n_actuator = 0
        self.actuator_status = False
        self.pos = [[0.0,0.0,0.0] for j in range(7)]
        self.ori = [[0.0,0.0,0.0] for j in range(7)]

    # Simulate data generation
    def gen_data(self) :
        self.pos = [[normal_th(self.pos[j][i],0.01,[-0.5,0.5]) for i in range(3)] for j in range(7)]
        self.ori = [[normal_th(self.ori[j][i],0.01,[-180,180]) for i in range(3)] for j in range(7)]

        if self.n_actuator%2 == 0 & self.n_actuator != 0 :
            self.n_actuator = 0
            self.actuator_status = False if random.uniform() < 0.6 else True
        elif self.actuator_status :
            self.n_actuator +=1

        return robot_data(self.pos,self.ori,self.actuator_status)

# MILLING ROBOT
class MillingRobot(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'MillingRobot'
        # Data generation attributes
        self.n_actuator = 0
        self.actuator_status = False
        self.pos = [[0.0,0.0,0.0] for j in range(7)]
        self.ori = [[0.0,0.0,0.0] for j in range(7)]

    # Simulate data generation
    def gen_data(self) :
        self.pos = [[normal_th(self.pos[j][i],0.01,[-0.5,0.5]) for i in range(3)] for j in range(7)]
        self.ori = [[normal_th(self.ori[j][i],0.01,[-180,180]) for i in range(3)] for j in range(7)]

        if self.n_actuator%2 == 0 & self.n_actuator != 0 :
            self.n_actuator = 0
            self.actuator_status = False if random.uniform() < 0.6 else True
        elif self.actuator_status :
            self.n_actuator +=1

        return robot_data(self.pos,self.ori,self.actuator_status)


################################################
######## SAFETY / ENVIRONMENTAL DEVICES ########
################################################

# AIR QUALITY
class AirQuality(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=10,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'AirQuality'
        
    # Simulate data generation
    def gen_data(self) :
        return {
            'temperature_sensor' : {'temperature' : normal_th(20,0.25,[17,23])},
            'humidity_sensor' : {'humidity' : normal_th(30,0.25,[27.5,32.5])},
            'pressure_sensor' : {'pressure' : normal_th(101000,0.25,[99500,102500])},
            'air_quality_sensor' : {
                'pm1' : normal_th(1,0.5,[0.5,1.5]),
                'pm25' : normal_th(9,0.5,[6,12]),
                'pm10' : normal_th(18,0.5,[14,22])
            }
        }

# AIR QUALITY MODIFIED
class AirQualityModified(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=10,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'AirQualityModified'
        
    # Simulate data generation
    def gen_data(self) :
        return {
            'temperature_humidity_sensor' : {
                'temperature' : normal_th(21,0.25,[17,23]),
                'humidity' : normal_th(29,0.25,[27.5,32.5])
            },
            'air_quality_sensor' : {
                'pm25' : normal_th(8,0.5,[6,12]),
                'pm10' : normal_th(19,0.5,[14,22])
            }
        }

# NOISE SENSOR
class NoiseSensor(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=20,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'NoiseSensor'
        
    # Simulate data generation
    def gen_data(self) :
        return {'noise_sensor' : {'noise' : normal_th(70,2,[50,90])}}

# SMOKE SENSOR
class SmokeSensor(IoTDevice):
    ## Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=20,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'SmokeSensor'
        
    # Simulate data generation
    def gen_data(self) :
        return {'smoke_sensor' : {'smoke' : False if random.uniform() < 0.995 else True}}

# SEISMIC SENSOR
class SeismicSensor(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=20,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'SeismicSensor'
        
    # Simulate data generation
    def gen_data(self) :
        return {'seismic_sensor' : {'intensity' : random.randint(0,1) if random.uniform() < 0.999 else random.randint(2,8)}}

# RAIN SENSOR
class RainSensor(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=20,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'RainSensor'
        
    # Simulate data generation
    def gen_data(self) :
        return {'rain_sensor' : {'cumdepth' : normal_th(10,2,[0,50])}}

# WIND SENSOR
class WindSensor(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=20,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'WindSensor'
        
    # Simulate data generation
    def gen_data(self) :
        return {
            'wind_sensor' : {
                'speed' : normal_th(4,2,[0,15]),
                'direction' : normal_th(180,10,[0,360])
            }
        }

# INDOORS ALARM
class IndoorsAlarm(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=15,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'IndoorsAlarm'
        
    # Simulate data generation
    def gen_data(self) :
        return {
            'air_quality_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'temperature_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'humidity_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'fire_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'seismic_alarm' : {'status' : False if random.uniform() < 0.995 else True}
        }

# OUTDOORS ALARM
class OutdoorsAlarm(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=15,print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,print_logs)
        self.name = 'OutdoorsAlarm'
        
    # Simulate data generation
    def gen_data(self) :
        return {
            'air_quality_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'temperature_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'humidity_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'rain_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'wind_alarm' : {'status' : False if random.uniform() < 0.995 else True}
        }
