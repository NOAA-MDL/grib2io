import sys
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

# Mock low-level extensions
mock_g2clib = MagicMock()
mock_g2clib.__version__ = 'mock'
sys.modules['grib2io.g2clib'] = mock_g2clib
sys.modules['grib2io.iplib'] = MagicMock()
sys.modules['grib2io.redtoreg'] = MagicMock()

# Mock _grib2io to prevent loading logic but allow it to exist
sys.modules['grib2io._grib2io'] = MagicMock()

# Now we can import the tables module
sys.path.insert(0, 'src')
from grib2io import tables

class TestShortnameLogic(unittest.TestCase):
    def test_chemical_shortname(self):
        # Mock a message for O3 mass mixing ratio (constituentType 0, param 2)
        msg = MagicMock()
        msg.constituentType.value = 0
        msg.parameterNumber = 2
        msg.typeOfFirstFixedSurface.value = 1 # surface
        msg.scaledValueOfFirstFixedSurface = 0
        msg.sourceSinkIndicator = None

        with patch('grib2io.tables.get_table') as mock_get_table:
            mock_get_table.side_effect = lambda t: {
                '4.230': {'0': ['Ozone', 'O3']},
                '4.233': {},
                'aerosol_level': {'1': 'sfc'},
                'aerosol_parameter': {'2': 'mr'}
            }.get(t, {})

            shortname = tables._build_chemical_shortname(msg)
            self.assertEqual(shortname, 'sfc_O3_mr')

    def test_aerosol_shortname_source_sink(self):
        # Mock a message for Dust (62001) with Wildfire source (5)
        msg = MagicMock()
        msg.typeOfAerosol.value = 62001
        msg.parameterNumber = 2
        msg.typeOfFirstFixedSurface.value = 100 # isobaric
        msg.scaledValueOfFirstFixedSurface = 50000
        msg.sourceSinkIndicator.value = 5
        # Set attributes that might be checked
        msg.scaledValueOfFirstSize = 0
        msg.scaledValueOfFirstWavelength = 0

        with patch('grib2io.tables.get_table') as mock_get_table:
            mock_get_table.side_effect = lambda t: {
                'aerosol_type': {'62001': 'du'},
                'aerosol_parameter': {'2': 'mmr'},
                'aerosol_level': {'100': 'pres'}
            }.get(t, {})

            shortname = tables._build_aerosol_shortname(msg)
            # pres50000_du_mmr_ss5
            self.assertEqual(shortname, 'pres50000_du_mmr_ss5')

    def test_chemical_shortname_with_aero_table(self):
        # Test that chemical shortname also checks 4.233 (aerosol table) as requested
        msg = MagicMock()
        msg.constituentType.value = 62001 # Dust in aerosol table
        msg.parameterNumber = 2
        msg.typeOfFirstFixedSurface.value = 1
        msg.scaledValueOfFirstFixedSurface = 0
        msg.sourceSinkIndicator = None

        with patch('grib2io.tables.get_table') as mock_get_table:
            mock_get_table.side_effect = lambda t: {
                '4.230': {}, # Not in chemical table
                '4.233': {'62001': ['Dust', 'du']}, # but in aerosol table
                'aerosol_level': {'1': 'sfc'},
                'aerosol_parameter': {'2': 'mr'}
            }.get(t, {})

            shortname = tables._build_chemical_shortname(msg)
            self.assertEqual(shortname, 'sfc_du_mr')

if __name__ == '__main__':
    unittest.main()
