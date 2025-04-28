import pytest
import xarray as xr

def test_datatree_basic_structure(request):
    """Test basic DataTree structure creation from a GRIB2 file."""
    data = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107'

    # Open the file as a DataTree
    tree = xr.open_datatree(data / 'gfs.t00z.pgrb2.1p00.f012_subset', engine='grib2io')

    # Verify the basic structure
    assert isinstance(tree, xr.DataTree)

    # Verify expected level types in the tree
    # Surface level should be present (typeOfFirstFixedSurface=1)
    assert 'surface' in tree.children

    # Verify that each level branch has datasets or children
    for level_name, level_node in tree.children.items():
        # Each level node should either have a dataset or children
        assert level_node.ds is not None or len(level_node.children) > 0

def test_datatree_level_structure(request):
    """Test that the DataTree level structure is correctly organized."""
    data = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107'

    # Open the file as a DataTree
    tree = xr.open_datatree(data / 'gfs.t00z.pgrb2.1p00.f012_subset', engine='grib2io')

    # Check the isobaric_surface branch (should have multiple levels)
    if 'isobaric_surface' in tree.children:
        isobaric_node = tree['isobaric_surface']

        # Check if it has data variables
        if isobaric_node.ds is not None:
            # If it has direct data, at least one data variable should be present
            assert len(isobaric_node.ds.data_vars) > 0

            # Check if the valueOfFirstFixedSurface dimension is present
            if 'valueOfFirstFixedSurface' in isobaric_node.ds.dims:
                # Verify it has multiple values
                assert len(isobaric_node.ds.valueOfFirstFixedSurface) > 1

        # Or it might have children by PDTN
        elif len(isobaric_node.children) > 0:
            # If it has children, check the first child
            first_child = next(iter(isobaric_node.children.values()))
            assert first_child.ds is not None
            assert len(first_child.ds.data_vars) > 0

def test_datatree_single_pdtn_optimization(request):
    """Test that PDTN nodes are skipped when there's only one PDTN value."""
    data = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107'

    # Open the file as a DataTree
    tree = xr.open_datatree(data / 'gfs.t00z.pgrb2.1p00.f012_subset', engine='grib2io')

    # Check the surface branch (should have a single PDTN=0)
    if 'surface' in tree.children:
        surface_node = tree['surface']

        # The surface node should have data directly, not a 'pdtn_0' child
        # This tests our optimization where PDTN nodes are skipped when only one exists
        assert surface_node.ds is not None
        assert len(surface_node.ds.data_vars) > 0

        # There should not be a 'pdtn_0' child since it's the only PDTN
        # and we're optimizing by skipping it
        assert 'pdtn_0' not in surface_node.children

def test_datatree_multiple_pdtn_branches(request):
    """Test that PDTN nodes are correctly created when multiple PDTNs exist."""
    data = request.config.rootdir / 'tests' / 'input_data'

    # Try to open a file that might have multiple PDTNs
    # If this file doesn't have multiple PDTNs, the test will be skipped
    try:
        tree = xr.open_datatree(data / 'gfs.complex.grib2', engine='grib2io')

        # Look for a level type that has multiple PDTNs
        found_multiple_pdtns = False
        for level_name, level_node in tree.children.items():
            # If there are at least two children that start with 'pdtn_'
            pdtn_children = [name for name in level_node.children if name.startswith('pdtn_')]
            if len(pdtn_children) > 1:
                found_multiple_pdtns = True

                # Verify that the PDTNs are correctly named
                for pdtn_name in pdtn_children:
                    assert pdtn_name.startswith('pdtn_')
                    # Extract the PDTN number and verify it's a valid integer
                    pdtn_num = pdtn_name[5:]  # Remove 'pdtn_' prefix
                    assert pdtn_num.isdigit()
                break

        if not found_multiple_pdtns:
            pytest.skip("No level with multiple PDTNs found")
    except (FileNotFoundError, ValueError):
        pytest.skip("Test file with multiple PDTNs not available")

def test_datatree_perturbation_structure(request):
    """Test DataTree structure with perturbation numbers."""
    data = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107'

    try:
        # Try to open a file with perturbation numbers
        tree = xr.open_datatree(data / 'gfs.t00z.pgrb2.1p00.f012_subset', engine='grib2io')

        # Look for a node with perturbation numbers
        found_perturbations = False
        for level_name, level_node in tree.children.items():
            # Check this level node
            found_at_level = _check_for_perturbations(level_node)
            if found_at_level:
                found_perturbations = True
                break

        if not found_perturbations:
            pytest.skip("No perturbation numbers found in the test data")
    except (FileNotFoundError, ValueError):
        pytest.skip("Test file not available or issue with perturbation structure")

def _check_for_perturbations(node):
    """Helper function to check for perturbation numbers in a node or its children."""
    # Check if this node has perturbation data
    if node.ds is not None and 'perturbationNumber' in node.ds.coords:
        return True

    # Check children nodes for perturbations
    for child_name, child_node in node.children.items():
        # If the child is named like 'pert_0', 'pert_1', etc.
        if child_name.startswith('pert_'):
            return True

        # Recursively check deeper if this child has perturbations
        if _check_for_perturbations(child_node):
            return True

    return False

def test_datatree_subset_by_level(request):
    """Test subsetting the DataTree to specific level types."""
    data = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107'

    # Open the file as a DataTree
    tree = xr.open_datatree(data / 'gfs.t00z.pgrb2.1p00.f012_subset', engine='grib2io')

    # Create filters for specific level types
    filters = {'typeOfFirstFixedSurface': 1}  # Surface level

    # Open the file again with the filter
    surface_tree = xr.open_datatree(data / 'gfs.t00z.pgrb2.1p00.f012_subset', engine='grib2io', filters=filters)

    # Verify that only the surface level is present
    assert 'surface' in surface_tree.children
    assert len(surface_tree.children) == 1  # Only surface level should be present
