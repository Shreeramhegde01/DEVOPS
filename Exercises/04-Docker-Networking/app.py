import socket

from flask import Flask, jsonify

app = Flask(__name__)

# Containers on the same user-defined bridge network, reached by *container name*
# through Docker's embedded DNS server.
DEPENDENCIES = {"mysql": 3306, "redis": 6379}


@app.route('/about', methods=['GET'])
def about():
    return jsonify({
        "name": "Simple REST API",
        "version": "1.0",
        "description": "This is a simple REST API built with Flask."
    })


@app.route('/status', methods=['GET'])
def status():
    """Resolve every dependency by name and open a TCP connection to it."""
    results = {}
    for host, port in DEPENDENCIES.items():
        entry = {"port": port, "reachable": False}
        try:
            entry["ip"] = socket.gethostbyname(host)
            with socket.create_connection((host, port), timeout=2):
                entry["reachable"] = True
        except OSError as exc:
            entry["error"] = str(exc)
        results[host] = entry

    healthy = all(r["reachable"] for r in results.values())
    return jsonify({"container": socket.gethostname(), "dependencies": results}), (200 if healthy else 503)


if __name__ == '__main__':
    # 0.0.0.0 so the app is reachable through the published port (-p 5001:5001)
    app.run(host='0.0.0.0', port=5001)
