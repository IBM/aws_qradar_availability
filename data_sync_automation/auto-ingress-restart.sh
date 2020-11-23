#!/bin/bash

RESTART_TOUCHFILE=/store/tmp/ecIngressRestartRequired
CLASSPATH_BUILDER=/opt/qradar/systemd/bin/ecs-ec-ingress.build_classpath.sh
DATA_SYNC_CONFIG=/opt/qradar/conf/dr.conf
INGRESS_JAR_CHECK=/opt/ibm/si/services/ecs-ec-ingress/eventgnosis/lib/q1labs/q1labs_semsources_protocol_ibmqradardlc.jar

. $DATA_SYNC_CONFIG

# drop out immediately if DR is not enabled
if [ "$is_dr" == "FALSE" ]; then
	exit 1
fi

# establish site identity
if [ -f /root/main_site ]; then
	SITE_ID="MAIN"
elif [ -f /root/dest_site ]; then
	SITE_ID="DEST"
elif [ "$is_dr" == "PRIMARY" ] && [ "$site_state" == "ACTIVE" ]; then
	touch /root/main_site
	SITE_ID="MAIN"
	if [ -f /opt/qradar/systemd/bin/ecs-ec-ingress.build_classpath.sh ]; then
		sed -i -e 's/is_dr=DR/site_state=STANDBY/' /opt/qradar/systemd/bin/ecs-ec-ingress.build_classpath.sh
	fi
	{ crontab -l; echo ""; echo "* * * * * $PWD/$0"; } | crontab -
elif [ "$is_dr" == "DR" ] && [ "$site_state" == "STANDBY" ]; then
	touch /root/dest_site
	SITE_ID="DEST"
	{ crontab -l; echo ""; echo "* * * * * $PWD/$0"; } | crontab -
fi

# if there is no site identity, bail out
if [ -z "$SITE_ID" ]; then
	echo "DR not enabled, aborting"
	exit 1
fi

# if this is the primary site, check for standby and jarfile.
# if both, restart ingress
if [ "$SITE_ID" == "MAIN" ] && [ "$site_state" == "STANDBY" ] && [ -f "$INGRESS_JAR_CHECK" ]; then
	systemctl restart ecs-ec-ingress
fi

# if this is destination site and ingress touchfile exists,
# delete it and restart ingress
if [ "$SITE_ID" == "DEST" ] && [ -f "$RESTART_TOUCHFILE" ]; then
	systemctl restart ecs-ec-ingress
	rm -f "$RESTART_TOUCHFILE"
fi

