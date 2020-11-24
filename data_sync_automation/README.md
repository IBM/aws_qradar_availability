# Automating DataSync failovers in AWS
QRadar's built-in HA solution doesn't function properly in AWS, making it difficult to auto-recover from major AZ failures. With the introduction of the Data Synchronization App for QRadar, however, it is possible to automate a Disaster Recovery style of failover. 
## Overview
AWS' Elastic Load Balancers provide CloudWatch metrics related to 'health' of hosts in the load balancing Target Groups. They will even maintain metrics on healthy host counts per target group per availability zone. We can leverage these metrics to determine when QRadar hosts performing collection in a specific AZ fail.  By using an AWS Lambda function, triggered by a CloudWatch Alarm based on the UnHealthyHostCount metric, we can detect when communication fails to a QRadar host and automatically failover to the secondary AZ by calling the QRadar APIs.

This solution is an example that can be used as a starting point for implementing highly resilient collection that can recover from the loss of an AZ and quickly resume service with near zero data loss (depending on collection protocol).
## Pre-requisites
As a starting point, we will assume that QRadar is already configured with a Main Site and Destination Site each in separate subnets and separate AZs but in the same VPC.  The example presented here represents Main and Destination deployments each with one Console and one Event Processor and with the Data Synchronization solution already set up. The reader should be familiar with this solution before attempting to add automation. See [Data Synchronization app Overview](https://www.ibm.com/support/knowledgecenter/SS42VS_SHR/com.ibm.dsapp.doc/c_Qapps_DS_intro.html)
### Modify the DataSync failover behaviour
By default, when the Destination site is activated an interactive deploy action is required. This cannot be automated by the API but it can be automated on the QRadar hosts themselves.  Copy the `aut-ingress-restart.sh` script to every host in each deployment and execute it on each host. This will setup a cron job that will automatically restart ecs-ec-ingress according to the DR configuration and state.
### Set up a load balancer
There are two steps for this: create a target group that includes the Event Processors from both deployments and then create a Network Loadbalancer that will listen for incoming event sources (it is recommended that DLC be used for this scenario) and forward to the target group on the correct port (32500 for DLC).

In Create Target Group, choose IP address type and TCP protocol, provide the port number for collection (32500) and then select the VPC hosting the QRadar deployments. Next, register each of the Event Processors from both deployments and create the target group.
![TargetGroup Basic](https://github.com/ibm-security-intelligence/aws_qradar_availability/blob/main/data_sync_automation/images/targetgroup-basic.png)

In and exsting Load Balancer or a new one, navigate to the Listeners tab and add a listener for the target group, same port number.
![Loadbalancer Listeners](https://github.com/ibm-security-intelligence/aws_qradar_availability/blob/main/data_sync_automation/images/loadbalancer-listeners.png)
## Step 1 - create an IAM policy and Role
We will need an IAM policy to grant the Lambda function access to LoadBalancers, permit logging and so forth. In AWS IAM, create a new policy using the JSON in iam-policy.json and give it a meaningful name (e.g. manage_failover).

Create an IAM role that can be assigned to the Lambda function and assign the newly created IAM policy to it. From the IAM -> roles page, create role, choose Lambda as the use case and attach the policy. Again, choose a name that is relevant (e.g. manage_failover).
## Step 2 - create two SNS topics
The Lambda function needs a trigger for execution when a CloudWatch Alarm fires. Setup the first SNS topic to receive notification when the alarm state happens. CloudWatch will send the notification this topic and the Lambda function will be triggered by that notification. The second topic will be used by the Lambda function to send notification to any subscribers when a failover happens.

In SNS -> Topics, create a topic. Make sure to set the type to Standard (FIFO types cannot be used as Lambda triggers). The name should be meaningful (e.g. manage_failover_trigger). None of the optional sections are required, click Create topic at the bottom. Repeat for a second topic name (e.g. manage_failover_notifications).
## Step 3 - create a CloudWatch Alarm
In CloudWatch -> Alarms, create alarm and select a metric. The one we need is in NetworkELB -> Target Group, per AZ Metrics. From the list of Metrics, choose the one named UnHealthyHostCount that corresponds to the QRadar load balancer and the AZ for the Main Site. This metric will track the count of unhealthy hosts (EPs) in our primary deployment. When all is well, it should be zero. Click the Select Metric button.
![CloudWatch Metric](https://github.com/ibm-security-intelligence/aws_qradar_availability/blob/main/data_sync_automation/images/cloudwatch-alarm-metric.png)

Specify the conditions under which this metric will cause an alarm to be raised. In the Metric panel, change the statistic to Maximum and the Period to 1 minute. In the Conditions panel choose static, Greater/Equal and a threshold of 1. Open the Addition configuration section and set the datapoints to 3 out of 3. These conditions and thresholds are a good starting point but you may wish to tune them to be more sensitive. With these values it will require the UnHealthyHostCount to be 1 or higher for 3 minutes before the Lambda function is triggered. Click next.
![CloudWatch Conditions](https://github.com/ibm-security-intelligence/aws_qradar_availability/blob/main/data_sync_automation/images/cloudwatch-alarm-conditions.png)

Configure the action to take when the alarm is raised. make sure the state is 'in Alarm' and select the SNS topic created above. Click next at the bottom and name the alarm (e.g. Main Site UnHealthyHostCount). Click next and then Create alarm.
![CloudWatch Action](https://github.com/ibm-security-intelligence/aws_qradar_availability/blob/main/data_sync_automation/images/cloudwatch-alarm-actions.png)
## Step 4 - create a Lambda function
In Lambda -> Functions, create a new function. Select 'Author from scratch'. In the Basic Information Panel, give the function a name (e.g. manage_failover), choose a Python 2.7 Runtime and Change the default execution role to the role created above (e.g. manage_failover).
![Lambda Basic](https://github.com/ibm-security-intelligence/aws_qradar_availability/blob/main/data_sync_automation/images/lambda-basic.png)

In Advanced settings select the VPC of the deployment and then select all the subnets tha host the Main and Dest consoles. Choose a security group that will allow the Lambda funtion to communicate with the consoles (i.e. via HTTPS). This step is important as it allows the lambda function to reach the QRadar REST APIs.
![Lambda Advanced](https://github.com/ibm-security-intelligence/aws_qradar_availability/blob/main/data_sync_automation/images/create-lambda-advanced.png)
## Step 5 - configure the Lambda function
In the lambda page, find the Runtime settings panel and change the handler to manage_failover.lambda_handler so that Lambda can find the function in the zip file. In the Function code panel, choose Upload a .zip file from the Actions drop down and upload the manage_failover.py zip file. Finally in Basic settings, increase the timeout from the default 3 seconds to a more reasonable value like 5 minutes.  Be sure to allow enough time for the function to make multiple QRadar API calls.
![Lambda Runtime](https://github.com/ibm-security-intelligence/aws_qradar_availability/blob/main/data_sync_automation/images/lambda-runtime.png)
![Lambda Function](https://github.com/ibm-security-intelligence/aws_qradar_availability/blob/main/data_sync_automation/images/lambda-function-code.png)
![Lambda Basic](https://github.com/ibm-security-intelligence/aws_qradar_availability/blob/main/data_sync_automation/images/lambda-basic.png)

Now, configure the trigger for the lambda function so that it will execute when the CloudWatch Alarm fires. Click '+ Add trigger' and select SNS. Choose the correct topic (e.g. manage_failover_trigger). Finally, in the Environment panel, add the following variables:
* DEST_SITE_ADDRESS: the IP address of the console at the destination site
* DEST_SITE_TOKEN: an API token from the destination site with admin privileges
* MAIN_SITE_ADDRESS: the IP address of the console at the destination site
* MAIN_SITE_TOKEN: an API token from the destination site with admin privileges
* NAMESPACE: AWS/NetworkELB
* SNS_TOPIC: the topic ARN from the second SNS topic created above
![Lambda Env](https://github.com/ibm-security-intelligence/aws_qradar_availability/blob/main/data_sync_automation/images/lambda-environment.png)
# Next Steps
The failover automation is now in place. End-to-end testing will involve making one of the EPs in the Main site unvailable via the load balancer. This can be done by shutting it down, changing it's security group or any other method of interrupting the collection. With the defaults described above it will take several minutes. The failover can also be triggered by executing the labda function directly with a test event to simulate the Unhealthy target alarm and this is a good way to confirm the correct configuration and operation of the lambda function.

Once an automated failover has occurred, returning service back to the main site can be done via the Data Synchromization App according to its [documentation](https://www.ibm.com/support/knowledgecenter/SS42VS_SHR/com.ibm.dsapp.doc/c_Qapps_DS_intro.html)
