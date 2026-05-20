import numpy as np


def snap_to_nearest_cell_center(grid_lats, grid_lons, point_lat, point_lon):
    """
    Snap the given point lat/lon to the nearest grid cell center.

    Parameters
    ----------
    grid_lats
        The latitude values for each cell in the grid.
    grid_lons
        The longitude values for each cell in the grid.
    point_lat
        Latitude of point to snap.
    point_lon
        Longitude of point to snap.

    Returns
    -------
    lat
        Latitude snapped to nearest cell center.
    lon
        Longitude snapped to nearest cell center.
    """
    snap_lat = np.abs(grid_lats - point_lat)
    snap_lon = np.abs(grid_lons - point_lon)
    max_idx = np.maximum(snap_lat, snap_lon)
    j, i = np.where(max_idx == np.min(max_idx))
    return np.array(grid_lats[j, i])[0], np.array(grid_lons[j, i])[0]


def verify_lat_lon_bounds(lats, lons):
    """
    Verify that the given latitude and longitude bounds are valid.

    Parameters
    ----------
    lats
        Latitude bounds.
    lons
        Longitude bounds.

    Returns
    -------
    None
    """
    if lats is not None:
        if len(lats) != 2:
            raise ValueError(
                f"The `lats` keyword should supply a two-item tuple or list of (southern lat, northern lat) boundaries instead of '{lats}'."
            )
        if lats[0] < -90 or lats[1] > 90:
            raise ValueError(
                f"The southern latitude boundary '{lats[0]}' and northern latitude boundary '{lats[1]}' must be between -90 and 90 degrees."
            )
        if lats[0] > lats[1]:
            raise ValueError(f"The southern latitude boundary '{lats[0]}' must be less than the northern latitude boundary '{lats[1]}'")
    if lons is not None:
        if len(lons) != 2:
            raise ValueError(
                f"The `lons` keyword should supply a two-item tuple or list of (western lon, eastern lon) boundaries instead of '{lons}'."
            )
        if lons[0] > lons[1]:
            raise ValueError(f"The western longitude boundary '{lons[0]}' must be less than the eastern longitude boundary '{lons[1]}'")
