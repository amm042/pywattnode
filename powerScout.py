import pywattnodeapi as mdbus
import struct
import logging
import time


class PowerScoutClient(mdbus.SerialModbusClient):
    reg_names = [i.strip() for i in """kWh System LSW
kWh System MSW
kW System
kW Demand System Max
kW Demand System Now
kW System Max
kW System Min 
kVARh System LSW 
kVARh System MSW 
kVAR System 
kVAh System LSW 
kVAh System MSW 
kVA System 
Displacement PF System 
Apparent PF System 
Amps System Avg 
Volts Line to Line Avg 
Volts Line to Neutral Avg 
Volts L1 to L2 
Volts L2 to L3 
Volts L1 to L3 
Line Frequency 
kWh L1 LSW 
kWh L1 MSW 
kWh L2 LSW 
kWh L2 MSW 
kWh L3 LSW 
kWh L3 MSW 
kW L1 
kW L2 
kW L3 
kVARh L1 LSW 
kVARh L1 MSW 
kVARh L2 LSW 
kVARh L2 MSW 
kVARh L3 LSW 
kVARh L3 MSW 
kVAR L1 
kVAR L2 
kVAR L3 
kVAh L1 LSW
kVAh L1 MSW
kVAh L2 LSW
kVAh L2 MSW
kVAh L3 LSW
kVAh L3 MSW
kVA L1
kVA L2
kVA L3
Displacement PF L1
Displacement PF L2
Displacement PF L3
Apparent PF L1
Apparent PF L2
Apparent PF L3
Amps L1
Amps L2
Amps L3
Volts L1 to Neutral
Volts L2 to Neutral
Volts L3 to Neutral
Time Since Reset LSW
Time Since Reset MSW""".split('\n')]
    base_reg = 4000
    meters = 6
    veris_kW_scalar= [0.001,
                      0.001,
                      0.001,
                      0.001,
                      0.001,
                      0.001]
    A_scalar = [0.01,
                0.1, 
                0.1, 
                0.1, 
                1,              
                1, 
                1]
    V_scalar = [0.1,
                0.1, 
                0.1, 
                0.1, 
                1,              
                1, 
                1]
    PF_scalar = [0.01,
                 0.01,
                 0.01,
                 0.01,
                 0.01,
                 0.01]
    kW_scalar = [0.00001,
                 0.001,
                 0.1,
                 1,
                 10,
                 100]
    V_scalar = [0.1,
                0.1,
                0.1,
                0.1,
                1,
                1,
                1]
    def __init__(self,baseAddress=1):
        mdbus.SerialModbusClient.__init__(self)
        self.baseAddress = baseAddress
    def ident(self,meter):
        addr = self.baseAddress + meter
        idstr = self.doRequest(
            mdbus.makeIdent(addr),
                mdbus.decodeAscii)
        self.log.info ("Meter %d, ident string: %s (rev 0x%02x, act 0x%02x)"%\
                       (meter, idstr[2:], ord(idstr[0]), ord(idstr[1])))
    def setScaling(self,meter,scale):
        raise Exception("Warning requires the PS18 reboot!")
        addr = self.baseAddress + meter
        self.doRequest(
            mdbus.makeWriteReg(
                 addr, 4301, scale))
        
    def _scale(self, data, meter):
        for key in data.keys():
            if 'kW' in key or 'kVA' in key:
                data[key] = PowerScoutClient.kW_scalar[self.scalar[meter]] * data[key]
            elif 'PF' in key:
                data[key] = PowerScoutClient.PF_scalar[self.scalar[meter]] * data[key]
            elif 'Amps' in key:
                data[key] = PowerScoutClient.A_scalar[self.scalar[meter]] * data[key]
            elif 'Volts' in key:
                data[key] = PowerScoutClient.V_scalar[self.scalar[meter]] * data[key]
            elif 'Frequency' in key:
                data[key] = 0.01 * data[key]
    def readAll (self, meter):
        addr = self.baseAddress + meter
        #print PowerScoutClient.reg_names
        #print "reading", len(PowerScoutClient.reg_names), 'starting from', PowerScoutClient.base_reg
        data = self.doRequest(
            mdbus.makeReadReg(
                 addr, PowerScoutClient.base_reg, len(PowerScoutClient.reg_names), fnc=3), 
                 mdbus.decodeInt16)
        res = {}
        for i in range (0, len(PowerScoutClient.reg_names)):            
            if 'LSW' == PowerScoutClient.reg_names[i][-3:]:
                name = PowerScoutClient.reg_names[i][:-4]
                if not name in res:
                    res[name] = 0
                res[name] += data[i]
            elif 'MSW' == PowerScoutClient.reg_names[i][-3:]:
                name = PowerScoutClient.reg_names[i][:-4]
                if not name in res:
                    res[name] = 0
                res[name] += (data[i]<<16)
            else:
                res[PowerScoutClient.reg_names[i]] = data[i]
        self._scale(res, meter)            
        return res
    def formatString(self, data):
        
        output = []
        cnt = 0
        
        groups = ['L1','L2','L3', 'System']
        remain = data.keys()
        
        for group in groups:
            cnt = 0
            k = data.keys()
            k.sort()
            for key in k:
                if not 'to' in key and group in key:
                    cnt += 1
                    output.append ("%27s = %9.3f"%(key,data[key]))
                    
                    remain.remove(key)            
                    if cnt >= 3:
                        output.append("\n")
                        cnt = 0
            output.append('\n')
            
        cnt = 0
        for key in remain:
            cnt += 1
            output.append ("%27s = %9.3f"%(key,data[key]))                    
            if cnt >= 3:
                output.append("\n")
                cnt = 0
        
        return "".join(output)
    def open(self, port='/dev/ttyUSB0', baudrate=9600):
        mdbus.SerialModbusClient.open(self,port,baudrate)
        
        self.scalar = [1]*6
        self.ctValue = [0]*6
        for meter in range(0,6):
            #self.ident(meter)
            #model = self.getModelName(meter)
            #mnum = self.getModelNumber(meter)
            
            #self.log.debug("Model name: %s Model number: %s"%(model,mnum))
            addr = self.baseAddress + meter
            
            #ensure DENT format
            #self.doRequest(
            #    mdbus.makeWriteReg(
            #         addr, 4525, 0))
            
            #self.ident(meter)
            #self.log ("setScaling to 1")
            #self.setScaling(meter, 1)

            #self.log.info('addr is %d'%addr)
            
            tmp = self.doRequest(
                mdbus.makeReadReg(
                    addr, 4300, 2, fnc=3), mdbus.decodeInt16)
            self.ctValue[meter] = tmp[0] 
            self.scalar[meter] = tmp[1]
                        
            self.log.info("Meter %d using CT: %d and data scalar: %d"%\
                        (meter, self.ctValue[meter], self.scalar[meter]))
    def sync(self, seconds):
        self.doRequest(
                mdbus.makeWriteReg(
                     0xff, 128, seconds))
    def getModelName(self,meter):
        addr = self.baseAddress + meter
        return self.doRequest(
            mdbus.makeReadReg(
                addr, 4200, 5, fnc=3),mdbus.decodeAscii)
        
    def getModelNumber(self,meter):
        addr = self.baseAddress + meter
        return self.doRequest(
            mdbus.makeReadReg(
                addr, 4205, 5, fnc=3),mdbus.decodeAscii)
    def getPower(self,meter):
        """returns power in watts for each of L1, L2, and L3"""
        addr = self.baseAddress + meter
        r = []
        res = self.doRequest(
                        mdbus.makeReadReg(
                            #addr, 4009, 3, fnc=3),mdbus.decodeInt16)
                            addr, 4028, 3, fnc=3),mdbus.decodeInt16)
        
        return [PowerScoutClient.kW_scalar[self.scalar[meter]]*i for i in res]
    def getVerisPower(self,meter):
        """returns power in watts for each of L1, L2, and L3"""
        addr = self.baseAddress + meter
        r = []
        res = self.doRequest(
                        mdbus.makeReadReg(
                            #addr, 4009, 3, fnc=3),mdbus.decodeInt16)
                            addr, 9, 3, fnc=3),mdbus.decodeInt16)
            
        return [1000.0*PowerScoutClient.veris_kW_scalar[self.scalar[meter]]*i for i in res]
        
    def getPf (self,meter):        
        addr = self.baseAddress + meter
        r = []
        res = self.doRequest(
                        mdbus.makeReadReg(
                            addr, 4049, 3, fnc=3),mdbus.decodeInt16)
        return res
    def getVolts(self,meter):
        addr = self.baseAddress + meter
        r = []
        res = self.doRequest(
                        mdbus.makeReadReg(
                            addr, 4058, 3, fnc=3),mdbus.decodeInt16)
        
        return [PowerScoutClient.V_scalar[self.scalar[meter]]*i for i in res]        
    def getSystemPower(self,meter):
        addr = self.baseAddress + meter
        res = self.doRequest(mdbus.makeReadReg(
                    addr, 4002, 1, fnc=3),mdbus.decodeInt16)[0]
        return res
        #return 1000.0*PowerScoutClient.kW_scalar[self.scalar[meter]]*\
                
    def getConfig(self,meter):
        addr = self.baseAddress + meter
        r = []
        r.append("Model: %s" % (self.getModelName(meter)))
        r.append("Model No: %s"%(self.getModelNumber(meter)))
#        r.append("CT Type: %d"% (self.doRequest(
#            mdbus.makeReadReg(
#                addr, 4524, 1, fnc=3),mdbus.decodeInt16)))
#        r.append("Slave ID: %d"% (self.doRequest(
#            mdbus.makeReadReg(
#                addr, 4525, 1, fnc=3),mdbus.decodeInt16)))       
 #       r.append("CT Phase Shift: %d"% (self.doRequest(
 #           mdbus.makeReadReg(
 #               addr, 4598, 1, fnc=3),mdbus.decodeInt16)))
 #       r.append("Volts Multiplier: %d"% (self.doRequest(
 #           mdbus.makeReadReg(
 #               addr, 4603, 1, fnc=3),mdbus.decodeInt16)))
 #       r.append("Amps Multiplier: %d"% (self.doRequest(
 #           mdbus.makeReadReg(
 #               addr, 4604, 1, fnc=3),mdbus.decodeInt16)))
 #       r.append("Service Type: %d"% (self.doRequest(
 #           mdbus.makeReadReg(
 #               addr, 4606, 1, fnc=3),mdbus.decodeInt16)))
 #       r.append("Set Line Frequency: %d"% (self.doRequest(
 #           mdbus.makeReadReg(
 #               addr, 4608, 1, fnc=3),mdbus.decodeInt16)))
        #r.append("Data Scale: %d"% (self.doRequest(
        #    mdbus.makeReadReg(
        #        addr, 4600, 2, fnc=3),mdbus.decodeInt16)[1]))

        return "\n".join(r)
        
def test():
    log = logging.getLogger('modbus')
    log.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    log.addHandler(ch)
    
    log = logging.getLogger('log')    
    log.addHandler(ch)
    
    
    port = '/dev/ttyUSB0'
    
    log.info ("Opening '%s'" % (port))
    
    p = PowerScoutClient(0x10);
    p.open(port)
    
    #while (True):
        
    #for scale in range (3,4):
    
    log.info(p.getConfig(0))
    
    while True:
        totalP = 0
        p.sync(1)        
        
        buf = []
        for meter in range(0,6):
            pwr = p.readAll(meter)
            print p.formatString(pwr)
            buf.append(pwr)
        log.info("Total kW: %8.5f"%(sum([i['kW System'] for i in buf])))
        
        time.sleep(1)    
        
    log.info('Done.')
    exit()
if __name__ == "__main__" : test()