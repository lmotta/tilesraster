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

def getResponseTilesRaster(itemCatalog, z, x, y):
    if itemCatalog['tilesraster'] is None:
        filepath = os.path.join( IMAGES_DIR, itemCatalog['file'] )
        itemCatalog['tilesraster'] = TilesRaster( filepath, 'PNG')
        # Check image error
        if itemCatalog['tilesraster'].status_error:
            status = STATUS_HTTP_TILES_RASTER[ itemCatalog['tilesraster'].status_error ]
            return responseError( itemCatalog['tilesraster'].message, status )
    # Check tile error
    data = itemCatalog['tilesraster'].bytesTile( z, x, y )
    if itemCatalog['tilesraster'].status_error:
        status = STATUS_HTTP_TILES_RASTER[ itemCatalog['tilesraster'].status_error ]
        return responseError( itemCatalog['tilesraster'].message, status )
    return Response( data, mimetype='image/png' )

@app.route('/demo')
def demo():
    return render_template('demo_leaflet.html')

@app.route('/')
def index():
    return responseError("Need Paths: .../tile/k/z/x/y OR .../tile/k/q", 400)

@app.route('/tile/<k>/<z>/<x>/<y>')
@functools.lru_cache(maxsize=1024)
def tilezxy(k, z, x, y):
    # Check Valid arguments
    return getResponseTilesRaster( catalogRaster[ k ], int(z), int(x), int(y) )

@app.route('/tile/<k>/<q>')
@functools.lru_cache(maxsize=1024)
def tileq(k, q):
    # Check Valid arguments
    z, x, y = TilesRaster.quadKey2tile( q  )
    return getResponseTilesRaster( catalogRaster[ k ], z, x, y )


if __name__ == '__main__':
    app.run()
