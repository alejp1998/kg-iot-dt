#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : Alejandro Jarabo
# Created Date: 2022-09-19
# Contact : ale.jarabo.penas@ericsson.com
# version ='1.0'
# ---------------------------------------------------------------------------
""" Auxiliar Variables/Functions/Imports
Module defining auxiliar content to be used by the main modules.
"""
# ---------------------------------------------------------------------------
# Imports
from numpy import random
from datetime import datetime, timedelta
from colorama import Fore, Back, Style
from builtins import print as prnt
import paho.mqtt.client as mqtt
import time, json, re, uuid
from pygments import highlight
from pygments.formatters.terminal256 import Terminal256Formatter
from pygments.lexers.web import JsonLexer
# ---------------------------------------------------------------------------

###########################
######## VARIABLES ########
###########################

# Root topics for publishing
prodline_root = 'productionline/'
safetyenv_root = 'safetyenvironmental/'
arrow_str = '     |------> '
arrow_str2 = '     |          |---> '

###########################
######## FUNCTIONS ########
###########################

# Print device data
def print_device_data(timestamp,data,sdf) :
    print(arrow_str + f'[timer]',kind='')
    print(arrow_str2 + f'(timestamp)<datetime>={timestamp}',kind='')
    for mname in data :
        print(arrow_str + f'[{mname}]',kind='')
        for mproperty in data[mname] :
            tdbtype = sdf['sdfObject'][mname]['sdfProperty'][mproperty]['type']
            print(arrow_str2 + f'({mproperty})<{tdbtype}>={data[mname][mproperty]}',kind='')

# Colored prints
def print(text,kind='') :
    prnt(cprint_dict[kind] + str(text) + Style.RESET_ALL)


##############################
######## DICTIONARIES ########
##############################

# Colored prints
cprint_dict = {
    'info': Fore.WHITE,
    'success' : Fore.GREEN,
    'fail': Fore.RED,
    'summary': Fore.MAGENTA,
    'debug': Fore.BLUE,
    '': Fore.YELLOW 
}
