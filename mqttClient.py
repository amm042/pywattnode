    
import logging
import paho.mqtt.client as mq

class mqClient():
    def __init__(self, config, serno):
        
        self.log = logging.getLogger(__name__)
        self.topic = 'wn_{}/raw'.format(serno)
            
        if config.has_section('mqtt'):                    
            self.broker_url = config.get('db', 'broker')
            self.log.info("MQTT logging enabled to broker: {}".format(self.broker_url))
            
            self.client = mq.Client()
            
            self.client.loop_start()
            
        else:
            self.client = None
            self.broker_url = None
            self.log.info("MQTT not enabled (set [mqtt] broker = ... )")
            
    def close(self):
        if self.client:
            self.client.loop_stop()
            self.client = None
            
    def pub(self, data):
        
        self.client.publish(self.topic, data)