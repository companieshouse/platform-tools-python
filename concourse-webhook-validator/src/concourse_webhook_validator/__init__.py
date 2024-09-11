import argparse
import os
import re
import sys
import yaml

"""
Defaults
"""
WEBHOOK_REGEX = '^[a-zA-Z0-9]*$'

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


def load_pipeline_config(pipeline_config_file_path:str) -> object:
    """
    The file must exist before we load it. Once loaded the
    entire python object is returned.
    """
    if os.path.isfile(pipeline_config_file_path):
        with open(pipeline_config_file_path, 'r') as file:
            pipeline_config = yaml.safe_load(file)

        return pipeline_config
    
    else:
        format_output(
            "The specified pipeline file could not be found",
            "error"
        )
        format_output(
            f"{pipeline_config_file_path}",
            "error"
        )
        sys.exit(1)


def validate_pipeline_config(pipeline_config:object) -> int:
    """
    For a pipeline to be considered 'valid' it must contain both
    'jobs' and resources' keys.
    0: Valid
    1: Invalid
    """
    validation_error = 0
    if 'jobs' not in pipeline_config:
        format_output(
            "No 'jobs' found in pipeline configuration",
            "warn"
        )
        validation_error = 1
    
    if 'resources' not in pipeline_config:
        format_output(
            "No 'resources' found in pipeline configuration",
            "warn"
        )
        validation_error = 1
    
    return validation_error


def parse_pipeline_resources(pipeline_config:object, webhook_dict:dict) -> dict:
    for resource in pipeline_config['resources']:
        resource_name = resource['name']
        if 'webhook_token' in resource:
            if resource['webhook_token'] is not None:
                resource_webhook_token = resource['webhook_token']
                webhook_dict[resource_name] = {'rwt': resource_webhook_token}
    
    return webhook_dict


def parse_pipeline_jobs(pipeline_config:object, webhook_dict:dict) -> dict:
    for job in pipeline_config['jobs']:
        if job['name'] == 'create-webhooks':
            for create_plan in job['plan']:
                if 'webhook_token' in create_plan['params']:
                    create_webhook_token = create_plan['params']['webhook_token']
                    webhook_dict[create_plan['params']['resource_name']].update(
                        {
                            'cwt': create_webhook_token
                        }
                    )
        if job['name'] == 'delete-webhooks':
            for delete_plan in job['plan']:
                if 'webhook_token' in delete_plan['params']:
                    delete_webhook_token = delete_plan['params']['webhook_token']
                    webhook_dict[delete_plan['params']['resource_name']].update(
                        {
                            'dwt': delete_webhook_token
                        }
                    )

    return webhook_dict


def validate_webhooks(resource_webhooks_dict:dict) -> dict:
    for resource in resource_webhooks_dict:
        resource_webhooks = resource_webhooks_dict[resource]
        """
        A valid webhook token must only contain alphanumeric characters
        0: Valid
        1: Invalid
        """
        valid_webhook = re.search(WEBHOOK_REGEX, resource_webhooks['rwt'])
        if valid_webhook:
            resource_webhooks_dict[resource].update(
                {
                    'rwv': 0
                }
            )
        else:
            resource_webhooks_dict[resource].update(
                {
                    'rwv': 1
                }
            )

        """
        The webhook tokens specified in 'create-webhooks' and 'delete-webhooks'
        must match the token specified on the resource
        0: Match
        1: No match
        2: No webhook job found
        """
        if 'cwt' in resource_webhooks:
            if resource_webhooks['cwt'] == resource_webhooks['rwt']:
                resource_webhooks_dict[resource].update(
                    {
                        'cwv': 0
                    }
                )
            else:
                resource_webhooks_dict[resource].update(
                    {
                        'cwv': 1
                    }
                )
        else:
            resource_webhooks_dict[resource].update(
                {
                    'cwv': 2
                }
            )

        if 'dwt' in resource_webhooks:
            if resource_webhooks['dwt'] == resource_webhooks['rwt']:
                resource_webhooks_dict[resource].update(
                    {
                        'dwv': 0
                    }
                )
            else:
                resource_webhooks_dict[resource].update(
                    {
                        'dwv': 1
                    }
                )
        else:
            resource_webhooks_dict[resource].update(
                {
                    'dwv': 2
                }
            )
        
    return resource_webhooks_dict


def display_results(webhooks_dict:dict) -> int:
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

    resource_name_text = "Resource name"
    resource_token_valid_text = "Token valid"
    create_token_matches_text = "Create matches"
    delete_token_matches_text = "Delete matches"

    """
    Table header includes some padding to allow the text to be properly centered
    without being cramped agaist the '|' separators.
    """
    print(f"{resource_name_text.ljust(int(resource_name_length + 1))}|" +
            f"{resource_token_valid_text.center(int(len(resource_token_valid_text) + 2))}|" +
            f"{create_token_matches_text.center(int(len(create_token_matches_text) + 2))}|" +
            f"{delete_token_matches_text.center(int(len(delete_token_matches_text) + 2))}\n" +
            f"{'-' * int(resource_name_length + 1)}|" +
            f"{'-' * int(len(resource_token_valid_text) + 2)}|" +
            f"{'-' * int(len(create_token_matches_text) + 2)}|" +
            f"{'-' * int(len(delete_token_matches_text) + 2)}")
    

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
        if webhooks_dict[resource]['rwv'] == 0:
            resource_webhook_valid = '✅'
        else:
            resource_webhook_valid = '❌'
            resource_validation_failed = 1
            resource_failed_reasons.append(f"'{resource}' webhook token contains non-alphanumeric characters")

        """
        0: Match
        1: No match
        2: No webhook job found
        """
        if webhooks_dict[resource]['cwv'] == 0:
            create_webhook_valid = '✅'
        elif webhooks_dict[resource]['cwv'] == 1:
            create_webhook_valid = '❌'
            resource_validation_failed = 1
            resource_failed_reasons.append(f"'create-webhooks' job '{resource}' has a different token to the resource")
        else:
            create_webhook_valid = '❓'
            resource_validation_failed = 1
            resource_failed_reasons.append(f"'{resource}' missing 'create-webhooks' job or webhook token parameter not set")

        if webhooks_dict[resource]['dwv'] == 0:
            delete_webhook_valid = '✅'
        elif webhooks_dict[resource]['dwv'] == 1:
            delete_webhook_valid = '❌'
            resource_validation_failed = 1
            resource_failed_reasons.append(f"'delete-webhooks' job '{resource}' has a different token to the resource")
        else:
            delete_webhook_valid = '❓'
            resource_validation_failed = 1
            resource_failed_reasons.append(f"'{resource}' missing 'delete-webhooks' job or webhook token parameter not set")
        
        print(f"{resource.ljust(int(resource_name_length) + 1)}|" +
                f" {resource_webhook_valid.center(int(len(resource_token_valid_text)))}|" +
                f" {create_webhook_valid.center(int(len(create_token_matches_text)))}|" +
                f"{delete_webhook_valid.center(int(len(delete_token_matches_text)))}")
    
    if resource_validation_failed == 1:
        print()
        for reason in resource_failed_reasons:
            format_output(
                reason,
                "warn"
            )
    
    return resource_validation_failed

def main() -> None:
    parser = argparse.ArgumentParser(description="Program arguments and options")
    parser.add_argument('pipeline',
                        default=None,
                        help="The name of the pipeline to load",
                        nargs=1
                        )
    parser.add_argument('--base-dir',
                        default='',
                        help="The base directory in which the pipeline configurations are stored",
                        nargs=1)
    parser.add_argument('--deployment',
                        default='',
                        help="The name of the Concourse deployment",
                        nargs=1)
    parser.add_argument('--team',
                        default='',
                        help="The team name that the pipeline is configured for",
                        nargs=1)
    args = parser.parse_args()
    
    if len(args.base_dir) == 0:
        pipeline_base_dir = ''
    else:
        pipeline_base_dir = args.base_dir[0]
    
    if len(args.deployment) == 0:
        pipeline_deployment = ''
    else:
        pipeline_deployment = args.deployment[0]
    
    if len(args.team) == 0:
        pipeline_team = ''
    else:
        pipeline_team = args.team[0]
    
    pipeline_file = args.pipeline[0]
    pipeline_file_path = os.path.join(pipeline_base_dir, pipeline_deployment, pipeline_team, pipeline_file)

    webhooks_dict = {}
    format_output(
        f"Checking webhooks configuration: {colours.bold}{pipeline_file}{colours.end}"
    )
    pipeline_config = load_pipeline_config(pipeline_file_path)
    if validate_pipeline_config(pipeline_config) == 0:
        webhooks_dict = parse_pipeline_resources(pipeline_config, webhooks_dict)
        if len(webhooks_dict) > 0:
            webhooks_dict = parse_pipeline_jobs(pipeline_config, webhooks_dict)
            webhooks_dict = validate_webhooks(webhooks_dict)
            if display_results(webhooks_dict) == 0:
                print()
                format_output(
                    "Webhooks configuration check completed successfully"
                )
            else:
                format_output(
                    "Validation failures were encountered",
                    "error"
                )
                sys.exit(1)

        else:
            format_output(
                "No webhooked resources found"
            )

    else:
        format_output(
            f"Pipeline does not appear to be a valid configuration: {colours.bold}{pipeline_file}{colours.end}",
            "error"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
    sys.exit(0)
