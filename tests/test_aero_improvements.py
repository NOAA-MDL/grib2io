import pytest
import numpy as np
import pandas as pd
import xarray as xr
from grib2io.templates import Grib2Metadata
import grib2io.templates

def test_constituent_type_descriptor():
    # PDTN 40
    section4 = np.zeros(20, dtype=np.int64)
    section4[1] = 40
    section4[9+2] = 0 # Ozone

    class MockMsg:
        def __init__(self):
            self.section4 = section4
            self.pdtn = 40

    msg = MockMsg()
    desc = grib2io.templates.ConstituentType()
    val = desc.__get__(msg)
    assert val.value == 0
    assert "Ozone" in val.definition

def test_surface_attributes_shift_pdt40():
    # PDTN 40 surface attributes are shifted by +1
    section4 = np.zeros(20, dtype=np.int64)
    section4[1] = 40
    section4[10+2] = 1 # Ground or Water Surface

    class MockMsg:
        def __init__(self):
            self.section4 = section4
            self.pdtn = 40

    msg = MockMsg()
    desc = grib2io.templates.TypeOfFirstFixedSurface()
    val = desc.__get__(msg)
    assert val.value == 1
    assert "Ground or Water Surface" in val.definition

def test_ensemble_attributes_shift_pdt41():
    # PDTN 41 ensemble attributes are shifted by +1 relative to PDTN 1
    section4 = np.zeros(30, dtype=np.int64)
    section4[1] = 41
    section4[16+2] = 2 # Negatively Perturbed Forecast

    class MockMsg:
        def __init__(self):
            self.section4 = section4
            self.pdtn = 41

    msg = MockMsg()
    desc = grib2io.templates.TypeOfEnsembleForecast()
    val = desc.__get__(msg)
    assert val.value == 2
    assert "Negatively Perturbed" in val.definition

def test_interval_attributes_shift_pdt42():
    # PDTN 42 interval attributes are shifted by +1 relative to PDTN 8
    section4 = np.zeros(40, dtype=np.int64)
    section4[1] = 42
    section4[24+2] = 0 # Average

    class MockMsg:
        def __init__(self):
            self.section4 = section4
            self.pdtn = 42

    msg = MockMsg()
    desc = grib2io.templates.StatisticalProcess()
    val = desc.__get__(msg)
    assert val.value == 0
    assert val.definition == "Average"

def test_aero_protocol_compliance():
    """
    Verify that scientific provenance (history) is appended correctly.
    """
    ds = xr.Dataset(attrs={'history': '2020-01-01 00:00:00 UTC: Original\n'})
    from grib2io.xarray_backend import parse_data_model

    # Mock data model parsing that adds history
    ds_new = parse_data_model(ds, 'nws-viz')

    assert 'Normalized to nws-viz data model' in ds_new.attrs['history']
    assert 'Original' in ds_new.attrs['history']
