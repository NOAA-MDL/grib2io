import pytest
import numpy as np
import grib2io

def test_from_bytes(request):
    file = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107' / 'gfs.t00z.pgrb2.1p00.f012_subset'
    
    with grib2io.open(file) as f:
        data_file = [msg.data for msg in f.read()]
        
    with open(file,'rb') as f:
        binary = f.read()
    with grib2io.open(binary) as f:
        data_binary = [msg.data for msg in f.read()]
        
    for from_file,from_binary in zip(data_file,data_binary):
        np.testing.assert_array_equal(from_file,from_binary)
        
