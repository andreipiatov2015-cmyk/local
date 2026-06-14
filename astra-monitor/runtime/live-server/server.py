#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Astra Monitor - Live Server
Flask server for stream management
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return jsonify({
        'service': 'Astra Monitor Live Server',
        'status': 'running',
        'version': '2.0'
    })

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/streams')
def streams():
    return jsonify({'streams': []})

@app.route('/api/streams/<stream_id>')
def stream_info(stream_id):
    return jsonify({
        'id': stream_id,
        'status': 'active',
        'viewers': 0
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8083))
    app.run(host='0.0.0.0', port=port, debug=False)