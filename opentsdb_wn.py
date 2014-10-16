import threading
import logging
import Queue
import sqlite3
import traceback
import requests
import json
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


class dblogger(threading.Thread):
    def __init__(self, config, serno):
        super(dblogger, self).__init__()
        self.setDaemon(True)       
        
        self.name = "OpenTSDB push thread"
        
        self.shutdownEvt = threading.Event()
        self.q = Queue.Queue()
        
        self.url = config.get('db', 'url')
        self.log = logging.getLogger(__name__)
        self.log.info("OpenTSDB logger activated on wn_{}".format(serno))
        self.serno = serno
                        
        self.localdb = config.get('db', 'localdb')
        
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
            self.log.error(traceback.format_exc())
            quit()
        
    def run(self):
        db = sqlite3.connect(self.localdb)
        count = 0
        try:        
            while not self.shutdownEvt.is_set():
                try:                    
                    cmd, data = self.q.get(True)
                    
                    if cmd == "log_data":
                        cr = db.cursor()
                        sql = "INSERT INTO wattnode VALUES (Null, ?, ?, ?, " + \
                        ", ".join(["?"]*len(wattNodeLogVars)) + ")"
                                                                    
                        cr.execute(sql, [self.serno, 
                                         getUTCTimestampS(data['time']), 
                                         True] + \
                                         [data[x] for x in wattNodeLogVars])
                        db.commit()
                        count = count + 1
                        
                        if count > 10:
                            self.q.put(('push', None)) # enqueue a push command
                            count = 0
                        
                    if cmd == 'quit' or cmd == 'push':
                        # push dirty samples to opentsdb
                        cr = db.cursor()
                        sql = "SELECT * from wattnode WHERE DIRTY = 1 LIMIT 30"
                        
                        wl = []
                        idlist= []
                        for d in cr.execute(sql):                            
                            f = zip ( ('id', 'serialnumber', 'ts', 'dirty')+ tuple(wattNodeLogVars), d)
                            d = {k:v for k,v in f}
                            idlist += [d['id']]
                            for param in wattNodeLogVars: 
                                wl += [
                                       {'metric': 'wattnode_{}'.format(d['serialnumber']),
                                        'timestamp': d['ts'],
                                        'value': d[param],
                                        'tags': {'parameter': param},
                                        }
                                       ]
                        if len(wl) > 0:
                            r = requests.post('http://{}:4242/api/put?details'.format(self.url),
                                              data = json.dumps(wl))
                            if r.status_code != requests.codes.ok:                                
                                self.log.error('Unknown error:' + r.text)                                                                
                            else:
                                self.log.info("pushed {} params to opentsdb".format(len(wl)))
                                rslt = json.loads(r.text)                            
                                
                                if len(rslt['errors']) > 0:
                                    self.log.error('query was: '+ json.dumps(wl))
                                    self.log.error('errors in pushing data')
                                    self.log.error(rslt)                                    
                                                                
                                #update dirty flags, skip error check from opentsdb for now.
                                for i in idlist:
                                    #self.log.warn("UPDATE wattnode SET DIRTY=0 WHERE ID={}".format(i))
                                    cr.execute("UPDATE wattnode SET DIRTY=0 WHERE ID=?", (i,))
                                db.commit()                            
                                    
                            c = cr.execute("SELECT COUNT(*) FROM wattnode WHERE DIRTY = 1").fetchone()[0]
                            
                            if (c > 10):
                                self.q.put(('push', None)) # enqueue a push command

                except Exception as x:
                    self.log.error(traceback.format_exc())
        finally:
            db.close()
        
    def close(self):
        
        self.shutdownEvt.set()
        self.q.put( ('quit', None) )
        self.join()
    
    def logit(self, data):
        
        self.q.put( ('log_data', data) )
        
        
if __name__=="__main__":
    print pywattnodeapi.__wattNodeAdvancedVars
    print pywattnodeapi.__wattNodeBasicVars
    create = """CREATE TABLE IF NOT EXISTS wattnode (
            ID INTEGER PRIMARY KEY, 
            SERIALNUMBER INTEGER NOT NULL,""" + \
            " REAL, ".join(pywattnodeapi.__wattNodeBasicVars) + \
            " REAL, ".join(pywattnodeapi.__wattNodeAdvancedVars) + ' REAL)'
    print create
    
    