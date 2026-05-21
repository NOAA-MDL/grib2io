import grib2io, warnings, xarray as xr, icechunk, tempfile, os
warnings.filterwarnings('ignore')
from grib2io.kerchunk import ReferenceGenerator
from grib2io.icechunk import IcechunkWriter

s3_url = 's3://noaa-gfs-bdp-pds/gfs.20240501/00/atmos/gfs.t00z.pgrb2.0p25.f000'
manifest = ReferenceGenerator(s3_url, storage_options={'anon': True}).generate()

store_path = tempfile.mkdtemp() + "/gfs"
writer = IcechunkWriter(store_path)
writer.write(manifest)
writer.commit("GFS 2024-05-01 00Z f000")
print("written + committed")

session = writer.get_readonly_session()
ds = xr.open_zarr(session.store, consolidated=False)
print("opened ds, vars:", len(ds.data_vars))

data = ds.TMP.isel(valid_time=0, isobaric_surface=0, y=slice(100,105), x=slice(100,105)).compute()
print("loaded shape:", data.shape)
print("min/max:", round(float(data.min()),2), round(float(data.max()),2))
print("SUCCESS")
