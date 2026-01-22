import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs


def plot_static(da: xr.DataArray):
    """
    Generate a publication-quality static plot using Matplotlib and Cartopy.

    Parameters
    ----------
    da : xarray.DataArray
        The geospatial data to plot. Must have latitude and longitude coordinates.

    Returns
    -------
    matplotlib.figure.Figure
        The generated figure object.
    """
    fig = plt.figure(figsize=(12, 8))
    # Aero Protocol: Mandatory projection in axes
    ax = plt.axes(projection=ccrs.PlateCarree())

    # Aero Protocol: Mandatory transform in plot calls
    da.plot(
        ax=ax,
        transform=ccrs.PlateCarree(),
        x="longitude",
        y="latitude",
        cmap="viridis",
        robust=True,
    )

    ax.coastlines()
    ax.gridlines(draw_labels=True)

    title = f"{da.attrs.get('fullName', da.name)}"
    plt.title(title)

    return fig


def plot_interactive(da: xr.DataArray):
    """
    Generate an exploratory interactive plot using hvPlot.

    Parameters
    ----------
    da : xarray.DataArray
        The geospatial data to plot.

    Returns
    -------
    holoviews.DynamicMap
        The interactive plot object.
    """
    import hvplot.xarray  # noqa

    # Aero Protocol: rasterize=True for large grids
    return da.hvplot.quadmesh(
        x="longitude",
        y="latitude",
        rasterize=True,
        geo=True,
        tiles="OSM",
        cmap="viridis",
    )
