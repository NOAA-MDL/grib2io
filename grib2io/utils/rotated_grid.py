"""
Tools for working with Rotated Lat/Lon Grids.
"""

import math
import numpy as np

def rotated_grid_transform(lats, lons, lat_sp, lon_sp, option=2):
    """
    Construct latitudes for a Gaussian grid.

    Parameters
    ----------

    **`lats : array_like`**:

    Input latitudes in degrees.
    
    **`lats : array_like`**:

    Input longitudes in degrees.

    **`lat_sp : float`**:

    Latitude of the Southern Pole.

    **`lon_sp : float`**:

    Longitude of the Southern Pole.

    **`option : int`**:

    Transform regular to rotated (1) or rotated to regular (2) [DEFAULT].

    Returns
    -------
    
    Sequence of transformed latitude, longitude in degrees.
    """

    # Convert lats and lons degress to radians
    lons = (lons*math.pi) / 180.0
    lats = (lats*math.pi) / 180.0

    theta = 90.0 + lat_sp # Rotation around y-axis
    phi = lon_sp # Rotation around z-axis

    # Convert to radians
    theta = (theta*math.pi) / 180.0
    phi = (phi*math.pi) / 180.0

    # Convert from spherical to cartesian coordinates
    x = np.cos(lons)*np.cos(lats)
    y = np.sin(lons)*np.cos(lats)
    z = np.sin(lats)

    if option == 1: # Regular -> Rotated

        x_new = np.cos(theta)*np.cos(phi)*x + np.cos(theta)*np.sin(phi)*y + np.sin(theta)*z
        y_new = -np.sin(phi)*x + np.cos(phi)*y
        z_new = -np.sin(theta)*np.cos(phi)*x - np.sin(theta)*np.sin(phi)*y + np.cos(theta)*z

    elif option == 2:  # Rotated -> Regular

        phi = -phi
        theta = -theta

        x_new = np.cos(theta)*np.cos(phi)*x + np.sin(phi)*y + np.sin(theta)*np.cos(phi)*z
        y_new = -np.cos(theta)*np.sin(phi)*x + np.cos(phi)*y - np.sin(theta)*np.sin(phi)*z
        z_new = -np.sin(theta)*x + np.cos(theta)*z

    # Convert cartesian back to spherical coordinates
    lons_new = np.arctan2(y_new,x_new)
    lats_new = np.arcsin(z_new)

    # Convert radians back to degrees
    lons_new = (lons_new*180.0) / math.pi # Convert radians back to degrees
    lats_new = (lats_new*180.0) / math.pi

    return lats_new, lons_new
