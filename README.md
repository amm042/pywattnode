pywattnode
==========

Python interface and logger for the wattnode energy meter (modbus)

Installing as an init script 
----------
Pre-Requisites:
Following packages need to be pre-installed.<br />
    sudo pip install paho-mqtt <br />
    sudo pip install simplejson <br />

In addition this assumes pywattnode is cloned in /home/pi/pywattnode and pip is already installed

    $ sudo ln -s /home/pi/pywattnode /usr/local/pyWattnode
    $ sudo cp pywattnode/pywattnode /etc/init.d
    $ sudo cp pywattnode/pywattnode.conf /etc
    $ chmod +x pywattnode/pywattnode.py
    $ sudo update-rc.d pywattnode defaults
    $ sudo service pywattnode start
