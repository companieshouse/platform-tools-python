import argparse
import os
import sys
import yaml

from prettytable import PrettyTable


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


def load_pipeline_config(pipeline_config_path: str) -> dict:
    """
    The file must exist before we load it. Once loaded the
    entire python dict is returned.
    """
    if os.path.exists(pipeline_config_path):
        with open(pipeline_config_path, 'r') as file:
            pipeline_config = yaml.safe_load(file)
    else:
        pipeline_config = {}

    return pipeline_config


def output_settings(args_dict: dict) -> None:
    print()
    format_output(
        f"Repository URI:    [{args_dict['repo_uri']}]"
    )
    format_output(
        f"Repository branch: [{args_dict['repo_branch']}]"
    )
    format_output(
        f"Task file path:    [{args_dict['task_path']}]"
    )
    print()


def validate_pipelines(args_dict: dict, pipelines_list: list) -> dict:
    """
    Validate the pipeline configuration
    """

    format_output(
        "Starting concourse-resources configuration validation",
        "info"
    )
    output_settings(args_dict)

    pipelines_base_dir = args_dict['pipelines_base_dir']
    pipeline_validity = {}
    for pipeline_file in pipelines_list:
        pipeline_name = str(os.path.basename(pipeline_file))
        pipeline_config_path = os.path.join(pipelines_base_dir, pipeline_file)
        pipeline_validity[pipeline_name] = {
            "config_status": "",
            "config_message": "",
            "resources_status": "skipped",
            "resources_message": "N/A",
            "tasks_status": "skipped",
            "tasks_message": "N/A"
        }
        format_output(
            f"Validating pipeline: [{pipeline_name}]",
            "info"
        )

        pipeline_config = load_pipeline_config(pipeline_config_path)
        if not pipeline_config:
            pipeline_validity[pipeline_name]['config_status'] = "failed"
            pipeline_validity[pipeline_name]['config_message'] = "Failed to load configuration or configuration invalid"
            continue

        if 'resources' not in pipeline_config and 'jobs' not in pipeline_config:
            pipeline_validity[pipeline_name]['config_status'] = "skipped"
            pipeline_validity[pipeline_name]['config_message'] = "No resources or jobs configured"
            continue

        pipeline_validity[pipeline_name]['config_status'] = "passed"
        
        if 'resources' in pipeline_config:
            resources_check_result = validate_concourse_resources_resource(pipeline_config, args_dict['repo_uri'], args_dict['repo_branch'])
            pipeline_validity[pipeline_name]['resources_status'] = resources_check_result['status']
            pipeline_validity[pipeline_name]['resources_message'] = resources_check_result['message']
        else:
            pipeline_validity[pipeline_name]['resources_status'] = "skipped"
            pipeline_validity[pipeline_name]['resources_message'] = "No resources configured"

        if 'jobs' in pipeline_config:
            tasks_check_result = validate_concourse_resources_tasks(pipeline_config, args_dict['task_path'])
            pipeline_validity[pipeline_name]['tasks_status'] = tasks_check_result['status']
            pipeline_validity[pipeline_name]['tasks_message'] = tasks_check_result['message']
        else:
            pipeline_validity[pipeline_name]['tasks_status'] = "skipped"
            pipeline_validity[pipeline_name]['tasks_message'] = "No jobs and tasks configured"

    return pipeline_validity


def validate_concourse_resources_resource(pipeline_config: dict, repo_uri: str, repo_branch: str) -> dict[str, str]:
    resources_error = False
    concourse_resources_used = False
    resources_check_result = {}
    for resource in pipeline_config['resources']:
        if resource['name'] == 'concourse-resources' and resource['type'] == 'git':
            concourse_resources_used = True
            if resource['source']['uri'] != repo_uri:
                resources_check_result['status'] = "failed"
                resources_check_result['message'] = f"Incorrect git repository [{resource['source']['uri']}]"
                resources_error = True
                break

            if resource['source']['branch'] != repo_branch:
                resources_check_result['status'] = "failed"
                resources_check_result['message'] = f"Incorrect git branch [{resource['source']['branch']}]"
                resources_error = True
                break
                
    if not concourse_resources_used:
        resources_check_result['status'] = "skipped"
        resources_check_result['message'] = "Did not find a resources entry for concourse-resources"


    if concourse_resources_used and not resources_error:
        resources_check_result['status'] = "passed"
        resources_check_result['message'] = ""

    return resources_check_result


def validate_concourse_resources_tasks(pipeline_config: dict, task_path: str) -> dict[str, str]:
    task_error = False
    tasks_check_result = {}
    tasks_using_files = False
    for job in pipeline_config['jobs']:
        for job_plan in job['plan']:
            if 'file' in job_plan:
                tasks_using_files = True
                task_file_path = str(job_plan['file'])
                if not task_file_path.startswith(task_path):
                    task_error = True
                    tasks_check_result['status'] = "failed"
                    tasks_check_result['message'] = f"Incorrect task file path: [{task_file_path}]"
                    break

    if not tasks_using_files:
        tasks_check_result['status'] = "skipped"
        tasks_check_result['message'] = "Did not find any tasks using task files"
    
    if tasks_using_files and not task_error:
        tasks_check_result['status'] = "passed"
        tasks_check_result['message'] = ""

    return tasks_check_result


def display_report(pipeline_validity_dict: dict) -> dict:
    pipeline_errors_dict = {}
    pipeline_warnings_dict = {}
    results_icon_dict = {
        "failed": "❌",
        "passed": "✅",
        "skipped": "❓"
    }

    report_table = PrettyTable()
    report_table.align = "c"
    report_table.field_names = ["Pipeline", "Config", "Resources", "Tasks"]

    for pipeline in sorted(pipeline_validity_dict):
        resources_status = pipeline_validity_dict[pipeline]['resources_status']
        resources_icon = results_icon_dict[resources_status]
        resources_message = pipeline_validity_dict[pipeline]['resources_message']
        if resources_status == 'failed':
            pipeline_errors_dict[pipeline] = resources_message
        elif resources_status == 'skipped':
            pipeline_warnings_dict[pipeline] = resources_message

        tasks_status = pipeline_validity_dict[pipeline]['tasks_status']
        tasks_icon = results_icon_dict[tasks_status]
        tasks_message = pipeline_validity_dict[pipeline]['tasks_message']
        if tasks_status == 'failed':
            pipeline_errors_dict[pipeline] = tasks_message
        elif tasks_status == 'skipped':
            pipeline_warnings_dict[pipeline] = tasks_message

        config_status = pipeline_validity_dict[pipeline]['config_status']
        config_icon = results_icon_dict[config_status]
        config_message = pipeline_validity_dict[pipeline]['config_message']
        if config_status == 'failed':
            pipeline_errors_dict[pipeline] = config_message
        elif config_status == 'skipped':
            pipeline_warnings_dict[pipeline] = config_message

        report_table.add_row([pipeline, f"{config_icon}", f"{resources_icon}", f"{tasks_icon}"])

    print()
    print(report_table)

    output_dict = {
        "warnings": pipeline_warnings_dict,
        "errors": pipeline_errors_dict
    }

    return output_dict


def output_messages_and_exit(output_dict: dict) -> None:
    if 'warnings' in output_dict:
        print()
        for pipeline in output_dict['warnings']:
            format_output(
                f"{pipeline}: {output_dict['warnings'][pipeline]}",
                "warn"
            )

    if 'errors' in output_dict:
        print()
        for pipeline in output_dict['errors']:
            format_output(
                f"{pipeline}: {output_dict['errors'][pipeline]}",
                "error"
            )

        print()
        format_output(
            "Validation errors encountered",
            "error"
        )
        sys.exit(1)

    print()
    format_output(
        "Validation completed successfully",
        "info"
    )
    sys.exit()


def load_pipelines_file(args_dict: dict) -> list[str]:
    pipelines_file = args_dict['pipelines_file']
    pipelines_list = []
    with open(pipelines_file, 'r') as file:
        while pipeline := file.readline():
            pipelines_list.append(pipeline.rstrip())

    return pipelines_list


def process_args() -> dict[str, str]:
    parser = argparse.ArgumentParser(description="Program arguments and options",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('pipelines_file',
                        default=None,
                        help="A file containing a list of pipelines to process",
                        nargs=1)
    parser.add_argument('--base-dir',
                        default='.',
                        help="The base directory in which the pipeline configurations are stored",
                        nargs=1)
    parser.add_argument('--repo-uri',
                        default='git@github.com:companieshouse/ci-concourse-resources.git',
                        help="The Github URI to use during validation",
                        nargs=1)
    parser.add_argument('--repo-branch',
                        default='shared-services',
                        help="The repository branch to use during validation",
                        nargs=1)
    parser.add_argument('--task-path',
                        default='concourse-resources/tasks',
                        help="The task file path to use during validation",
                        nargs=1)
    args = parser.parse_args()

    args_dict = {
        'pipelines_file': args.pipelines_file[0],
        'pipelines_base_dir': args.base_dir[0],
        'repo_uri': args.repo_uri,
        'repo_branch': args.repo_branch,
        'task_path': args.task_path
    }
    print(args_dict)
    return args_dict


def main() -> None:
    args_dict = process_args()
    pipelines_list = load_pipelines_file(args_dict)
    pipeline_validity_dict = validate_pipelines(args_dict, pipelines_list)

    output_dict = display_report(pipeline_validity_dict)
    output_messages_and_exit(output_dict)


"""
Entrypoint
"""
if __name__ == "__main__":
    main()
