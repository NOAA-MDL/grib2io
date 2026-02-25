import sys
from unittest.mock import MagicMock

# Mock grib2io and g2clib since they are not installed
sys.modules['grib2io.g2clib'] = MagicMock()
sys.modules['grib2io.tables'] = MagicMock()

# Now we can import templates from src
sys.path.insert(0, 'src')
from grib2io import templates

def test_pdt76():
    # section4 = [numcoord, pdtnum, *pdt]
    # For PDT 76, we expect pdt to have 10 elements before constituentType?
    # Octet 10-22 (9 elements), 23-24 (1), 25 (1)
    # Total 11 elements in pdt.
    pdt = [0] * 11
    pdt[9] = 123 # Constituent Type at index 9 in pdt
    pdt[10] = 1 # Source/Sink at index 10 in pdt

    section4 = np.array([0, 76] + pdt, dtype=np.int64)

    class MockMsg:
        def __init__(self):
            self.section4 = section4
            self.pdtn = 76
            self._isNDFD = False

    msg = MockMsg()

    # Mock tables.get_value_from_table to return something for constituentType
    import grib2io.tables
    grib2io.tables.get_value_from_table.side_effect = lambda v, t: f"val_{v}_table_{t}"

    ct = templates.ConstituentType()
    val_ct = ct.__get__(msg)
    print(f"PDT 76 ConstituentType value: {val_ct.value}")
    assert val_ct.value == 123

    ss = templates.SourceSinkIndicator()
    val_ss = ss.__get__(msg)
    print(f"PDT 76 SourceSinkIndicator value: {val_ss.value}")
    assert val_ss.value == 1

import numpy as np
if __name__ == '__main__':
    try:
        test_pdt76()
        print("Verification successful!")
    except Exception as e:
        print(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
