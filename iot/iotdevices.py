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
    def __init__(self,devuuid='',print_logs=False):
        Thread.__init__(self)
        self.active = True
        self.uuid = re.sub(r'(\S{8})(\S{4})(\S{4})(\S{4})(.*)',r'\1-\2-\3-\4-\5',uuid.uuid4().hex) if devuuid=='' else devuuid  # assign unique identifier
        self.mod_uuids = [re.sub(r'(\S{8})(\S{4})(\S{4})(\S{4})(.*)',r'\1-\2-\3-\4-\5',uuid.uuid4().hex) for i in range(10)] # modules unique identifiers
        self.print_logs = print_logs

    # MQTT Callback Functions
    def on_log(client, userdata, level, buf):
        print("log: " + buf, kind='info')
        
    def on_connect(self, client, userdata, flags, rc):
        print(f'{self.name}[{self.uuid[0:6]}] connected.', kind='success')
        msg = fill_header_data(self.name,self.topic,self.uuid)
        msg['category'] = 'CONNECTED'
        self.client.publish(self.root+self.topic,json.dumps(msg, indent=4))

    def on_disconnect(self, client, userdata, rc):
        print(f'{self.name}[{self.uuid[0:6]}] disconnected.', kind='fail')
        msg = fill_header_data(self.name,self.topic,self.uuid)
        msg['category'] = 'DISCONNECTED'
        self.client.publish(self.root+self.topic,json.dumps(msg, indent=4))

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
            self.client.publish(self.root+self.topic,json.dumps(msg, indent=4)) # publish it
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
    def __init__ (self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'conveyorbelt'
        self.name = 'ConveyorBelt'
        self.interval = 5
        

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
    def __init__(self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'tagscanner'
        self.name = 'TagScanner'
        self.interval = 60*5 # interval between data reports
        
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
    def __init__(self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'productioncontrol'
        self.name = 'ProductionControl'
        self.interval = 60*5

    # Simulate data generation
    def gen_data(self) :
        # Random status
        rand_val = random.uniform()
        if rand_val < 0.6 :
            status = 'active'
        elif rand_val < 0.9 :
            status = 'paused' 
        else :
            status = 'idle'

        return {'production_control' : {'production_status' : status}}

# REPAIR CONTROL
class RepairControl(IoTDevice):
    # Initialization
    def __init__(self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'repaircontrol'
        self.name = 'RepairControl'
        self.interval = 60*2

    # Simulate data generation
    def gen_data(self) :
        # Random status
        rand_val = random.uniform()
        if rand_val < 0.1 :
            status = 'done'
        elif rand_val < 0.6 :
            status = 'ongoing' 
        else :
            status = 'idle'

        return {'repair_control' : {'repair_status' : status}}
                  
# PRODUCT CONFIG SCANNER
class ConfigurationScanner(IoTDevice):
    # Initialization
    def __init__(self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'configurationscanner'
        self.name = 'ConfigurationScanner'
        self.interval = 30

    # Simulate data generation
    def gen_data(self) :
        return {
            'left_cam': {'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'},
            'right_cam': {'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'},
            'front_cam': {'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'},
            'back_cam': {'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'},
            'top_cam': {'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'},
            'bottom_cam': {'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'}
        }

# PRODUCT QUALITY SCANNER
class QualityScanner(IoTDevice):
    # Initialization
    def __init__(self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'qualityscanner'
        self.name = 'QualityScanner'
        self.interval = 30

    # Simulate data generation
    def gen_data(self) :
        return {
            'left_cam': {'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'},
            'right_cam': {'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'},
            'front_cam': {'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'},
            'back_cam': {'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'},
            'top_cam': {'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'},
            'bottom_cam': {'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'}
        }

# FAULT NOTIFIER
class FaultNotifier(IoTDevice):
    # Initialization
    def __init__(self,focus,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'faultnotifier'
        self.name = 'FaultNotifier'
        self.interval = 30
        self.focus = focus

    # Simulate data generation
    def gen_data(self) :
        return {
            'fault_notifier': {
                'uuid': self.mod_uuids[0],
                'focus' : self.focus,
                'alarm' : False if random.uniform() < 0.975 else True
            }
        }

# POSE DETECTOR
class PoseDetector(IoTDevice):
    # Initialization
    def __init__(self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'posedetector'
        self.name = 'PoseDetector'
        self.interval = 5 # interval between data reports
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
                'position' : self.last_pos,
                'orientation' : self.last_ori
            }
        }

# PIECE DETECTOR
class PieceDetector(IoTDevice):
    # Initialization
    def __init__(self,focus,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'piecedetector'
        self.name = 'PieceDetector'
        self.focus = focus
        self.pieces = car_parts if self.focus == 'parts' else car_underpans
        self.interval = 5 # interval between data reports
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
            self.piece = self.pieces[random.randint(0,len(self.pieces))]
        else :
            self.last_pos = [normal_th(self.last_pos[i],0.01,[-0.5,0.5]) for i in range(3)]
            self.last_ori = [normal_th(self.last_ori[i],0.01,[-180,180]) for i in range(3)]

        return {
            'piece_detection_cam' : {
                'focus' : self.focus,
                'piece_id' : self.piece,
                'position' : self.last_pos,
                'orientation' : self.last_ori
            }
        }

# PICK UP ROBOT
class PickUpRobot(IoTDevice):
    # Initialization
    def __init__(self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'pickuprobot'
        self.name = 'PickUpRobot'
        self.actuator_name = 'picker'
        self.interval = 5 # interval between data reports
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
    def __init__(self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'clampingrobot'
        self.name = 'ClampingRobot'
        self.actuator_name = 'clamper'
        self.interval = 5 # interval between data reports
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
    def __init__(self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'drillingrobot'
        self.name = 'DrillingRobot'
        self.actuator_name = 'drill'
        self.interval = 5 # interval between data reports
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
    def __init__(self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = prodline_root
        self.topic = 'millingrobot'
        self.name = 'MillingRobot'
        self.actuator_name = 'mill'
        self.interval = 5 # interval between data reports
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
    def __init__ (self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = safetyenv_root
        self.topic = 'airquality'
        self.name = 'AirQuality'
        self.interval = 5 # interval between data reports
        
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
    def __init__ (self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = safetyenv_root
        self.topic = 'airqualitymodified'
        self.name = 'AirQualityModified'
        self.interval = 5 # interval between data reports
        
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
    def __init__ (self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = safetyenv_root
        self.topic = 'noisesensor'
        self.name = 'NoiseSensor'
        self.interval = 30 # interval between data reports
        
    # Simulate data generation
    def gen_data(self) :
        return {'noise_sensor' : {'noise' : normal_th(70,2,[50,90])}}

# SMOKE SENSOR
class SmokeSensor(IoTDevice):
    # Initialization
    def __init__ (self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = safetyenv_root
        self.topic = 'smokesensor'
        self.name = 'SmokeSensor'
        self.interval = 30 # interval between data reports
        
    # Simulate data generation
    def gen_data(self) :
        return {'smoke_sensor' : {'smoke' : False if random.uniform() < 0.995 else True}}

# SEISMIC SENSOR
class SeismicSensor(IoTDevice):
    # Initialization
    def __init__ (self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = safetyenv_root
        self.topic = 'seismicsensor'
        self.name = 'SeismicSensor'
        self.interval = 30 # interval between data reports
        
    # Simulate data generation
    def gen_data(self) :
        return {'seismic_sensor' : {'intensity' : random.randint(0,1) if random.uniform() < 0.999 else random.randint(2,8)}}

# RAIN SENSOR
class RainSensor(IoTDevice):
    # Initialization
    def __init__ (self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = safetyenv_root
        self.topic = 'rainsensor'
        self.name = 'RainSensor'
        self.interval = 30 # interval between data reports
        
    # Simulate data generation
    def gen_data(self) :
        return {'rain_sensor' : {'cumdepth' : normal_th(10,2,[0,50])}}

# WIND SENSOR
class WindSensor(IoTDevice):
    # Initialization
    def __init__ (self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = safetyenv_root
        self.topic = 'windsensor'
        self.name = 'WindSensor'
        self.interval = 30 # interval between data reports
        
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
    def __init__ (self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = safetyenv_root
        self.topic = 'indoorsalarm'
        self.name = 'IndoorsAlarm'
        self.interval = 15 # interval between data reports
        
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
    def __init__ (self,devuuid='',print_logs=False):
        IoTDevice.__init__(self,devuuid,print_logs)
        self.root = safetyenv_root
        self.topic = 'outdoorsalarm'
        self.name = 'OutdoorsAlarm'
        self.interval = 15 # interval between data reports
        
    # Simulate data generation
    def gen_data(self) :
        return {
            'air_quality_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'temperature_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'humidity_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'rain_alarm' : {'status' : False if random.uniform() < 0.995 else True},
            'wind_alarm' : {'status' : False if random.uniform() < 0.995 else True}
        }
