"""Task 5 - test restricted actions inside the container.

Runs the same actions in two containers built from the same image:
  * one with Docker's default AppArmor profile (docker-default)
  * one with our custom profile (my-apparmor-profile)
and prints what was ALLOWED / BLOCKED in each, so the effect of the profile is visible side by side.

Usage:  python test_restricted_actions.py        (run apply_apparmor.py first so the image exists)
Exit code is 0 only if every action that must be blocked is blocked by my-apparmor-profile.
"""
import sys
import time

import docker

IMAGE = "flask-apparmor"
PROFILE = "my-apparmor-profile"

SPAWN_SHELL = ("import subprocess; "
               "print(subprocess.run(['/bin/sh', '-c', 'echo shell-started'], capture_output=True, text=True).stdout)")
HTTP_CHECK = "import urllib.request; print(urllib.request.urlopen('http://localhost:5000/').status)"

# (description, command, should my-apparmor-profile block it?)
CHECKS = [
    ("Read /etc/passwd", ["cat", "/etc/passwd"], True),
    ("Write a file in /etc", ["touch", "/etc/hacked"], True),
    ("Execute /bin/bash from a shell in the container", ["sh", "-c", "/bin/bash -c 'echo shell-started'"], True),
    ("Flask/Python process spawns /bin/sh", ["python", "-c", SPAWN_SHELL], True),
    ("Read the app's own code /app/app.py", ["cat", "/app/app.py"], False),
    ("App still answers HTTP on port 5000", ["python", "-c", HTTP_CHECK], False),
]


def run_checks(client, security_opt):
    container = client.containers.run(IMAGE, security_opt=security_opt, detach=True)
    try:
        time.sleep(3)  # give Flask a moment to start
        results = []
        for description, command, _ in CHECKS:
            exit_code, output = container.exec_run(command)
            results.append((exit_code, output.decode(errors="replace").strip().splitlines()[-1:] or [""]))
        profile = client.api.inspect_container(container.id).get("AppArmorProfile")
        return profile, results
    finally:
        container.remove(force=True)


def main():
    client = docker.from_env()

    default_profile, default_results = run_checks(client, security_opt=None)
    try:
        custom_profile, custom_results = run_checks(client, security_opt=[f"apparmor={PROFILE}"])
    except docker.errors.APIError as exc:
        sys.exit(f"Could not start a container with {PROFILE}: {exc.explanation}\n"
                 f"Load it first:  sudo apparmor_parser -r -W /etc/apparmor.d/{PROFILE}")

    def verdict(code):
        return f"{'ALLOWED' if code == 0 else 'BLOCKED'} (exit {code})"

    print(f"{'Action':<50} {default_profile or 'docker-default':<22} {custom_profile}")
    print("-" * 96)
    failures = 0
    for (description, _, must_block), (d_code, _), (c_code, c_out) in zip(CHECKS, default_results, custom_results):
        print(f"{description:<50} {verdict(d_code):<22} {verdict(c_code)}")
        if c_code != 0:
            print(f"{'':<50} {'':<22} -> {c_out[0][:70]}")
        if must_block == (c_code == 0):
            failures += 1

    print("\nRESULT:", "all restrictions enforced" if failures == 0 else f"{failures} check(s) not as expected")
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
