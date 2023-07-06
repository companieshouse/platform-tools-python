# ec2-tag-query

Searches for and returns data on EC2 instances based on the supplied tag name and tag value. The tag name must be supplied as configured in AWS and wildcards can be used in the tag value.

## Building this project

This project uses the `setuptools` build system available via `pip install build`. A build can be triggered with `python3 -m build`.

A basic Makefile is provided and provides the following actions
* `make build`: Builds the project
* `make clean`: Clean any post-build artefacts

The Python build output will be placed in a `./dist` directory and will comprise a tarball archive as well as a compiled wheel package.

## Requirements

* python >= 3.9
* boto3 >= 1.24.0
* botocore >= 1.27.0

## Command Line Options

```
usage: ec2-tag-query [-h] [--profile [profile]] [--region [region]] [--extended | --no-extended] [--output {text,json}]
                     [--confirm | --no-confirm]
                     tag value

Program arguments and options

positional arguments:
  tag                   Tag to use to filter instances.
  value                 Value of the supplied tag.

optional arguments:
  -h, --help            show this help message and exit
  --profile [profile]   AWS profile to use for authentication. Default: AWS_PROFILE var
  --region [region]     AWS region to query. Default: eu-west-2
  --extended, --no-extended
                        Display extended instance detail. (default: False)
  --output {text,json}  Output format.
  --confirm, --no-confirm
                        Verify settings before executing query. (default: False)
```

## Outputs

The script outputs to stdout either in column-formatted plain text or optionally as a JSON object. By default output is in a brief format which includes 

* EC2 instance ID
* Instance Name (if configured)
* Private IP address
* Running state

When in extended output mode, the script will additionally include

* Public IP (if configured)
* Launch timestamp
* Instance type

## Examples

Looking up instances based on their Name tag
```
$ ec2-tag-query Name devops2-mesos*

Instance Id            Name                   Private IP             State
============================================================================================
i-0861de88a722694d1    devops2-mesos-slave2   10.75.87.212           running
i-0363b0bef2b7fd942    devops2-mesos-slave1   10.75.47.111           running
i-011033ed6ad2ff273    devops2-mesos-master1  10.75.41.238           running
```

Overriding the currently exported AWS_PROFILE to lookup extended information in a different account
```
$ ec2-tag-query Environment platform --profile shared-services-eu-west-2 --extended --output json
{
    "i-0e3cbdd512fb9db42": {
        "Instance Id": "i-0e3cbdd512fb9db42",
        "Name": "ci-platform-web",
        "HostName": "Undefined",
        "Private IP": "10.44.8.88",
        "Public IP": "Undefined",
        "Type": "m5.large",
        "State": "running",
        "Launch Time": "2023-04-12 09:55:13+00:00"
    },
    "i-04b23c39d995397c4": {
        "Instance Id": "i-04b23c39d995397c4",
        "Name": "ci-platform-worker",
        "HostName": "Undefined",
        "Private IP": "10.44.8.45",
        "Public IP": "Undefined",
        "Type": "t3a.medium",
        "State": "running",
        "Launch Time": "2023-05-24 13:08:04+00:00"
    },
...
```
