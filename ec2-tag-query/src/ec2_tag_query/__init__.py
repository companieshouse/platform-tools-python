import os
import sys
import boto3
import argparse
import json
from collections import defaultdict
from botocore import exceptions as botoexcept

"""
A tool for retrieving basic information from the running EC2 instances.
Largely taken from https://gist.github.com/dastergon/b4994c605f76d528d0c4
but modified to allow argument-based specification of tag name and value,
query region and to display brief or extended details in both text or
json. Text output will be in columns for density reasons.
"""


def confirm_settings(TagName, TagValue, Region, Profile, Output):
    message = """
AWS Profile: {}
AWS Region:  {}
Tag Name:    {}
Tag Value:   {}
Output Mode: {}
""".format(
        Profile, Region, TagName, TagValue, Output
    )

    print(message)

    try:
        input("Press Enter to continue or CTRL+C to exit.")
    except KeyboardInterrupt:
        sys.exit("")


def get_ec2_instances(TagName, TagValue, Region, Profile, OutputMode, Extended):

    try:
        # Connect to EC2
        session = boto3.Session(profile_name=Profile)
        ec2 = session.resource("ec2", Region)

        # Get information for all running instances
        running_instances = ec2.instances.filter(
            Filters=[{"Name": "tag:" + TagName, "Values": [TagValue]}]
        )

        ec2info = defaultdict()
        for instance in running_instances:
            for tag in instance.tags:
                if tag["Key"] == "Name":
                    name = tag["Value"]

                hostname = "Undefined"
                if "HostName" in tag["Key"]:
                    hostname = tag["Value"]

                privateip = "Undefined"
                if instance.private_ip_address != None:
                    privateip = instance.private_ip_address

                publicip = "Undefined"
                if instance.public_ip_address != None:
                    publicip = instance.public_ip_address

                # Render datetime object
                launchtime = "{}".format(instance.launch_time)

            # Add instance info to a dictionary
            if Extended:
                ec2info[instance.id] = {
                    "Instance Id": instance.id,
                    "Name": name,
                    "HostName": hostname,
                    "Private IP": privateip,
                    "Public IP": publicip,
                    "Type": instance.instance_type,
                    "State": instance.state["Name"],
                    "Launch Time": launchtime,
                }
            else:
                ec2info[instance.id] = {
                    "Instance Id": instance.id,
                    "Name": name,
                    "Private IP": privateip,
                    "State": instance.state["Name"],
                }

    except botoexcept.NoCredentialsError as nocrederr:
        sys.exit(nocrederr)

    except botoexcept.UnauthorizedSSOTokenError as ssotokenerr:
        sys.exit(ssotokenerr)

    except botoexcept.ProfileNotFound as profileerr:
        sys.exit(profileerr)

    if OutputMode == "json":
        print(json.dumps(ec2info, indent=4))
    else:
        # Determine column width by checking string lengths + 2 characters for padding
        if len(ec2info.items()) > 0:
            col_width = (
                max(
                    len(data_value)
                    for instance_id, instance_data in ec2info.items()
                    for data_key, data_value in instance_data.items()
                )
                + 2
            )

            # Set up column headers
            if Extended:
                col_headers = [
                    "Instance Id",
                    "Name",
                    "HostName",
                    "Private IP",
                    "Public IP",
                    "Type",
                    "State",
                    "Launch Time",
                ]
            else:
                col_headers = ["Instance Id", "Name", "Private IP", "State"]

            # Setup output
            print("")
            print("".join(col_header.ljust(col_width) for col_header in col_headers))
            print("=" * (col_width * len(col_headers)))

            for instance_id, instance_data in ec2info.items():
                print(
                    "".join(
                        data_value.ljust(col_width)
                        for data_key, data_value in instance_data.items()
                    )
                )

        else:
            # No results returned
            print("")
            print("No results found.")

    print("")


def main():
    # Double-check we're running with at least Python 3.9
    if sys.version_info < (3,9):
        sys.exit("Error: Python 3.9 or higher is required.")

    # Parse command line arguments/options
    parser = argparse.ArgumentParser(description="Program arguments and options")
    parser.add_argument("tag", help="Tag to use to filter instances.")
    parser.add_argument("value", help="Value of the supplied tag.")
    parser.add_argument(
        "--profile",
        metavar="profile",
        nargs="?",
        help="AWS profile to use for authentication. Default: AWS_PROFILE var",
        default="",
    )
    parser.add_argument(
        "--region",
        metavar="region",
        nargs="?",
        help="AWS region to query. Default: eu-west-2",
        default="eu-west-2",
    )
    parser.add_argument(
        "--extended",
        metavar="extended",
        help="Display extended instance detail.",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--output",
        default="text",
        type=str,
        help="Output format.",
        choices=["text", "json"],
    )
    parser.add_argument(
        "--confirm",
        metavar="confirm",
        help="Verify settings before executing query.",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    args = parser.parse_args()

    # Check to ensure user's AWS_PROFILE env var is set or we've been
    # given a value via the --profile argument. Values provided via
    # command line argument take precedence.
    if not os.environ.get("AWS_PROFILE") and args.profile == "":
        sys.exit("Error: AWS_PROFILE is not set and no profile specified.")
    elif os.environ.get("AWS_PROFILE") and args.profile == "":
        awsprofile = os.environ.get("AWS_PROFILE")
    elif not os.environ.get("AWS_PROFILE") and args.profile != "":
        awsprofile = args.profile
    elif os.environ.get("AWS_PROFILE") and args.profile != "":
        awsprofile = args.profile
    else:
        sys.exit("Unexpected error determining AWS Profile.")

    # Confirm script settings before continuing
    if args.confirm:
        confirm_settings(args.tag, args.value, args.region, awsprofile, args.output)

    # Connect to API and run the query
    try:
        get_ec2_instances(
            args.tag, args.value, args.region, awsprofile, args.output, args.extended
        )
    except KeyboardInterrupt:
        sys.exit("\nOperation cancelled by user.\n")

if __name__ == "__main__":
    main()
