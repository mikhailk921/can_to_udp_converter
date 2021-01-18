#!/usr/bin/python3

import argparse
import select
import struct
import can
import socket
import errno

MESSAGE_SIZE = 4
STARTING_PORT = 2000


def checkPort(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("", port))
    except socket.error as e:
        if e.errno == errno.EADDRINUSE:
            print("Port {} is already in use".format(port))
        else:
            print(e)
        return False

    sock.close()
    return True


def getNextFreePort():
    global STARTING_PORT
    while True:
        if checkPort(STARTING_PORT) is True:
            STARTING_PORT += 1
            return STARTING_PORT -1
        else:
            STARTING_PORT += 1


class CANToEthConverter:
    def __init__(self, nameCANInterface, IP, sendPort, recPort):
        self._nameCANInterface = nameCANInterface
        self._CANInterface = can.interface.Bus(channel=self._nameCANInterface, bustype='socketcan_native')
        self._IP = IP
        self._sendPort = sendPort
        self._recPort = recPort
        self._sendSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._recSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._recSocket.bind(('', self._recPort))
        self._timeout = 0.01

    def readFromCANBus(self, CANInterface):
        data = CANInterface.recv(self._timeout)
        while True:
            if not data:
                break
            data = CANInterface.recv(self._timeout)
        return data

    def sendToCANBus(self, CANInterface, arbitration_id=0x0, data=[]):
        message = CANInterface.Message(arbitration_id=arbitration_id, data=list(data))
        CANInterface.send(message)

    def readFromEthSock(self, sock):
        import time
        recMess = bytearray()
        try:
            t0 = time.time()
            while self._timeout > (time.time() - t0):
                dt = self._timeout - (time.time() - t0)
                r, w, e = select.select([sock], [], [], dt)
                if sock in e:
                    return -1, recMess
                if sock in r:
                    data = bytearray(sock.recv())
                    if not data:
                        return 0, recMess
                    recMess += data
                    t0 = time.time()
            return 0, recMess
        except Exception as e:
            print(e)
            return -1, recMess

    def sendToEthSock(self, sock, data):
        try:
            dataSize = MESSAGE_SIZE + len(data)
            data = struct.pack("I", dataSize) + data

            byteSent = sock.sendto(data, (self._IP, self._sendPort))

            while byteSent < dataSize:
                size = sock.sendto(data[byteSent:], (self._IP, self._sendPort))
                if size == 0:
                    break
                byteSent += size
            return 0
        except Exception as e:
            print(e)
            return -1

    def run(self):
        while True:
            dataFromCAN = self.readFromCANBus(self._CANInterface)
            if dataFromCAN is not None:
                pass
            status, dataFromSock = self.readFromEthSock(self._recSocket)
            if dataFromSock is not None and status == 0:
                pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process CAN data from a socket-can device.')
    parser.add_argument('ip', default='')
    parser.add_argument('nameCANInterface', default='can0')
    args = parser.parse_args()

    converter = CANToEthConverter(args.nameCANInterface, args.ip, getNextFreePort(), getNextFreePort())
