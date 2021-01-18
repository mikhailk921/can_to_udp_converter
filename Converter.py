#!/usr/bin/python3

import argparse
import select
import struct
import can
import socket
import errno

DESCRIPTION_MESSAGE_SIZE = 4  # The first 4 bytes of the message describe its length in bytes
STARTING_PORT = 2000

# Errors
STATUS_ERROR = -1
STATUS_OK = 0
STATUS_TIMEOUT = 1


def checkPort(port) -> bool:
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


def getNextFreePort() -> int:
    global STARTING_PORT
    STARTING_PORT += 1
    if STARTING_PORT > 65535:
        STARTING_PORT = 1024
    while True:
        if checkPort(STARTING_PORT) is True:
            return STARTING_PORT
        else:
            STARTING_PORT += 1


class CANToEthConverter:
    def __init__(self, nameCANInterface, ip, portToSend, portToReceive):
        self._nameCANInterface = nameCANInterface
        self._CANInterface = can.interface.Bus(channel=self._nameCANInterface, bustype='socketcan_native')
        self._ip = ip
        self._portToSend = portToSend
        self._portToReceive = portToReceive
        self._socketToSend = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socketToReceive = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socketToReceive.bind(('', self._portToReceive))
        self._timeout = 0.01

    def _readFromCANBus(self, CANInterface):
        receivedData = CANInterface.recv(self._timeout)
        while True:
            data = CANInterface.recv(self._timeout)
            if not data:
                break
            receivedData += data
        return receivedData

    def _sendToCANBus(self, CANInterface, arbitration_id=0x0, data=bytearray()):
        message = CANInterface.Message(arbitration_id=arbitration_id, data=list(data))
        CANInterface.send(message)

    def _recvFromSockWithTimeout(self, sock, nbytes, timeout):
        import time
        receivedData = bytearray()
        t0 = time.time()
        try:
            while len(receivedData) < nbytes:
                dt = timeout - (time.time() - t0)
                if dt < 0:
                    return STATUS_TIMEOUT, receivedData
                r, w, e = select.select([sock], [], [], dt)
                if sock in e:
                    return STATUS_ERROR, receivedData
                if sock in r:
                    data = bytearray(sock.recv(nbytes - len(receivedData)))
                    if not data:
                        return STATUS_ERROR, receivedData
                    t0 = time.time()
                    receivedData += data
            return STATUS_OK, receivedData
        except Exception as e:
            print(e)
            return STATUS_ERROR, receivedData

    def _readFromEthSock(self, sock):
        global DESCRIPTION_MESSAGE_SIZE
        result, data = self._recvFromSockWithTimeout(sock, DESCRIPTION_MESSAGE_SIZE, self._timeout)
        if not data or result != STATUS_OK:
            return None
        messageSize = struct.unpack_from("<I", memoryview(data).tobytes(), 0)[0] - DESCRIPTION_MESSAGE_SIZE
        result, data = self._recvFromSockWithTimeout(sock, messageSize, self._timeout)
        return None if not data or result != STATUS_OK else data

    def _sendToEthSock(self, sock, data):
        global DESCRIPTION_MESSAGE_SIZE
        try:
            dataSize = DESCRIPTION_MESSAGE_SIZE + len(data)
            data = struct.pack("I", dataSize) + data
            byteSent = sock.sendto(data, (self._ip, self._portToSend))

            while byteSent < dataSize:
                size = sock.sendto(data[byteSent:], (self._ip, self._portToSend))
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
    parser = argparse.ArgumentParser(description='Converter CAN to UDP socket and back')
    parser.add_argument('-a', '--address', dest='ip', default='', type=str, help="ip address")
    parser.add_argument('-d', '--devices', dest='devices', default=[], nargs="+", help="Devices list")
    args = parser.parse_args()

    print("ip address: {}".format(args.ip))
    print("devices list: {}".format(args.devices))

    if len(args.devices) == 0:
        exit(0)

    converterList = []

    for dev in args.devices:
        portToSend = portToReceive = getNextFreePort()
        converterList.append(CANToEthConverter(dev, args.ip, portToSend, portToReceive))

    while True:
        for converter in converterList:
            converter.update()
