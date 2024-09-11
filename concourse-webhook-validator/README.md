# concourse-webhook-validator

Parses a provided Concourse pipeline configuration and discovers resources configured with webhooks. These resources are then compared against the defined `create-webhooks` and `delete-webhooks` jobs to validate the webhook configuration.

The scripts exists with a return code of `0` on a successful validation. The scripts exists with a return code of `1` if any validation errors are found.

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
usage: concourse-webhook-validator [-h] [--base-dir BASE_DIR] [--deployment DEPLOYMENT] [--team TEAM] pipeline

Program arguments and options

positional arguments:
  pipeline              The name of the pipeline to load

optional arguments:
  -h, --help            show this help message and exit
  --base-dir BASE_DIR   The base directory in which the pipeline configurations are stored
  --deployment DEPLOYMENT
                        The name of the Concourse deployment
  --team TEAM           The team name that the pipeline is configured for
```

## Outputs

The script outputs to stdout in column-formatted plain text. Script output messages are in the default Concourse-style log format.


## Examples

Validate the webhooks of a pipeline configuration in the current working directory
```
$ concourse-webhook-validator concourse-ami
Info: Checking webhooks configuration: concourse-ami
Info: Webhooked resources discovered: 6

Resource name                        | Token valid | Create matches | Delete matches
-------------------------------------|-------------|----------------|----------------
concourse-6-source-code              |      ✅     |       ✅       |      ✅
concourse-6-source-code-pull-request |      ✅     |       ✅       |      ✅
concourse-6-release-tag              |      ✅     |       ✅       |      ✅
concourse-7-source-code              |      ✅     |       ✅       |      ✅
concourse-7-source-code-pull-request |      ✅     |       ✅       |      ✅
concourse-7-release-tag              |      ✅     |       ✅       |      ✅

Info: Webhooks configuration check completed successfully
```

Validate a pipeline configuration within a specific directory structure location, based on the Concourse deployment and team name.
```
$ concourse-webhook-validator --base-dir ci-pipelines/pipelines --deployment ssplatform --team team-platform concourse-ami
Info: Checking webhooks configuration: concourse-ami
Info: Webhooked resources discovered: 6

Resource name                        | Token valid | Create matches | Delete matches
-------------------------------------|-------------|----------------|----------------
concourse-6-source-code              |      ✅     |       ✅       |      ✅
concourse-6-source-code-pull-request |      ✅     |       ✅       |      ✅
concourse-6-release-tag              |      ✅     |       ✅       |      ✅
concourse-7-source-code              |      ✅     |       ✅       |      ✅
concourse-7-source-code-pull-request |      ✅     |       ✅       |      ✅
concourse-7-release-tag              |      ✅     |       ✅       |      ✅

Info: Webhooks configuration check completed successfully
```
