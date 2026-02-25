import sys
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import xarray as xr
import datetime

# Mock grib2io and its extensions
mock_g2clib = MagicMock()
mock_g2clib.__version__ = 'mock'
sys.modules['grib2io.g2clib'] = mock_g2clib
sys.modules['grib2io.iplib'] = MagicMock()
sys.modules['grib2io.redtoreg'] = MagicMock()

# Mock _grib2io carefully
mock_grib2io_core = MagicMock()
sys.modules['grib2io._grib2io'] = mock_grib2io_core

# Import from src
sys.path.insert(0, 'src')
from grib2io import tables, templates, xarray_backend

class TestAeroImprovements(unittest.TestCase):
    def test_chemical_shortname_generation(self):
        # Mock a message for O3 mass mixing ratio
        msg = MagicMock()
        msg.constituentType.value = 0 # Ozone
        msg.parameterNumber = 2 # Mass Mixing Ratio
        msg.typeOfFirstFixedSurface.value = 1 # Surface
        msg.scaledValueOfFirstFixedSurface = 0
        msg.sourceSinkIndicator = None

        # We need to ensure tables.get_table('4.230') returns what we expect
        # tables.get_table is already mocked via the modules mock? No.

        with patch('grib2io.tables.get_table') as mock_get_table:
            mock_get_table.side_effect = lambda t: {
                '4.230': {'0': ['Ozone', 'O3']},
                '4.233': {},
                'aerosol_level': {'1': 'sfc'},
                'aerosol_parameter': {'2': 'mr'}
            }.get(t, {})

            shortname = tables._build_chemical_shortname(msg)
            self.assertEqual(shortname, 'sfc_O3_mr')

    def test_aerosol_shortname_with_source_sink(self):
        msg = MagicMock()
        msg.typeOfAerosol.value = 62001 # Dust
        msg.parameterNumber = 2 # Mass mixing ratio
        msg.sourceSinkIndicator.value = 5 # Wild fires
        msg.typeOfFirstFixedSurface.value = 1 # Surface
        msg.scaledValueOfFirstFixedSurface = 0

        with patch('grib2io.tables.get_table') as mock_get_table:
            mock_get_table.side_effect = lambda t: {
                'aerosol_type': {'62001': 'du'},
                'aerosol_parameter': {'2': 'mmr'},
                'aerosol_level': {'1': 'sfc'}
            }.get(t, {})

            shortname = tables._build_aerosol_shortname(msg)
            self.assertEqual(shortname, 'sfc_du_mmr_ss5')

    def test_parse_data_model_nws_viz_chem(self):
        # Create a mock dataset with chemical constituent coordinate
        ds = xr.Dataset(
            data_vars={'o3mr': (('y', 'x'), np.random.rand(2, 2))},
            coords={
                'constituentType': ('constituentType', [0]),
                'sourceSinkIndicator': ('sourceSinkIndicator', [5])
            }
        )
        ds['o3mr'].attrs = {
            'units': 'kg kg-1',
            'typeOfFirstFixedSurface': ['Ground or Water Surface', 'unknown'],
            'typeOfSecondFixedSurface': ['Reserved', 'unknown'],
        }

        with patch('grib2io.tables.get_value_from_table') as mock_get_val, \
             patch('grib2io.tables.get_table') as mock_get_table:

            mock_get_table.return_value = {} # for shortname_to_cf
            mock_get_val.side_effect = lambda v, t: f"val_{v}"

            ds_parsed = xarray_backend.parse_data_model(ds, 'nws-viz')

            self.assertIn('constituent_type', ds_parsed.coords)
            self.assertIn('source_sink_indicator', ds_parsed.coords)
            self.assertEqual(ds_parsed['source_sink_indicator'].attrs['long_name'], 'Source/Sink Indicator')

    def test_optional_dask_rule(self):
        # Ensure parse_data_model works with both numpy and dask
        ds_numpy = xr.Dataset(
            data_vars={'var': (('y', 'x'), np.random.rand(2, 2))},
            coords={'constituentType': [0]}
        )
        ds_numpy['var'].attrs = {'units': 'kg kg-1', 'typeOfFirstFixedSurface': ['Surface', 'm']}

        ds_dask = ds_numpy.chunk({'y': 1})

        with patch('grib2io.tables.get_value_from_table') as mock_get_val, \
             patch('grib2io.tables.get_table') as mock_get_table:
            mock_get_table.return_value = {}
            mock_get_val.return_value = 'some_chem'

            res_numpy = xarray_backend.parse_data_model(ds_numpy, 'nws-viz')
            res_dask = xarray_backend.parse_data_model(ds_dask, 'nws-viz')

            self.assertFalse(res_numpy.chunks)
            self.assertTrue(res_dask.chunks)
            xr.testing.assert_allclose(res_numpy.compute(), res_dask.compute())

if __name__ == '__main__':
    unittest.main()
