import sys, os

from flask import Flask, Response

from tilesraster import TilesRaster


app = Flask(__name__)

IMAGES_DIR = '/home/lmotta/data/db/images/landsat_232-063'
STATUS_HTTP_TILES_RASTER = {
    0: 200, # OK
    1: 500, # Internal Server Error
    2: 400  # Bad Request
}

def getTilesRaster(image):
    filepath = os.path.join( IMAGES_DIR, image )
    return TilesRaster( filepath, 'PNG')

def responseError(message, status):
    return Response( f"{message}\n", status, mimetype='text/plain' )

def getResponseTilesRaster(tilesraster, z, x, y):
    data = tilesraster.bytesTile( z, x, y )
    if tileraster.status_error:
        status = STATUS_HTTP_TILES_RASTER[ tilesraster.status_error ]
        return responseError( tilesraster.message, status )
    return Response( data, mimetype='image/png' )

tileraster = getTilesRaster('LC82320632013239LGN00_r6g5b4.tif')

@app.route('/')
def index():
    return f"<h1>Need:/tile/<z>/<x>/<y> </h1>"

@app.route("/tile/<z>/<x>/<y>")
def tilezxy(z, x, y):
    # Check Valid z, x, y
    if tileraster.status_error:
        status = STATUS_HTTP_TILES_RASTER[ tileraster.status_error ]
        return responseError( tileraster.message, status )
    return getResponseTilesRaster( tileraster, int(z), int(x), int(y) )

@app.route("/tile/<q>")
def tileq(q):
    # Check Valid q
    if tileraster.status_error:
        status = STATUS_HTTP_TILES_RASTER[ tileraster.status_error ]
        return responseError( tileraster.message, status )
    z, x, y = TilesRaster.quadKey2tile( q  )
    return getResponseTilesRaster( tileraster, z, x, y )


if __name__ == '__main__':
    app.run()
