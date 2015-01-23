pywattnode
==========

Python interface and logger for the wattnode energy meter (modbus)

Installing as an init script 
----------

This assumes pywattnode is cloned in /home/pi/pywattnode

    $ sudo ln -s /home/pi/pywattnode /usr/local/pyWattnode
    $ sudo cp pywattnode/pywattnode /etc/init.d
    $ sudo cp pywattnode/pywattnode.conf /etc
    $ chmod +x pywattnode/pywattnode.py
    $ sudo update-rc.d pywattnode defaults
    $ sudo service pywattnode start
