# Automating DataSync failovers in AWS
QRadar's built-in HA solution doesn't function properly in AWS, making it difficult to auto-recover from major AZ failures. With the introduction of the Data Synchronization App for QRadar, however, it is possible to automate a Disaster Recovery style of failover. 
## Overview
AWS' Elastic Load Balancers provide CloudWatch metrics related to 'health' of hosts in the load balancing Target Groups. They will even maintain metrics on healthy host counts per target group per availability zone. We can leverage these metrics to determine when QRadar hosts performing collection in a specific AZ fail.  By using an AWS Lambda function, triggered by a CloudWatch Alarm based on the UnHealthyHostCount metric, we can detect when communication fails to a QRadar host and automatically failover to the secondary AZ by calling the QRadar APIs.

This solution is an example that can be used as a starting point for implementing highly resilient collection that can recover from the loss of an AZ and quickly resume service with near zero data loss (depending on collection protocol).
## Pre-requisites
As a starting point, we will assume that QRadar is already configured with a Main Site and Destination Site each in separate subnets and separate AZs but in the same VPC.  The example presented here represents Main and Destination deployments each with one Console and one Event Processor and with the Data Synchronization solution already set up. The reader should be familiar with this solution before attempting to add automation. See [Data Synchronization app Overview](https://www.ibm.com/support/knowledgecenter/SS42VS_SHR/com.ibm.dsapp.doc/c_Qapps_DS_intro.html)
## Step 1 - create an IAM policy and Role
We will need an IAM policy to grant the Lambda function access to LoadBalancers, permit logging and so forth. In AWS IAM, create a new policy using the JSON in iam-policy.json and give it a meaningful name (e.g. manage_failover).
Create an IAM role that can be assigned to the Lambda function and assign the newly created IAM policy to it. From the IAM -> roles page, create role, choose Lambda as the use case and attach the policy. Again, choose a name that is relevant (e.g. manage_failover).
## Step 2 - create an SNS topic
## Step 3 - create a CloudWatch Alarm
## Step 4 - create a Lambda function
## Step 5 - configure the Lambda function

