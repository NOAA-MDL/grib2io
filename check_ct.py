import grib2io
import numpy as np

# Mock a message with PDT 40
section4 = np.zeros(20, dtype=np.int64)
section4[1] = 40 # PDTN
section4[2+13] = 123 # Should be constituentType if _key is 13
section4[2+9] = 456 # Should be constituentType if _key is 9

class MockMsg:
    def __init__(self):
        self.section4 = section4
        self.pdtn = 40
        self._isNDFD = False

from grib2io.templates import ConstituentType

ct = ConstituentType()
print(f"ConstituentType for PDT 40: {ct.__get__(MockMsg())}")
