import sys, os, functools

from flask import Flask, Response, render_template

from tilesraster import TilesRaster


app = Flask(__name__)

IMAGES_DIR = '/home/lmotta/data/db/images/landsat'
# IMAGES_DIR = '/home/ubuntu/data/images'
STATUS_HTTP_TILES_RASTER = {
    0: 200, # OK
    1: 500, # Internal Server Error
    2: 400  # Bad Request
}

catalogRaster = {
    '15293': { 'file': 'LC82320682015293LGN00_r6g5b4.tif', 'tilesraster': None },
    '13166': { 'file': 'LC82330682013166LGN00_r6g5b4.tif', 'tilesraster': None }
}

def responseError(message, status):
    return Response( f"{message}\n", status, mimetype='text/plain' )

@app.route('/demo')
def demo():
    return render_template('demo_leaflet.html')

@app.route('/')
def index():
    return responseError("Need Paths: .../tile/k/z/x/y", 400)

@app.route('/tile/<k>/<z>/<x>/<y>')
@functools.lru_cache(maxsize=1024)
def tilezxy(k, z, x, y):
    def error(tilesraster):
        status = STATUS_HTTP_TILES_RASTER[ tilesraster.status_error ]
        return responseError( tilesraster.message, status )

    if not k in catalogRaster:
        msg = f"Missing image in Database(K = {k})"
        return responseError( msg, 400 )

    tilesraster = catalogRaster[ k ]['tilesraster']
    if tilesraster is None:
        filepath = os.path.join( IMAGES_DIR, catalogRaster[ k ]['file'] )
        tilesraster = TilesRaster( filepath, 'PNG')
        # Check image error
        if tilesraster.status_error:
            return error( tilesraster )
        catalogRaster[ k ]['tilesraster'] = tilesraster

    if not z.isdigit() or not x.isdigit() or not y.isdigit():
        msg = f"Parameters 'z/x/y' need be a integer number"
        return responseError( msg, 400 )

    data = tilesraster.bytesTile( int( z ), int( x), int( y ) )
    if tilesraster.status_error:
        return error( tilesraster )
    return Response( data, mimetype='image/png' )



if __name__ == '__main__':
    app.run()
