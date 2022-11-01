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

######################
######## MAIN ########
######################

# PRODUCTION LINE - INITIAL DEVICES
# Initialization Task
TagScanner(devuuid="8a40d136-8401-41bd-9845-7dc8f28ea582").start()
ProductionControl(devuuid="3d193d4c-ba9c-453e-b98b-cec9546b9182").start()

# Underpan Configuration Task
PickUpRobot(devuuid="5f3333b9-8292-4371-b5c5-c1ec21d0b652").start()
PieceDetector(devuuid="45d289e7-4da6-4c10-aa6e-2c1d48b223e2",focus='underpans').start()

# Body Configuration Task
PickUpRobot(devuuid="da0ba61c-a9bf-4e0d-b975-33b7b4c5d2e8").start()
ClampingRobot(devuuid="5ee2149f-ef6e-402b-937e-8e04a2133cdd").start()
DrillingRobot(devuuid="98247600-c4fe-4728-bda6-ed8fadf81af2").start()
PieceDetector(devuuid="d7295016-4a54-4c98-a4c1-4f0c7f7614b5",focus='parts').start()
PoseDetector(devuuid="2c91bd9d-bdfc-4a6b-b465-575f43897d59").start()

# Vehicle Scanning
ConfigurationScanner(devuuid="0d451573-243e-423b-bfab-0f3117f88bd0").start()
FaultNotifier(devuuid="f1b43cb8-127a-43b5-905d-9f145171079es",focus='configuration').start()

# Window Milling
PickUpRobot(devuuid="6625b9ac-55e2-49c8-ab47-d1da21b5f0b5").start()
MillingRobot(devuuid="5ce94c31-3004-431e-97b3-c8f779fb180d").start()
PoseDetector(devuuid="1df9566a-2f06-48f0-975f-28058c6784c0").start()

# Quality Check
QualityScanner(devuuid="fd9ccbb2-be41-4507-85ac-a431fe886541").start()
FaultNotifier(devuuid="5bb02f4b-0dfe-45d4-8a87-e902e6ea0bf6",focus='quality').start()

# Artificial Repair
RepairControl(devuuid="4525aa12-06fb-484f-be38-58afb33e1558").start()

# Product Completion
PickUpRobot(devuuid="ae5e4ad3-bd59-4dc8-b242-e72747d187d4").start()
PoseDetector(devuuid="f2d73019-1e87-48a7-b93c-af0a4fc17994").start()

# Tasks Connectors
ConveyorBelt(devuuid="fbeaa5f3-e532-4e02-8429-c77301f46470").start()
ConveyorBelt(devuuid="f169a965-bb15-4db3-97cd-49b5b641a9fe").start()
ConveyorBelt(devuuid="3140ce5c-0d08-4aff-9bb4-14a9e6a33d12").start()
ConveyorBelt(devuuid="a6f65d7a-019a-4723-9b81-fb4a163fa23a").start()
ConveyorBelt(devuuid="f342e60b-6a54-4f20-8874-89a550ebc75c").start()

# SAFETY / ENVIRONMENTAL - INITIAL DEVICES
# Indoors Monitorization
air_quality_indoors = AirQuality(devuuid="5362cb80-381d-4d21-87ba-af283640fa98",print_logs=True)
air_quality_indoors.start()
NoiseSensor(devuuid="7fc17e8f-1e1c-43f8-a2d1-9ff4bcfbf9ff").start()
SmokeSensor(devuuid="5a84f26b-bf77-42d3-ab8a-83a214112844").start()
SeismicSensor(devuuid="4f1f6ac2-f565-42af-a186-db17f7ed94c2").start()

# Outdoors Monitorization
AirQuality(devuuid="c11c3f56-0f26-415f-a00d-3bb929f5ca20").start()
RainSensor(devuuid="70a15d0b-f6d3-4833-b929-74abdff69fa5").start()
WindSensor(devuuid="f41db548-3a85-491e-ada6-bab5c106ced6").start()

# Safety Alarms
IndoorsAlarm(devuuid="4d36d0c4-891f-44ec-afe1-278258058944").start()
OutdoorsAlarm(devuuid="b60108c2-46a3-4b67-9b8d-38586cb3039d").start()

# CASES SIMULATION

# CASE 1. A KNOWN DEVICE DISAPPEARS AND A NEW ONE WITH SIMILAR CHARACTERISTICS APPEARS
# Similar characteristics implies that it will have a few modifications in its modules/attribs
# and the data it reports will have a somehow similar behavior.
time.sleep(10)
air_quality_indoors.active = False # stop indoors air quality
air_quality_modified_indoors = AirQualityModified(print_logs=True) 
air_quality_modified_indoors.start() # start modified indoors air quality

# CASE 2. A COMPLETELY UNKNOWN DEVICE APPEARS
# A device with a new name and SDF definition appears in the network flow, therefore the
# KG agent must decide where this device belongs in the KG structure, making the modifications 
# necessary in the schema and the data.
# To determine where it belongs first we search for the most similar existing devices
# which would be the ones with a lower distance in a given feature space. Once we know 
# the most similar devices we will query the neighborhood of these devices and use it
# to determine how this new device should be included in the graph.