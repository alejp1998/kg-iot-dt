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
    def __init__(self,topic,devuuid,interval,modifier,print_logs):
        Thread.__init__(self)
        # Topic, publishing interval and log printing
        self.topic = topic
        self.interval = interval
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
        self.client.publish(self.topic,json.dumps(msg, indent=4))

    def on_disconnect(self, client, userdata, rc):
        print(f'{self.name}[{self.uuid[0:6]}] disconnected.', kind='fail')
        msg = fill_header_data(self.name,self.topic,self.uuid)
        msg['category'] = 'DISCONNECTED'
        self.client.publish(self.topic,json.dumps(msg, indent=4))

    # Message generation function
    def gen_msg(self):
        msg = fill_header_data(self.name,self.topic,self.uuid)
        msg['data'], dev_mod_uuids = fill_module_uuids(self.gen_new_data(),self.mod_uuids)
        msg['module_uuids'] = dev_mod_uuids
        msg['category'] = 'DATA'
        return msg

    # Generate data from a normal distribution between a min and a maximum value
    def sample_normal_th_mod(self,mu,sigma,th) :
        # Apply modification factor to values
        mu += mu*self.modifier
        sigma += sigma*self.modifier
        th = [th[0] + th[0]*self.modifier, th[1] + th[1]*self.modifier]

        # Generate random value within thresholds
        val = random.normal(mu,sigma)
        if val < th[0] :
            return th[0]
        elif val > th[1] :
            return th[1]
        else :
            return val

    # Define periodic behavior
    def periodic_behavior(self):
        # Wait a random amount of time (up to 5secs) before starting
        time.sleep(random.randint(0,5))
        # Periodically publish data when connected
        self.msg_count = 0
        tic = time.perf_counter()
        while True :
            if not self.active :
                print(f'{self.name}[{self.uuid[0:6]}] inactive - Count={self.msg_count}, Last msg {tic-last_tic:.3f}s ago.', kind='') # print info
                while not self.active :
                    time.sleep(5)
            self.msg_count += 1
            last_tic = tic
            tic = time.perf_counter()
            msg = self.gen_msg() # generate message with random data
            self.client.publish(self.topic,json.dumps(msg, indent=4)) # publish it
            print(f'{self.name}[{self.uuid[0:6]}] msg to ({self.topic}) - Count={self.msg_count}, Last msg {tic-last_tic:.3f}s ago.', kind='info') # print info
            if self.print_logs :
                if self.msg_count == 1 :
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
    def __init__ (self, topic=prodline_root, devuuid='', interval=5, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'ConveyorBelt'
        # Initial values
        self.conveyor_belt = {
            'status': True, 
            'lin_speed': self.sample_normal_th_mod(3.5,0.5,[3,4]), 
            'rot_speed': self.sample_normal_th_mod(24,0.5,[22,26]), 
            'weight': self.sample_normal_th_mod(10,0.5,[8,12])
        }
    
    # THE DEVICES SHOULD ALSO BE CONSTRUCTED DETERMINING THE LIST OF OTHER DEVICES OR TOPICS THEY 
    # ARE SUBSCRIBED TO, AND WHICH DEVICES ARE SUBSCRIBED TO THE TOPICS THE DEVICE PUBLISHES

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # CONVEYOR BELT MODULE
        self.conveyor_belt['status'] = coin(0.95) if self.conveyor_belt['status'] else coin(0.6)
        self.conveyor_belt['lin_speed'] = get_new_sample(self.conveyor_belt['lin_speed'])
        self.conveyor_belt['rot_speed'] = get_new_sample(self.conveyor_belt['rot_speed'])
        self.conveyor_belt['weight'] = get_new_sample(self.conveyor_belt['weight'])
        
        # Modifications based on status value
        conveyor_belt_copy = self.conveyor_belt.copy()
        conveyor_belt_copy['lin_speed'] = self.conveyor_belt['lin_speed'] if self.conveyor_belt['status'] else 0.0
        conveyor_belt_copy['rot_speed'] = self.conveyor_belt['rot_speed'] if self.conveyor_belt['status'] else 0.0
        
        # Return updated data dictionary
        return {'conveyor_belt' : conveyor_belt_copy}

# TAG SCANNER
class TagScanner(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=60*3, modifier=0.0, print_logs=False):
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
    def __init__(self,topic=prodline_root,devuuid='',interval=60*3, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'ProductionControl'
        # Initial values
        self.production_control = {'production_status' : True}

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # PRODUCTION CONTROL MODULE
        self.production_control['production_status'] = coin(0.95) if self.production_control['production_status'] else coin(0.6)
        
        # Return updated data dictionary
        return {'production_control' : self.production_control}

# REPAIR CONTROL
class RepairControl(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=60*2, modifier=0.0, print_logs=False):
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
    def __init__(self,topic=prodline_root,devuuid='',interval=30, modifier=0.0, print_logs=False):
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
    def __init__(self,topic=prodline_root,devuuid='',interval=30, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'QualityScanner'
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

# FAULT NOTIFIER
class FaultNotifier(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=30,focus='configuration', modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'FaultNotifier'
        # Initial data
        self.fault_notifier = {
            'focus': 0 if focus=='configuration' else 1,
            'alarm': False
        }

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # FAULT NOTIFIER MODULE
        self.fault_notifier['alarm'] = coin(0.05) if not self.fault_notifier['alarm'] else coin(0.6)
        
        # Return updated data dictionary
        return {'fault_notifier': self.fault_notifier}

# POSE DETECTOR
class PoseDetector(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'PoseDetector'
        # Initial data
        self.pose_detection_cam = {
            'x_position' : self.sample_normal_th_mod(0,2,[-0.5,0.5]), 
            'y_position' : self.sample_normal_th_mod(0,2,[-0.5,0.5]),  
            'z_position' : self.sample_normal_th_mod(0,2,[-0.5,0.5]),
            'roll_orientation' : self.sample_normal_th_mod(0,10,[-180,180]), 
            'pitch_orientation' : self.sample_normal_th_mod(0,10,[-180,180]), 
            'yaw_orientation' : self.sample_normal_th_mod(0,10,[-180,180])
        }

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # POSE DETECTION CAM MODULE
        for attrib in self.pose_detection_cam:
            if attrib == 'uuid':
                continue
            self.pose_detection_cam[attrib] = get_new_sample(self.pose_detection_cam[attrib])

        # Return updated data dictionary
        return {'pose_detection_cam' : self.pose_detection_cam}

# PIECE DETECTOR
class PieceDetector(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10,focus='parts', modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'PieceDetector'
        # Data generation attributes
        self.pieces = car_parts if focus == 'parts' else car_underpans
        # Initial values
        self.piece_detection_cam = {
            'focus' : 0 if focus == 'parts' else 1,
            'piece_id' : random.randint(0,len(self.pieces)),
            'x_position' : self.sample_normal_th_mod(0.5,2,[-0.5,0.5]),
            'y_position' : self.sample_normal_th_mod(0.5,2,[-0.5,0.5]), 
            'z_position' : self.sample_normal_th_mod(0.5,2,[-0.5,0.5]),
            'roll_orientation' : self.sample_normal_th_mod(0,5,[-180,180]),
            'pitch_orientation' : self.sample_normal_th_mod(0,5,[-180,180]),
            'yaw_orientation' : self.sample_normal_th_mod(0,5,[-180,180])
        }

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # PIECE DETECTION CAM MODULE
        for attrib in self.piece_detection_cam:
            if attrib in ['uuid','focus','piece_id'] :
                continue
            self.piece_detection_cam[attrib] = get_new_sample(self.piece_detection_cam[attrib])
        self.piece_detection_cam['piece_id'] = self.piece_detection_cam['piece_id'] if coin(0.7) else random.randint(0,len(self.pieces))

        # Return updated data dictionary
        return {'piece_detection_cam' : self.piece_detection_cam}

# PICK UP ROBOT
class PickUpRobot(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'PickUpRobot'
        # Initial data
        self.joint1 = self.init_joint_data(0,0)
        self.joint2 = self.init_joint_data(1,45)
        self.joint3 = self.init_joint_data(2,90)
        self.actuator = self.init_joint_data(3,135)
        self.actuator['actuator_status'] = False

    # Generate initial joint data
    def init_joint_data(self,mu1,mu2):
        sigma, th1, th2 = 2, [mu1-0.5, mu1+0.5], [mu2-15, mu2+15]
        joint_dic = {}
        for i_pos in ['x_position','y_position','z_position']:
            joint_dic[i_pos] = self.sample_normal_th_mod(mu1,sigma,th1)
        for i_ori in ['roll_orientation','pitch_orientation','yaw_orientation']:
            joint_dic[i_ori] = self.sample_normal_th_mod(mu2,sigma,th2)
        return joint_dic

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # JOINTS MODULES
        # JOINTS AND ACTUATOR MODULES
        for attrib in self.joint1:
            if attrib == 'uuid':
                continue
            self.joint1[attrib] = get_new_sample(self.joint1[attrib])
            self.joint2[attrib] = get_new_sample(self.joint2[attrib]) 
            self.joint3[attrib] = get_new_sample(self.joint3[attrib])
            self.actuator[attrib] = get_new_sample(self.actuator[attrib])
        self.actuator['actuator_status'] = coin(0.2) if not self.actuator['actuator_status'] else coin(0.4)

        # Return updated data dictionary
        return {'joint1':self.joint1,'joint2':self.joint2,'joint3':self.joint3,'actuator':self.actuator}

# CLAMPING ROBOT
class ClampingRobot(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'ClampingRobot'
        # Initial data
        self.joint1 = self.init_joint_data(0.25,10)
        self.joint2 = self.init_joint_data(1.25,55)
        self.joint3 = self.init_joint_data(2.25,100)
        self.actuator = self.init_joint_data(3.25,145)
        self.actuator['actuator_status'] = False

    # Generate initial joint data
    def init_joint_data(self,mu1,mu2,sigma):
        sigma, th1, th2 = 1, [mu1-0.5, mu1+0.5], [mu2-15, mu2+15]
        joint_dic = {}
        for i_pos in ['x_position','y_position','z_position']:
            joint_dic[i_pos] = self.sample_normal_th_mod(mu1,sigma,th1)
        for i_ori in ['roll_orientation','pitch_orientation','yaw_orientation']:
            joint_dic[i_ori] = self.sample_normal_th_mod(mu2,sigma,th2)
        return joint_dic

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # JOINTS AND ACTUATOR MODULES
        for attrib in self.joint1:
            if attrib == 'uuid':
                continue
            self.joint1[attrib] = get_new_sample(self.joint1[attrib])
            self.joint2[attrib] = get_new_sample(self.joint2[attrib]) 
            self.joint3[attrib] = get_new_sample(self.joint3[attrib])
            self.actuator[attrib] = get_new_sample(self.actuator[attrib])
        self.actuator['actuator_status'] = coin(0.15) if not self.actuator['actuator_status'] else coin(0.5)

        # Return updated data dictionary
        return {'joint1':self.joint1,'joint2':self.joint2,'joint3':self.joint3,'actuator':self.actuator}

# DRILLING ROBOT
class DrillingRobot(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'DrillingRobot'
        # Initial data
        self.joint1 = self.init_joint_data(0.5,20)
        self.joint2 = self.init_joint_data(1.5,65)
        self.joint3 = self.init_joint_data(2.5,110)
        self.actuator = self.init_joint_data(3.5,155)
        self.actuator['actuator_status'] = False

    # Generate initial joint data
    def init_joint_data(self,mu1,mu2):
        sigma, th1, th2 = 0.5, [mu1-0.5, mu1+0.5], [mu2-15, mu2+15]
        joint_dic = {}
        for i_pos in ['x_position','y_position','z_position']:
            joint_dic[i_pos] = self.sample_normal_th_mod(mu1,sigma,th1)
        for i_ori in ['roll_orientation','pitch_orientation','yaw_orientation']:
            joint_dic[i_ori] = self.sample_normal_th_mod(mu2,sigma,th2)
        return joint_dic

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # JOINTS AND ACTUATOR MODULES
        for attrib in self.joint1:
            if attrib == 'uuid':
                continue
            self.joint1[attrib] = get_new_sample(self.joint1[attrib])
            self.joint2[attrib] = get_new_sample(self.joint2[attrib]) 
            self.joint3[attrib] = get_new_sample(self.joint3[attrib])
            self.actuator[attrib] = get_new_sample(self.actuator[attrib])
        self.actuator['actuator_status'] = coin(0.25) if not self.actuator['actuator_status'] else coin(0.3)

        # Return updated data dictionary
        return {'joint1':self.joint1,'joint2':self.joint2,'joint3':self.joint3,'actuator':self.actuator}

# MILLING ROBOT
class MillingRobot(IoTDevice):
    # Initialization
    def __init__(self,topic=prodline_root,devuuid='',interval=10, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'MillingRobot'
        # Initial data
        self.joint1 = self.init_joint_data(0.75,30)
        self.joint2 = self.init_joint_data(1.75,75)
        self.joint3 = self.init_joint_data(2.75,120)
        self.actuator = self.init_joint_data(3.75,165)
        self.actuator['actuator_status'] = False

    # Generate initial joint data
    def init_joint_data(self,mu1,mu2):
        sigma, th1, th2 = 3, [mu1-0.5, mu1+0.5], [mu2-15, mu2+15]
        joint_dic = {}
        for i_pos in ['x_position','y_position','z_position']:
            joint_dic[i_pos] = self.sample_normal_th_mod(mu1,sigma,th1)
        for i_ori in ['roll_orientation','pitch_orientation','yaw_orientation']:
            joint_dic[i_ori] = self.sample_normal_th_mod(mu2,sigma,th2)
        return joint_dic

    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        # JOINTS MODULES
        for attrib in self.joint1:
            if attrib == 'uuid':
                continue
            self.joint1[attrib] = get_new_sample(self.joint1[attrib])
            self.joint2[attrib] = get_new_sample(self.joint2[attrib]) 
            self.joint3[attrib] = get_new_sample(self.joint3[attrib])

        # ACTUATOR MODULE
        for attrib in self.actuator:
            if attrib == 'actuator_status' :
                continue
            self.actuator[attrib] = get_new_sample(self.actuator[attrib])
        self.actuator['actuator_status'] = coin(0.1) if not self.actuator['actuator_status'] else coin(0.6)

        # Return updated data dictionary
        return {'joint1':self.joint1,'joint2':self.joint2,'joint3':self.joint3,'actuator':self.actuator}


################################################
######## SAFETY / ENVIRONMENTAL DEVICES ########
################################################

# AIR QUALITY
class AirQuality(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=10, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'AirQuality'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {
            'temperature_sensor' : {'temperature' : sample_normal_th(20,0.25,[17,23])},
            'humidity_sensor' : {'humidity' : sample_normal_th(30,0.25,[27.5,32.5])},
            'pressure_sensor' : {'pressure' : sample_normal_th(101000,0.25,[99500,102500])},
            'air_quality_sensor' : {
                'pm1' : sample_normal_th(1,0.5,[0.5,1.5]),
                'pm25' : sample_normal_th(9,0.5,[6,12]),
                'pm10' : sample_normal_th(18,0.5,[14,22])
            }
        }

# AIR QUALITY MODIFIED
class AirQualityModified(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=10, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'AirQualityModified'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {
            'temperature_humidity_sensor' : {
                'temperature' : sample_normal_th(21,0.25,[17,23]),
                'humidity' : sample_normal_th(29,0.25,[27.5,32.5])
            },
            'air_quality_sensor' : {
                'pm25' : sample_normal_th(8,0.5,[6,12]),
                'pm10' : sample_normal_th(19,0.5,[14,22])
            }
        }

# NOISE SENSOR
class NoiseSensor(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=20, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'NoiseSensor'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {'noise_sensor' : {'noise' : sample_normal_th(70,2,[50,90])}}

# SMOKE SENSOR
class SmokeSensor(IoTDevice):
    ## Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=20, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'SmokeSensor'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {'smoke_sensor' : {'smoke' : random.uniform() < 0.005}}

# SEISMIC SENSOR
class SeismicSensor(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=20, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'SeismicSensor'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {'seismic_sensor' : {'intensity' : random.randint(0,1) if random.uniform() < 0.95 else random.randint(2,8)}}

# RAIN SENSOR
class RainSensor(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=20, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'RainSensor'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {'rain_sensor' : {'cumdepth' : sample_normal_th(10,2,[0,50])}}

# WIND SENSOR
class WindSensor(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=20, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'WindSensor'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {
            'wind_sensor' : {
                'speed' : sample_normal_th(4,2,[0,15]),
                'direction' : sample_normal_th(180,10,[0,360])
            }
        }

# INDOORS ALARM
class IndoorsAlarm(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=15, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'IndoorsAlarm'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {
            'air_quality_alarm' : {'status' : random.uniform() < 0.005},
            'temperature_alarm' : {'status' : random.uniform() < 0.005},
            'humidity_alarm' : {'status' : random.uniform() < 0.005},
            'fire_alarm' : {'status' : random.uniform() < 0.005},
            'seismic_alarm' : {'status' : random.uniform() < 0.005}
        }

# OUTDOORS ALARM
class OutdoorsAlarm(IoTDevice):
    # Initialization
    def __init__(self,topic=safetyenv_root,devuuid='',interval=15, modifier=0.0, print_logs=False):
        IoTDevice.__init__(self,topic,devuuid,interval,modifier,print_logs)
        self.name = 'OutdoorsAlarm'
        
    # Simulate time series behavior around initial values
    def gen_new_data(self) :
        return {
            'air_quality_alarm' : {'status' : random.uniform() < 0.005},
            'temperature_alarm' : {'status' : random.uniform() < 0.005},
            'humidity_alarm' : {'status' : random.uniform() < 0.005},
            'rain_alarm' : {'status' : random.uniform() < 0.005},
            'wind_alarm' : {'status' : random.uniform() < 0.005}
        }
