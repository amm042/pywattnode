#!/usr/bin/python

import sys
import os
import ConfigParser
import traceback
from pywattnodeapi import SerialModbusClient, makeReadReg, makeWriteReg,\
                            decodeFloat32, decodeInt32, decodeInt16
import time
import SocketServer

#-----------------------------------------------------------------------
# Logging
#-----------------------------------------------------------------------
import logging
log = logging.getLogger("server")

class WnHandler (SocketServer.BaseRequestHandler):
    count = 0
    def __init__(self):
        SocketServer.BaseRequestHandler.__init__(self)
        count += 1
        self.log = logging.getLogger("handler-%d"%(count))
    def __init__(self, request, client_address, server):        
        SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)
        count += 1
        self.log = logging.getLogger("handler-%d"%(count))
        
    def handle(self):
        self.log.debug ("Started handler")
        self.data = self.request.recv(1024).strip()
        self.log.debug ("%s wrote:" % self.client_address[0])
        self.log.debug (self.data)

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass
        
def serve(wn):    
    HOST, PORT = "localhost", 9999

    # Create the server, binding to localhost on port 9999
    #server = SocketServer.TCPServer((HOST, PORT), WnHandler)
    
    server = ThreadedTCPServer((HOST, PORT), WnHandler)
    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    server.serve_forever()
        
def main():
    
    log.setLevel(logging.INFO)
    #log.setLevel(logging.DEBUG)
    # create console handler 
    ch = logging.StreamHandler()
    #logging.basicConfig()
    # create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    log.addHandler(ch)

    cfgfile = ""
    if len(sys.argv) <= 1:
        files = os.listdir(os.getcwd())        
        files = filter(lambda x: os.path.splitext(x)[1]=='.conf',files)
        
        if len(files)==0:
            log.critical("No config file found!")
            exit(-1)
        else:
            cfgfile = files[0]            
            log.warn ("Using auto detecting config file: '%s'", cfgfile)            
    else:
        cfgfile = sys.argv[1]
        log.info("Reading config file '%s'", cfgfile)
                    
    try:
        config = ConfigParser.ConfigParser()
        config.read (cfgfile)        
    except:
        log.exception("failed to read config file")
        exit(-2)
    
    port = config.get('wattnode', 'port')
    
    req_opts = ['address', 'ctamps', 'averaging']    
        
    wnconfig = {}
    for n in req_opts:
        wnconfig[n] = config.getint('wattnode', n)    
        
    log.info ("Opening '%s', config = %s" % (port,wnconfig))
    p = SerialModbusClient(); 
    p.open(port)
    
    serno = p.doRequest(
            makeReadReg(
                wnconfig['address'], 1700,2),decodeInt32) [0]
                
    # turn off averaging
    p.doRequest(makeWriteReg(wnconfig['address'],1607,wnconfig['averaging']))
    
    # setup for 15A ct
    p.doRequest(makeWriteReg(wnconfig['address'],1602,wnconfig['ctamps']))  
    
    log.info ("starting server")
               
    try:
        serve(p)        
    except KeyboardInterrupt:            
        print "Shutting down"
    except:
        log.critical(traceback.format_exc())            

    p.close()    

if __name__ == "__main__": main()
