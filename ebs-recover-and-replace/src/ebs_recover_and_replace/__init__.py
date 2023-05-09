import argparse
import botocore
import boto3
import hashlib
import json
import os
import sys
import time

from collections import Counter


class colours:
    dblue = "\033[0;34m"
    dred = "\033[0;31m"
    byellow = "\033[1;33m"
    bgreen = "\033[1;32m"
    bold = "\033[1m"
    end = "\033[0m"


def format_output(message="", style="info", indent=4):
    prefix = ""
    suffix = ""
    if style == "error":
        print(f"{colours.dred}{style.capitalize()}:{colours.end} {message}")
    else:
        if style == "info":
            prefix = f"{colours.dblue}{style.capitalize()}:{colours.end} "

        if style == "warn":
            prefix = f"{colours.byellow}{style.capitalize()}:{colours.end} "

        if style == "item":
            prefix = f"{'':<{indent}}"

        if style == "choice":
            prefix = f"{colours.bgreen}→{colours.end} "

        if style == "header":
            prefix = f"{colours.bold}"
            suffix = f"{colours.end}"

    print(prefix + message + suffix)


def separator(width=80):
    print()
    banner = f"{'-' * width}"
    format_output(banner, "header")


def process_searchtags(searchtags):
    """
    Processes the searchtags provided on the command line and converts it to
    a dict. First by splitting on the comma and then on the equals to form a
    raw output. This is then processed further to remove all leading and
    trailing whitespace from both the dictionary keys and the values.
    """
    raw_dict = dict(pair.split("=") for pair in searchtags.split(","))
    clean_dict = {k.strip(): v.strip() for k, v in raw_dict.items()}
    return clean_dict


def validate_response(response):
    if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
        format_output(
            f"Received {response['ResponseMetadata']['HTTPStatusCode']} error from AWS",
            "error",
        )
        sys.exit(1)


def create_ec2_client(awsprofile, awsregion):
    """
    Connects to the AWS API and returns an EC2 client object
    """
    format_output("Connecting to AWS...")
    format_output(f"AWS Profile: [{awsprofile}]")
    format_output(f"AWS Region:  [{awsregion}]")
    try:
        # Connect to EC2
        session = boto3.Session(profile_name=awsprofile)
        ec2_client = session.client("ec2", awsregion)
        return ec2_client

    except botocore.exceptions.NoCredentialsError as nocrederr:
        format_output(nocrederr, "error")
        sys.exit(1)

    except botocore.exceptions.UnauthorizedSSOTokenError as ssotokenerr:
        format_output(ssotokenerr, "error")
        sys.exit(1)

    except botocore.exceptions.ProfileNotFound as profileerr:
        format_output(profileerr, "error")
        sys.exit(1)


def query_ec2_instances(ec2_client, searchtags, instanceid=None):
    """
    Returns a list of EC2 instances and associated data based on filters
    formed from the provided tag names and values.
    Can optionally be provided an instance ID to further refine the results.
    """
    format_output("Querying instances...")
    format_output(f"Search Tags: [{searchtags}]")
    filters_list = []
    for tagname, tagvalue in searchtags.items():
        filters_list.append({"Name": "tag:" + tagname, "Values": [tagvalue]})

    if instanceid is not None:
        filters_list.append({"Name": "instance-id", "Values": [instanceid]})

    # Get information for all running instances
    try:
        running_instances = ec2_client.describe_instances(
            Filters=filters_list,
        )

    except botocore.exceptions.UnauthorizedSSOTokenError as ssotokenerr:
        format_output(ssotokenerr, "error")
        sys.exit(1)

    except botocore.exceptions.ProfileNotFound as profileerr:
        format_output(profileerr, "error")
        sys.exit(1)

    instance_dict = {}
    for reservation in running_instances["Reservations"]:
        for instance in reservation["Instances"]:
            instance_id = instance["InstanceId"]
            private_ip = instance["PrivateIpAddress"]

            block_dev_list = []
            for block_dev in instance["BlockDeviceMappings"]:
                block_dev_list.append(
                    {
                        "DeviceName": block_dev["DeviceName"],
                        "VolumeId": block_dev["Ebs"]["VolumeId"],
                    }
                )

            for tags in instance["Tags"]:
                if tags["Key"] == "Name":
                    instance_name = tags["Value"]

            instance_dict[instance_id] = {
                "Name": instance_name,
                "IPAddress": private_ip,
                "BlockDevs": block_dev_list,
            }

    instances_num = len(Counter(instance_dict))

    if instances_num == 0:
        ec2_client.close()
        format_output("No results returned", "error")
        sys.exit(1)
    else:
        return instance_dict


def get_instance_choice(instance_dict):
    """
    If more than 1 instance is returned on a query, the user must specify on which
    instance the operations are to take place on.
    """
    format_output(f"Instances Found: {len(Counter(instance_dict))}")
    format_output("Select an instance to continue:", "choice")
    for index, instance_id in enumerate(instance_dict):
        instance_name = instance_dict[instance_id]["Name"]
        private_ip = instance_dict[instance_id]["IPAddress"]
        format_output(
            f"[{index}] {instance_id}, {instance_name} ({private_ip})", "item"
        )

    print()
    while True:
        selection_raw = input("Instance Selection: ")
        try:
            selection_int = int(selection_raw)
        except ValueError:
            format_output(
                f"Selection must be a number from 0 to {len(Counter(instance_dict)) - 1}",
                "warn",
            )
            continue

        if not (0 <= selection_int <= len(Counter(instance_dict)) - 1):
            format_output(
                f"Selection must be a number from 0 to {len(Counter(instance_dict)) - 1}",
                "warn",
            )
            continue
        else:
            for index, instance_id in enumerate(instance_dict):
                if index == selection_int:
                    selected_instance_id = instance_id
                    selected_instance_dict = instance_dict[instance_id]

            instance_dict.clear()
            instance_dict[selected_instance_id] = selected_instance_dict
            return instance_dict


def get_volume_choice(instance_dict):
    """
    Displays instance data to the user for confirmation and lists attached volumes for
    the user to choose from. The selected volume(s) will be used to later search
    for volume snapshots
    """

    for index, instance_id in enumerate(instance_dict):
        format_output(f"Instance ID:   {instance_id}")
        format_output(f"Instance Name: {instance_dict[instance_id]['Name']}")
        format_output(f"IP Address:    {instance_dict[instance_id]['IPAddress']}")
        format_output(f"Block Devices: {len(instance_dict[instance_id]['BlockDevs'])}")

        format_output("Select an option to continue:", "choice")
        for index, device in enumerate(instance_dict[instance_id]["BlockDevs"]):
            volume_id = device["VolumeId"]
            device_node = device["DeviceName"]
            if "sda" in device_node:
                device_message = "** ROOT **"
            else:
                device_message = ""
            format_output(
                f"[{index}] {volume_id} ({device_node}) {device_message}", "item"
            )

        format_output("[A] All block devices", "item")

        print()
        while True:
            selection_raw = input("Device Selection: ")

            if selection_raw == "A" or selection_raw == "a":
                format_output("All block devices selected")
                return instance_dict
            else:
                try:
                    selection_int = int(selection_raw)
                except ValueError:
                    format_output(
                        f"Selection must be a number from 0 to {len(instance_dict[instance_id]['BlockDevs']) - 1} or A for all block devices",
                        "warn",
                    )
                    continue

                if not (
                    0
                    <= selection_int
                    <= len(instance_dict[instance_id]["BlockDevs"]) - 1
                ):
                    format_output(
                        f"Selection must be a number from 0 to {len(instance_dict[instance_id]['BlockDevs']) - 1} or A for all block devices",
                        "warn",
                    )
                    continue
                else:
                    for index, device in enumerate(
                        instance_dict[instance_id]["BlockDevs"]
                    ):
                        if index != selection_int:
                            del instance_dict[instance_id]["BlockDevs"][index]

                    return instance_dict


def get_volume_data(ec2_client, instance_dict):
    """
    Returns additional data about each chosen volume, such as encryption status
    availability zone and capacity
    """
    format_output("Updating volume data...")

    for instance_id in instance_dict:
        for block_index, block_device in enumerate(
            instance_dict[instance_id]["BlockDevs"]
        ):
            device_name = block_device["DeviceName"]
            volume_id = block_device["VolumeId"]
            format_output(f"Querying Volume: {volume_id} ({device_name})")
            volume_data = ec2_client.describe_volumes(VolumeIds=[volume_id])

            for volume in volume_data["Volumes"]:
                instance_dict[instance_id]["BlockDevs"][block_index].update(
                    {
                        "AvailabilityZone": volume["AvailabilityZone"],
                        "Encrypted": volume["Encrypted"],
                        "Size": volume["Size"],
                        "VolumeType": volume["VolumeType"],
                    }
                )

                if volume["Encrypted"]:
                    instance_dict[instance_id]["BlockDevs"][block_index].update(
                        {"KmsKeyId": volume["KmsKeyId"]}
                    )
                else:
                    instance_dict[instance_id]["BlockDevs"][block_index].update(
                        {"KmsKeyId": ""}
                    )

    return instance_dict


def query_ebs_snapshots(ec2_client, instance_dict, max_results=5):
    """
    Queries for any EBS snapshots based on a provided EBS volume ID. If any are
    found, the `max_results` most recent snapshots are returned.
    """
    format_output("Querying EBS snapshots...")

    omit_indexes = []
    for instance_id in instance_dict:
        for block_index, block_device in enumerate(
            instance_dict[instance_id]["BlockDevs"]
        ):
            device_name = block_device["DeviceName"]
            volume_id = block_device["VolumeId"]
            format_output(f"Source Volume: {volume_id} ({device_name})")
            snapshot_data = ec2_client.describe_snapshots(
                Filters=[{"Name": "volume-id", "Values": [volume_id]}],
                OwnerIds=["self"],
                MaxResults=max_results,
            )

            if len(snapshot_data["Snapshots"]) == 0:
                format_output(
                    f"Snapshots Found: {len(snapshot_data['Snapshots'])} - Omitting Volume"
                )
                omit_indexes.append(block_index)

            if len(snapshot_data["Snapshots"]) > 0:
                format_output(f"Snapshots Found: {len(snapshot_data['Snapshots'])}")
                instance_dict[instance_id]["BlockDevs"][block_index].update(
                    {"Snapshots": len(snapshot_data["Snapshots"])}
                )

                snapshot_list = []
                for snapshot in snapshot_data["Snapshots"]:
                    if snapshot["VolumeId"] == volume_id:
                        snapshot_id = snapshot["SnapshotId"]
                        snapshot_starttime = f"{snapshot['StartTime']}"
                        snapshot_list.append(
                            {"SnapshotId": snapshot_id, "StartTime": snapshot_starttime}
                        )

                instance_dict[instance_id]["BlockDevs"][block_index].update(
                    {"SnapshotData": snapshot_list}
                )

    omit_indexes.reverse()
    for instance_id in instance_dict:
        for index in omit_indexes:
            del instance_dict[instance_id]["BlockDevs"][index]

        if len(instance_dict[instance_id]["BlockDevs"]) == 0:
            separator()
            ec2_client.close()
            format_output("No valid snapshots found", "error")
            sys.exit(1)

    return instance_dict


def get_snapshot_choice(instance_dict):
    """
    Present the volume and available snapshots to the user so a single
    snapshot per volume can be selected for restore.
    """
    for instance_id in instance_dict:
        for block_index, block_device in enumerate(
            instance_dict[instance_id]["BlockDevs"]
        ):
            device_name = block_device["DeviceName"]
            volume_id = block_device["VolumeId"]
            format_output(f"Source Volume: {volume_id} ({device_name})")
            format_output("Select a snapshot to continue:", "choice")

            for snapshot_index, snapshot_data in enumerate(
                block_device["SnapshotData"]
            ):
                snapshot_id = snapshot_data["SnapshotId"]
                snapshot_starttime = snapshot_data["StartTime"]
                format_output(
                    f"[{snapshot_index}] {snapshot_id} ({snapshot_starttime})", "item"
                )

            omit_indexes = []
            print()
            while True:
                selection_raw = input("Snapshot Selection: ")

                try:
                    selection_int = int(selection_raw)
                except ValueError:
                    format_output(
                        f"Selection must be a number from 0 to {len(block_device['SnapshotData']) - 1}",
                        "warn",
                    )
                    continue

                if not (0 <= selection_int <= len(block_device["SnapshotData"]) - 1):
                    format_output(
                        f"Selection must be a number from 0 to {len(block_device['SnapshotData']) - 1}",
                        "warn",
                    )
                    continue
                else:
                    for snapshot_index, snapshot_data in enumerate(
                        block_device["SnapshotData"]
                    ):
                        if snapshot_index != selection_int:
                            omit_indexes.append(snapshot_index)

                    omit_indexes.reverse()
                    for snapshot_index, snapshot_data in enumerate(
                        block_device["SnapshotData"]
                    ):
                        for omit_index in omit_indexes:
                            del block_device["SnapshotData"][omit_index]

                    break

    return instance_dict


def get_reattach_choice(instance_dict):
    """
    Would the user like the volumes restored from snapshot to be automatically
    attached? This will control whether the target instance is stopped and the
    volumes swapped with the restored volumes. Otherwise the script will exit
    after restoring the volumes from the selected snapshots.
    """

    for instance_id in instance_dict:
        format_output(
            """Would you like the restored volumes to be automatically switched with the existing
volumes on the target instance?

If answering "yes", the target instance will be shut-down and the existing volumes
detached. The volumes restored from snapshot will then be attached in their place.

If answering "no", new volumes will be created from the selected snapshots only.

NOTE: The original volumes will continue to exist. No resources will be removed.""",
            "choice",
        )

        print()
        while True:
            answer_raw = input("Switch Volumes: ")

            if answer_raw.lower() == "yes":
                instance_dict[instance_id].update({"SwitchVols": True})
                break
            elif answer_raw.lower() == "no":
                instance_dict[instance_id].update({"SwitchVols": False})
                break
            else:
                format_output('Please answer with "yes" or "no"', "warn")
                continue

    return instance_dict


def get_user_confirmation(instance_dict):
    """
    Confirm all the data we now have for the user to make a final confirmation
    before commiting any EBS and EC2 operations.
    """

    for instance_id in instance_dict:
        format_output(f"Instance ID:   {instance_id}")
        format_output(f"Instance Name: {instance_dict[instance_id]['Name']}")
        format_output(f"IP Address:    {instance_dict[instance_id]['IPAddress']}")
        print()
        format_output(
            "Volume ID".ljust(25)
            + "Device Node".ljust(15)
            + "Snapshot ID".ljust(25)
            + "Snapshot Date",
            "header",
        )
        for block_device in instance_dict[instance_id]["BlockDevs"]:
            print(
                "{}".format(block_device["VolumeId"]).ljust(25)
                + "{}".format(block_device["DeviceName"]).ljust(15)
                + "{}".format(block_device["SnapshotData"][0]["SnapshotId"]).ljust(25)
                + "{}".format(block_device["SnapshotData"][0]["StartTime"])
            )

        print()
        format_output(f"Switch Volumes: {instance_dict[instance_id]['SwitchVols']}")
        print()
        format_output("Proceeed with the chosen options?", "choice")
        print()
        while True:
            answer_raw = input("Proceed: ")
            if answer_raw.lower() == "yes":
                return True
            elif answer_raw.lower() == "no":
                return False
            else:
                format_output('Please answer with "yes" or "no"', "warn")
                continue


def restore_ebs_volume(
    ec2_client, block_device, searchtags_dict, wait_delay=15, wait_attempts=40
):
    """
    Creates a new EBS volume based on a provided snapshot ID.
    The new volume ID is returned once creation has been completed.
    """
    print()
    device_name = block_device["DeviceName"]
    snapshot_id = block_device["SnapshotData"][0]["SnapshotId"]
    tags_list = [
        {"Key": "DeviceName", "Value": device_name},
        {"Key": "Restored", "Value": "true"},
        {"Key": "SourceSnapshot", "Value": snapshot_id},
    ]

    for tagname, tagvalue in searchtags_dict.items():
        tags_list.append({"Key": tagname, "Value": tagvalue})

    format_output(f"Initiating restore from {snapshot_id} for {device_name}...")
    if block_device["Encrypted"]:
        response = ec2_client.create_volume(
            AvailabilityZone=block_device["AvailabilityZone"],
            Encrypted=block_device["Encrypted"],
            KmsKeyId=block_device["KmsKeyId"],
            Size=block_device["Size"],
            SnapshotId=snapshot_id,
            VolumeType=block_device["VolumeType"],
            TagSpecifications=[{"ResourceType": "volume", "Tags": tags_list}],
        )
    else:
        response = ec2_client.create_volume(
            AvailabilityZone=block_device["AvailabilityZone"],
            Encrypted=block_device["Encrypted"],
            Size=block_device["Size"],
            SnapshotId=snapshot_id,
            VolumeType=block_device["VolumeType"],
            TagSpecifications=[{"ResourceType": "volume", "Tags": tags_list}],
        )

    validate_response(response)
    new_volume_id = response["VolumeId"]
    format_output(f"Waiting for {new_volume_id} to become ready...")
    new_volume_waiter = ec2_client.get_waiter("volume_available")

    try:
        new_volume_waiter.wait(
            Filters=[
                {"Name": "status", "Values": ["available"]},
            ],
            VolumeIds=[new_volume_id],
            WaiterConfig={"Delay": wait_delay, "MaxAttempts": wait_attempts},
        )
        return new_volume_id

    except botocore.exceptions.WaiterError as waiterr:
        if "Max attempts exceeded" in waiterr.message:
            format_output(
                f"Volume {new_volume_id} failed to become ready in {wait_delay * wait_attempts} seconds",
                "error",
            )
        else:
            format_output(waiterr.message, "error")
        sys.exit(1)


def toggle_ec2_state(ec2_client, instance_id, state=1, wait_delay=15, wait_attempts=40):
    """
    Basic instance state toggle.  Requires an instance_id to operate against
    and a desired state. 0 = stop instance, 1 = start instance
    """
    print()
    if state == 1:
        format_output(f"Triggering start of instance {instance_id}...")
        response = ec2_client.start_instances(InstanceIds=[instance_id])

        validate_response(response)
        format_output(f"Waiting for instance {instance_id} to start... ")
        running_waiter = ec2_client.get_waiter("instance_running")

        try:
            running_waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={"Delay": wait_delay, "MaxAttempts": wait_attempts},
            )

        except botocore.exceptions.WaiterError as waiterr:
            print()
            if "Max attempts exceeded" in waiterr.message:
                format_output(
                    f"Instance {instance_id} failed to start in {wait_delay * wait_attempts} seconds",
                    "error",
                )
            else:
                format_output(waiterr.message, "error")
            sys.exit(1)

    else:
        format_output(f"Triggering stop of instance {instance_id}...")
        response = ec2_client.stop_instances(InstanceIds=[instance_id])

        validate_response(response)
        format_output(f"Waiting for instance {instance_id} to stop...")
        stop_waiter = ec2_client.get_waiter("instance_stopped")

        try:
            stop_waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={"Delay": wait_delay, "MaxAttempts": wait_attempts},
            )

        except botocore.exceptions.WaiterError as waiterr:
            print()
            if "Max attempts exceeded" in waiterr.message:
                format_output(
                    f"Stopping instance {instance_id} failed to complete in {wait_delay * wait_attempts} seconds",
                    "error",
                )
            else:
                format_output(waiterr.message, "error")
            sys.exit(1)


def detach_ebs_volume(
    ec2_client, instance_id, volume_id, device_name, wait_delay=15, wait_attempts=40
):
    """
    Detaches an EBS volume with the supplied ID and device_name from the provided
    instance ID.
    """
    print()
    format_output(f"Detaching volume: {volume_id} ({device_name})...")
    response = ec2_client.detach_volume(
        Device=device_name, InstanceId=instance_id, VolumeId=volume_id
    )

    validate_response(response)
    format_output(f"Waiting for volume {volume_id} to detach... ")
    available_waiter = ec2_client.get_waiter("volume_available")

    try:
        available_waiter.wait(
            Filters=[{"Name": "status", "Values": ["available"]}],
            VolumeIds=[volume_id],
            WaiterConfig={"Delay": wait_delay, "MaxAttempts": wait_attempts},
        )

    except botocore.exceptions.WaiterError as waiterr:
        print()
        if "Max attempts exceeded" in waiterr.message:
            format_output(
                f"Volume {volume_id} failed to detach in {wait_delay * wait_attempts} seconds",
                "error",
            )
        else:
            format_output(waiterr.message, "error")
        sys.exit(1)


def attach_ebs_volume(
    ec2_client, instance_id, new_volume_id, device_name, wait_delay=15, wait_attempts=40
):
    """
    Attaches an EBS volume with the supplied ID and device_name to the provided
    instance ID.
    """
    print()
    format_output(f"Attaching volume: {new_volume_id} ({device_name})...")
    response = ec2_client.attach_volume(
        Device=device_name, InstanceId=instance_id, VolumeId=new_volume_id
    )

    validate_response(response)
    format_output(f"Waiting for volume {new_volume_id} to detach...")
    in_use_waiter = ec2_client.get_waiter("volume_in_use")

    try:
        in_use_waiter.wait(
            Filters=[{"Name": "status", "Values": ["in-use"]}],
            VolumeIds=[new_volume_id],
            WaiterConfig={"Delay": wait_delay, "MaxAttempts": wait_attempts},
        )

    except botocore.exceptions.WaiterError as waiterr:
        print()
        if "Max attempts exceeded" in waiterr.message:
            format_output(
                f"Volume {new_volume_id} failed to attach in {wait_delay * wait_attempts} seconds",
                "error",
            )
        else:
            format_output(waiterr.message, "error")
        sys.exit(1)

    return True


def manage_restore_process(ec2_client, instance_dict, searchtags_dict):
    """
    Primary restore function used to manage the restore process and call
    out to further functions as required.
    """
    print()
    for instance_id in instance_dict:
        format_output(f"Starting volume restore process for {instance_id}")
        separator()
        for block_device in instance_dict[instance_id]["BlockDevs"]:
            new_volume_id = restore_ebs_volume(
                ec2_client, block_device, searchtags_dict
            )
            block_device.update({"NewVolumeId": new_volume_id})

        if instance_dict[instance_id]["SwitchVols"]:
            toggle_ec2_state(ec2_client, instance_id, 0)
            for block_device in instance_dict[instance_id]["BlockDevs"]:
                volume_id = block_device["VolumeId"]
                new_volume_id = block_device["NewVolumeId"]
                device_name = block_device["DeviceName"]
                detach_ebs_volume(ec2_client, instance_id, volume_id, device_name)
                attach_ebs_volume(ec2_client, instance_id, new_volume_id, device_name)
            toggle_ec2_state(ec2_client, instance_id, 1)

    separator()
    format_output("Restore process completed")


def seconds_to_dhms(total_seconds):
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    total_hours = total_minutes // 60
    minutes = total_minutes % 60
    days = total_hours // 24
    hours = total_hours % 24

    output_string = ""
    if days > 0:
        if days == 1:
            label = "day"
        else:
            label = "days"

        output_string += f"{days} {label}, "

    if hours > 0:
        if hours == 1:
            label = "hour"
        else:
            label = "hours"
        output_string += f"{hours} {label}, "

    if minutes > 0:
        if minutes == 1:
            label = "minute"
        else:
            label = "minutes"
        output_string += f"{minutes} {label}, "

    output_string += f"{seconds} seconds ago"
    return output_string


def save_plan(searchtags_dict, instance_dict, save_file):
    """
    Format and output a JSON-formatted file that can be used
    as a plan to be loaded and executed at a later date
    """
    print()
    format_output("Preparing recovery plan...")

    output_dict = {}
    output_dict.update(
        {"plan": {"instance_dict": instance_dict, "searchtags_dict": searchtags_dict}}
    )
    plan_checksum = hashlib.md5(
        json.dumps(output_dict["plan"], sort_keys=True, ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()
    output_dict.update(
        {"metadata": {"timestamp": int(time.time()), "checksum": plan_checksum}}
    )

    try:
        format_output(f"Saving plan to file: {save_file}")
        with open(save_file, "w") as f:
            f.write(json.dumps(output_dict))

        f.close()
        format_output("Plan saved successfully")

    except OSError as err:
        format_output(err, "error")
        sys.exit(1)


def load_plan(load_file):
    """
    Load a previously-saved JSON-formatted plan file and validate
    the data within is consistent
    """
    format_output("Loading recovery plan...")

    input_dict = {}

    try:
        format_output(f"Reading plan from file: {load_file}")
        with open(load_file, "r") as f:
            input_dict = json.load(f)

        f.close()
        format_output("Plan loaded successfully")

    except OSError as err:
        format_output(err, "error")
        sys.exit(1)

    format_output("Validating plan...")
    if type(input_dict) is not dict:
        format_output("Loaded plan is not a valid data structure", "error")
        sys.exit(1)

    if "metadata" not in input_dict or "plan" not in input_dict:
        format_output("Invalid plan. Expected structure elements are missing", "error")
        sys.exit(1)

    if (
        "searchtags_dict" not in input_dict["plan"]
        or "instance_dict" not in input_dict["plan"]
    ):
        format_output("Invalid plan. Expected plan elements are missing", "error")
        sys.exit(1)

    metadata_checksum = input_dict["metadata"]["checksum"]
    plan_checksum = hashlib.md5(
        json.dumps(input_dict["plan"], sort_keys=True, ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()
    if metadata_checksum != plan_checksum:
        format_output("Plan checksum mismatch. Has the plan been modified?", "error")
        sys.exit(1)

    format_output("Plan validated successfully")
    plan_age_seconds = int(time.time()) - input_dict["metadata"]["timestamp"]
    format_output(f"Plan created: {seconds_to_dhms(plan_age_seconds)}")
    return input_dict["plan"]["searchtags_dict"], input_dict["plan"]["instance_dict"]


def verify_instance(ec2_client, plan_instance_id, plan_instance_metadata):
    """
    Verifies that the provided Instance exists in AWS
    and that the provided instance data matches
    """
    format_output(f"Checking Instance ID: {plan_instance_id}...")

    try:
        response = ec2_client.describe_instances(InstanceIds=[plan_instance_id])

    except botocore.exceptions.UnauthorizedSSOTokenError as ssotokenerr:
        format_output(ssotokenerr, "error")
        sys.exit(1)

    except botocore.exceptions.ProfileNotFound as profileerr:
        format_output(profileerr, "error")
        sys.exit(1)

    validate_response(response)
    for reservation in response["Reservations"]:
        if len(reservation["Instances"]) == 1:
            for instance in reservation["Instances"]:
                format_output("Verifying Instance Name... ", "item")
                instance_name = ""
                for tags in instance["Tags"]:
                    if tags["Key"] == "Name":
                        instance_name = tags["Value"]

                if plan_instance_metadata["Name"] != instance_name:
                    format_output(
                        f"Instance name does not match. Plan: {plan_instance_metadata['Name']}, Actual: {instance_name}",
                        "error",
                    )
                    sys.exit(1)

                format_output("Verifying Instance IP Address...", "item")
                if plan_instance_metadata["IPAddress"] != instance["PrivateIpAddress"]:
                    format_output(
                        f"Instance IP Address does not match. Plan: {plan_instance_metadata['IPAddress']}, Actual: {instance['PrivateIpAddress']}",
                        "error",
                    )
                    sys.exit(1)

        else:
            format_output(
                f"The instance with Instance ID {plan_instance_id} could not be found",
                "error",
            )
            sys.exit(1)


def verify_volume(ec2_client, plan_volume_id, plan_volume_metadata):
    """
    Verifies that the provided Volume exists in AWS
    and that the provided volume data matches
    """
    format_output(f"Checking Volume ID: {plan_volume_id}...")

    try:
        response = ec2_client.describe_volumes(VolumeIds=[plan_volume_id])

    except botocore.exceptions.UnauthorizedSSOTokenError as ssotokenerr:
        format_output(ssotokenerr, "error")
        sys.exit(1)

    except botocore.exceptions.ProfileNotFound as profileerr:
        format_output(profileerr, "error")
        sys.exit(1)

    validate_response(response)
    if len(response["Volumes"]) == 1:
        for volume in response["Volumes"]:
            for key in plan_volume_metadata.keys():
                format_output(f"Verifying {key}...", "item")
                if key == "DeviceName":
                    if plan_volume_metadata[key] != volume["Attachments"][0]["Device"]:
                        format_output(
                            f"{key} does not match. Plan: {plan_volume_metadata[key]}, Actual: {volume['Attachments'][0]['Device']}",
                            "error",
                        )
                        sys.exit(1)
                elif plan_volume_metadata[key] != volume[key]:
                    format_output(
                        f"{key} does not match. Plan: {plan_volume_metadata[key]}, Actual: {volume[key]}",
                        "error",
                    )
                    sys.exit(1)

    else:
        format_output(
            f"The volume with Volume ID {plan_volume_id} could not be found", "error"
        )
        sys.exit(1)


def verify_snapshot(ec2_client, plan_snapshot_id, plan_snapshot_metadata):
    """
    Verifies that the provided Snapshot exists in AWS
    and that the provided snapshot data matches
    """
    format_output(f"Checking Snapshot ID: {plan_snapshot_id}...")

    try:
        response = ec2_client.describe_snapshots(SnapshotIds=[plan_snapshot_id])

    except botocore.exceptions.UnauthorizedSSOTokenError as ssotokenerr:
        format_output(ssotokenerr, "error")
        sys.exit(1)

    except botocore.exceptions.ProfileNotFound as profileerr:
        format_output(profileerr, "error")
        sys.exit(1)

    validate_response(response)
    if len(response["Snapshots"]) == 1:
        for snapshot in response["Snapshots"]:
            for key in plan_snapshot_metadata.keys():
                format_output(f"Verifying {key}...", "item")
                if key == "StartTime":
                    snapshot_starttime = f"{snapshot['StartTime']}"
                    if plan_snapshot_metadata[key] != snapshot_starttime:
                        format_output(
                            f"{key} does not match. Plan: {plan_snapshot_metadata[key]}, Actual: {snapshot_starttime}",
                            "error",
                        )
                        sys.exit(1)

                elif plan_snapshot_metadata[key] != snapshot[key]:
                    format_output(
                        f"{key} does not match. Plan: {plan_snapshot_metadata[key]}, Actual: {snapshot[key]}",
                        "error",
                    )
                    sys.exit(1)

    else:
        format_output(
            f"The snapshot with Snapshot ID {plan_snapshot_id} could not be found",
            "error",
        )
        sys.exit(1)


def revalidate_loaded_plan(ec2_client, instance_dict):
    """
    Re-validates the provided instance_dict to ensure the supplied
    AWS resource IDs are valid and still exist
    """
    format_output("Re-validating resource IDs...")

    for instance_id in instance_dict:
        instance_metadata = {
            "Name": instance_dict[instance_id]["Name"],
            "IPAddress": instance_dict[instance_id]["IPAddress"],
        }
        verify_instance(ec2_client, instance_id, instance_metadata)
        print()

        for block_dev in instance_dict[instance_id]["BlockDevs"]:
            volume_id = block_dev["VolumeId"]
            volume_metadata = {
                "DeviceName": block_dev["DeviceName"],
                "AvailabilityZone": block_dev["AvailabilityZone"],
                "Encrypted": block_dev["Encrypted"],
                "Size": block_dev["Size"],
                "VolumeType": block_dev["VolumeType"],
            }

            if block_dev["Encrypted"]:
                volume_metadata.update({"KmsKeyId": block_dev["KmsKeyId"]})
            verify_volume(ec2_client, volume_id, volume_metadata)
            print()

            snapshot_id = block_dev["SnapshotData"][0]["SnapshotId"]
            snapshot_metadata = {"StartTime": block_dev["SnapshotData"][0]["StartTime"]}
            verify_snapshot(ec2_client, snapshot_id, snapshot_metadata)


def main():
    """
    Setup ArgumentParser
    """
    parser = argparse.ArgumentParser(description="Program arguments and options")
    parser.add_argument(
        "--searchtags",
        metavar="searchtags",
        nargs="?",
        help="A CSV list of Key=Value pairs used for search filtering on instance tags. Example: TagName=TagValue,Foo=Bar",
        default=None,
    )
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
        "--switchvols",
        metavar="switchvols",
        help="Automatically switch volumes with those restored from snapshot",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--saveplan",
        metavar="saveplan",
        nargs="?",
        help="Take no actions but output a plan to the file specified",
        default=None,
    )
    parser.add_argument(
        "--loadplan",
        metavar="loadplan",
        nargs="?",
        help="Load a saved plan from the file specified",
        default=None,
    )
    args = parser.parse_args()

    if args.saveplan is not None and args.loadplan is not None:
        format_output("saveplan and loadplan options are mutually exclusive", "error")
        sys.exit(1)

    if args.searchtags is None and args.loadplan is None:
        format_output("--searchtags not provided", "error")
        sys.exit(1)
    elif args.searchtags is not None and args.loadplan is None:
        searchtags_dict = process_searchtags(args.searchtags)

    """
    Check to ensure user's AWS_PROFILE env var is set or we've been
    given a value via the --profile argument. Values provided via
    command line argument take precedence.
    """
    if not os.environ.get("AWS_PROFILE") and args.profile == "":
        format_output("AWS_PROFILE is not set and --profile not set.", "error")
        sys.exit(1)
    elif os.environ.get("AWS_PROFILE") and args.profile == "":
        awsprofile = os.environ.get("AWS_PROFILE")
    elif not os.environ.get("AWS_PROFILE") and args.profile != "":
        awsprofile = args.profile
    elif os.environ.get("AWS_PROFILE") and args.profile != "":
        awsprofile = args.profile
    else:
        format_output("Unexpected error determining AWS Profile.", "error")
        sys.exit(1)

    """
    Run the main script sequence encapsulated in a try/except so we
    can gracefully capture a CTRL+C if pressed
    """
    try:
        ec2_client = create_ec2_client(awsprofile, args.region)
        separator()

        if args.loadplan is not None:
            searchtags_dict, instance_dict = load_plan(args.loadplan)
            separator()
            revalidate_loaded_plan(ec2_client, instance_dict)
            separator()
        else:
            instance_dict = query_ec2_instances(ec2_client, searchtags_dict)
            separator()
            if len(Counter(instance_dict)) > 1:
                instance_dict = get_instance_choice(instance_dict)
                separator()
            instance_dict = get_volume_choice(instance_dict)
            separator()
            instance_dict = get_volume_data(ec2_client, instance_dict)
            separator()
            instance_dict = query_ebs_snapshots(ec2_client, instance_dict)
            separator()
            instance_dict = get_snapshot_choice(instance_dict)
            separator()
            if args.switchvols:
                for instance_id in instance_dict:
                    instance_dict[instance_id].update({"SwitchVols": True})
            else:
                instance_dict = get_reattach_choice(instance_dict)
            separator()

        if args.saveplan is not None:
            save_plan(searchtags_dict, instance_dict, args.saveplan)
        else:
            if get_user_confirmation(instance_dict):
                separator()
                manage_restore_process(ec2_client, instance_dict, searchtags_dict)
            else:
                ec2_client.close()
                format_output("Operation cancelled by user.", "warn")

            ec2_client.close()

    except KeyboardInterrupt:
        print()
        format_output("Operation cancelled by user.", "warn")


if __name__ == "__main__":
    main()
