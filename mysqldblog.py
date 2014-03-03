try:
	import MySQLdb
except ImportError:
	MySQLdb = None

from warnings import filterwarnings
import traceback



class dblogger:
    createWattnodeSql = """CREATE TABLE IF NOT EXISTS `%s`.`wattnode` (
  `id` bigint UNSIGNED NOT NULL AUTO_INCREMENT,
  `time` TIMESTAMP  NOT NULL DEFAULT now(),
  `Address` SMALLINT UNSIGNED NOT NULL,
  `EnergyA` FLOAT  NOT NULL,
  `EnergyB` Float  NOT NULL,
  `PowerA` FLOAT  NOT NULL,
  `PowerB` float  NOT NULL,
  `VoltA` float  NOT NULL,
  `VoltB` float  NOT NULL,
  `Freq` Float  NOT NULL,
  `PowerFactorA` Float  NOT NULL,
  `PowerFactorB` float  NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `time_idx`(`time`),
  INDEX `addr_idx`(`Address`)
)
ENGINE = MyISAM;"""

    def __init__(self, config, log):
        self.log = log 
        self.seqno = 0       
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
            self.cursor.execute ("CREATE DATABASE IF NOT EXISTS %s;"%(self.config.get('db','name')))
            
            self.cursor.execute (dblogger.createWattnodeSql %(self.config.get('db','name')))
            #self.cursor.execute (dblogger.createStatsSql %(self.config['name']))
            filterwarnings('default', category = MySQLdb.Warning)                                    
            
            self.conn.close()
            self.cursor.close()
            
            # now reconnect to the db (so reconnect works properly)
            self.conn = MySQLdb.connect(db = self.config.get('db', 'name'), \
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
            
    def logit(self, data):
                
        sql = """INSERT INTO wattnode (Address, EnergyA, EnergyB, PowerA, 
PowerB, VoltA, VoltB, Freq, PowerFactorA, PowerFactorB) VALUES 
(%d, %f, %f, %f, 
%f, %f, %f, %f, %f, %f)"""%\
                (data['address'], data['EnergyA'], data['EnergyB'], data['PowerA'],
                 data['PowerB'], data['VoltA'], data['VoltB'], 
                 data['Freq'], data['PowerFactorA'], data['PowerFactorB'])
                    
        self.seqno += 1            
        
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
