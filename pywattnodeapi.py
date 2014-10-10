#!/usr/bin/python

import sys
#sys.path.append("../pymodbus-0.5")
#from pymodbus.utilities import computeCRC

import struct
import serial
import threading

import time
import datetime
import getopt
import ConfigParser
#-----------------------------------------------------------------------
# Logging
#-----------------------------------------------------------------------
import logging


def __generate_crc16_table():
    ''' Generates a crc16 lookup table

    .. note:: This will only be generated once
    '''
    result = []
    for byte in range(256):
        crc = 0x0000
        for bit in range(8):
            if (byte ^ crc) & 0x0001: crc = (crc >> 1) ^ 0xa001
            else: crc >>= 1
            byte >>= 1
        result.append(crc)
    return result

__crc16_table = __generate_crc16_table()

def computeCRC(data):
    ''' Computes a crc16 on the passed in data.
    @param data The data to create a crc16 of

    The difference between modbus's crc16 and a normal crc16
    is that modbus starts the crc value out at 0xffff.

    Accepts a string or a integer list
    taken from pymodbus.utilities
    '''
    crc = 0xffff
    pre = lambda x: x
    if isinstance(data, str): pre = lambda x: ord(x)

    for a in data: crc = ((crc >> 8) & 0xff) ^ __crc16_table[
            (crc ^ pre(a)) & 0xff];
    return crc



#-----------------------------------------------------------------------
# Misc
#-----------------------------------------------------------------------
FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
def dumpHex(src, length=8):
    result=[]
    for i in xrange(0, len(src), length):
        s = src[i:i+length]
        hexa = ' '.join(["%02X"%ord(x) for x in s])
        printable = s.translate(FILTER)
        result.append("%04X   %-*s   %s\n" % (i, length*3, hexa, printable))
    return ''.join(result)

def decodeAscii(s, res=None):
    return s

def decodeInt16(s, res=None):
    if s != None and len(s)>=2:
        if res == None:
            res = []

        res.append(struct.unpack(">H", s[:2])[0])
        return decodeInt16(s[2:],res)
    else:
        return res

def decodeInt32(s, res= None):
    if s != None and len(s)>=4:
        if res == None:
            res = []

        # swap order of registers
        # so everything is big endian
        x = s[2:4]
        x+= s[:2]
        res.append(struct.unpack(">I", x)[0])
        return decodeInt32(s[4:],res)
    else:
        return res

def decodeFloat32(s, res = None):
    if s != None and len(s)>= 4:
        if res == None:
            res = []

        # swap order of registers
        # so everything is big endian
        x = s[2:4]
        x+= s[:2]

        result = struct.unpack(">f",x)[0]
        res.append(result)
        return decodeFloat32(s[4:], res)
    else:
        return res
def decodeBasicFp(s):
    regs = {}
    ofs = 0
    #for reg in range(1000,1034,2):
    for reg in __wattNodeBasicVars:
        regs[reg] = decodeFloat32(s[ofs:ofs+4])[0]
        ofs += 4
    #print 'basic fp:', regs
    return regs

def decodeAdvancedFp(s):
    regs = {}
    ofs = 0
    #for reg in range(1100,1176,2):
    for reg in __wattNodeAdvancedVars:
        regs[reg] = decodeFloat32(s[ofs:ofs+4])[0]
        ofs += 4
    #print 'adv fp:', regs
    return regs

def makeIdent(saddr=0):
    data = struct.pack(">BB", saddr, 0x11)
    data += struct.pack("<H",computeCRC(data))
    return data
def makeWriteReg(saddr=0, regaddr=0, value=0):
    data = struct.pack(">BBHH",saddr,6,regaddr,value)
    data += struct.pack("<H",computeCRC(data))
    return data

def makeReadReg(saddr=0, regaddr=0, regcnt=0, fnc=4):
    '''
    Function 03 query structure
    Byte    Value    Description
    1    1...247    Slave device address
    2    3    Function code
    3    0...255    Starting address, high byte
    4    0...255    Starting address, low byte
    5    0...255    Number of registers, high byte
    6    0...255    Number of registers, low byte
    7(...8)    LRC/CRC    Error check value
    '''
    data = struct.pack("BB",saddr, fnc)
    data += struct.pack(">H",regaddr)
    data += struct.pack(">H",regcnt)
    data += struct.pack("<H",computeCRC(data))

    return data

def decodeRaw(s):
    return s

class ModbusException(Exception):
    """Base class for modbus related exceptions."""

#-----------------------------------------------------------------------
# Client
#-----------------------------------------------------------------------
class SerialModbusClient ():
    '''
    This class allows Serial RTU communication with MODBUS devices
    '''
    #mindelay = datetime.timedelta(milliseconds=3.6)
    mindelay = datetime.timedelta(milliseconds=75.0)
    # powerscout needs a longer min delay
    # wattnode can work with 3.6ms
    def __init__(self, log = None):
        #self.log = logging.getLogger("wattnodeapi")
        #self.log.setLevel(loglevel)
        if log:
            self.log = log
        else:
            self.log = logging.getLogger('modbus')
        self.lastReq = datetime.datetime.now()
        # create console handler
        #ch = logging.StreamHandler()
        #logging.basicConfig()
        # create formatter
        #formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        # add formatter to ch
        #ch.setFormatter(formatter)
        # add ch to logger
        #self.log.addHandler(ch)

    def open(self, port='/dev/ttyS0', baudrate=9600):
        # 8N1 is default
        # 1 second timeout
        self.ser = serial.Serial(port, baudrate, timeout=2)

    def detectDevs(self):
        """send a ReportSlaveID message to the broadcast address"""

        self.log.info ('Searching for modbus devices')

        oldtimeout= self.ser.timeout
        self.ser.timeout = 0.1
        devs = {}

        for i in range(1,256):
            try:
                resp = self.doRequest(makeReadReg(i, 1700,2),decodeInt32)
                print 'got', resp
            except ModbusException:
                pass

            self.ser.flushInput()

        self.ser.timeout = oldtimeout
    def close(self):
        self.ser.close()
    def _handleError(self, s):
        self.log.debug("recv: %s" % (dumpHex(s)))
        if computeCRC(s) == 0:
            code = struct.unpack("B",s[2])[0]
            if code == 2 :
                self.log.warning("Illegal Data Address")
                raise ModbusException("Illegal Data Address")
            elif code == 3:
                self.log.warning("Illegal Data Value")
                raise ModbusException("Illegal Data Value")
            else:
                self.log.warning("Exception 0x%x" % (code))
                raise ModbusException("Exception 0x%x" % (code))
        else:
            self.log.warning("invalid crc")
            self.log.warning(dumpHex(s))
            raise ModbusException("invalid crc")

    def _handleRead(self, decoder):
        # this reading structure only works for 0x4 type messages...
        s = self.ser.read(3) # addr, fcode, byte count

        if len(s) >0:
            code = struct.unpack("B",s[1])[0]

            if (code & 0x80) == 0x80:
                s += self.ser.read(2) # CRC
                self._handleError(s)
            else:
                pklen = struct.unpack("B",s[2])[0]
                s+= self.ser.read(pklen+2) # include crc bytes

                if computeCRC(s) == 0 :
                    #self.log.debug("  crc is valid")
                    #self.log.debug(dumpHex(s))
                    self.log.debug("recv: %s" % (dumpHex(s)))

                    #strip control bytes and last two crc bytes
                    return decoder(s[3:-2])
                else:
                    self.log.warning("invalid crc")
                    #self.log.warning(dumpHex(s))
                    self.log.debug("recv: %s" % (dumpHex(s)))
                    raise ModbusException("invalid crc")
        else:
            raise ModbusException("Modbus timeout")
    def _handleWrite(self):
        s = self.ser.read(2) # addr, fcode
        if len(s) >0:
            code = struct.unpack("B",s[1])[0]
            if (code & 0x80) == 0x80:
                #error bit is set
                s += self.ser.read(3) # exception code + CRC
                self._handleError(s)
            else:
                s += self.ser.read(6) # addr, value, crc (each 16 bits)
                if computeCRC(s) == 0:
                    return
                else:
                    self.log.warning("invalid crc")
                    self.log.warning(dumpHex(s))
                    raise ModbusException("invalid crc")
        else:
            raise ModbusException("Modbus timeout")
    def doRequest(self, req=None, decoder=decodeRaw):
        if req != None:
            self.log.debug("send: %s" % (dumpHex(req)))

            td = datetime.datetime.now() - self.lastReq
            # need at least 3.6 milliseconds between response and next command, enforce delay here
            if td < SerialModbusClient.mindelay:
                delay = SerialModbusClient.mindelay - td
                #self.log.warn ('too fast, inserting delay of %d ms'%(delay.microseconds/1000.0))
                time.sleep(delay.microseconds/1000000.0) # in seconds

            # sanity check
            td = datetime.datetime.now() - self.lastReq
            if td < SerialModbusClient.mindelay:
                self.log.error('timing sanity check failed')

            self.ser.write(req)

            addr,fc = struct.unpack("BB", req[0:2])

            # bcast does not generate a response
            s = None
            if addr != 0xff:
                if fc == 0x03 or fc == 0x04:
                    s = self._handleRead(decoder)
                elif fc == 0x06:
                    s = self._handleWrite()
                elif fc == 0x11:
                    s = self._handleRead(decodeAscii)
                else:
                    raise ModbusException("unsupported function code")

            self.lastReq = datetime.datetime.now()

            return s

#-----------------------------------------------------------------------
# Test code
#-----------------------------------------------------------------------

__wattNodeBasicVars = [
"EnergySum",
"EnergyPosSum",
"EnergySumNR",
"EnergyPosSumNR",

"PowerSum",
"PowerA",
"PowerB",
"PowerC",

"VoltAvgLN",
"VoltA",
"VoltB",
"VoltC",
"VoltAvgLL",
"VoltAB",
"VoltBC",
"VoltAC",

"Freq"
]

__wattNodeAdvancedVars = [
"EnergyA",
"EnergyB",
"EnergyC",
"EnergyPosA",
"EnergyPosB",
"EnergyPosC",
"EnergyNegSum",
"EnergyNegSumNR",
"EnergyNegA",
"EnergyNegB",
"EnergyNegC",
"EnergyReacSum",
"EnergyReacA",
"EnergyReacB",
"EnergyReacC",
"EnergyAppSum",
"EnergyAppA",
"EnergyAppB",
"EnergyAppC",

"PowerFactorAvg",
"PowerFactorA",
"PowerFactorB",
"PowerFactorC",

"PowerReacSum",
"PowerReacA",
"PowerReacB",
"PowerReacC",
"PowerAppSum",
"PowerAppA",
"PowerAppB",
"PowerAppC",

"CurrentA",
"CurrentB",
"CurrentC",

"Demand",
"DemandMin",
"DemandMax",
"DemandApp"
]

wattNodeLogVars = __wattNodeBasicVars + __wattNodeAdvancedVars

__wattNodeCurrentVars = [
"CurrentA",
"CurrentB",
"CurrentC"
]

__wattNodeDiagVars = [
"SerialNumber",
"UptimeSecs",
"TotalSecs",

"Model",
"Version",
"Options",
"ErrorStatus",
"PowerFailCount",
"CrcErrorCount",
"FrameErrorCount",
"PacketErrorCount",
"OverrunCount",
"ErrorStatus1",
"ErrorStatus2",
"ErrorStatus3",
"ErrorStatus4",
"ErrorStatus5",
"ErrorStatus6",
"ErrorStatus7",
"ErrorStatus8"  #18
]

__wattNodeDemandVars = [
"Demand",
"DemandMin",
"DemandMax",
"DemandApp"
]



if __name__ == "__main__":
    log = logging.getLogger('log')
    log.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    log.addHandler(ch)

    addresses = [ {'address': 1}]
    port = '/dev/ttyUSB0'

    log.info ("Opening '%s'" % (port))

    p = SerialModbusClient(log);
    p.open(port)

    # read the wattnode id
    serNos =[]
    for address in addresses:
        serno = p.doRequest(makeReadReg(
                address['address'], 1700,2),decodeInt32) [0]
        address['serno'] = serno

        # turn off averaging
        p.doRequest(makeWriteReg(address['address'],1607,0))

        # setup for 200A ct
        p.doRequest(makeWriteReg(address['address'],1602,200))

    for address in addresses:
        print "Watt-node on address %d reported serial number: %d" % \
             (address['address'], address['serno'])

    items = []

    for address in addresses:
        items.append(
                {"name":"WATT_%s_PowerSum"%(address['serno']),
                 "cmd": makeReadReg(address['address'], 1008, 2),
                 "decode":decodeFloat32,
                 "interval":datetime.timedelta(seconds=1),
                 "last":datetime.datetime.min})


        items.append(
        {"name":"WATT_%s_EnergySum"%(address['serno']),
        "cmd": makeReadReg(address['address'],1000,2),
        "decode":decodeFloat32,
        "interval":datetime.timedelta(minutes=5),
        "last":datetime.datetime.min})

        items.append(
        {"name":"WATT_%s_RealPower"%(address['serno']),
        "cmd": makeReadReg(address['address'],1008,2),
        "decode":decodeFloat32,
        "interval":datetime.timedelta(seconds=1),
        "last":datetime.datetime.min})

        items.append(
        {"name":"WATT_%s_ReactivePower"%(address['serno']),
        "cmd": makeReadReg(address['address'],1146,2),
        "decode":decodeFloat32,
        "interval":datetime.timedelta(seconds=1),
        "last":datetime.datetime.min})

        items.append(
        {"name":"WATT_%s_Volt"%(address['serno']),
        "cmd": makeReadReg(address['address'],1016,2),
        "decode":decodeFloat32,
        "interval":datetime.timedelta(seconds=1),
        "last":datetime.datetime.min})

        items.append(
        {"name":"WATT_%s_Freq"%(address['serno']),
        "cmd": makeReadReg(address['address'],1032,2),
        "decode":decodeFloat32,
        "interval":datetime.timedelta(seconds=1),
        "last":datetime.datetime.min})

    while True:
        try:
            min = datetime.timedelta(seconds=5)

            for cmd in items:
                now = datetime.datetime.now()
                if (now - cmd["last"] > cmd["interval"]):
                    val = p.doRequest(cmd["cmd"], cmd["decode"])

                    cmd["last"] = now

                    if val == None:
                        print "no response"
                    else:
                        print "%s = %s" % (cmd["name"], val[0])
                     #   c.inT(cmd["name"], "%s"%(val[0]))

                if (cmd["last"] + cmd["interval"] < now + min):
                    min = (cmd["last"] + cmd["interval"]) - now

            time.sleep(min.seconds)

        except KeyboardInterrupt:
            break

    print "Shutting down"
    p.close()
