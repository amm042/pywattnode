
try:
    import couchdb
except ImportError:
    # if we don't have couchdb installed this won't work, but won't die either.
    couchdb = None

from uuid import uuid1
import time
from getname import getmachinename
from datetime import datetime
from socket import gethostname

class dblogger:
    def __init__(self, config, log):
        self.log = log 
        self.shorthostname = gethostname()
        self.hostname = getmachinename()
        self.seqno = 0
        self.config = config
        self.log.debug("making initial db connection to '%s'",
                       config.get('db','host'))
        
        self.dbname = config.get('db','dbname')
        self.doConnect()
        
        # kludgy map string into a bool...
        if {"true": True, "yes":True, "false": False, "no":False}.get(config.get('db','replicate').lower()):
            self.server.replicate ('wattnode', \
                                   "".join( (config.get('remotedb','host'),\
                                             config.get('remotedb','dbname')) ),\
                                   continuous=True)
        
    def close(self):
        pass
        
    def doConnect(self):
        self.server = couchdb.Server(self.config.get('db','host'))
        
        if self.dbname in self.server:
            self.db = self.server[self.dbname]
        else:
            self.db = self.server.create(self.dbname) 
            
        return True                
            
    def logit(self, data):
        data['host'] = self.hostname
        now = datetime.now()
        data['time'] = now.isoformat()
        key = "%s %s"%(self.shorthostname, now.strftime("%Y-%m-%d %H:%M:%S"))
        #self.db[uuid1(clock_seq=self.seqno).hex] = data
        self.db[key] = data
        self.seqno += 1
