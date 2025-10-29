import pytest
import hashlib
import grib2io
import numpy as np

def test_open_class_attrs(request):
    data = request.config.rootdir / 'tests' / 'input_data'
    g = grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f024')

    # Test attributes of the open class
    assert not g.closed
    assert g.current_message == 0
    assert g.messages == 743
    assert g.size == 45663524

    # Test index file stuff
    if g.save_index and g.use_index:
        assert g.indexfile is not None

    # Test variables property
    variables_hash_expected = 'c3bea231411082822877912aac45bab4b45a3941'
    variables_hash = hashlib.sha1(''.join([i for i in g.variables]).encode('ascii')).hexdigest()
    assert variables_hash == variables_hash_expected

    # Test levels property
    levels_hash_expected = '79263dc9bf3dac5cefdc3a06b6c70612350d0dd1'
    levels_hash = hashlib.sha1(''.join([i for i in g.levels]).encode('ascii')).hexdigest()
    assert levels_hash == levels_hash_expected

    # Test close file
    g.close()
    assert g.closed
