    
import threading
import logging
import Queue
import sqlite3
import traceback
import requests
import json
import time
import random
#from pywattnodeapi import __wattNodeAdvancedVars, __wattNodeBasicVars

import calendar

from  pywattnodeapi import wattNodeLogVars

def getUTCTimestampS(dt):
    '''
    Returns the standard timestamp with second precision from given time
    Note: For database performance concern, using second precision is recommended

    dt: Python DateTime object
    '''    
    return int(calendar.timegm(dt.timetuple()))


class opentsdb_thread(threading.Thread):
    def __init__(self, serno, url, localdb):
        super(opentsdb_thread, self).__init__()
        self.setDaemon(True)       
        self.name = "OpenTSDB push thread"                
        self.q = Queue.Queue()
        self.queue_running = False        
        self.shutdownEvt = threading.Event()
        
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        self.url = url
        
        self.log.info("opentsdb url: {}".format(self.url))
        self.localdb = localdb
        self.serno = serno
                
        try:
            db = sqlite3.connect(self.localdb)
            create = """CREATE TABLE IF NOT EXISTS wattnode (
            ID INTEGER PRIMARY KEY, 
            SERIALNUMBER INTEGER NOT NULL,
            TS INTEGER NOT NULL, 
            DIRTY INTEGER NOT NULL,\n""" + \
            ",\n".join(["{} REAL".format(x) for x in wattNodeLogVars]) + ")"
            
            db.cursor().execute(create)
            db.commit()     
            db.close() 
            
            self.start()
        except Exception as x:
            self.log.critical(x)
            self.log.critical(traceback.format_exc())
    
    def run(self):
        try:
            self.queue_running = True
            db = sqlite3.connect(self.localdb)
            count = 0
            
            self.log.debug("thread started")
            try:        
                while not self.shutdownEvt.is_set():                
                    
                    try:                        
                        commands = []
                        datas = []
                        while not self.q.empty():
                            commands += [self.q.get(False)]
                        
                        if len(commands) == 0:
                            time.sleep(random.randint(1,10))
                        else:
                            for cmd,data in commands:                                               
                                if cmd == "log_data":
                                   datas += [data]
                                    
                                if cmd == 'quit' or cmd == 'push':
                                    pass  # legacy
                                
                            if len(datas) > 0:
                                # push dirty samples to opentsdb

                                wl = []
                                #idlist= []
                                for d in datas:                            
                                    #f = zip ( ('id', 'serialnumber', 'ts', 'dirty')+ tuple(wattNodeLogVars), d)
                                    #d = {k:v for k,v in f}
                                    #idlist += [d['id']]
                                    for param in wattNodeLogVars: 
                                        wl += [
                                               {'metric': 'wattnode_{}'.format(self.serno),
                                                'timestamp': getUTCTimestampS(d['time']),
                                                'value': d[param],
                                                'tags': {'parameter': param},
                                                }
                                               ]
                                if len(wl) > 0:
                                    self.log.debug("got {} params to push to opentsdb".format(len(wl)))
                                    
                                    rt_ct = 0
                                    rt_tm = 22
                                    success = False
                                    while not success and rt_ct < 10:
                                        try:
                                            r = requests.post('{}/put?details'.format(self.url),
                                                              data = json.dumps(wl), timeout = rt_tm)
                                            success = True
                                        except requests.Timeout:
                                            rt_ct += 1
                                            rt_tm *= 1.76
                                            self.log.error("Timeout while talking to server, retry {} of {} with timeout {}".format(rt_ct, 10, rt_tm))
    
                                    if not success or r.status_code != requests.codes.ok:
                                        if success:                                
                                            self.log.error('Unknown error:' + r.text)
                                        
                                        # put everything back on the queue
                                        for d in datas:
                                            self.q.put( ('log_data', d) )
                                    else:
                                        self.log.info("pushed {} params to opentsdb".format(len(wl)))
                                        rslt = json.loads(r.text)                            
                                        
                                        if len(rslt['errors']) > 0:
                                            self.log.error('query was: '+ json.dumps(wl))
                                            self.log.error('errors in pushing data')
                                            self.log.error(rslt)                                    

                                    if self.q.empty():
                                        # close the connection if we don't expect another put for a while
                                        r.close()
    
                    except Exception as x:
                        self.log.critical(x)
                        self.log.critical(traceback.format_exc())
            finally:
                db.close()
        finally:
            self.queue_running = False
            self.log.critical("thread exit")   
    def close(self):       
        self.shutdownEvt.set()
        self.q.put( ('quit', None) )
        self.join(5)
                
class dblogger():
    def __init__(self, config, serno):
                      
        self.url = config.get('db', 'url')
        self.log = logging.getLogger(__name__)
        self.log.info("OpenTSDB logger activated on wn_{}".format(serno))
        self.serno = serno
                        
        self.localdb = config.get('db', 'localdb')
        
        self.thread = None # opentsdb_thread(self.url, self.localdb)

    def close(self):
        if self.thread and self.thread.queue_running:
            self.thread.close()
    
    def logit(self, data):
        if not self.thread or  not self.thread.queue_running:
            self.thread = opentsdb_thread(self.serno, self.url, self.localdb)
            
        self.thread.q.put( ('log_data', data) )        
        
if __name__=="__main__":
    print pywattnodeapi.__wattNodeAdvancedVars
    print pywattnodeapi.__wattNodeBasicVars
    create = """CREATE TABLE IF NOT EXISTS wattnode (
            ID INTEGER PRIMARY KEY, 
            SERIALNUMBER INTEGER NOT NULL,""" + \
            " REAL, ".join(pywattnodeapi.__wattNodeBasicVars) + \
            " REAL, ".join(pywattnodeapi.__wattNodeAdvancedVars) + ' REAL)'
    print create
    
    