# Creating a DLC auto-scaling solution
One of the advantages of using DLC is that during an outage of its upstream QRadar, it will buffer incoming events and patiently wait for QRadar to return. This works very well with the solution described in [data_sync_automation](../aws_qradar_availability/data_sync_automation/) due to the breif outage that happens during QRadar DataSync failover. DLC's buffering will ensure that data is only delayed and not lost.

However, this means that we're dependant upon the resiliency of DLC to maintain data flow. If the DLC should fail or if a datacenter or availability zone outage takes it out, then we could lose data or suffer an extended outage. The solution here is to setup AWS autoscaling to ensure that a DLC will be recovered/replaced automatically if it fails.

![DLC Failover Concept](images/multi-az-dlc-simplified.png)

In the above example, we have an initial DLC setup in one availability zone and added to an auto-scaling group where only one instance is running. If there is a major failure in the first AZ, autoscaling will create a new instance in the second AZ.

## The simple version
Let's start with a single-instance DLC autoscaling solution. In this use case our autoscaling group will have only a single DLC. If a failure is detected then that single instance will be replaced. The DLC wasn't really designed to run in a cluster so maintaining single-instance keeps things simple. This procedure can be repeated to provide multiple resilient DLC instances. Multi-instance autoscaling groups will come later.

### Create a DLC instance
Begin by installing a DLC instance on an EC2 instance normally, following the DLC Guide. This should include all the steps required for enabling TLS communication with QRadar. Be sure to confirm that DLC connection and authentication is working fully before proceeding.

### Create and mount an EFS filesystem
Second, set up and EFS filesystem in the same VPC as the DLC instance. This will be used to hold the DLC's state and things like log source configuration that will have to change over time. Follow the AWS guidance [here](https://aws.amazon.com/efs/getting-started/) or [here](https://aws.amazon.com/getting-started/tutorials/create-network-file-system/) to create the EFS filesystem. Once it is up an working, mount this filesystem in the DLC instance at the /mnt path. e.g:
```
mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2 fs-XXXXXXXX.efs.REGION.amazonaws.com:/ /mnt
```

Also add the above to the end of /etc/fstab so that it will survive a reboot. e.g:
```
fs-XXXXXXXX.efs.REGION.amazonaws.com:/	/mnt	nfs4	nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2	0	0
```

Now that we have the external storage available, we can move the DLC's stored data and config with the `migrate_to_nfs.sh` script. This scipt is invoked without parameters and will create a subdirectory on the nfs mount using the UUID of the DLC and within that copy config.json, logSources.json and /store. It will then symlink these to their original locations.

### Setup autoscaling for the DLC
wip
