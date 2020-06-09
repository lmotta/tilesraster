# -*- coding: utf-8 -*-
#
"""
***********************************************************************************
Name                 : Tile server                                               *
Description          : Example in Flask for use the Tile Raster script.          *
Date                 : June, 2020                                                 *
copyright            : (C) 2020 by Luiz Motta                                     *
email                : motta.luiz@gmail.com                                       *
***********************************************************************************

***********************************************************************************
*                                                                                 *
*   This code is licensed under an MIT/X style license with the following terms:  *
*                                                                                 *
*   Copyright (c) 2020 Luiz Motta                                                 *
*                                                                                 *
*   Permission is hereby granted, free of charge, to any person obtaining a copy  *
*   of this software and associated documentation files (the "Software"), to deal *
*   in the Software without restriction, including without limitation the rights  *
*   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell     *
*   copies of the Software, and to permit persons to whom the Software is         *
*   furnished to do so, subject to the following conditions:                      *
*                                                                                 *
*   The above copyright notice and this permission notice shall be included in    *
*   all copies or substantial portions of the Software.                           *
*                                                                                 *
*   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR    *
*   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,      *
*   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE   *
*   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER        *
*   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, *
*   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN     *
*   THE SOFTWARE.                                                                 *
*                                                                                 *
***********************************************************************************
"""

__author__ = 'Luiz Motta'
__date__ = '2020-06-09'
__copyright__ = '(C) 2020, Luiz Motta'
__revision__ = '$Format:%H$'


import os, functools

from flask import Flask, Response, render_template

from tileraster import TileRaster


app = Flask(__name__)

STATUS_HTTP_TILES_RASTER = {
    0: 200, # OK
    1: 500, # Internal Server Error
    2: 400  # Bad Request
}

IMAGES_DIR = '/home/lmotta/data/db/drone'
catalogRaster = {
    'ac': { 'file': 'ac.tif', 'tileraster': None }
}

def responseError(message, status):
    return Response( f"{message}\n", status, mimetype='text/plain' )

@app.route('/demo')
def demo():
    return render_template('demo_openlayers_drone.html')

@app.route('/')
def index():
    return responseError("Need Paths: .../tile/k/z/x/y", 400)

@app.route('/tile/<k>/<z>/<x>/<y>')
@functools.lru_cache(maxsize=1024)
def tilezxy(k, z, x, y):
    def error(tileraster):
        status = STATUS_HTTP_TILES_RASTER[ tileraster.status_error ]
        return responseError( tileraster.message, status )

    if not k in catalogRaster:
        msg = f"Missing image in Database(K = {k})"
        return responseError( msg, 500 )

    tileraster = catalogRaster[ k ]['tileraster']
    if tileraster is None:
        filepath = os.path.join( IMAGES_DIR, catalogRaster[ k ]['file'] )
        tileraster = TileRaster( filepath, 'PNG')
        # Check image error
        if tileraster.status_error:
            return error( tileraster )
        catalogRaster[ k ]['tileraster'] = tileraster

    if not z.isdigit() or not x.isdigit() or not y.isdigit():
        msg = f"Parameters 'z/x/y' need be a integer number"
        return responseError( msg, 400 )

    data = tileraster.bytesTile( int( z ), int( x), int( y ) )
    if tileraster.status_error:
        return error( tileraster )
    return Response( data, mimetype='image/png' )


if __name__ == '__main__':
    app.run()
