#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Astra Monitor - Reboot Server
Flask server for system reboot management
"""

from flask import Flask, jsonify
from flask_cors import CORS
import os
import subprocess

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return jsonify({
        'service': 'Astra Monitor Reboot Server',
        'status': 'running',
        'version': '2.0'
    })

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/reboot')
def reboot():
    return jsonify({'message': 'Reboot scheduled', 'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8084))
    app.run(host='0.0.0.0', port=port, debug=False)