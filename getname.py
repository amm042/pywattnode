import httplib
import socket
from xml.dom.minidom import parseString, Node

def getmachinename():    
    hostname = socket.gethostname().split('.')[0]
    try:    
        svr = 'ip-address.domaintools.com'
        url = '/myip.xml'
        
        conn = httplib.HTTPConnection(svr)
        conn.request("GET", url)
        response = conn.getresponse()
            
        data = response.read()
        if response.status == 200:        
            doc = parseString(data)
                    
            for node in doc.getElementsByTagName("hostname"):
                for i in node.childNodes:
                    if i.nodeType == Node.TEXT_NODE:
                        return ".".join((hostname, i.data))
            
        else:
            raise Exception (response.msg + '\n' + data)    
    except:
        return hostname    
if __name__ == "__main__":
    print getmachinename()