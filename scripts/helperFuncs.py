## Helper functions for DSWx products (created by Ryan Chiu)
import rasterio
import numpy as np
import xarray as xr

def urls_to_dataset(granule_dataframe):
    '''method that takes in a list of OPERA tile URLs and returns an xarray dataset with dimensions
    latitude, longitude and time'''

    dataset_list = []
    
    for i, row in granule_dataframe.iterrows():
        with rasterio.open(row.hrefs) as ds:
            # extract CRS string
            crs = str(ds.crs).split(':')[-1]

            # extract the image spatial extent (xmin, ymin, xmax, ymax)
            xmin, ymin, xmax, ymax = ds.bounds

            # the x and y resolution of the image is available in image metadata
            x_res = np.abs(ds.transform[0])
            y_res = np.abs(ds.transform[4])

            # read the data 
            img = ds.read()

            # Ensure img has three dimensions (bands, y, x)
            if img.ndim == 2:
                img = np.expand_dims(img, axis=0) 

        lon = np.arange(xmin, xmax, x_res)
        lat = np.arange(ymax, ymin, -y_res)

        da = xr.DataArray(
            data=img,
            dims=["band", "lat", "lon"],
            coords=dict(
                lon=(["lon"], lon),
                lat=(["lat"], lat),
                time=i,
                band=np.arange(img.shape[0])
            ),
            attrs=dict(
                description="OPERA DSWx B01",
                units=None,
            ),
        )
        da.rio.write_crs(crs, inplace=True)

        dataset_list.append(da)
    return xr.concat(dataset_list, dim='time').squeeze()