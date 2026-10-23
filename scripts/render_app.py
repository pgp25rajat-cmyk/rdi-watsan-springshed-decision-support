"""WSGI adapter for Render. Reuses the existing Tool; does not change module calculations."""
from __future__ import annotations

import hmac
import os
import threading

from flask import Flask, Response, jsonify, redirect, request, send_from_directory
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

import spring_tool_server as core
from deployment_storage import archive_run


def create_app(tool=None, archive=None):
    app = Flask(__name__, static_folder=None)
    app.config['MAX_CONTENT_LENGTH'] = core.MAX_BODY
    password = os.environ.get('SPRING_PILOT_PASSWORD', '')
    if not password:
        raise ValueError('SPRING_PILOT_PASSWORD is required for the hosted pilot')
    if os.environ.get('SPRING_REQUIRE_ARCHIVE', '1') == '1' and not os.environ.get('SPRING_RUN_BUCKET'):
        raise ValueError('Configure SPRING_RUN_BUCKET before starting the hosted pilot')
    tool = tool if tool is not None else core.Tool()
    archive = archive or archive_run
    slot = threading.BoundedSemaphore(1)

    @app.before_request
    def authenticate():
        if request.path == '/api/health':
            return None
        auth = request.authorization
        user = os.environ.get('SPRING_PILOT_USER', 'watsan')
        if not auth or not hmac.compare_digest((auth.username or '').encode(), user.encode()) or not hmac.compare_digest((auth.password or '').encode(), password.encode()):
            return Response('Sign in to the WATSAN pilot.', 401,
                            {'WWW-Authenticate': 'Basic realm="WATSAN field pilot", charset="UTF-8"'})

    @app.after_request
    def headers(response):
        response.headers.setdefault('Cache-Control', 'no-store')
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

    @app.get('/api/health')
    def health():
        # Render's probe must not need a password or allocate/open the raster layers.
        return jsonify(ok=True, version=core.VERSION, hosted=True)

    @app.get('/api/status')
    def status():
        return jsonify(tool.health())

    @app.get('/api/springs')
    def springs():
        return jsonify(tool.springs())

    @app.get('/api/di_sites')
    def di_sites():
        return jsonify(core.existing_di_sites())

    @app.post('/api/assess')
    def assess():
        if not slot.acquire(blocking=False):
            return jsonify(error='Another assessment is running. Please wait and try again.'), 429, {'Retry-After': '15'}
        try:
            payload = request.get_json()
            core.clean_request(payload)
            result = tool.assess(payload)
            try:
                result['persistence'] = archive(result, payload)
            except Exception:
                app.logger.exception('Assessment archive upload failed')
                result['persistence'] = {'durable': False, 'reason': 'Archive upload failed. Download this result before leaving.'}
            return jsonify(result)
        except (ValueError, BadRequest, UnsupportedMediaType):
            return jsonify(error='Check the request: valid spring coordinates and a JSON field form are required.'), 400
        except RequestEntityTooLarge:
            return jsonify(error='The request is too large (maximum 1 MB).'), 413
        except Exception:
            app.logger.exception('Assessment failed')
            return jsonify(error='The assessment could not be completed. Please try again.'), 500
        finally:
            slot.release()

    @app.get('/api/terrain/<int:z>/<int:x>/<int:y>.png')
    def terrain(z, x, y):
        if not (0 <= z <= 16 and 0 <= x < 2**z and 0 <= y < 2**z):
            return jsonify(error='No such tile'), 404
        # The hosted pilot's visual terrain comes from the existing public provider.
        # The browser downloads the PNG; the GIS worker avoids decoding/cutting tiles
        # while an assessment is using its limited memory. Calculations still use
        # the private, cached Copernicus DEM, exactly as before.
        if os.environ.get('SPRING_TERRAIN_SOURCE') == 'public':
            response = redirect(core.Terrain.WEB.format(z=z, x=x, y=y), code=302)
            response.headers['Cache-Control'] = 'private, max-age=3600'
            return response
        return Response(tool.terrain.tile(z, x, y), mimetype='image/png',
                        headers={'Cache-Control': 'private, max-age=3600'})

    @app.get('/', defaults={'path': ''})
    @app.get('/<path:path>')
    def frontend(path):
        if path.startswith('api/'):
            return jsonify(error='Unknown address'), 404
        target = (core.DIST / path).resolve()
        if path and target.is_relative_to(core.DIST.resolve()) and target.is_file():
            return send_from_directory(core.DIST, path)
        return send_from_directory(core.DIST, 'index.html')

    return app
