# concourse-resources-validator

Parses a provided list of Concourse pipeline configuratio files and discovers `concourse-resources` resource configuration and job task files that are then validated against a set of known-good defaults.

The script exits with a return code of `0` on a successful validation. The script exits with a return code of `1` if any validation errors are found. Non-fatal warnings will emit a log message and exit with a return code of `0`.

## Building this project

This project uses the `setuptools` build system available via `pip install build`. A build can be triggered with `python3 -m build`.

A basic Makefile is provided and provides the following actions
* `make build`: Builds the project
* `make clean`: Clean any post-build artefacts

The Python build output will be placed in a `./dist` directory and will comprise a tarball archive as well as a compiled wheel package.

## Requirements

* PyYAML >= 6.0

## Command Line Options

```
usage: concourse-resources-validator.py [-h] [--base-dir BASE_DIR] [--repo-uri REPO_URI] [--repo-branch REPO_BRANCH]
                                        [--task-path TASK_PATH]
                                        pipelines_file

Program arguments and options

positional arguments:
  pipelines_file        A file containing a list of pipelines to process

options:
  -h, --help            show this help message and exit
  --base-dir BASE_DIR   The base directory in which the pipeline configurations are stored (default: .)
  --repo-uri REPO_URI   The Github URI to use during validation (default: git@github.com:companieshouse/ci-concourse-resources.git)
  --repo-branch REPO_BRANCH
                        The repository branch to use during validation (default: shared-services)
  --task-path TASK_PATH
                        The task file path to use during validation (default: concourse-resources/tasks)
```

## Outputs

The script outputs to stdout in column-formatted plain text. Script output messages are in the default Concourse-style log format.


## Examples

Validate a list of pipelines in a file
```
$ concourse-resources-validator /tmp/list-of-pipelines
Info: Starting concourse-resources configuration validation

Info: Repository URI:    [git@github.com:companieshouse/ci-concourse-resources.git]
Info: Repository branch: [shared-services]
Info: Task file path:    [concourse-resources/tasks/*]

Info: Validating pipeline: [my-service-pipeline]
Info: Validating pipeline: [other-service-pipeline]

+------------------------+--------+-----------+-------+
|           Pipeline     | Config | Resources | Tasks |
+------------------------+--------+-----------+-------+
|  my-service-pipeline   |   ✅   |     ✅    |   ✅  |
| other-service-pipeline |   ✅   |     ✅    |   ❌  |
+------------------------+--------+-----------+-------+


Error: other-service-pipeline: Incorrect task file path: [ansible-code/tasks/build.yml]

Error: Validation errors encountered
```
