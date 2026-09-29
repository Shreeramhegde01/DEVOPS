# shopping_cart.py - AppB: view and add items to the shopping cart
import os
import socket

from flask import Flask, jsonify, request

app = Flask(__name__)

cart = []   # in-memory, so every replica has its own cart (see README "Observations")


@app.route("/cart", methods=["GET"])
def get_cart():
    return jsonify(cart)


@app.route("/cart", methods=["POST"])
def add_to_cart():
    item = request.json
    cart.append(item)
    return jsonify(cart), 201


@app.route("/whoami", methods=["GET"])
def whoami():
    return jsonify({"service": "shopping-cart", "pod": socket.gethostname(), "node": os.environ.get("NODE_NAME")})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
