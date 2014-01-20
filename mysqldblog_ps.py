import MySQLdb
from warnings import filterwarnings
import traceback
import logging

class dblogger:
    createSql = """CREATE TABLE IF NOT EXISTS `powerscout`.`energy` (
  `id` bigint  NOT NULL AUTO_INCREMENT,
  `when` timestamp  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `seqno` int  NOT NULL,
  `meter` smallint  NOT NULL,
  `freq` double  NOT NULL,
  `L1_kwh` double  NOT NULL,
  `L2_kwh` double  NOT NULL,
  `L3_kwh` double  NOT NULL,
  `L1_kvarh` double  NOT NULL,
  `L2_kvarh` double  NOT NULL,
  `L3_kvarh` double  NOT NULL,
  `L1_kvah` double  NOT NULL,
  `L2_kvah` double  NOT NULL,
  `L3_kvah` double  NOT NULL,
  `L1_volts` double  NOT NULL,
  `L2_volts` double  NOT NULL,
  `L3_volts` double  NOT NULL,
  PRIMARY KEY (`id`)
)
ENGINE = MyISAM;"""

    def __init__(self, config):
        self.log = logging.getLogger("db")
        self.config = config
        self.log.debug("making initial db connection to '%s'",
                       config.get('db','host'))
        self.doConnect()
    def close(self):
        self.cursor.close()
        self.conn.close()
        
    def doConnect(self):
        try:
            #db = self.config.get('db','name'), \
            self.conn = MySQLdb.connect(\
                                        host = self.config.get('db','host'), \
                                        user = self.config.get('db','user'), \
                                        passwd = self.config.get('db','pass'),
                                        reconnect=1)
            self.cursor = self.conn.cursor()
            
            filterwarnings('ignore', category = MySQLdb.Warning)
            # the next lines will create warnings if the database/table
            self.cursor.execute ("CREATE DATABASE IF NOT EXISTS powerscout;")            
            self.cursor.execute (dblogger.createSql)            
            filterwarnings('default', category = MySQLdb.Warning)                                    
            
            self.conn.close()
            self.cursor.close()
            
            # now reconnect to the db (so reconnect works properly)
            self.conn = MySQLdb.connect(db = 'powerscout', \
                                        host = self.config.get('db','host'), \
                                        user = self.config.get('db','user'), \
                                        passwd = self.config.get('db','pass'),
                                        reconnect=1)
            self.cursor = self.conn.cursor()            
            
            #self.cursor.execute ("USE %s"%(self.config.get('db','name')))
            
            return True
        except (AttributeError, MySQLdb.OperationalError):
            self.log.error('connect failed: %s'%( traceback.format_exc()))
        
        return False            
            
    def logit(self, meter, seqno, data):
        data['seqno'] = seqno
        data['meter'] = meter
        #map powerscout register names to the DB names
        map = {'freq': 'Line Frequency',
               'seqno': 'seqno',
               'meter': 'meter'}
        
        for L in ['L1', 'L2', 'L3']:
            for db_name,ps_name in [('%s_kwh', 'kWh %s'),
                                    ('%s_kvarh', 'kVARh %s'),
                                    ('%s_kvah', 'kVAh %s'),
                                    ('%s_volts', 'Volts %s to Neutral')]:
                map[db_name%L] = ps_name%L
        
        keys = map.keys()
        #self.log.info(str(map))
        #self.log.info(str(data))
        sql = "INSERT INTO energy (" + \
              ",".join(keys) +\
              ") VALUES (" +\
              ",".join([str(data[map[v]]) for v in keys]) +\
              ")"                        
        
        try:
            self.conn.ping()
            ok = True
        except (MySQLdb.OperationalError):
            ok = False
            
        if ok == False:
            ok = self.doConnect()
    
        if ok != False:        
            try:                
                self.cursor.execute(sql)
                self.conn.commit()             
            except (AttributeError, MySQLdb.OperationalError):
                self.log.error('execute failed: %s', traceback.format_exc())      
        else:
            self.log.error('could not connect to db')