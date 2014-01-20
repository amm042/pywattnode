#!/usr/bin/python

import sys
import os
import ConfigParser
import traceback
from pywattnodeapi import ModbusException

from powerScout import PowerScoutClient
from datetime import datetime, timedelta
import time # for sleep
import serial
import logging
import logging.handlers
from mysqldblog_ps import dblogger as mysql_dblogger
import random
import sys


def runlog(p, config):
    log = logging.getLogger('log')
    
    db= mysql_dblogger(config)
    log.info('database connected')
    
    seqno = int(random.random() * sys.maxint)
    try:        
        period_sec =  timedelta(seconds = config.getint('powerscout', 'period_sec'))        
        
        while True:
            start = datetime.now()
            
            # sync all meters
            p.sync(1)  
            
            for meter in range(0,6):
                pwr = p.readAll(meter)
                log.debug(p.formatString(pwr))                            
                db.logit(meter, seqno, pwr)
            
            seqno += 1                
            sleep = period_sec - (datetime.now() - start)
            sleep_s = (sleep.days * 86400) + sleep.seconds + (sleep.microseconds / 1000000.0)
            log.info('took %s seconds; sleep time is %f seconds', period_sec - sleep, sleep_s)
            if sleep_s > 0:
                time.sleep(sleep_s)
            else:
                log.warning('took %s seconds; not meeting timing spec.', period_sec - sleep)
    finally: 
        db.close()

def createLogger(logfile):
    for name in ["log", "modbus", "db"]:
        log = logging.getLogger(name)        
        log.setLevel(logging.DEBUG)
    
        #tty= True
        #ch = logging.StreamHandler()
        ch = None
         
        if ch == None:    
            tty = False
            
            try:
                if sys.stdout.isatty():
                    tty = True
            except:            
                tty = False
                
            if tty:
                # create console handler
                ch = logging.StreamHandler()
            else:
                try:
                    # if running as a deamon log to a file
                    ch = logging.handlers.TimedRotatingFileHandler(
                            logfile, when='D',
                            interval = 1, backupCount=10)
                except IOError:            
                    ch = logging.handlers.TimedRotatingFileHandler(
                            os.path.split(logfile)[1], when='D',
                            interval = 1, backupCount=10)
    
                    
        # create formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        # add formatter to ch
        ch.setFormatter(formatter)
        # add ch to logger
        log.addHandler(ch)    

def readConfig(cfgfile):
    log = logging.getLogger('log')
    if len(sys.argv) <= 1:
        # first check /etc/pywattnode.conf       
        if os.path.isfile('/etc/'+cfgfile):            
            log.info ("Using global config file: '/etc/%s'", cfgfile)
            cfgfile = '/etc/%s'%cfgfile
        else:
            # check cwd
            files = os.listdir(os.getcwd())        
            files = filter(lambda x: os.path.basename(x) == cfgfile, files)
            
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
    
    debug_level = config.get ('debug', 'level')
    
    
    for name in ["log", "modbus", "db"]:
        log = logging.getLogger(name)        
            
        if debug_level == 'DEBUG':
            log.setLevel(logging.DEBUG)
        elif debug_level == 'INFO':
            log.setLevel(logging.INFO)
        elif debug_level == 'ERROR':
            log.setLevel(logging.ERROR)
        elif debug_level == 'CRITICAL':
            log.setLevel(logging.CRITICAL)
        else:
            # default level
            log.setLevel(logging.WARN)
        
    return config
def detectDev(log,str):
    log.info('Looking for powerscout')
    
    if os.path.exists('/dev/powerscout'):
        log.info ('Native powerscout node exists')
        yield '/dev/powerscout'
    else:
        for i in os.listdir('/dev'):
            if i.startswith(str):
                log.info('Found possible powerscout on /dev/%s', i)
                yield '/dev/'+i
    

def main():
    createLogger('/var/log/powerscout.log')
    log = logging.getLogger('log')
    config = readConfig('powerscout.conf')        
    
    port_prefix = config.get('powerscout', 'port_prefix')
    
#---- main run loop
    while True:
        for port in detectDev(log, port_prefix):            
            log.info ("Opening '%s'" % (port))
            p = None
            try:
                p = PowerScoutClient(int(config.get('powerscout', 'base_address')))

                p.open(port = port)                                                                                                    
                        
                log.info ("Setup complete, starting logger")
                           
                try:
                    runlog(p, config)
                except KeyboardInterrupt:            
                    log.critical("Shutting down")
                    p.close()
                    exit(1)
                except SystemExit:
                    log.critical("Exit() called, shutting down")
                    p.close()
                    raise
                except:
                    log.critical(traceback.format_exc())

            except serial.SerialException, msg:
                log.error("Failed to open port, will retry: %s", msg)
                time.sleep(15)
            except ModbusException, msg:
                log.error("Modbus error during init, will retry: %s", msg)
                time.sleep(15)
            
            finally:
                if p != None:
                    p.close()
        
        log.warn ("Tried all ports, waiting to retry in 5s")
        time.sleep (5)        
#---- main run loop

if __name__ == "__main__": main()
