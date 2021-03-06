# -*- coding: utf-8 -*-
#
"""
***********************************************************************************
Name                 : Tile raster                                               *
Description          : Create a tile(PNG) from parameters: zoom, xtile, ytile.    *
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


import os, math, collections

from osgeo import gdal, osr
from osgeo.gdalconst import GA_ReadOnly
gdal.AllRegister()
gdal.UseExceptions()

class TileRaster():
    SRS_WGS84 = '+proj=longlat +datum=WGS84 +no_defs'
    SRS_PSEUDO_MERCATOR = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext  +no_defs'
    TILE_SIZE = 256
    def __init__(self, filepath, formatImage):
        def hasGeorefence():
            if ( 0.0, 1.0, 0.0, 0.0, 0.0, 1.0 ) == self._ds.GetGeoTransform():
                self._message = 'Image missing georeference(geotransform)'
                self._statusError = 1
                return False
            srs = self._ds.GetProjectionRef()
            if not bool( srs ):
                self._message = 'Image missing georeference(projectionref)'
                self._statusError = 1
                return False
            return True

        def getMinMaxPoint():
            xMin, xRes, _xRotation, yMax, _yRotation, yRes = self._ds.GetGeoTransform()
            xSize, ySize = self._ds.RasterXSize, self._ds.RasterYSize
            xMax = xMin + xRes * xSize
            yMin = yMax + yRes * ySize # yRes Negative
            #
            srsImage = osr.SpatialReference( self._ds.GetProjectionRef() )
            srsTile = osr.SpatialReference()
            srsTile.ImportFromProj4( self.SRS_WGS84 )
            if not srsImage.IsSame( srsTile ):
                ct = osr.CoordinateTransformation( srsImage, srsTile )
                try:
                    ( xMin, yMin, _z ) = ct.TransformPoint( xMin, yMin )
                    ( xMax, yMax, _z ) = ct.TransformPoint( xMax, yMax )
                except RuntimeError as e:
                    self._message = f"Transform - {str(e)}"
                    self._statusError = 1
                    return None
            Point = collections.namedtuple('Point', 'x y')
            MinMax = collections.namedtuple('MinMax', 'min max')
            return MinMax( Point( xMin, yMin ), Point( xMax, yMax ) )

        self.driverName = formatImage
        self._message = None
        self._statusError = 0 # 0(None), 1(image), 2(request/tile out image)
        try:
            self._ds = gdal.Open( filepath, GA_ReadOnly )
        except RuntimeError as e:
            self._message = f"Open: {str(e)}"
            self._statusError = 1
            self._ds = None
            return

        if not hasGeorefence():
            self._ds = None
            return

        self.pointsImage = getMinMaxPoint()
        if self.pointsImage is None:
            self._ds = None

    def __del__(self):
        self._ds = None

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

        def getDatasetTile(tile):
            # Warp
            args = {
                'destNameOrDestDS': '',
                'srcDSOrSrcDSTab': self._ds,
                'format': 'mem',
                'dstSRS': self.SRS_PSEUDO_MERCATOR,
                'resampleAlg': gdal.GRA_Bilinear,
                'height': self.TILE_SIZE, 'width': self.TILE_SIZE,
                'outputBounds': [ tile.min.x, tile.min.y, tile.max.x, tile.max.y ],
                'outputBoundsSRS': self.SRS_WGS84
            }
            try:
                ds = gdal.Warp( **args )
            except RuntimeError as e:
                self._message = f"Warp - {str(e)}"
                self._statusError = 1
                ds = None
            return ds

        if self._ds is None: return False

        Point = collections.namedtuple('Point', 'x y')
        MinMax = collections.namedtuple('MinMax', 'min max')
        pointMin = num2deg( zoom, xtile, ytile+1 )
        pointMax = num2deg( zoom, xtile+1, ytile )
        tile = MinMax( pointMin, pointMax )

        # Image: Left, Right, Bottom and Upper
        if self.pointsImage.max.x < tile.min.x or \
           self.pointsImage.min.x > tile.max.x or \
           self.pointsImage.max.y < tile.min.y or \
           self.pointsImage.min.y > tile.max.y:
           #
           self._message = f"Tile out of image"
           self._statusError = 2
           return False

        ds = getDatasetTile( tile )
        if ds is None:
            return False
        _ds = gdal.GetDriverByName( self.driverName ).CreateCopy( filepath, ds )
        _ds, ds = 2 * [None]
        aux_xml = "{}.aux.xml".format( filepath )
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

    def bytesTile(self, zoom, xtile, ytile):
        def getBytesFromTempfile():
            # https://lists.osgeo.org/pipermail/gdal-dev/2016-August/045030.html
            try:
                f = gdal.VSIFOpenL( memfile, 'rb')
                gdal.VSIFSeekL(f, 0, 2) # seek to end
                size = gdal.VSIFTellL(f)
                gdal.VSIFSeekL(f, 0, 0) # seek to beginning
                data = gdal.VSIFReadL(1, size, f)
                gdal.VSIFCloseL(f)
            except RuntimeError as e:
                self._message = f"Load memfile - {str(e)}"
                self._statusError = 1
                data = None
            return data

        memfile = '/vsimem/temp'
        isOk = self._createImage( memfile, zoom, xtile, ytile )
        if not isOk:
            return None
        data = getBytesFromTempfile()
        gdal.Unlink( memfile )
        return data
