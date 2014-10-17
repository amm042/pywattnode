#!/usr/bin/python

import sys
import os
import ConfigParser
import traceback

from pywattnodeapi import SerialModbusClient, ModbusException, makeReadReg,\
    makeWriteReg, decodeInt32, decodeFloat32, decodeBasicFp, decodeAdvancedFp,\
    __wattNodeAdvancedVars,__wattNodeBasicVars

from datetime import datetime, timedelta
import time # for sleep
import serial
import logging
import logging.handlers
from mysqldblog import dblogger as mysql_dblogger
from couchdblog import dblogger as couch_dblogger

def runlog(p, wnconfig, config, log, tty, serno):

    dbtype = config.get('db', 'dbtype')
    if dbtype == 'mysql':
        db= mysql_dblogger(config, log)
    elif dbtype == 'couchdb':
        db= couch_dblogger(config, log)
    elif dbtype == 'plotwatt':
        from plotwatt import dblogger as plotwatt_dblogger
        db = plotwatt_dblogger(config, log)
    elif dbtype == 'opentsdb':
        from opentsdb_wn import dblogger 
        db = dblogger(config, serno)
    else:
        raise Exception("dbtype ('%s') not supported."%(dbtype))
    log.info('database connected')
    try:
        period_sec =  timedelta(seconds = config.getint('wattnode', 'period_sec'))

        #regs = []
        #for i in range(0, len(wnconfig)):
            #t = config.get('wattnode%d'%(i+1), 'regs')
            #t = [int(i) for i in t.split(',')]
            #regs.append (t)

        while True:
            start = datetime.utcnow()

            output = ""
            for i in range(0, len(wnconfig)):
                basic = p.doRequest(makeReadReg(wnconfig[i]['address'], 1000, 34), decodeBasicFp)
                adv = p.doRequest(makeReadReg(wnconfig[i]['address'], 1100, 76), decodeAdvancedFp)
                # merge the dicts
                data = dict (basic, **adv)
                data['address']=  wnconfig[i]['address']
                data['time'] = start

                #for key,value in data.iteritems():
                #log.info("%20s = %9.3f"%('address',data['address']))
                #for key in __wattNodeBasicVars:
                #    log.info("%20s = %9.3f"%(key,data[key]))
                output += "\n%20s = %9d\n"%('address',data['address'])

                for i in range(0, len(__wattNodeBasicVars), 4):
                    output += "".join ( ["%20s = %9.3f"%(key,data[key]) for key in __wattNodeBasicVars[i:i+4]])
                    output += "\n"
                #output += "\n".join( ["%20s = %9.3f"%(key,data[key]) for key in __wattNodeBasicVars])
                output += "\n"
                for i in range(0, len(__wattNodeAdvancedVars), 4):
                    output += "".join ( ["%20s = %9.3f"%(key,data[key]) for key in __wattNodeAdvancedVars[i:i+4]])
                    output += "\n"
                #output += "\n".join( ["%20s = %9.3f"%(key,data[key]) for key in __wattNodeAdvancedVars])
                db.logit(data)

            #if tty:
                #log.info(output)

            sleep = period_sec - (datetime.utcnow() - start)
            sleep_s = (sleep.days * 86400) + sleep.seconds + (sleep.microseconds / 1000000.0)
            log.info('took %s seconds; sleep time is %f seconds', period_sec - sleep, sleep_s)
            if sleep_s > 0:
                time.sleep(sleep_s)
            else:
                log.warning('took %s seconds; not meeting timing spec.', period_sec - sleep)
    finally:
        db.close()

def createLogger(logfile):
    log = logging.getLogger()
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
    
    LOGFMT = '%(asctime)s %(name)-30s %(levelname)-8s %(message)s'
    
    #formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    formatter = logging.Formatter(LOGFMT)
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    log.addHandler(ch)
    return log, tty

def readConfig(log, cfgfile):

    if len(sys.argv) <= 1:
        # first check /etc/pywattnode.conf
        if os.path.isfile(cfgfile):
            log.info ("Using global config file: '%s'", cfgfile)
        else:
            # check cwd
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

    debug_level = config.get ('debug', 'level')

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
    log.info('Looking for wattnode')

    if os.path.exists('/dev/wattnode'):
        log.info ('Native wattnode node exists')
        yield '/dev/wattnode'
    else:
        for i in os.listdir('/dev'):
            if i.startswith(str):
                log.info('Found possible wattnode on /dev/%s', i)
                yield '/dev/'+i


def main():
    log, tty = createLogger('pywattnode.log')#createLogger('/var/log/pywattnode.log')
    config = readConfig(log, '/etc/pywattnode.conf')

    port_prefix = config.get('wattnode', 'port')

    count = config.getint('wattnode', 'count')

    wnconfig = []
    req_opts = ['address', 'ctamps', 'averaging', 'phase', 'ctdirections']
    for i in range (1, count+1):
        cfg = {}
        for n in req_opts:
            cfg[n] = config.getint('wattnode%d'%(i), n)
        wnconfig.append(cfg)

#---- main run loop
    while True:
        for port in detectDev(log, port_prefix):
            log.info ("Opening '%s', config = %s" % (port,wnconfig))
            p = None
            try:
                p = SerialModbusClient(log)

                success = False
                serno = None
                while success == False:
                    try:
                        p.open(port)

                        log.info ("Reading wattnode serial numbers...")

                        for i in range(0, len(wnconfig)):
                            #read serial no
                            serno = p.doRequest(
                                                makeReadReg(
                                                wnconfig[i]['address'], 1700,2),decodeInt32) [0]
                            log.info ("Got wattnode serial number: %d", serno)

                            log.info ("Configuring averaging (%d)..."%(wnconfig[i]['averaging']))
                            # turn off averaging
                            p.doRequest(makeWriteReg(wnconfig[i]['address'],1607,wnconfig[i]['averaging']))

                            log.info ("Configuring CT amps (%d)..."%(wnconfig[i]['ctamps']))
                            # setup for 15A ct
                            p.doRequest(makeWriteReg(wnconfig[i]['address'],1602,wnconfig[i]['ctamps']))

                            log.info ("Configuring CT direction (%d)..."%(wnconfig[i]['ctdirections']))
                            p.doRequest(makeWriteReg(wnconfig[i]['address'],1606,wnconfig[i]['ctdirections']))

                            log.info ("Configuring phase offset (%d)..."%(wnconfig[i]['phase']))
                            p.doRequest(makeWriteReg(wnconfig[i]['address'],1618,wnconfig[i]['phase']))

                        success = True

                    except serial.SerialException, msg:
                        log.error("Failed to open port, will retry: %s", msg)
                        time.sleep(15)
                    except ModbusException, msg:
                        log.error("Modbus error during init, will retry: %s", msg)
                        time.sleep(15)

                log.info ("Setup complete, starting logger")

                try:
                    runlog(p, wnconfig, config, log, tty, serno)
                except KeyboardInterrupt:
                    log.critical("Shutting down")
                    p.close()
                    exit(1)
                except SystemExit:
                    log.critical("Exit() called, shutting down")
                    p.close()
                    raise
                except Exception as x:
                    log.critical(x)
                    log.critical(traceback.format_exc())

            finally:
                if p:
                    p.close()

        log.warn ("Tried all ports, waiting to retry in 5s")
        time.sleep (5)
#---- main run loop

if __name__ == "__main__": main()
