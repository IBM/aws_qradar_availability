#!/bin/bash

DLC_UUID=`basename /etc/dlc/instance/*`

mkdir /mnt/${DLC_UUID}

if [ $? -eq 0 ]; then
	systemctl stop dlc
	mv /opt/ibm/si/services/dlc/conf/config.json /mnt/${DLC_UUID}/config.json
	ln -s /mnt/${DLC_UUID}/config.json /opt/ibm/si/services/dlc/conf/config.json
	mv /opt/ibm/si/services/dlc/conf/logSources.json /mnt/${DLC_UUID}/logSources.json
	ln -s /mnt/${DLC_UUID}/logSources.json /opt/ibm/si/services/dlc/conf/logSources.json
	mv /store /mnt/${DLC_UUID}/
	ln -s /store /mnt/${DLC_UUID}/store
	systemctl start dlc
else
	echo "Relocation failed: unable to create /mnt/${DLC_UUID}"
	exit 1
fi

