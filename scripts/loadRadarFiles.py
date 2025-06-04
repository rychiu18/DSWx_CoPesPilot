# Loading radar files based on inputs from "input.yaml" file and plotting all images

# data wrangling imports
from helperFuncs import *
import rasterio
import rioxarray
import numpy as np
import pandas as pd
import xarray as xr
import yaml
import geopandas as gpd
import geoviews as gv
import hvplot.xarray
import hvplot.pandas
from bokeh.models import FixedTicker
gv.extension('bokeh')
from datetime import datetime
from osgeo import gdal

# STAC imports to retrieve cloud data
from pystac_client import Client

# GDAL setup for accessing cloud data
gdal.SetConfigOption('GDAL_HTTP_COOKIEFILE','~/cookies.txt')
gdal.SetConfigOption('GDAL_HTTP_COOKIEJAR', '~/cookies.txt')
gdal.SetConfigOption('GDAL_DISABLE_READDIR_ON_OPEN','EMPTY_DIR')
gdal.SetConfigOption('CPL_VSIL_CURL_ALLOWED_EXTENSIONS','TIF, TIFF')

with open('input.yaml', 'r') as file:
    yamlData = yaml.safe_load(file)

# Define data search parameters
# Define AOI as left, bottom, right and top lat/lon extent
aoi = (yamlData['left'], yamlData['bottom'], yamlData['right'], yamlData['top']) # twin harbors (AOI - area of interest)
date_range = yamlData['startDate'] + '/' + yamlData['endDate'] # between these two dates

# Define a dictionary with appropriate keys: 'bbox' and 'datetime'
search_params = {
                  'bbox' : aoi, 
                  'datetime' : date_range,
                }

## Executing a search with the PySTAC API
# Define the base URL for the STAC to search
STAC_URL = 'https://cmr.earthdata.nasa.gov/stac'
# Update the dictionary opts with list of collections to search
collections = ["OPERA_L3_DSWX-S1_V1_1.0"]
search_params.update(collections=collections)
print(search_params)


# We open a client instance to search for data, and retrieve relevant data records
catalog = Client.open(f'{STAC_URL}/POCLOUD/')
search_results = catalog.search(**search_params)

print(f'{type(search_results)=}')

results = list(search_results.items_as_dicts())
print(f"Number of tiles found intersecting given bounding box: {len(results)}")

times = pd.DatetimeIndex([result['properties']['datetime'] for result in results])
# data = {'hrefs': [value['href'] for result in results for key, value in result['assets'].items() if '0_B01_WTR' in key], 'tile_id': [value['href'].split('/')[-1].split('_')[3] for result in results for key, value in result['assets'].items() if '0_B01_WTR' in key]}
data = {'hrefs': [value['href'] for result in results for key, value in result['assets'].items() if '0_B02_BWTR' in key], 'tile_id': [value['href'].split('/')[-1].split('_')[3] for result in results for key, value in result['assets'].items() if '0_B02_BWTR' in key]}

# Construct Pandas DataFrame to summarize granules from search results
if yamlData['estuary'] == 'Grays Harbor':
    tileID = 'T10TDT'
    mapName = 'Grays Harbor'
if yamlData['estuary'] == 'Willapa Bay':
    tileID = 'T10TDS'
    mapName = 'Willapa Bay'
granules = pd.DataFrame(index=times, data=data)
granules = granules[granules.tile_id == tileID] # Grays Harbor (T10TDT)
granules.index.name = 'times'

print(granules)

## Filter out duplicates
unique_dates = pd.DataFrame(columns=['Date'])
unique_dates['Date'] = granules.index.date
duplicate_idx = []
for i in range(len(unique_dates)-1):
    if unique_dates['Date'][i] == unique_dates['Date'][i+1]:
        duplicate_idx.append(i)
        duplicate_idx.append(i+1)
# find index of 2nd element to remove
remove_idx = []
for i in range(len(duplicate_idx)):
    if i%2:
        remove_idx.append(duplicate_idx[i])
remove_idx.reverse() # reverse to remove each index without affecting entire list
granules = granules.reset_index()
for i in remove_idx:
    granules = granules.drop([i])
granules = granules.set_index('times')

print('Starting url to dataset...')
dataset= urls_to_dataset(granules) # takes a while if date range is large
print('...url to dataset conversion complete')

## Loading in Grays Harbor/Willapa Bay polygon bounds
if yamlData['estuary'] == 'Grays Harbor':
    polygon = gpd.read_file('../data/Shapefiles/GraysHarbor_DSWxShapefile_v2-polygon.shp')
else:
    polygon = gpd.read_file('../data/Shapefiles/WillapaBay_DSWxShapefile_v2-polygon.shp')
polygon = polygon.to_crs('epsg:32610')

# Filter out based on polygon
dataset = dataset.rename({'lon':'x', 'lat':'y', 'band':'band'}).squeeze()
dataset = dataset.rio.clip(polygon.geometry)
dataset = dataset.rename({'x':'easting', 'y':'northing', 'band':'band'}).squeeze()

# Creates basemap
base1 = gv.tile_sources.OSM.opts(width=1000, height=1000, padding=0.1)

# Initialize image options dictionary
image_opts = dict(
                    x='easting',
                    y='northing',    
                    rasterize=True, 
                    dynamic=True,
                    aspect='equal',
                    alpha=0.8,
                    pixel_ratio=4,
                    padding = 0,
                    fontscale = 2
                 ) 

# Initialize layout options dictionary
layout_opts = dict(
                    xlabel='Longitude',
                    ylabel='Latitude'
                  )

## Defines colormap for visualization
color_key = {
    "Water": "#0000ff",
}

layout_opts.update(
                    title=str(mapName) + ' ( %sZ)'%granules[0:1].index.strftime('%Y-%m-%d %H:%M:%S')[0],
                    cmap=tuple(color_key.values()),
                    colorbar=False
                  )

bwtr = dataset.where(dataset==1)
image_opts.update(crs=dataset.rio.crs)
p = bwtr.hvplot(**image_opts).opts(**layout_opts) * base1


# ### STATISTICS ###
# # Calculated number of wet cells and wetted surface area
# nonnan_idx = ~np.isnan(bwtr.data)
# print('Number of wet cells:', len(bwtr.data[nonnan_idx]))
# print('Wetted area:', len(bwtr.data[nonnan_idx])*30*30, 'm^2')

### PLOT ###
hvplot.show(p)
