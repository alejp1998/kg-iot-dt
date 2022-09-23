#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" IoT Devices Simulation
In this module a IoT Device Class implementing a MQTT Client is defined. 
This class is then inherited by several device subclasses such as robotic arms or scanners, that publish their simulated data
updates to the MQTT network. The network messages have a JSON format, that includes an SDF description of the device reporting 
the data. In this SDF description we can find a description of the type of device, the modules it implements, and the type of data 
these modules report to the network. 

The simulation of the data samples is done through the sampling from random distributions that are adapted to the type of the data (such as temperature, 
position, or speed). It is also important to mention that these devices generate data independently, instead of being affected by what is being
observed or measured in other devices, since the focus of these project is not this interaction between devices, but the identification and integration
of new devices (as well as changes in the current devices) into the Knowledge Base structure.
"""
# ---------------------------------------------------------------------------
# Imports 
from threading import Thread
import paho.mqtt.client as mqtt
from numpy import random
from datetime import datetime
import re
import time
import uuid
import json
# ---------------------------------------------------------------------------

# Root topics for publishing
prodline_root = 'productionline/'
safetyenv_root = 'safetyenvironmental/'

# Auxiliary vars
car_parts = ['door','window','wheel','seat','mirror']
car_underpans = ['S60','S80','V60','XC60','XC70']
broker_addr = '0.0.0.0' # broker_addr = 'mosquitto'
broker_port = 8883

###################################
######## IOT DEVICES CLASS ########
###################################

# IoT Device Class to Inherit
class IoTDevice(Thread) :
    # Initialization
    def __init__(self,uid=''):
        Thread.__init__(self)
        self.uid = re.sub(r'(\S{8})(\S{4})(\S{4})(\S{4})(.*)',r'\1-\2-\3-\4-\5',uuid.uuid4().hex) if uid=='' else uid  # assign unique identifier
        self.mod_uids = [re.sub(r'(\S{8})(\S{4})(\S{4})(\S{4})(.*)',r'\1-\2-\3-\4-\5',uuid.uuid4().hex) for i in range(10)] # modules unique identifiers

    # MQTT Callback Functions
    def on_log(client, userdata, level, buf):
        print("log: " + buf)
        
    def on_connect(self, client, userdata, flags, rc):
        print("{}[{}] connected.".format(self.device_name,self.uid[0:6]))
        # print(self.device_desc)
        self.client.publish(self.root+self.topic,json.dumps(self.device_desc, indent=4))

    def on_disconnect(self, client, userdata, rc):
        print("{}[{}] disconnected.".format(self.device_name,self.uid[0:6]))
        #self.client.connect(broker_addr, port=broker_port) # connect to the broker
        #self.client.loop() # run client loop for callbacks to be processed
        #self.periodic_behavior() # start periodic behavior

    # Define periodic behavior
    def periodic_behavior(self):
        # Wait a random amount of time (up to 5secs) before starting
        time.sleep(random.randint(0,5))
        # Periodically publish data when connected
        while True :
            json_data = self.gen_data()
            self.client.publish(self.root+self.topic,json_data)
            print("{}[{}] -> ({}).".format(self.device_name,self.uid[0:6],self.topic))
            #print(json_data)
            self.client.loop() # run client loop for callbacks to be processed
            time.sleep(self.interval)
    
    # Thread execution
    def run(self):
        self.client = mqtt.Client(self.uid) # create new client instance

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
    def __init__ (self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'conveyorbelt'
        self.device_name = 'Conveyor Belt'
        self.interval = 5
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())
        

    # Simulate data generation
    def gen_data(self) :
        status = True if random.uniform() < 0.9 else False
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'conveyor_belt' : {
                    'uid': self.mod_uids[0],
                    'status' : status,
                    'linear_speed' : normal_th(3.5,0.5,[3,4]) if status else 0.0,
                    'rotational_speed' : normal_th(24,0.5,[22,26]) if status else 0.0,
                    'weight' : normal_th(10,0.5,[8,12])
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)            

# TAG SCANNER
class TagScanner(IoTDevice):
    # Initialization
    def __init__(self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'tagscanner'
        self.device_name = 'Tag Scanner'
        self.interval = 60*5 # interval between data reports
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())
        
    # Simulate data generation
    def gen_data(self) :
        product_id = random.randint(0,10)
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'rfid_scanner' : {
                    'uid': self.mod_uids[0],
                    'product_id' : product_id,
                    'process_id' : product_id
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# PRODUCTION CONTROL
class ProductionControl(IoTDevice):
    # Initialization
    def __init__(self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'productioncontrol'
        self.device_name = 'Production Control'
        self.interval = 60*5
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())

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

        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'production_control' : {
                    'uid': self.mod_uids[0],
                    'production_status' : status
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# REPAIR CONTROL
class RepairControl(IoTDevice):
    # Initialization
    def __init__(self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'repaircontrol'
        self.device_name = 'Repair Control'
        self.interval = 60*2
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())

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

        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'repair_control' : {
                    'uid': self.mod_uids[0],
                    'repair_status' : status
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)
                  
# PRODUCT CONFIG SCANNER
class ConfigurationScanner(IoTDevice):
    # Initialization
    def __init__(self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'configurationscanner'
        self.device_name = 'Configuration Scanner'
        self.interval = 30
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())

    # Simulate data generation
    def gen_data(self) :
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'left_cam': {
                    'uid': self.mod_uids[0],
                    'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'
                },
                'right_cam': {
                    'uid': self.mod_uids[1],
                    'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'
                },
                'front_cam': {
                    'uid': self.mod_uids[2],
                    'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'
                },
                'back_cam': {
                    'uid': self.mod_uids[3],
                    'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'
                },
                'top_cam': {
                    'uid': self.mod_uids[4],
                    'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'
                },
                'bottom_cam': {
                    'uid': self.mod_uids[5],
                    'config_status' : 'correct' if random.uniform() < 0.975 else 'incorrect'
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# PRODUCT QUALITY SCANNER
class QualityScanner(IoTDevice):
    # Initialization
    def __init__(self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'qualityscanner'
        self.device_name = 'Quality Scanner'
        self.interval = 30
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())

    # Simulate data generation
    def gen_data(self) :
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'left_cam': {
                    'uid': self.mod_uids[0],
                    'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'
                },
                'right_cam': {
                    'uid': self.mod_uids[1],
                    'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'
                },
                'front_cam': {
                    'uid': self.mod_uids[2],
                    'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'
                },
                'back_cam': {
                    'uid': self.mod_uids[3],
                    'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'
                },
                'top_cam': {
                    'uid': self.mod_uids[4],
                    'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'
                },
                'bottom_cam': {
                    'uid': self.mod_uids[5],
                    'quality_status' : 'correct' if random.uniform() < 0.99 else 'incorrect'
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# FAULT NOTIFIER
class FaultNotifier(IoTDevice):
    # Initialization
    def __init__(self,focus,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'faultnotifier'
        self.device_name = 'Fault Notifier'
        self.interval = 30
        self.focus = focus
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())

    # Simulate data generation
    def gen_data(self) :
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'fault_notifier': {
                    'uid': self.mod_uids[0],
                    'focus' : self.focus,
                    'alarm' : False if random.uniform() < 0.975 else True
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# POSE DETECTOR
class PoseDetector(IoTDevice):
    # Initialization
    def __init__(self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'posedetector'
        self.device_name = 'Pose Detector'
        self.interval = 5 # interval between data reports
        self.n_calls = 0
        self.last_pos = [0.0,0.0,0.0]
        self.last_ori = [0.0,0.0,0.0]
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())

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

        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'pose_detection_cam' : {
                    'uid': self.mod_uids[0],
                    'object_position' : self.last_pos,
                    'object_orientation' : self.last_ori
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# PIECE DETECTOR
class PieceDetector(IoTDevice):
    # Initialization
    def __init__(self,focus,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'piecedetector'
        self.device_name = 'Piece Detector'
        self.focus = focus
        self.pieces = car_parts if self.focus == 'parts' else car_underpans
        self.interval = 5 # interval between data reports
        self.n_calls = 0
        self.last_pos = [0.0,0.0,0.0]
        self.last_ori = [0.0,0.0,0.0]
        self.piece = self.pieces[random.randint(0,len(self.pieces))]
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())

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

        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'piece_detection_cam' : {
                    'uid': self.mod_uids[0],
                    'focus' : self.focus,
                    'piece_id' : self.piece,
                    'piece_position' : self.last_pos,
                    'piece_orientation' : self.last_ori
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# PICK UP ROBOT
class PickUpRobot(IoTDevice):
    # Initialization
    def __init__(self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'pickuprobot'
        self.device_name = 'Pick Up Robot'
        self.actuator_name = 'picker'
        self.interval = 5 # interval between data reports
        self.n_actuator = 0
        self.actuator_status = False
        self.pos = [[0.0,0.0,0.0] for j in range(7)]
        self.ori = [[0.0,0.0,0.0] for j in range(7)]
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())

    # Simulate data generation
    def gen_data(self) :
        self.pos = [[normal_th(self.pos[j][i],0.01,[-0.5,0.5]) for i in range(3)] for j in range(7)]
        self.ori = [[normal_th(self.ori[j][i],0.01,[-180,180]) for i in range(3)] for j in range(7)]

        if self.n_actuator%2 == 0 & self.n_actuator != 0 :
            self.n_actuator = 0
            self.actuator_status = False if random.uniform() < 0.6 else True
        elif self.actuator_status :
            self.n_actuator +=1

        data = robot_data(self.topic,self.device_desc,self.uid,self.mod_uids,self.device_name,self.pos,self.ori,self.actuator_name,self.actuator_status)
        return json.dumps(data, indent=4)

# CLAMPING ROBOT
class ClampingRobot(IoTDevice):
    # Initialization
    def __init__(self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'clampingrobot'
        self.device_name = 'Clamping Robot'
        self.actuator_name = 'clamper'
        self.interval = 5 # interval between data reports
        self.n_actuator = 0
        self.actuator_status = False
        self.pos = [[0.0,0.0,0.0] for j in range(7)]
        self.ori = [[0.0,0.0,0.0] for j in range(7)]
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())

    # Simulate data generation
    def gen_data(self) :
        self.pos = [[normal_th(self.pos[j][i],0.01,[-0.5,0.5]) for i in range(3)] for j in range(7)]
        self.ori = [[normal_th(self.ori[j][i],0.01,[-180,180]) for i in range(3)] for j in range(7)]

        if self.n_actuator%2 == 0 & self.n_actuator != 0 :
            self.n_actuator = 0
            self.actuator_status = False if random.uniform() < 0.6 else True
        elif self.actuator_status :
            self.n_actuator +=1

        data = robot_data(self.topic,self.device_desc,self.uid,self.mod_uids,self.device_name,self.pos,self.ori,self.actuator_name,self.actuator_status)
        return json.dumps(data, indent=4)

# DRILLING ROBOT
class DrillingRobot(IoTDevice):
    # Initialization
    def __init__(self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'drillingrobot'
        self.device_name = 'Drilling Robot'
        self.actuator_name = 'drill'
        self.interval = 5 # interval between data reports
        self.n_actuator = 0
        self.actuator_status = False
        self.pos = [[0.0,0.0,0.0] for j in range(7)]
        self.ori = [[0.0,0.0,0.0] for j in range(7)]
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())

    # Simulate data generation
    def gen_data(self) :
        self.pos = [[normal_th(self.pos[j][i],0.01,[-0.5,0.5]) for i in range(3)] for j in range(7)]
        self.ori = [[normal_th(self.ori[j][i],0.01,[-180,180]) for i in range(3)] for j in range(7)]

        if self.n_actuator%2 == 0 & self.n_actuator != 0 :
            self.n_actuator = 0
            self.actuator_status = False if random.uniform() < 0.6 else True
        elif self.actuator_status :
            self.n_actuator +=1

        data = robot_data(self.topic,self.device_desc,self.uid,self.mod_uids,self.device_name,self.pos,self.ori,self.actuator_name,self.actuator_status)
        return json.dumps(data, indent=4)

# MILLING ROBOT
class MillingRobot(IoTDevice):
    # Initialization
    def __init__(self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = prodline_root
        self.topic = 'millingrobot'
        self.device_name = 'Milling Robot'
        self.actuator_name = 'mill'
        self.interval = 5 # interval between data reports
        self.n_actuator = 0
        self.actuator_status = False
        self.pos = [[0.0,0.0,0.0] for j in range(7)]
        self.ori = [[0.0,0.0,0.0] for j in range(7)]
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())

    # Simulate data generation
    def gen_data(self) :
        self.pos = [[normal_th(self.pos[j][i],0.01,[-0.5,0.5]) for i in range(3)] for j in range(7)]
        self.ori = [[normal_th(self.ori[j][i],0.01,[-180,180]) for i in range(3)] for j in range(7)]

        if self.n_actuator%2 == 0 & self.n_actuator != 0 :
            self.n_actuator = 0
            self.actuator_status = False if random.uniform() < 0.6 else True
        elif self.actuator_status :
            self.n_actuator +=1

        data = robot_data(self.topic,self.device_desc,self.uid,self.mod_uids,self.device_name,self.pos,self.ori,self.actuator_name,self.actuator_status)
        return json.dumps(data, indent=4)


################################################
######## SAFETY / ENVIRONMENTAL DEVICES ########
################################################

# AIR QUALITY SENSOR
class AirQualitySensor(IoTDevice):
    # Initialization
    def __init__ (self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = safetyenv_root
        self.topic = 'airqualitysensor'
        self.device_name = 'Air Quality Sensor'
        self.interval = 30 # interval between data reports
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())
        
    # Simulate data generation
    def gen_data(self) :
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'temperature_sensor' : {
                    'uid': self.mod_uids[0],
                    'temperature' : normal_th(20,0.25,[17,23])
                },
                'humidity_sensor' : {
                    'uid': self.mod_uids[1],
                    'humidity' : normal_th(30,0.25,[27.5,32.5])
                },
                'pressure_sensor' : {
                    'uid': self.mod_uids[2],
                    'pressure' : normal_th(101000,0.25,[99500,102500])
                },
                'airquality_sensor' : {
                    'uid': self.mod_uids[3],
                    'pm1' : normal_th(1,0.5,[0.5,1.5]),
                    'pm25' : normal_th(9,0.5,[6,12]),
                    'pm10' : normal_th(18,0.5,[14,22]),
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# NOISE SENSOR
class NoiseSensor(IoTDevice):
    # Initialization
    def __init__ (self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = safetyenv_root
        self.topic = 'noisesensor'
        self.device_name = 'Noise Sensor'
        self.interval = 30 # interval between data reports
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())
        
    # Simulate data generation
    def gen_data(self) :
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'noise_sensor' : {
                    'uid': self.mod_uids[0],
                    'noise' : normal_th(70,2,[50,90])
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# SMOKE SENSOR
class SmokeSensor(IoTDevice):
    # Initialization
    def __init__ (self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = safetyenv_root
        self.topic = 'smokesensor'
        self.device_name = 'Smoke Sensor'
        self.interval = 30 # interval between data reports
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())
        
    # Simulate data generation
    def gen_data(self) :
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'smoke_sensor' : {
                    'uid': self.mod_uids[0],
                    'smoke' : False if random.uniform() < 0.995 else True
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# SEISMIC SENSOR
class SeismicSensor(IoTDevice):
    # Initialization
    def __init__ (self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = safetyenv_root
        self.topic = 'seismicsensor'
        self.device_name = 'Seismic Sensor'
        self.interval = 30 # interval between data reports
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())
        
    # Simulate data generation
    def gen_data(self) :
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'seismic_sensor' : {
                    'uid': self.mod_uids[0],
                    'intensity' : random.randint(0,1) if random.uniform() < 0.999 else random.randint(2,8)
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# RAIN SENSOR
class RainSensor(IoTDevice):
    # Initialization
    def __init__ (self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = safetyenv_root
        self.topic = 'rainsensor'
        self.device_name = 'Rain Sensor'
        self.interval = 30 # interval between data reports
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())
        
    # Simulate data generation
    def gen_data(self) :
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'rain_sensor' : {
                    'uid': self.mod_uids[0],
                    'cumdepth' : normal_th(10,2,[0,50])
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# WIND SENSOR
class WindSensor(IoTDevice):
    # Initialization
    def __init__ (self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = safetyenv_root
        self.topic = 'windsensor'
        self.device_name = 'Wind Sensor'
        self.interval = 30 # interval between data reports
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())
        
    # Simulate data generation
    def gen_data(self) :
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'wind_sensor' : {
                    'uid': self.mod_uids[0],
                    'speed' : normal_th(4,2,[0,15]),
                    'direction' : normal_th(180,10,[0,360])
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# INDOORS ALARM
class IndoorsAlarm(IoTDevice):
    # Initialization
    def __init__ (self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = safetyenv_root
        self.topic = 'indoorsalarm'
        self.device_name = 'Indoors Alarm'
        self.interval = 15 # interval between data reports
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())
        
    # Simulate data generation
    def gen_data(self) :
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'airquality_alarm' : {
                    'uid': self.mod_uids[0],
                    'status' : False if random.uniform() < 0.995 else True
                },
                'temperature_alarm' : {
                    'uid': self.mod_uids[1],
                    'status' : False if random.uniform() < 0.995 else True
                },
                'humidity_alarm' : {
                    'uid': self.mod_uids[2],
                    'status' : False if random.uniform() < 0.995 else True
                },
                'fire_alarm' : {
                    'uid': self.mod_uids[3],
                    'status' : False if random.uniform() < 0.995 else True
                },
                'seismic_alarm' : {
                    'uid': self.mod_uids[4],
                    'status' : False if random.uniform() < 0.995 else True
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)

# OUTDOORS ALARM
class OutdoorsAlarm(IoTDevice):
    # Initialization
    def __init__ (self,uid=''):
        IoTDevice.__init__(self,uid)
        self.root = safetyenv_root
        self.topic = 'outdoorsalarm'
        self.device_name = 'Outdoors Alarm'
        self.interval = 15 # interval between data reports
        with open('sdfObject/'+self.topic+'.sdf.json', 'r') as sdf_json_desc:
            self.device_desc = json.loads(sdf_json_desc.read())
        
    # Simulate data generation
    def gen_data(self) :
        data = {
            'topic' : self.topic,
            'sdf': self.device_desc,
            'uid' : self.uid,
            'device_name' : self.device_name,
            'data' : {
                'airquality_alarm' : {
                    'uid': self.mod_uids[0],
                    'status' : False if random.uniform() < 0.995 else True
                },
                'temperature_alarm' : {
                    'uid': self.mod_uids[1],
                    'status' : False if random.uniform() < 0.995 else True
                },
                'humidity_alarm' : {
                    'uid': self.mod_uids[2],
                    'status' : False if random.uniform() < 0.995 else True
                },
                'rain_alarm' : {
                    'uid': self.mod_uids[3],
                    'status' : False if random.uniform() < 0.995 else True
                },
                'wind_alarm' : {
                    'uid': self.mod_uids[4],
                    'status' : False if random.uniform() < 0.995 else True
                },
                'time_control': {
                    'uid': self.mod_uids[9],
                    'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
                }
            }
        }
        return json.dumps(data, indent=4)


#####################################
######## AUXILIARY FUNCTIONS ########
#####################################

# Generate data from a normal distribution between a min and a maximum value
def normal_th(mu,sigma,th) :
    value = random.normal(mu,sigma)
    if value < th[0] :
        return th[0]
    elif value > th[1] :
        return th[1]
    else :
        return round(value,5)

# Generate random position data within a defined zone
def random_position() :
    return [0.0, 0.0, 0.0]

# Generate random orientation data within a given zone
def random_orientation() :
    return [0.0, 0.0, 0.0]

def robot_data(topic,dev_desc,uid,mod_uids,dev_name,pos,ori,actuator_name,actuator_status) :
    return {
        'topic' : topic,
        'sdf': dev_desc,
        'uid' : uid,
        'device_name' : dev_name,
        'data' : {
            'joint1' : {
                'uid': mod_uids[0],
                'position' : pos[0],
                'orientation' : ori[0]
            },
            'joint2' : {
                'uid': mod_uids[1],
                'position' : pos[1],
                'orientation' : ori[1]
            },
            'joint3' : {
                'uid': mod_uids[2],
                'position' : pos[2],
                'orientation' : ori[2]
            },
            'joint4' : {
                'uid': mod_uids[3],
                'position' : pos[3],
                'orientation' : ori[3]
            },
            'joint5' : {
                'uid': mod_uids[4],
                'position' : pos[4],
                'orientation' : ori[4]
            },
            'joint6' : {
                'uid': mod_uids[5],
                'position' : pos[5],
                'orientation' : ori[5]
            },
            actuator_name : {
                'uid': mod_uids[6],
                'status' : actuator_status,
                'position' : pos[6],
                'orientation' : ori[6]
            },
            'time_control': {
                'uid': mod_uids[9],
                'timestamp' : datetime.now(tz=None).strftime("%Y-%m-%dT%H:%M:%S")
            }

        }
    }


######################
######## MAIN ########
######################

# PRODUCTION LINE
# Initialization Task
TagScanner(uid="8a40d136-8401-41bd-9845-7dc8f28ea582").start()
ProductionControl(uid="3d193d4c-ba9c-453e-b98b-cec9546b9182").start()

# Underpan Configuration Task
PickUpRobot(uid="5f3333b9-8292-4371-b5c5-c1ec21d0b652").start()
PieceDetector('underpans',uid="45d289e7-4da6-4c10-aa6e-2c1d48b223e2").start()

# Body Configuration Task
PickUpRobot(uid="da0ba61c-a9bf-4e0d-b975-33b7b4c5d2e8").start()
ClampingRobot(uid="5ee2149f-ef6e-402b-937e-8e04a2133cdd").start()
DrillingRobot(uid="98247600-c4fe-4728-bda6-ed8fadf81af2").start()
PieceDetector('parts',uid="d7295016-4a54-4c98-a4c1-4f0c7f7614b5").start()
PoseDetector(uid="2c91bd9d-bdfc-4a6b-b465-575f43897d59").start()

# Vehicle Scanning
ConfigurationScanner(uid="0d451573-243e-423b-bfab-0f3117f88bd0").start()
FaultNotifier('configuration',uid="f1b43cb8-127a-43b5-905d-9f145171079es").start()

# Window Milling
PickUpRobot(uid="6625b9ac-55e2-49c8-ab47-d1da21b5f0b5").start()
MillingRobot(uid="5ce94c31-3004-431e-97b3-c8f779fb180d").start()
PoseDetector(uid="1df9566a-2f06-48f0-975f-28058c6784c0").start()

# Quality Check
QualityScanner(uid="fd9ccbb2-be41-4507-85ac-a431fe886541").start()
FaultNotifier('quality',uid="5bb02f4b-0dfe-45d4-8a87-e902e6ea0bf6").start()

# Artificial Repair
RepairControl(uid="4525aa12-06fb-484f-be38-58afb33e1558").start()

# Product Completion
PickUpRobot(uid="ae5e4ad3-bd59-4dc8-b242-e72747d187d4").start()
PoseDetector(uid="f2d73019-1e87-48a7-b93c-af0a4fc17994").start()

# Tasks Connectors
ConveyorBelt(uid="fbeaa5f3-e532-4e02-8429-c77301f46470").start()
ConveyorBelt(uid="f169a965-bb15-4db3-97cd-49b5b641a9fe").start()
ConveyorBelt(uid="3140ce5c-0d08-4aff-9bb4-14a9e6a33d12").start()
ConveyorBelt(uid="a6f65d7a-019a-4723-9b81-fb4a163fa23a").start()
ConveyorBelt(uid="f342e60b-6a54-4f20-8874-89a550ebc75c").start()

# SAFETY / ENVIRONMENTAL
# Indoors Monitorization
AirQualitySensor(uid="5362cb80-381d-4d21-87ba-af283640fa98").start()
NoiseSensor(uid="7fc17e8f-1e1c-43f8-a2d1-9ff4bcfbf9ff").start()
SmokeSensor(uid="5a84f26b-bf77-42d3-ab8a-83a214112844").start()
SeismicSensor(uid="4f1f6ac2-f565-42af-a186-db17f7ed94c2").start()

# Outdoors Monitorization
AirQualitySensor(uid="d4a988d9-307d-419d-b50d-1491358764e5").start()
RainSensor(uid="d4a988d9-307d-419d-b50d-1491358764e5").start()
WindSensor(uid="f41db548-3a85-491e-ada6-bab5c106ced6").start()

# Safety Alarms
IndoorsAlarm(uid="4d36d0c4-891f-44ec-afe1-278258058944").start()
OutdoorsAlarm(uid="b60108c2-46a3-4b67-9b8d-38586cb3039d").start()
