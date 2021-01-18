#!/usr/bin/python3

import argparse
import select
import struct
#import can
import socket
import errno

MESSAGE_DESC_SIZE = 4
STARTING_PORT = 2000
STATUS_ERROR = -1
STATUS_OK = 0
STATUS_TIMEOUT = 1


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
    if STARTING_PORT > 65535:
        STARTING_PORT = 1024
    while True:
        if checkPort(STARTING_PORT) is True:
            STARTING_PORT += 1
            return STARTING_PORT -1
        else:
            STARTING_PORT += 1


class CANToEthConverter:
    def __init__(self, nameCANInterface, ip, portToSend, portToReceive):
        self._nameCANInterface = nameCANInterface
        self._CANInterface = can.interface.Bus(channel=self._nameCANInterface, bustype='socketcan_native')
        self._IP = ip
        self._portToSend = portToSend
        self._portToReceive = portToReceive
        self._socketToSend = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socketToReceive = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socketToReceive.bind(('', self._portToReceive))
        self._timeout = 0.01

    def _readFromCANBus(self, CANInterface):
        data = CANInterface.recv(self._timeout)
        while True:
            if not data:
                break
            data = CANInterface.recv(self._timeout)
        return data

    def _sendToCANBus(self, CANInterface, arbitration_id=0x0, data=bytearray()):
        message = CANInterface.Message(arbitration_id=arbitration_id, data=list(data))
        CANInterface.send(message)

    def _recvFromSockWithTimeout(self, sock, nbytes, timeout):
        import time
        recData = bytearray()
        try:
            t0 = time.time()
            while len(recData) < nbytes:
                dt = timeout - (time.time() - t0)
                if dt < 0:
                    return STATUS_TIMEOUT, recData
                r, w, e = select.select([sock], [], [], dt)
                if sock in e:
                    return STATUS_ERROR, recData
                if sock in r:
                    data = bytearray(sock.recv(nbytes - len(recData)))
                    if not data:
                        return STATUS_ERROR, recData
                    t0 = time.time()
                    recData += data
                    if nbytes == len(recData):
                        break
            return STATUS_OK, recData
        except Exception as e:
            print(e)
            return STATUS_ERROR, recData

    def _readFromEthSock(self, sock):
        global MESSAGE_DESC_SIZE
        result, data = self._recvFromSockWithTimeout(sock, MESSAGE_DESC_SIZE, self._timeout)
        if not data or result != STATUS_OK:
            return None
        messageSize = struct.unpack_from("<I", memoryview(data).tobytes(), 0)[0] - MESSAGE_DESC_SIZE
        result, data = self._recvFromSockWithTimeout(sock, messageSize, self._timeout)
        return None if not data or result != STATUS_OK else data

    def _sendToEthSock(self, sock, data):
        global MESSAGE_DESC_SIZE
        try:
            dataSize = MESSAGE_DESC_SIZE + len(data)
            data = struct.pack("I", dataSize) + data
            byteSent = sock.sendto(data, (self._IP, self._portToSend))

            while byteSent < dataSize:
                size = sock.sendto(data[byteSent:], (self._IP, self._portToSend))
                if size == 0:
                    break
                byteSent += size
            return 0
        except Exception as e:
            print(e)
            return -1

    def update(self):
        while True:
            dataFromCAN = self._readFromCANBus(self._CANInterface)
            if dataFromCAN is not None:
                self._sendToEthSock(self._socketToSend, dataFromCAN)
            dataFromSock = self._readFromEthSock(self._socketToReceive)
            if dataFromSock is not None:
                # parse message
                self._sendToCANBus(self._CANInterface, data=dataFromSock)

    def __del__(self):
        self._socketToSend.close()
        self._socketToReceive.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process CAN data from a socket-can device.')
    parser.add_argument('-a', dest='ip', default='')
    parser.add_argument('-d', dest='devices', default=[], nargs="+")
    args = parser.parse_args()

    print("ip address: {}".format(args.ip))
    print("devices list: {}".format(args.devices))

    converterList = []

    for dev in args.devices:
        converterList.append(CANToEthConverter(dev, args.ip, getNextFreePort(), getNextFreePort()))

    while True:
        for conv in converterList:
            conv.update()
