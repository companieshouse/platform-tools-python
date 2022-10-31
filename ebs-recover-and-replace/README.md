# ebs-recover-and-replace

Helps manage the restoration of EBS volumes from snapshots and attaching the restored volumes to a selected instance

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
usage: ebs-recover-and-replace [-h] [--searchtags [searchtags]] [--profile [profile]] [--region [region]]
                               [--switchvols | --no-switchvols] [--saveplan [saveplan]] [--loadplan [loadplan]]

Program arguments and options

optional arguments:
  -h, --help            show this help message and exit
  --searchtags [searchtags]
                        A CSV list of Key=Value pairs used for search filtering on instance tags. Example: TagName=TagValue,Foo=Bar
  --profile [profile]   AWS profile to use for authentication. Default: AWS_PROFILE var
  --region [region]     AWS region to query. Default: eu-west-2
  --switchvols, --no-switchvols
                        Automatically switch volumes with those restored from snapshot (default: False)
  --saveplan [saveplan]
                        Take no actions but output a plan to the file specified
  --loadplan [loadplan]
                        Load a saved plan from the file specified
```

## Outputs

The script outputs progress to stdout as it runs, including verifying applicable resource IDs including, such as

* Target EC2 instance ID
* EBS Volume IDs and attachment Device Names
* Snapshot IDs

## Saving and loading plans

Using the `saveplan` option, a JSON-formatted file can be written to disk instead of executing the specified plan. This file contains all the necessary data the script requires to execute the plan and so can function as a way of saving the plan for later execution in a similar way to `terraform plan -out=<filename>`.

Example:
```
ebs-recovery-and-replace --searchtags Environment=MyEnv,Service=MyService --saveplan my_saved_plan.out
```

A previously saved plan can be loaded using the `loadplan` option. This will read in a previously saved plan file and, after some validation of the plan to ensure consistency, will load the data and present the user with a confirmation screen similar to the one presented during normal operation.

Example:
```
ebs-recovery-and-replace --loadplan my_saved_plan.out
```
