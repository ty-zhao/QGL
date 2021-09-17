from QGL import *
from nist_APS2_converter import convert
import json

cl = ChannelLibrary("NIST")

q1 = cl.new_qubit("q1")
q2 = cl.new_qubit("q2")

aps2_1 = cl.new_APS2("BBNAPS2_1", address="192.168.2.2")
aps2_2 = cl.new_APS2("BBNAPS2_2", address="192.168.2.3")
aps2_3 = cl.new_APS2("BBNAPS2_3", address="192.168.2.4")
aps2_4 = cl.new_APS2("BBNAPS2_4", address="192.168.2.5")
aps2_5 = cl.new_APS2("BBNAPS2_5", address="192.168.2.6")
aps2_6 = cl.new_APS2("BBNAPS2_6", address="192.168.2.7")

dig = cl.new_Alazar("Alazar", address=0)

TDM = cl.new_TDM("TDM", address="192.168.2.11")

cl.set_control(q1, aps2_1)
cl.set_control(q2, aps2_2)

cl.commit()