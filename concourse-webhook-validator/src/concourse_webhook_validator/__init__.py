import argparse
import os
import re
import sys
import yaml

from prettytable import PrettyTable

"""
Defaults
"""
WEBHOOK_REGEX = "^[a-zA-Z0-9]*$"

"""
Classes & Functions
"""


class colours:
    blue = "\033[1;34m"
    red = "\033[1;31m"
    yellow = "\033[1;33m"
    bold = "\033[1m"
    end = "\033[0m"


def format_output(message="", style="info") -> None:
    prefix = ""

    if style == "error":
        prefix = f"{colours.red}{style.capitalize()}:{colours.end} "

    if style == "info":
        prefix = f"{colours.blue}{style.capitalize()}:{colours.end} "

    if style == "warn":
        prefix = f"{colours.yellow}{style.capitalize()}:{colours.end} "

    print(prefix + message)


def read_pipelines_list_from_file(pipeline_file) -> list:
    try:
        with open(pipeline_file, "r") as file:
            pipelines_list = [line.rstrip() for line in file]
    except OSError as err:
        format_output(
            f"Unable to open/read the provided file: {colours.bold}{pipeline_file}{colours.end}",
            "error",
        )
        sys.exit(1)
    except:
        format_output(
            f"Unexpected error opening file: {colours.bold}{pipeline_file}{colours.end}",
            "error",
        )
        sys.exit(1)

    return pipelines_list


def load_pipeline_config(pipeline_config_file_path: str) -> object:
    """
    The file must exist before we load it. Once loaded the
    entire python object is returned.
    """
    if os.path.isfile(pipeline_config_file_path):
        with open(pipeline_config_file_path, "r") as file:
            pipeline_config = yaml.safe_load(file)

        return pipeline_config

    else:
        format_output("The specified pipeline file could not be found", "error")
        format_output(f"{pipeline_config_file_path}", "error")
        sys.exit(1)


def validate_pipeline_config(pipeline_config: object) -> int:
    """
    For a pipeline to be considered 'valid' it must contain both
    'jobs' and resources' keys.
    0: Valid
    1: Invalid
    """
    validation_error = 0
    if "jobs" not in pipeline_config:
        format_output("No 'jobs' found in pipeline configuration", "warn")
        validation_error = 1

    if "resources" not in pipeline_config:
        format_output("No 'resources' found in pipeline configuration", "warn")
        validation_error = 1

    return validation_error


def parse_pipeline_resources(pipeline_config: object, webhook_dict: dict) -> None:
    for resource in pipeline_config["resources"]:
        resource_name = resource["name"]
        if "webhook_token" in resource:
            if resource["webhook_token"] is not None:
                resource_webhook_token = resource["webhook_token"]
                webhook_dict[resource_name] = {"rwt": resource_webhook_token}


def parse_pipeline_jobs(pipeline_config: object, webhook_dict: dict) -> None:
    for job in pipeline_config["jobs"]:
        if job["name"] == "create-webhooks":
            for create_plan in job["plan"]:
                if "webhook_token" in create_plan["params"]:
                    create_webhook_token = create_plan["params"]["webhook_token"]
                    webhook_dict[create_plan["params"]["resource_name"]].update(
                        {"cwt": create_webhook_token}
                    )
        if job["name"] == "delete-webhooks":
            for delete_plan in job["plan"]:
                if "webhook_token" in delete_plan["params"]:
                    delete_webhook_token = delete_plan["params"]["webhook_token"]
                    webhook_dict[delete_plan["params"]["resource_name"]].update(
                        {"dwt": delete_webhook_token}
                    )


def validate_webhooks(webhooks_dict: dict) -> None:
    for resource in webhooks_dict:
        resource_webhooks = webhooks_dict[resource]
        """
        A valid webhook token must only contain alphanumeric characters
        0: Valid
        1: Invalid
        """
        valid_webhook = re.search(WEBHOOK_REGEX, resource_webhooks["rwt"])
        if valid_webhook:
            webhooks_dict[resource].update({"rwv": 0})
        else:
            webhooks_dict[resource].update({"rwv": 1})

        """
        The webhook tokens specified in 'create-webhooks' and 'delete-webhooks'
        must match the token specified on the resource
        0: Match
        1: No match
        2: No webhook job found
        """
        if "cwt" in resource_webhooks:
            if resource_webhooks["cwt"] == resource_webhooks["rwt"]:
                webhooks_dict[resource].update({"cwv": 0})
            else:
                webhooks_dict[resource].update({"cwv": 1})
        else:
            webhooks_dict[resource].update({"cwv": 2})

        if "dwt" in resource_webhooks:
            if resource_webhooks["dwt"] == resource_webhooks["rwt"]:
                webhooks_dict[resource].update({"dwv": 0})
            else:
                webhooks_dict[resource].update({"dwv": 1})
        else:
            webhooks_dict[resource].update({"dwv": 2})


def display_results(webhooks_dict: dict) -> int:
    format_output(
        f"Webhooked resources discovered: {colours.bold}{len(webhooks_dict)}{colours.end}\n"
    )

    """
    Find the length of the longest resource name so we can scale the results table
    """
    resource_name_length = 0
    for resource in webhooks_dict:
        if len(resource) > resource_name_length:
            resource_name_length = len(resource)

    webhooks_table = PrettyTable()
    webhooks_table.field_names = ["Resource name", "Token valid", "Create matches", "Delete matches"]

    """
    Loop through and build the tabular output and track whether any
    resources failed their validation
    """
    resource_validation_failed = 0
    resource_failed_reasons = []
    for resource in webhooks_dict:
        """
        0: Valid token
        1: Invalid token
        """
        if webhooks_dict[resource]["rwv"] == 0:
            resource_webhook_valid = "✅"
        else:
            resource_webhook_valid = "❌"
            resource_validation_failed = 1
            resource_failed_reasons.append(
                f"'{resource}' webhook token contains non-alphanumeric characters"
            )

        """
        0: Match
        1: No match
        2: No webhook job found
        """
        if webhooks_dict[resource]["cwv"] == 0:
            create_webhook_valid = "✅"
        elif webhooks_dict[resource]["cwv"] == 1:
            create_webhook_valid = "❌"
            resource_validation_failed = 1
            resource_failed_reasons.append(
                f"'create-webhooks' job '{resource}' has a different token to the resource"
            )
        else:
            create_webhook_valid = "❓"
            resource_validation_failed = 1
            resource_failed_reasons.append(
                f"'{resource}' missing 'create-webhooks' job or webhook token parameter not set"
            )

        if webhooks_dict[resource]["dwv"] == 0:
            delete_webhook_valid = "✅"
        elif webhooks_dict[resource]["dwv"] == 1:
            delete_webhook_valid = "❌"
            resource_validation_failed = 1
            resource_failed_reasons.append(
                f"'delete-webhooks' job '{resource}' has a different token to the resource"
            )
        else:
            delete_webhook_valid = "❓"
            resource_validation_failed = 1
            resource_failed_reasons.append(
                f"'{resource}' missing 'delete-webhooks' job or webhook token parameter not set"
            )

        webhooks_table.add_row([resource, resource_webhook_valid, create_webhook_valid, delete_webhook_valid])

    print(webhooks_table)

    if resource_validation_failed == 1:
        print()
        for reason in resource_failed_reasons:
            format_output(reason, "warn")

    return resource_validation_failed


def print_validation_summary(validation_failure_list) -> None:
    print()
    print("-" * 80 + "\nValidation results summary\n" + "-" * 80)
    if len(validation_failure_list) > 0:
        format_output("The following pipelines had validation failures", "error")
        for failed_pipeline in validation_failure_list:
            format_output(f"{colours.bold}{failed_pipeline}{colours.end}", "error")
        sys.exit(1)
    else:
        format_output(
            "All pipelines have been successfully validated",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Program arguments and options")
    parser.add_argument(
        "pipeline",
        default=None,
        help="The name of the pipeline configuration to load",
        nargs=1,
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Specifies that the provided input is a file containing a list of pipeline configurations, one per line",
    )
    parser.add_argument(
        "--base-dir",
        default="",
        help="The base directory in which the pipeline configurations are stored",
        nargs=1,
    )
    parser.add_argument(
        "--deployment", default="", help="The name of the Concourse deployment", nargs=1
    )
    parser.add_argument(
        "--team",
        default="",
        help="The team name that the pipeline is configured for",
        nargs=1,
    )
    args = parser.parse_args()

    if len(args.base_dir) == 0:
        pipeline_base_dir = ""
    else:
        pipeline_base_dir = args.base_dir[0]

    if len(args.deployment) == 0:
        pipeline_deployment = ""
    else:
        pipeline_deployment = args.deployment[0]

    if len(args.team) == 0:
        pipeline_team = ""
    else:
        pipeline_team = args.team[0]

    if args.list:
        pipelines_list = read_pipelines_list_from_file(args.pipeline[0])
    else:
        pipelines_list = [args.pipeline[0]]

    validation_failure_list = []
    for pipeline in pipelines_list:
        pipeline_file_path = os.path.join(
            pipeline_base_dir, pipeline_deployment, pipeline_team, pipeline
        )
        pipeline_name_element_list = pipeline_file_path.rsplit("/", 1)
        pipeline_name = pipeline_name_element_list[len(pipeline_name_element_list) - 1]

        webhooks_dict = {}
        print()
        format_output(
            f"Checking webhooks configuration: {colours.bold}{pipeline_name}{colours.end}"
        )
        pipeline_config = load_pipeline_config(pipeline_file_path)
        if validate_pipeline_config(pipeline_config) == 0:
            parse_pipeline_resources(pipeline_config, webhooks_dict)
            if len(webhooks_dict) > 0:
                parse_pipeline_jobs(pipeline_config, webhooks_dict)
                validate_webhooks(webhooks_dict)
                if display_results(webhooks_dict) == 0:
                    print()
                    format_output("Webhooks configuration check completed successfully")
                else:
                    validation_failure_list.append(pipeline_name)
                    format_output(
                        "Webhooks validation failures were encountered", "warn"
                    )
            else:
                format_output("No webhooked resources found")
        else:
            validation_failure_list.append(pipeline_name)
            format_output(
                "Pipeline does not appear to be a valid configuration", "warn"
            )

    print_validation_summary(validation_failure_list)


if __name__ == "__main__":
    main()
    sys.exit(0)
