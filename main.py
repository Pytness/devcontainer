#!/usr/bin/env python3

import sys
import subprocess
import os
import argparse
from pathlib import Path


def get_template_names() -> list[str]:
    source_code_path = Path(__file__).resolve().parent
    templates_dir = source_code_path / "templates"

    templates = os.listdir(templates_dir)

    return [template.split(".")[-1] for template in templates]


def get_template_path(template_name: str) -> str:
    source_code_path = Path(__file__).resolve().parent
    templates_dir = source_code_path / "templates"

    return templates_dir / f"Dockerfile.{template_name}"


def generate_template(template_name: str) -> None:
    template_path = get_template_path(template_name)

    if not template_path.exists():
        print(f"Template {template_name} does not exist.")
        sys.exit(1)

    with open(template_path, "r") as template_file:
        template = template_file.read()

    print(template)


parser = argparse.ArgumentParser(
    description="Execute a command in a Docker container.")

parser.add_argument("--generate-template", nargs="?",
                    choices=get_template_names(),
                    help="Generate a template")

parser.add_argument("--dev-dockerfile", nargs="?",
                    default="~/.config/devcontainer/Dockerfile",
                    help="Develoment dockerfile to use")

parser.add_argument("--sdk-image", nargs="?",
                    default="",
                    help="Docker image to use as a base.")

parser.add_argument("--image", nargs="?", help="Docker image to use.")

parser.add_argument("--build", action="store_true",
                    help="Build the Docker image.")

parser.add_argument("--shell", nargs="?",
                    help="Shell to use in the container.")


UID = os.getuid()
GID = os.getgid()
HOME = os.environ.get("HOME", None)
SRC = os.getcwd()
USER = os.environ.get("USER", None)
GROUP = os.environ.get("USER", None)
SHELL = "/bin/zsh"

name = "dev"


CONFIG_DIR = os.environ.get("XDG_CONFIG_HOME")
CONFIG_DEV_DOCKERFILE = "devcontainer/Dockerfile"


def get_default_config_file_path() -> Path | None:
    return Path(CONFIG_DIR) / CONFIG_DEV_DOCKERFILE


def docker_exec(name: str, user: str, command: str) -> None:
    subprocess.run(
        [
            "docker",
            "exec",
            "--user",
            f"{user}:{user}",
            name,
            "sh",
            "-c",
            command,
        ]
    )


def build_container(dockerfile: str, image: str, sdk_image: str) -> None:

    subprocess.run(
        [
            "docker",
            "build",
            "--file",
            dockerfile,
            "--build-arg",
            f"SDK_IMAGE={sdk_image}",
            "--tag",
            image,
            ".",
        ]
    )


def run_container(name: str, image: str) -> None:
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--gpus",
            "all",
            "--env",
            "NVIDIA_DISABLE_REQUIRE=1",
            "--name",
            name,
            "--detach",
            "--tty",
            "--privileged",
            "--network",
            "host",
            "--volume",
            f"{SRC}:/devcontainer/src",
            "--volume",
            f"{SRC}/.devcontainer/env:/devcontainer/env",
            "--volume",
            f"{HOME}/:{HOME}",
            image,
            "/bin/bash",
        ]
    )


def stop_and_remove_container(name: str) -> None:
    subprocess.run(["docker", "stop", name])

    subprocess.run(["docker", "rm", name])


def add_user_to_running_docker(name: str) -> None:

    print(f"Creating container {name} ...")

    subprocess.run(
        [
            "docker",
            "exec",
            # "--user",
            # f"{USER}:{USER}",
            name,
            "sh",
            "-c",
            f"""
            sh -c 'groupadd -g {GID} {GROUP} &&
                   mkdir -p {HOME} &&
                   useradd -u {UID} -g {GROUP} -s /bin/bash -d {HOME} {USER} &&
                   chmod 755 {HOME} &&
                   chown {USER}:{GROUP} {HOME}'
            """,
        ]
    )


# open a shell into the running container
def open_shell(name: str) -> None:
    print(f"Opening shell in container {name}...")

    subprocess.run(
        [
            "docker",
            "exec",
            "--interactive",
            "--tty",
            "--user",
            f"{USER}:{GROUP}",
            name,
            "/bin/bash",
            "-c",
            f"cd /devcontainer/src && {SHELL}",
        ]
    )


if __name__ == "__main__":
    args = parser.parse_args()

    if args.generate_template:
        generate_template(args.generate_template)
        sys.exit(0)

    if args.image is None:
        print("No image specified.")
        sys.exit(1)

    dockerfile_path = Path(args.dev_dockerfile)

    if args.dev_dockerfile is None:
        dockerfile_path = get_default_config_file_path()

    if dockerfile_path is None:
        print("No dockerfile specified.")
        sys.exit(1)

    dockerfile_path = dockerfile_path.expanduser().resolve().absolute()

    image: str = args.image

    if args.shell:
        SHELL = args.shell

    if args.build:
        print(f"Building image {image} from {dockerfile_path}...")
        build_container(dockerfile_path, image, args.sdk_image)

    if image is None:
        print("Missing image, error.")
        sys.exit(1)

    run_container(name, image)
    add_user_to_running_docker(name)

    open_shell(name)

    print(f"Stopping container {name}...")

    stop_and_remove_container(name)
