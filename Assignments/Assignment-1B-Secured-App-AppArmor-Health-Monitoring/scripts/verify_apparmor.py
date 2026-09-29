"""Verifies with the Docker SDK that flask-auth-profile is applied to the running app container and enforced.

It compares the running (confined) container with a throw-away container from the same image that only has
Docker's default profile. Commands run as *root inside the container* to show that AppArmor still blocks them
even when an attacker has become root.

Usage:  python verify_apparmor.py
"""
import sys
import time

from common import APP_CONTAINER, APP_IMAGE, APPARMOR_PROFILE, client, get_container, http_json

WRITE_APP = "open('/app/app.py', 'a').write('# backdoor')"
SPAWN_SHELL = "import subprocess; subprocess.run(['/bin/sh', '-c', 'id'], check=True)"

# (description, command, user, must be blocked by the profile?)
CHECKS = [
    ("Read /etc/passwd (as root)", ["cat", "/etc/passwd"], "root", True),
    ("Modify application code /app/app.py (as root)", ["python", "-c", WRITE_APP], "root", True),
    ("Create a file in /etc (as root)", ["python", "-c", "open('/etc/evil', 'w')"], "root", True),
    ("App process spawns /bin/sh", ["python", "-c", SPAWN_SHELL], "appuser", True),
    ("Read the app's templates", ["python", "-c", "open('/app/templates/login.html').read()"], "appuser", False),
]


def run_checks(container):
    results = []
    for _, command, user, _ in CHECKS:
        exit_code, output = container.exec_run(command, user=user)
        results.append((exit_code, (output.decode(errors="replace").strip().splitlines() or [""])[-1]))
    return results


def verdict(code):
    return f"{'ALLOWED' if code == 0 else 'BLOCKED'} (exit {code})"


def main():
    docker_client = client()
    app = get_container(docker_client, APP_CONTAINER)
    if app is None or app.status != "running":
        sys.exit("secure-flask-app is not running - run deploy_secure_stack.py first")

    info = docker_client.api.inspect_container(app.id)
    _, attr = app.exec_run(["cat", "/proc/1/attr/current"])
    kernel_view = attr.decode().strip()
    print("=== Profile applied? ===")
    print(f"HostConfig.SecurityOpt : {info['HostConfig']['SecurityOpt']}")
    print(f"AppArmorProfile        : {info.get('AppArmorProfile')}")
    print(f"Kernel view of PID 1   : {kernel_view}")
    applied = info.get("AppArmorProfile") == APPARMOR_PROFILE and "(enforce)" in kernel_view

    baseline = docker_client.containers.run(APP_IMAGE, detach=True)   # Docker's default profile only
    try:
        time.sleep(2)
        default_results = run_checks(baseline)
        default_profile = docker_client.api.inspect_container(baseline.id).get("AppArmorProfile") or "docker-default"
    finally:
        baseline.remove(force=True)
    confined_results = run_checks(app)

    print("\n=== Enforcement ===")
    print(f"{'Action':<48} {default_profile:<20} {APPARMOR_PROFILE}")
    print("-" * 90)
    failures = 0
    for (description, _, _, must_block), (d_code, _), (c_code, c_out) in zip(CHECKS, default_results,
                                                                             confined_results):
        print(f"{description:<48} {verdict(d_code):<20} {verdict(c_code)}")
        if c_code != 0:
            print(f"{'':<48} {'':<20} -> {c_out[:60]}")
        failures += must_block == (c_code == 0)

    print("\n=== Application still works under the profile ===")
    user = f"verify{int(time.time())}"
    reg_status, _ = http_json("POST", "/api/register", {"username": user, "password": "verify-pass-1"})
    login_status, login = http_json("POST", "/api/login", {"username": user, "password": "verify-pass-1"})
    print(f"register -> {reg_status}, login -> {login_status} {login}")
    works = reg_status == 201 and login_status == 200

    ok = applied and failures == 0 and works
    print("\nRESULT:", "AppArmor profile applied and enforced, app functional" if ok else "verification FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
