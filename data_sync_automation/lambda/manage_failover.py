# Import the SDK and required libraries
import boto3
import json
import os
import logging
import sys
import socket
import requests
import ssl
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# qradar configurations
# TODO pull tokens from secret store instead of config
console_main=os.environ['MAIN_SITE_ADDRESS']
token_main=os.environ['MAIN_SITE_TOKEN']
console_dest=os.environ['DEST_SITE_ADDRESS']
token_dest=os.environ['DEST_SITE_TOKEN']

# Configure the SNS topic which you want to use for sending notifications
namespace = os.environ['NAMESPACE']
sns_arn = os.environ['SNS_TOPIC']

def lambda_handler(event, context):
	"""
	Main Lambda handler
	"""
	message = event['Records'][0]['Sns']['Message']
	global sns_client

	#print("Event: " + json.dumps(event, indent=2))
	print("Message: " + json.dumps(message, indent=2))

	try:
		sns_client = boto3.client('sns')
	except ClientError as e:
		logger.error(e.response['Error']['Message'])

	if "AlarmName" in message:
		json_message = json.loads(message)
		accountid = str(json_message['AWSAccountId'])
		alarm_name = str(json_message['AlarmName'])
		alarm_trigger = str(json_message['NewStateValue'])
		timestamp = str(json_message['StateChangeTime'])
		elb_name = ""
		az_name = ""
		region = os.environ["AWS_REGION"]
		if namespace == "AWS/ApplicationELB":
			for entity in json_message['Trigger']['Dimensions']:
				if entity['name'] == "LoadBalancer":
					elb_name = str(entity['value'])
				if entity['name'] == "AvailabilityZone":
					az_name = str(entity['value'])
		elif namespace == "AWS/NetworkELB":
			for entity in json_message['Trigger']['Dimensions']:
				if entity['name'] == "LoadBalancer":
					elb_name = str(entity['value'])
				if entity['name'] == "AvailabilityZone":
					az_name = str(entity['value'])
		logger.info("AccountID: {}".format(accountid))
		logger.info("Region: {}".format(region))
		logger.info("AvailabilityZone: {}".format(az_name))
		logger.info("LoadBalancer: {}, {}".format(namespace,elb_name))
		logger.info("Alarm Name: {}".format(alarm_name))
		logger.info("Alarm State: {}".format(alarm_trigger))
		
		sns_message = ""
		api_in_error = False

		# Take actions when an Alarm is triggered
		if alarm_trigger == 'ALARM':
			dest_console_url="https://{}/api/".format(console_main)
			main_console_url="https://{}/api/".format(console_main)
			logger.info(main_console_url)
			
			dr_config_dest=requests.get("{}{}".format(dest_console_url,"config/disaster_recovery/disaster_recovery_config"),verify=False,headers={"SEC":token_dest,"Allow-Hidden":"true"})
			if dr_config_dest.status_code != 200:
				api_in_error = True
			else
				dr_config_dest_json=dr_config_dest.json()
				logger.info(json.dumps(dr_config_dest_json,indent=3,sort_keys=True))
				# if the destination site is DR-enabled and in STANDBY, activate it
				if dr_config_dest_json['is_dr'] != 'FALSE' and dr_config_dest_json['site_state'] == 'STANDBY':
					dr_config_dest_json['site_state'] = 'ACTIVE'
					dr_config_dest_json['is_dr'] = 'PRIMARY'
					dr_config_dest_json['ariel_copy_enabled'] = True
					logger.info(json.dumps(dr_config_dest_json,indent=3,sort_keys=True))
					dest_result=requests.post("{}{}".format(dest_console_url,"staged_config/disaster_recovery/disaster_recovery_config"),verify=False,headers={"SEC":token_dest,"Allow-Hidden":"true"},data=dr_config_dest_json)
					if dest_result.status_code == 200:
						# deploy dest site asap, before attemtping to reach the main site
						dest_result=requests.post("{}{}".format(dest_console_url,"config/deploy_action?type=INCREMENTAL"),verify=False,headers={"SEC":token_dest,"Allow-Hidden":"true"})
						if dest_result.status_code != 200:
							api_in_error = True
					else:
						api_in_error = True

			if api_in_error:
				sns_message = sns_message + "Attempted failover to destination failed, API failure!!"
				send_sns(sns_message)
				return
				
			# TODO optionally remove the main site hosts from the target group to avoid mixed recovery
			
			# assuming we can still reach the main site console, deactivate it
			dr_config_main=requests.get("{}{}".format("{}{}".format(main_console_url,"config/disaster_recovery/disaster_recovery_config"),verify=False,headers={"SEC":token_main,"Allow-Hidden":"true"})
			if dr_config_main.status_code != 200:
				api_in_error = True
			else:
				dr_config_main_json = dr_config_main.json()
				logger.info(json.dumps(dr_config_main_json,indent=3,sort_keys=True))
				if dr_config_main_json['is_dr'] == 'PRIMARY' and dr_config_main_json['site_state'] == 'ACTIVE':
					dr_config_main_json['site_state'] = 'STANDBY'
					dr_config_dest_json['ariel_copy_enabled'] = False
					logger.info(json.dumps(dr_config_dest_json,indent=3,sort_keys=True))
					main_result = requests.post("{}{}".format(main_console_url,"staged_config/disaster_recovery/disaster_recovery_config"),verify=False,headers={"SEC":token_dest,"Allow-Hidden":"true"},data=dr_config_main_json)
					if main_result.status_code != 200:
						api_in_error = True
					else:
						ariel_copy_main=requests.get("{}{}".format("{}{}".format(main_console_url,"disaster_recovery/ariel_copy_profiles"),verify=False,headers={"SEC":token_main,"Allow-Hidden":"true"})
						if ariel_copy_main.status_code == 200:
							ariel_copy_main_json = ariel_copy_main.json()
							for profile in ariel_copy_main_json:
								profile['enabled'] = False
							logger.info(json.dumps(ariel_copy_main_json,indent=3,sort_keys=True))
							copy_result=requests.post("{}{}".format(main_console_url,"disaster_recovery/ariel_copy_profiles"),verify=False,headers={"SEC":token_main,"Allow-Hidden":"true"},data=ariel_copy_main_json)
						
					if main_result.status_code == 200:
						main_result=requests.post("{}{}".format(dest_console_url,"config/deploy_action?type=INCREMENTAL"),verify=False,headers={"SEC":token_dest,"Allow-Hidden":"true"})
						if main_result.status_code != 200:
							api_in_error = True
					else:
						api_in_error = True
			
			if api_in_error:
				sns_message = sns_message + "Attempted failover to destination failed, API failure!!"
				send_sns(sns_message)
				return

	return

def send_sns(accountid,region,az_name,elb_name,timestamp,alarm_name,message):
	logger.info("SNS message:")
	notif="accountid:{}\n region:{}\n az_name:{}\n elb_name:{}\n timestamp:{}\n alarm_name:{}\n\n message:{}\n".format(accountid, region, az_name, elb_name, timestamp, alarm_name, message)
	logger.info(notif)
	try:
		sns_client.publish(
			TopicArn=sns_arn,
			Message=notif,
			Subject='DR Failover: attempted failover to Destination',
			MessageStructure='string'
		)
	except ClientError as e:
		logger.error(e.response['Error']['Message'])


