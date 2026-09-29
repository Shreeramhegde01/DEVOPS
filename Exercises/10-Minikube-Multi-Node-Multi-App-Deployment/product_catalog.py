# product_catalog.py - AppA: lists the products available in the store
import os
import socket

from flask import Flask, jsonify

app = Flask(__name__)

products = [
    {"id": 1, "name": "Laptop", "price": 1200},
    {"id": 2, "name": "Phone", "price": 800},
    {"id": 3, "name": "Headphones", "price": 150},
]


@app.route("/products", methods=["GET"])
def get_products():
    return jsonify(products)


@app.route("/whoami", methods=["GET"])
def whoami():
    # NODE_NAME is injected by the Deployment (downward API) - shows how replicas are spread over nodes
    return jsonify({"service": "product-catalog", "pod": socket.gethostname(), "node": os.environ.get("NODE_NAME")})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
