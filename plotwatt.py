import pw.plotwattapi as pw

import traceback



class dblogger:

    def __init__(self, config, log):
        self.log = log
        self.config = config
        self.log.info("Connecting to plotwatt using house_id: {} api_key: {}".format(
            config.get('db','house_id'),
            config.get('db', 'api_key')))
        self.pw = pw.Plotwatt(config.get('db','house_id'),
                              config.get('db', 'api_key'))
        self.meters = self.pw.list_meters()
        self.batchsize = config.getint('db', 'batchsize')
        if len(self.meters) == 0:
            self.log.info("Creating new meter.")
            self.meters.extend(pw.create_meters(1))
        self.log.info("Using meter: {}".format(
            self.meters[0]))

        self.cache = []

    def close(self):
       	pass


    def logit(self, data):
        self.cache.append (data)

        if len (self.cache) >= self.batchsize:
            self.log.info ("Pushing {} readings...".format(len(self.cache)))
            self.log.debug ("{}, {}".format(
                                [x['PowerSum']/1000.0 for x in self.cache],
                                [x['time'] for x in self.cache]))

            self.pw.push_readings(
                    self.meters[0],
                    [x['PowerSum']/1000.0 for x in self.cache],
                    [x['time'] for x in self.cache])
            self.cache = []
        #sql = """INSERT INTO wattnode (Address, EnergyA, EnergyB, PowerA,
#PowerB, VoltA, VoltB, Freq, PowerFactorA, PowerFactorB) VALUES
#(%d, %f, %f, %f,
#%f, %f, %f, %f, %f, %f)"""%\
#                (data['address'], data['EnergyA'], data['EnergyB'], data['PowerA'],
#                 data['PowerB'], data['VoltA'], data['VoltB'],
#                 data['Freq'], data['PowerFactorA'], data['PowerFactorB'])


if __name__ == "__main__":

    HOUSE_ID = 11672
    API_KEY = "MDM0OTAyMzEwZTM0"
    p = pw.Plotwatt(HOUSE_ID, API_KEY)

    meters = p.list_meters()
    if len (meters) == 0:
        print 'creating meter'
        meters.extend(p.create_meters(1))
    print 'meters: ', meters



