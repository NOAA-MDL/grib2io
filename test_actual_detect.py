import sys
import os

sys.path.insert(0, os.path.abspath("src"))
from grib2io.xarray_backend import GribBackendEntrypoint
from xarray.backends.plugins import detect_parameters

try:
    params = detect_parameters(GribBackendEntrypoint.open_dataset)
    print(f"Params: {params}")
except TypeError as e:
    print(f"Caught TypeError: {e}")
except Exception as e:
    print(f"Caught Exception: {type(e).__name__}: {e}")
