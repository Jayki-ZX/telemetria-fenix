#!/usr/bin/env python

import time
import can
import threading
from can import Bus
from can.message import Message
from tools.operations import linear_map, voltage_transform
from front import FrontEnd

# TODO: implement this function
def parsed_message(msg: can.Message):
    id = msg.arbitration_id
    data = msg.data
    parsedd_message = {}
    if id == 0x001:
        parsedd_message = {
        }
    elif id == 0xc3:
        parsedd_message = {
        }
    return parsedd_message

locked = False
class Database(can.Listener):
    def __init__(self, file_name: str) -> None:
        self.file_name = file_name
        f = open(file=self.file_name, mode='w')
        f.write("timestamp,msg_id,data\n")
        f.close()

    def on_message_received(self, msg: can.Message) -> None:
        global locked
        while locked:
            time.sleep(0.2)
        locked = True
        f = open(file=self.file_name, mode='a')
        f.write("{},{},{}\n".format(msg.timestamp, msg.arbitration_id, msg.data.hex()))
        f.close()
        locked = False


class Frontend(can.Listener):
    def __init__(self, frontEnd) -> None:
        self.frontEnd = frontEnd
        self.commandIndex = 0
        self.commandPace = 0
        self.data = [0,0,0,0,0,0,0,0,0,0]

    def on_message_received(self, msg: can.Message) -> None:
        if msg.arbitration_id in [0x69, 0xcd]:
            commands = [0x1b, 0x1a, 0x33, 0x37, 0x42, 0x43, 0x44]
            parsedMessage = parsed_message_kelly(commands[self.commandIndex], msg)

            match commands[self.commandIndex]:
                case 0x33:
                    if msg.arbitration_id == 0x69:
                        self.data[3] = parsedMessage["motor_temperature"]
                    else:
                        self.data[9] = parsedMessage["motor_temperature"]
                case 0x37:
                    if msg.arbitration_id == 0x69:
                        self.data[1] = parsedMessage["mechanical_speed"]
                        self.data[2] = parsedMessage["mechanical_speed"]
                    else:
                        self.data[7] = parsedMessage["mechanical_speed"]
                        self.data[8] = parsedMessage["mechanical_speed"]

            self.frontEnd.data = self.data

            if self.commandPace == 1:
                self.commandIndex = (self.commandIndex+1) % len(commands)
                self.commandPace = 0
            else:
                self.commandPace = 1

def parsed_message_kelly(command: int, msg: can.Message):
    id = msg.arbitration_id
    data = msg.data
    parsed_message = {}
    if command == 0x1b:
        parsed_message["brake"] = linear_map(data[0], 0, 255, 0, 5)
        parsed_message["tps"] = linear_map(data[1], 0, 255, 0, 5)
        parsed_message["operation_voltage"] = voltage_transform(data[2])
        parsed_message["vs"] = linear_map(data[3],120, 134, 4.75, 5.25)
        parsed_message["bplus"] = voltage_transform(data[4])         # Resistance
    elif command == 0x1a:
        parsed_message["Ia"] = data[0]
        parsed_message["Ib"] = data[1]
        parsed_message["Ia"] = data[2]
        parsed_message["Va"] = voltage_transform(data[3])
        parsed_message["Vb"] = voltage_transform(data[4])
        parsed_message["Vc"] = voltage_transform(data[5])
    elif command == 0x33:
        parsed_message["pwm"] = data[0]
        parsed_message["enable_motor_rotation"] = data[1]
        parsed_message["motor_temperature"] = data[2]
        parsed_message["controller_temperature"] = data[3]
        parsed_message["high_side_heat_sink"] = data[4]
        parsed_message["low_side_heat_sink"] = data[5]
    elif command == 0x37:
        parsed_message["mechanical_speed"] = data[0]<<8 | data[1]
        parsed_message["current_controller"]  =data[2] #
        parsed_message["error_mechanical_speed"]  =data[3] <<8 | data[4] #
    elif command == 0x42:
        parsed_message["throttle_switch"] = data[0]
    elif command == 0x43:
        parsed_message["brake_switch"]  = data[0]
    elif command == 0x44:
        parsed_message["reverse_switch"]  = data[0]
    #print(parsed_message)
    return parsed_message

def request_kelly(bus):
    commands = [0x1b, 0x1a, 0x33, 0x37, 0x42, 0x43, 0x44]
    for c in commands:
        bus.send(
            Message(
            arbitration_id=0x64, data=[c], is_extended_id=False #respuesta 0x69
            )
        )
        bus.send(
            Message(
            arbitration_id=0xc8, data=[c], is_extended_id=False #respuesta 0xcd
            )
        )
        idrespond=[0x069, 0x0cd]
        while True:
            if len(idrespond)!=0:
                msg = bus.recv()
                if msg is not None:
                    response = parsed_message_kelly(c, msg) # 0x064 if msg.arbitration_id == 0x069 else 0x0c8 
                    idrespond.remove(msg.arbitration_id)
                    print(response)
                continue
            break
        time.sleep(1) #test

vcankellys = Bus(interface='socketcan', channel='can0', can_filters=[
    {"can_id": 0x069, "can_mask": 0xfff}, # response kelly1
    {"can_id": 0x0cd, "can_mask": 0xfff}, # response kelly2
])

vcan0 = Bus(interface='socketcan', channel='can0')
vcan1 = Bus(interface='socketcan', channel='can1')

frontEnd = FrontEnd()
can.Notifier([vcan0], [Frontend(frontEnd), Database('vcan0.csv')])
can.Notifier([vcan1], [Frontend(frontEnd), Database('vcan1.csv')])

def request_kelly_daemon():
    while True:
        request_kelly(vcankellys)

if __name__ == "__main__":
    t1 = threading.Thread(target=request_kelly_daemon)
    t1.start()
    frontEnd.run()
