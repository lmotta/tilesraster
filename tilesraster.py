# -*- coding: utf-8 -*-

import os, math, collections, functools

from osgeo import gdal, ogr, osr
from osgeo.gdalconst import GA_ReadOnly
gdal.AllRegister()
gdal.UseExceptions()

class TilesRaster():
    SRS_WGS84 = '+proj=longlat +datum=WGS84 +no_defs'
    SRS_PSEUDO_MERCATOR = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext  +no_defs'
    TILE_SIZE = 256
    @staticmethod
    def quadKey2tile(quadKey):
        """
        Adaptation from 'https://github.com/mapbox/mercantile'
        """
        Tile = collections.namedtuple("Tile", 'z x y')
        if not bool(quadKey):
            return Tile(0,0,0)
        xtile, ytile = 0, 0
        for i, digit in enumerate( reversed(quadKey) ):
            mask = 1 << i
            if digit == '1':
                xtile = xtile | mask
            elif digit == '2':
                ytile = ytile | mask
            elif digit == '3':
                xtile = xtile | mask
                ytile = ytile | mask
            elif digit != '0':
                raise Exception(f"Unexpected quadkey digit: {digit}")
        return Tile( i+1, xtile, ytile )

    def __init__(self, filepath, formatImage):
        def hasGeorefence():
            if ( 0.0, 1.0, 0.0, 0.0, 0.0, 1.0 ) == self.ds.GetGeoTransform():
                self._message = 'Image missing georeference(geotransform)'
                self._statusError = 1
                return False
            srs = self.ds.GetProjectionRef()
            if not bool( srs ):
                self._message = 'Image missing georeference(projectionref)'
                self._statusError = 1
                return False
            return True

        def getBBox():
            xMin, xRes, xRotation, yMax, yRotation, yRes = self.ds.GetGeoTransform()
            xSize, ySize = self.ds.RasterXSize, self.ds.RasterYSize
            xMax = xMin + xRes * xSize + ySize * xRotation
            yMin = yMax + yRes * ySize + xSize * yRotation # yRes Negative
            # Geom
            geom = self._createGeometry( xMin, yMin, xMax, yMax )
            geom.AssignSpatialReference( self.srsImage )
            try:
                geom.TransformTo( self.srsTile )
            except RuntimeError as e:
                self._message = f"Transform - {str(e)}"
                self._statusError = 1
                return None
            return geom

        self.driverName = formatImage
        self._message = None
        self._statusError = 0 # 0(None), 1(image), 2(request/tile)
        try:
            self.ds = gdal.Open( filepath, GA_ReadOnly )
        except RuntimeError as e:
            self._message = f"Open: {str(e)}"
            self._statusError = 1
            self.ds = None
            return
        if not hasGeorefence():
            self._message = f"Missing georeference"
            self._statusError = 1
            self.ds = None
            return
        self.srsImage = osr.SpatialReference( self.ds.GetProjectionRef() )
        self.srsTile = osr.SpatialReference()
        self.srsTile.ImportFromProj4( self.SRS_WGS84 )
        self.bbox = getBBox()
        if self.bbox is None:
            self.ds = None

    def __del__(self):
        self.ds = None

    def _createGeometry(self, xMin, yMin, xMax, yMax):
        ring = ogr.Geometry( ogr.wkbLinearRing )
        ring.AddPoint( xMin, yMin ) # Left  Bottom 
        ring.AddPoint( xMax, yMin ) # Right Bottom
        ring.AddPoint( xMax, yMax ) # Right Upper
        ring.AddPoint( xMin, yMax ) # Left Upper
        ring.AddPoint( xMin, yMin )
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)
        return poly

    def _createImage(self, filepath, zoom, xtile, ytile):
        def num2deg(z, x, y):
            """
            Adaptation from 'https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames'
            """
            n = 2.0 ** z
            vlong = x / n * 360.0 - 180.0
            lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
            vlat = math.degrees(lat_rad)
            return Point( vlong, vlat )

        def getDatasetTile(pointMin, pointMax, geomTile):
            def getPointMinMaxBuffer(ratio):
                xBuffer = ratio * ( pointMax.long - pointMin.long )
                yBuffer = ratio * ( pointMax.lat - pointMin.lat )
                pMin = Point( pointMin.long - xBuffer, pointMin.lat - yBuffer )
                pMax = Point( pointMax.long + xBuffer, pointMax.lat + yBuffer )
                return pMin, pMax

            def getDatasetResample():
                widthPct = self.TILE_SIZE / self.ds.RasterXSize * 100
                heightPct = self.TILE_SIZE / self.ds.RasterYSize * 100
                args = {
                    'destName': '',
                    'format': 'mem',
                    'srcDS': self.ds,
                    'widthPct': widthPct, 'heightPct': heightPct
                }
                try:
                    ds = gdal.Translate( **args )
                except RuntimeError as e:
                    self._message = f"Translate: {str(e)}"
                    self._statusError = 1
                    ds = None
                return ds

            def getDatasetSubset(pointMin, pointMax):
                args = {
                    'destName': '',
                    'format': 'mem',
                    'srcDS': self.ds,
                    'projWin': [ pMin.long, pMax.lat, pMax.long, pMin.lat ],
                    'projWinSRS': self.SRS_WGS84
                }
                try:
                    ds = gdal.Translate( **args )
                except RuntimeError as e:
                    self._message = f"Translate: {str(e)}"
                    self._statusError = 1
                    ds = None
                return ds
            
            # if self.bbox.Contains( geomTile ):
            #     pMin, pMax = getPointMinMaxBuffer(0.1)
            #     dsTile = getDatasetSubset( pMin, pMax )
            # else:
            #     dsTile = getDatasetResample()
            # if dsTile is None:
            #     return None
            # Warp
            args = {
                'destNameOrDestDS': '',
                'srcDSOrSrcDSTab': self.ds,
                'format': 'mem',
                'dstSRS': self.SRS_PSEUDO_MERCATOR,
                'resampleAlg': gdal.GRA_NearestNeighbour,
                'height': self.TILE_SIZE, 'width': self.TILE_SIZE,
                'outputBounds': [ pointMin.long, pointMin.lat, pointMax.long, pointMax.lat ],
                'outputBoundsSRS': self.SRS_WGS84
            }
            try:
                ds = gdal.Warp( **args )
            except RuntimeError as e:
                self._message = f"Warp - {str(e)}"
                self._statusError = 1
                ds = None
            return ds

        if self.ds is None:
            return False
        Point = collections.namedtuple('Point', 'long lat' )
        pointMin = num2deg( zoom, xtile, ytile+1 )
        pointMax = num2deg( zoom, xtile+1, ytile )
        geom = self._createGeometry( pointMin.long, pointMin.lat, pointMax.long, pointMax.lat )
        if not self.bbox.Intersects( geom ):
            self._message = f"Tile outside image"
            self._statusError = 2
            return False
        ds = getDatasetTile( pointMin, pointMax, geom )
        if ds is None:
            return False
        _ds = gdal.GetDriverByName( self.driverName ).CreateCopy( filepath, ds )
        _ds, ds = 2 * [None]
        aux_xml = "{}{}.aux.xml".format( *os.path.splitext( filepath) )
        if os.path.exists( aux_xml ):
            os.remove( aux_xml )
        self._statusError = 0
        return True

    @property
    def status_error(self): return self._statusError

    @property
    def message(self): return self._message

    def saveTile(self, filepath, zoom, xtile, ytile):
        return self._createImage( filepath, zoom, xtile, ytile )

    @functools.lru_cache(maxsize=1024)
    def bytesTile(self, zoom, xtile, ytile):
        def getBytesFromTempfile():
            # https://lists.osgeo.org/pipermail/gdal-dev/2016-August/045030.html
            f = gdal.VSIFOpenL( memfile, 'rb')
            gdal.VSIFSeekL(f, 0, 2) # seek to end
            size = gdal.VSIFTellL(f)
            gdal.VSIFSeekL(f, 0, 0) # seek to beginning
            data = gdal.VSIFReadL(1, size, f)
            gdal.VSIFCloseL(f)
            return data

        memfile = '/vsimem/temp'
        isOk = self._createImage( memfile, zoom, xtile, ytile )
        if not isOk:
            return None
        data = getBytesFromTempfile()
        gdal.Unlink( memfile )
        return data
