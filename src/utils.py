import subprocess
import sys
import os


def run_command(commands, cwd):
    """Run a list of commands."""
    try:
        for command in commands:
            subprocess.check_call(command, shell=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


def lambda_libs(lambda_dir):
    """Install requirements.txt to libs subfolder."""
    os_name = os.name

    # ref https://docs.aws.amazon.com/lambda/latest/dg/python-package.html#python-package-create-dependencies
    if os_name == "Darwin":
        # MacOS specific commands
        commands = [
            "rm -rf libs",
            'docker run --platform linux/x86_64 -v "$PWD":/var/task public.ecr.aws/sam/build-python3.9 /bin/sh -c "pip install -r requirements.txt -t libs; exit"',
        ]
    else:
        # Other OS (assuming Linux) specific commands
        # commands = [
        #     "rmdir /s /q libs",
        #     "mkdir libs",
        #     "pip install -r requirements.txt -t libs --python-version 3.9 --no-deps",
        # ]
        commands = [
            "rm -rf libs && mkdir libs",
            "pip install -r requirements.txt -t libs --platform manylinux_2_28_x86_64 --python-version 3.9 --no-deps",
        ]
    run_command(commands, lambda_dir)
