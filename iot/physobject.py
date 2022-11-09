#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" Physical Object Example
The simulation of the data samples is done through the sampling from random distributions that are adapted to the type of the data (such as temperature, 
position, or speed). It is also important to mention that these devices generate data independently, instead of being affected by what is being
observed or measured in other devices, since the focus of these project is not this interaction between devices, but the identification and integration
of new devices (as well as changes in the current devices) into the Knowledge Base structure.
"""
# ---------------------------------------------------------------------------
# Imports
from iotdevices import *
# ---------------------------------------------------------------------------

# PARAMETERS FOR DATA GENERATION DEPENDING ON TASK
# PRODUCTION LINE - Sine Waves
prod_underpan_params = {
    'pickup': (1,2.0,0.25,3*np.pi/2), #(offset,amplitude,period,phase_shift)
    'piece_det': (2,1.5,0.5,0) #(offset,amplitude,period,phase_shift)
}
prod_body_params = { 
    'pickup': (0,1.0,0.25,0), #(offset,amplitude,period,phase_shift)
    'drilling': (0,2.0,0.5,np.pi/2), #(offset,amplitude,period,phase_shift)
    'clamping': (0,3.0,0.75,np.pi), #(offset,amplitude,period,phase_shift)
    'piece_det' : (2,1.5,0.5,0), #(offset,amplitude,period,phase_shift)
    'pose_det': (1,0.5,0.25,np.pi) #(offset,amplitude,period,phase_shift)
}
prod_window_params = {
    'pickup': (1,0.5,0.25,np.pi/2), #(offset,amplitude,period,phase_shift)
    'milling': (0,0.5,0.125,0), #(offset,amplitude,period,phase_shift)
    'pose_det': (1,0.5,0.25,np.pi) #(offset,amplitude,period,phase_shift)
}
prod_completion_params = {
    'pickup': (-1,1.5,0.25,np.pi/2), #(offset,amplitude,period,phase_shift)
    'pose_det': (0,3,0.25,3*np.pi/2) #(offset,amplitude,period,phase_shift)
}

# SAFETY / ENVIRONMENTAL - Normal Time Series
safetyenv_indoor_vars = { #(mean, standard deviation)
    'temperature': (20,0.25),
    'humidity': (25,0.5),
    'pressure': (1.013,0.3),
    'pm1': (1,0.5),
    'pm25': (9,0.5),
    'pm10': (18,0.5),
}
safetyenv_outdoor_vars = { #(mean, standard deviation)
    'temperature': (10,0.25),
    'humidity': (50,1.0),
    'pressure': (1.013,0.1),
    'pm1': (1.25,0.5),
    'pm25': (10,0.5),
    'pm10': (20,0.5),
    'rain_cumdepth': (10,2),
    'wind_speed': (6,2),
    'wind_direction': (180,10)
}

######################
######## MAIN ########
######################
def main() :
    
    # PRODUCTION LINE - INITIAL DEVICES
    # Initialization Task
    TagScanner(devuuid="8a40d136-8401-41bd-9845-7dc8f28ea582").start()
    ProductionControl(devuuid="3d193d4c-ba9c-453e-b98b-cec9546b9182").start()

    # Underpan Configuration Task
    PickUpRobot(prod_underpan_params,devuuid="5f3333b9-8292-4371-b5c5-c1ec21d0b652").start()
    PieceDetector(prod_underpan_params,devuuid="45d289e7-4da6-4c10-aa6e-2c1d48b223e2").start()

    # Body Configuration Task
    PickUpRobot(prod_body_params,devuuid="da0ba61c-a9bf-4e0d-b975-33b7b4c5d2e8").start()
    ClampingRobot(prod_body_params,devuuid="5ee2149f-ef6e-402b-937e-8e04a2133cdd").start()
    DrillingRobot(prod_body_params,devuuid="98247600-c4fe-4728-bda6-ed8fadf81af2").start()
    PieceDetector(prod_body_params,devuuid="d7295016-4a54-4c98-a4c1-4f0c7f7614b5").start()
    PoseDetector(prod_body_params,devuuid="2c91bd9d-bdfc-4a6b-b465-575f43897d59").start()

    # Vehicle Scanning
    ConfigurationScanner(devuuid="0d451573-243e-423b-bfab-0f3117f88bd0").start()
    FaultNotifier(devuuid="f1b43cb8-127a-43b5-905d-9f145171079es").start()

    # Window Milling
    PickUpRobot(prod_window_params,devuuid="6625b9ac-55e2-49c8-ab47-d1da21b5f0b5").start()
    MillingRobot(prod_window_params,devuuid="5ce94c31-3004-431e-97b3-c8f779fb180d").start()
    PoseDetector(prod_window_params,devuuid="1df9566a-2f06-48f0-975f-28058c6784c0").start()

    # Quality Check
    QualityScanner(devuuid="fd9ccbb2-be41-4507-85ac-a431fe886541").start()
    FaultNotifier(devuuid="5bb02f4b-0dfe-45d4-8a87-e902e6ea0bf6").start()

    # Artificial Repair
    RepairControl(devuuid="4525aa12-06fb-484f-be38-58afb33e1558").start()

    # Product Completion
    PickUpRobot(prod_completion_params,devuuid="ae5e4ad3-bd59-4dc8-b242-e72747d187d4").start()
    PoseDetector(prod_completion_params,devuuid="f2d73019-1e87-48a7-b93c-af0a4fc17994").start()

    # Tasks Connectors
    ConveyorBelt(devuuid="fbeaa5f3-e532-4e02-8429-c77301f46470").start()
    ConveyorBelt(devuuid="f169a965-bb15-4db3-97cd-49b5b641a9fe").start()
    ConveyorBelt(devuuid="3140ce5c-0d08-4aff-9bb4-14a9e6a33d12").start()
    ConveyorBelt(devuuid="a6f65d7a-019a-4723-9b81-fb4a163fa23a").start()
    ConveyorBelt(devuuid="f342e60b-6a54-4f20-8874-89a550ebc75c").start()
    
    # SAFETY / ENVIRONMENTAL - INITIAL DEVICES
    # Ambient variables time series
    safetyenv_indoors = GroundTruth(safetyenv_indoor_vars)
    safetyenv_outdoors = GroundTruth(safetyenv_outdoor_vars)
    safetyenv_indoors.start()
    safetyenv_outdoors.start()

    # Indoors Monitoring
    air_quality_indoors = AirQuality(safetyenv_indoors,devuuid="5362cb80-381d-4d21-87ba-af283640fa98",print_logs=False)
    air_quality_indoors.start()
    NoiseSensor(devuuid="7fc17e8f-1e1c-43f8-a2d1-9ff4bcfbf9ff").start()
    SmokeSensor(devuuid="5a84f26b-bf77-42d3-ab8a-83a214112844").start()
    SeismicSensor(devuuid="4f1f6ac2-f565-42af-a186-db17f7ed94c2").start()

    # Outdoors Monitorization
    AirQuality(safetyenv_outdoors,devuuid="c11c3f56-0f26-415f-a00d-3bb929f5ca20").start()
    RainSensor(safetyenv_outdoors,devuuid="70a15d0b-f6d3-4833-b929-74abdff69fa5").start()
    WindSensor(safetyenv_outdoors,devuuid="f41db548-3a85-491e-ada6-bab5c106ced6").start()

    # Safety Alarms
    IndoorsAlarm(devuuid="4d36d0c4-891f-44ec-afe1-278258058944").start()
    OutdoorsAlarm(devuuid="b60108c2-46a3-4b67-9b8d-38586cb3039d").start()

    # TEST CASES

    # CASE 1. A KNOWN DEVICE DISAPPEARS AND A NEW ONE WITH SIMILAR CHARACTERISTICS APPEARS

    # Similar characteristics implies that it will have a few modifications in its modules/attribs
    # and the data it reports will have a somehow similar behavior.

    # In this case similarity should be quite high, which could justify applying a simple
    # replacement of the old device by the new device.

    time.sleep(0)
    #air_quality_indoors.active = False # stop indoors air quality
    air_quality_modified_indoors = AirQualityModified(safetyenv_indoors,print_logs=False) 
    air_quality_modified_indoors.start() # start modified indoors air quality

    # CASE 2. A COMPLEMENTARY DEVICE APPEARS IN A TASK

    # A device with the a new or existing class that has been added to an existing task appears, 
    # showing a high similarity to a set of devices that are present in the task he is to fulfill. 
    # In this case the device description and attributes should allow us to determine he belongs to the
    # task he is part of, ending up with the integration of the device in the task in the KG.

    # An example of this could be the addition of a robotic arm to speed up a task, with this robotic arm
    # showing a similar behavior to the robotic arm it is complementing in that task.



    # CASE 3. A COMPLETELY UNKNOWN DEVICE APPEARS

    # A device with a new name and SDF definition appears in the network flow, therefore the
    # KG agent must decide where this device belongs in the KG structure, making the modifications 
    # necessary in the schema and the data. This is a more complex problem, since there might not be
    # any device already in the structure that measures similar data or fulfills a similar function, 
    # making the decision of where to place this device very difficult.

    # To determine where it belongs first we search for the most similar existing devices
    # which would be the ones with a lower distance in a given feature space. Once we know 
    # the most similar devices we will query the neighborhood of these devices and analyze it
    # to determine how this new device should be included in the graph.

    # This only takes into account the problem of somehow finding out to which task the new 
    # device belongs, but it would not be able at all of creating a new task or higher ontological entity
    # to include the device in the structure in case it does not fit anywhere. To be able to do this it 
    # seems like it would be necessary to include more information in the device description, such
    # as which devices it interacts with. One option could be checking which devices are subscribed to other
    # devices topics to be able to construct more complex relations.
    

if __name__ == "__main__":
    main()