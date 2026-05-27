import pandas as pd

# Data extracted from the markdown tables
# taken from CF conventions standard names table
# https://cfconventions.org/Data/cf-standard-names/current/build/cf-standard-name-table.html
data = [
    {
        "NCEP GRIB Variable": "ABSV",
        "NCEP Description": "Absolute Vorticity",
        "CF Standard Name": "atmosphere_absolute_vorticity",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "DEN",
        "NCEP Description": "Density",
        "CF Standard Name": "air_density",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "DEPR",
        "NCEP Description": "Dew Point Depression",
        "CF Standard Name": "dew_point_depression",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "DPT",
        "NCEP Description": "Dew Point Temperature",
        "CF Standard Name": "dew_point_temperature",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "DZDT",
        "NCEP Description": "Vertical Velocity (Geometric)",
        "CF Standard Name": "upward_air_velocity",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "EPOT",
        "NCEP Description": "Equivalent Potential Temperature",
        "CF Standard Name": "equivalent_potential_temperature",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "GP",
        "NCEP Description": "Geopotential",
        "CF Standard Name": "geopotential",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "HGT",
        "NCEP Description": "Geopotential Height",
        "CF Standard Name": "geopotential_height",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "DIST",
        "NCEP Description": "Geometric Height",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "LAPR",
        "NCEP Description": "Lapse Rate",
        "CF Standard Name": "air_temperature_lapse_rate",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "MIXR",
        "NCEP Description": "Humidity Mixing Ratio",
        "CF Standard Name": "humidity_mixing_ratio",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "POT",
        "NCEP Description": "Potential Temperature",
        "CF Standard Name": "air_potential_temperature",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "PRES",
        "NCEP Description": "Pressure",
        "CF Standard Name": "air_pressure",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "PRMSL",
        "NCEP Description": "Pressure Reduced to MSL",
        "CF Standard Name": "air_pressure_at_mean_sea_level",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "PTEND",
        "NCEP Description": "Pressure Tendency",
        "CF Standard Name": "tendency_of_air_pressure",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "PVORT",
        "NCEP Description": "Potential Vorticity",
        "CF Standard Name": "atmosphere_potential_vorticity",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "RELV",
        "NCEP Description": "Relative Vorticity",
        "CF Standard Name": "atmosphere_relative_vorticity",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "RH",
        "NCEP Description": "Relative Humidity",
        "CF Standard Name": "relative_humidity",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SPFH",
        "NCEP Description": "Specific Humidity",
        "CF Standard Name": "specific_humidity",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "STRM",
        "NCEP Description": "Stream Function",
        "CF Standard Name": "atmosphere_streamfunction",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "TMAX",
        "NCEP Description": "Maximum Temperature",
        "CF Standard Name": "air_temperature",
        "CF Cell Method": "time: maximum",
    },
    {
        "NCEP GRIB Variable": "TMIN",
        "NCEP Description": "Minimum Temperature",
        "CF Standard Name": "air_temperature",
        "CF Cell Method": "time: minimum",
    },
    {
        "NCEP GRIB Variable": "MAXRH",
        "NCEP Description": "Maximum Relative Humidity",
        "CF Standard Name": "relative_humidity",
        "CF Cell Method": "time: maximum",
    },
    {
        "NCEP GRIB Variable": "MINRH",
        "NCEP Description": "Minimum Relative Humidity",
        "CF Standard Name": "relative_humidity",
        "CF Cell Method": "time: minimum",
    },
    {
        "NCEP GRIB Variable": "TMP",
        "NCEP Description": "Temperature",
        "CF Standard Name": "air_temperature",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "CAPE",
        "NCEP Description": "Convective Available Potential Energy",
        "CF Standard Name": "atmosphere_convective_available_potential_energy",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "CEIL",
        "NCEP Description": "Ceiling Height",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "ICSEV",
        "NCEP Description": "Icing Severity",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "ICPRB",
        "NCEP Description": "Icing Probability",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SIPD",
        "NCEP Description": "Supercooled Large Droplet Icing",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "ELLINX",
        "NCEP Description": "Ellrod Index",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "TURB",
        "NCEP Description": "Turbulence",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "CLOUDBASE",
        "NCEP Description": "CLoud Base Height",
        "CF Standard Name": "cloud_base_altitude",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "DRYTPROB",
        "NCEP Description": "Dry Thunderstorm Probability",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "TSTM",
        "NCEP Description": "Thunderstorm Probability",
        "CF Standard Name": "thunderstorm_probability",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "TRWSPD",
        "NCEP Description": "Transport Wind Speed",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "TRWDIR",
        "NCEP Description": "Transport Wind Direction",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "VRATE",
        "NCEP Description": "Ventilation Rate",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "RETOP",
        "NCEP Description": "Echo Top",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "MIXHT",
        "NCEP Description": "Mixing Height",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "PWTHER",
        "NCEP Description": "Predominant Weather",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "MAXREF",
        "NCEP Description": "Hourly Maximum of Simulated Reflectivity",
        "CF Standard Name": "equivalent_reflectivity_factor",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SNOWLR",
        "NCEP Description": "Snow Liquid Ratio",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SNOWLVL",
        "NCEP Description": "Snow Level",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "ASNOW",
        "NCEP Description": "Accumulated Snow",
        "CF Standard Name": "thickness_of_snowfall_amount",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "FICEAC",
        "NCEP Description": "Flat Ice Accumulation (FRAM)",
        "CF Standard Name": "unknown",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "APTMP",
        "NCEP Description": "Apparent Temperature",
        "CF Standard Name": "apparent_air_temperature",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "UGRD",
        "NCEP Description": "u-component of Wind",
        "CF Standard Name": "eastward_wind",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "VAPP",
        "NCEP Description": "Vapor Pressure",
        "CF Standard Name": "water_vapor_partial_pressure_in_air",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "VGRD",
        "NCEP Description": "v-component of Wind",
        "CF Standard Name": "northward_wind",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "VPOT",
        "NCEP Description": "Velocity Potential",
        "CF Standard Name": "atmosphere_velocity_potential",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "VTMP",
        "NCEP Description": "Virtual Temperature",
        "CF Standard Name": "virtual_temperature",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "VVEL",
        "NCEP Description": "Vertical Velocity (Pressure)",
        "CF Standard Name": "lagrangian_tendency_of_air_pressure",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "VUCSH",
        "NCEP Description": "Vertical u-component Shear",
        "CF Standard Name": "eastward_wind_shear",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "VVCSH",
        "NCEP Description": "Vertical v-component Shear",
        "CF Standard Name": "northward_wind_shear",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "WDIR",
        "NCEP Description": "Wind Direction",
        "CF Standard Name": "wind_from_direction",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "WIND",
        "NCEP Description": "Wind Speed",
        "CF Standard Name": "wind_speed",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "GUST",
        "NCEP Description": "Wind Gust Speed",
        "CF Standard Name": "wind_speed_of_gust",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "WTMP",
        "NCEP Description": "Water Temperature",
        "CF Standard Name": "sea_water_temperature",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "ACPCP",
        "NCEP Description": "Convective Precipitation",
        "CF Standard Name": "lwe_thickness_of_convective_precipitation_amount",
        "CF Cell Method": "time: sum",
    },
    {
        "NCEP GRIB Variable": "PTYPE",
        "NCEP Description": "Precipitation Type",
        "CF Standard Name": "predominant_precipitation_type_at_surface",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "APCP",
        "NCEP Description": "Total Precipitation",
        "CF Standard Name": "lwe_thickness_of_precipitation_amount",
        "CF Cell Method": "time: sum",
    },
    {
        "NCEP GRIB Variable": "CICE",
        "NCEP Description": "Cloud Ice",
        "CF Standard Name": "atmosphere_cloud_ice_content",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "CWAT",
        "NCEP Description": "Cloud Water",
        "CF Standard Name": "atmosphere_cloud_condensate_content",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "EVP",
        "NCEP Description": "Evaporation",
        "CF Standard Name": "water_evaporation_flux",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "HCDC",
        "NCEP Description": "High Cloud Cover",
        "CF Standard Name": "high_type_cloud_area_fraction",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "LCDC",
        "NCEP Description": "Low Cloud Cover",
        "CF Standard Name": "low_type_cloud_area_fraction",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "MCDC",
        "NCEP Description": "Medium Cloud Cover",
        "CF Standard Name": "medium_type_cloud_area_fraction",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "NCPCP",
        "NCEP Description": "Large Scale Precipitation",
        "CF Standard Name": "lwe_thickness_of_large_scale_precipitation_amount",
        "CF Cell Method": "time: sum",
    },
    {
        "NCEP GRIB Variable": "PRATE",
        "NCEP Description": "Precipitation Rate",
        "CF Standard Name": "precipitation_flux",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "PWAT",
        "NCEP Description": "Precipitable Water",
        "CF Standard Name": "atmosphere_water_vapor_content",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SNOC",
        "NCEP Description": "Convective Snow",
        "CF Standard Name": "lwe_thickness_of_convective_snowfall_amount",
        "CF Cell Method": "time: sum",
    },
    {
        "NCEP GRIB Variable": "SNOL",
        "NCEP Description": "Large Scale Snow",
        "CF Standard Name": "lwe_thickness_of_large_scale_snowfall_amount",
        "CF Cell Method": "time: sum",
    },
    {
        "NCEP GRIB Variable": "TCDC",
        "NCEP Description": "Total Cloud Cover",
        "CF Standard Name": "cloud_area_fraction",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "WEASD",
        "NCEP Description": "Water Equiv. of Accum. Snow Depth",
        "CF Standard Name": "lwe_thickness_of_surface_snow_amount",
        "CF Cell Method": "time: sum",
    },
    {
        "NCEP GRIB Variable": "LAND",
        "NCEP Description": "Land Cover (1=land, 0=sea)",
        "CF Standard Name": "land_area_fraction",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SFCR",
        "NCEP Description": "Surface Roughness",
        "CF Standard Name": "surface_roughness_length",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SNOD",
        "NCEP Description": "Snow Depth",
        "CF Standard Name": "surface_snow_thickness",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SNOM",
        "NCEP Description": "Snow Melt",
        "CF Standard Name": "surface_snow_melt_flux",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "SOILM",
        "NCEP Description": "Soil Moisture Content",
        "CF Standard Name": "soil_moisture_content",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "TSOIL",
        "NCEP Description": "Soil Temperature",
        "CF Standard Name": "soil_temperature",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "VEG",
        "NCEP Description": "Vegetation Cover",
        "CF Standard Name": "vegetation_area_fraction",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "WATR",
        "NCEP Description": "Water Runoff",
        "CF Standard Name": "runoff_flux",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "ALBDO",
        "NCEP Description": "Albedo",
        "CF Standard Name": "surface_albedo",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "DLWRF",
        "NCEP Description": "Downward Long-Wave Rad. Flux",
        "CF Standard Name": "surface_downwelling_longwave_flux_in_air",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "DSWRF",
        "NCEP Description": "Downward Short-Wave Rad. Flux",
        "CF Standard Name": "surface_downwelling_shortwave_flux_in_air",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "GRAD",
        "NCEP Description": "Global Radiation Flux",
        "CF Standard Name": "surface_downwelling_shortwave_flux_in_air",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "LHTFL",
        "NCEP Description": "Latent Heat Net Flux",
        "CF Standard Name": "surface_upward_latent_heat_flux",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "NLWRS",
        "NCEP Description": "Net Long-Wave Rad. Flux (Surface)",
        "CF Standard Name": "surface_net_downward_longwave_flux",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "NLWRT",
        "NCEP Description": "Net Long-Wave Rad. Flux (Top)",
        "CF Standard Name": "toa_net_downward_longwave_flux",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "NSWRS",
        "NCEP Description": "Net Short-Wave Rad. Flux (Surface)",
        "CF Standard Name": "surface_net_downward_shortwave_flux",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "NSWRT",
        "NCEP Description": "Net Short-Wave Rad. Flux (Top)",
        "CF Standard Name": "toa_net_downward_shortwave_flux",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "SHTFL",
        "NCEP Description": "Sensible Heat Net Flux",
        "CF Standard Name": "surface_upward_sensible_heat_flux",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "ULWRF",
        "NCEP Description": "Upward Long-Wave Rad. Flux",
        "CF Standard Name": "surface_upwelling_longwave_flux_in_air",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "USWRF",
        "NCEP Description": "Upward Short-Wave Rad. Flux",
        "CF Standard Name": "surface_upwelling_shortwave_flux_in_air",
        "CF Cell Method": "time: mean",
    },
    {
        "NCEP GRIB Variable": "DSLM",
        "NCEP Description": "Deviation of Sea Level from Mean",
        "CF Standard Name": "sea_surface_height_above_sea_level",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "HTSGW",
        "NCEP Description": "Sig. Height of Combined Wind Waves & Swell",
        "CF Standard Name": "sea_surface_wave_significant_height",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "ICEC",
        "NCEP Description": "Ice Cover",
        "CF Standard Name": "sea_ice_area_fraction",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "ICETK",
        "NCEP Description": "Ice Thickness",
        "CF Standard Name": "sea_ice_thickness",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SALTY",
        "NCEP Description": "Salinity",
        "CF Standard Name": "sea_water_salinity",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SWELL",
        "NCEP Description": "Significant Height of Swell Waves",
        "CF Standard Name": "sea_surface_swell_wave_significant_height",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SWDIR",
        "NCEP Description": "Direction of Swell Waves",
        "CF Standard Name": "sea_surface_swell_wave_from_direction",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "SWPER",
        "NCEP Description": "Mean Period of Swell Waves",
        "CF Standard Name": "sea_surface_swell_wave_period",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "UOGRD",
        "NCEP Description": "u-component of Current",
        "CF Standard Name": "eastward_sea_water_velocity",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "VOGRD",
        "NCEP Description": "v-component of Current",
        "CF Standard Name": "northward_sea_water_velocity",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "WTMP",
        "NCEP Description": "Water Temperature",
        "CF Standard Name": "sea_water_temperature",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "WVDIR",
        "NCEP Description": "Direction of Wind Waves",
        "CF Standard Name": "sea_surface_wind_wave_from_direction",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "WVHGT",
        "NCEP Description": "Significant Height of Wind Waves",
        "CF Standard Name": "sea_surface_wind_wave_significant_height",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "WVPER",
        "NCEP Description": "Mean Period of Wind Waves",
        "CF Standard Name": "sea_surface_wind_wave_period",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "TOZNE",
        "NCEP Description": "Total Ozone",
        "CF Standard Name": "atmosphere_mole_content_of_ozone",
        "CF Cell Method": None,
    },
    {
        "NCEP GRIB Variable": "VIS",
        "NCEP Description": "Visibility",
        "CF Standard Name": "visibility_in_air",
        "CF Cell Method": None,
    },
]

# Create the pandas DataFrame
# For empty 'CF Cell Method' cells, we use None, which pandas converts to NaN (Not a Number)
cf_standard_names = pd.DataFrame(data)

# A dictionary to map GRIB2 Code Table 4.7 (Derived Forecast)
# to their equivalent CF Convention cell_methods.
grib_derived_to_cf_methods = {
    0: {
        "grib_meaning": "Unweighted Mean of All Members",
        "cf_cell_methods": "time: mean",
    },
    1: {
        "grib_meaning": "Weighted Mean of All Members",
        "cf_cell_methods": "time: mean (comment: weighted)",
    },
    2: {
        "grib_meaning": "Standard Deviation with respect to Cluster Mean",
        "cf_cell_methods": "time: standard_deviation (comment: with respect to cluster mean)",
    },
    3: {
        "grib_meaning": "Standard Deviation with respect to Cluster Mean, Normalized",
        "cf_cell_methods": "time: standard_deviation (comment: normalized)",
    },
    4: {
        "grib_meaning": "Spread of All Members",
        "cf_cell_methods": "time: standard_deviation",
    },
    5: {
        "grib_meaning": "Large Anomaly Index of All Members",
        "cf_cell_methods": None,
    },  # No direct CF equivalent
    6: {
        "grib_meaning": "Unweighted Mean of the Cluster Members",
        "cf_cell_methods": "time: mean (comment: of cluster members)",
    },
    7: {
        "grib_meaning": "Interquartile Range",
        "cf_cell_methods": "time: range (comment: interquartile)",
    },
    8: {
        "grib_meaning": "Minimum Of All Ensemble Members",
        "cf_cell_methods": "time: minimum",
    },
    9: {
        "grib_meaning": "Maximum Of All Ensemble Members",
        "cf_cell_methods": "time: maximum",
    },
    10: {
        "grib_meaning": "Variance of all ensemble members",
        "cf_cell_methods": "time: variance",
    },
    192: {
        "grib_meaning": "Unweighted Mode of All Members",
        "cf_cell_methods": "time: mode",
    },
    193: {
        "grib_meaning": "Percentile value (10%) of All Members",
        "cf_cell_methods": None,
    },  # No direct CF equivalent
    194: {
        "grib_meaning": "Percentile value (50%) of All Members",
        "cf_cell_methods": "time: median",
    },
    195: {
        "grib_meaning": "Percentile value (90%) of All Members",
        "cf_cell_methods": None,
    },  # No direct CF equivalent
    197: {
        "grib_meaning": "Climate Percentile",
        "cf_cell_methods": None,
    },  # No direct CF equivalent
    198: {
        "grib_meaning": "Deviation of Ensemble Mean from Daily Climatology",
        "cf_cell_methods": None,
    },  # Not a cell method
    199: {
        "grib_meaning": "Extreme Forecast Index",
        "cf_cell_methods": None,
    },  # No direct CF equivalent
    200: {"grib_meaning": "Equally Weighted Mean", "cf_cell_methods": "time: mean"},
    201: {
        "grib_meaning": "Percentile value (5%) of All Members",
        "cf_cell_methods": None,
    },  # No direct CF equivalent
    202: {
        "grib_meaning": "Percentile value (25%) of All Members",
        "cf_cell_methods": None,
    },  # No direct CF equivalent
    203: {
        "grib_meaning": "Percentile value (75%) of All Members",
        "cf_cell_methods": None,
    },  # No direct CF equivalent
    204: {
        "grib_meaning": "Percentile value (95%) of All Members",
        "cf_cell_methods": None,
    },  # No direct CF equivalent
    255: {
        "grib_meaning": "Missing",
        "cf_cell_methods": None,
    },  # Represents a missing value
}


def add_cf_metadata(ds):
    # type: (xarray.Dataset,) -> xarray.Dataset
    """Convert grib2io metadata to CF metadata.

    Includes metadata from the Climate and Forecast (CF) conventions,
    the Attribute Conventions for Data Discovery (ACDD) and some in
    neither but recommended by the NCEI netCDF templates.

    Parameters
    ----------
    ds : xr.Dataset
        The dataset on which to convert metadata.
        
    Returns
    -------
    xr.Dataset
        The same dataset, with more CF metadata
    """
    # Expand CRS metadata
    import pyproj
    ds_crs = pyproj.CRS.from_wkt(ds.attrs["crs_wkt"])
    ds.coords["grid_mapping"] = ((), -1, ds_crs.to_cf())
    if ds_crs.ellipsoid.inverse_flattening == 0.0:
        # Data was calculated on a sphere
        ds.coords["grid_mapping"].attrs["earth_radius"] = ds_crs.ellipsoid.semi_major_metre
    
    # Add dimension coords
    if ds.coords["grid_mapping"].attrs["grid_mapping_name"] == "latitude_longitude":
        # lat-lon CRS
        ds.coords["y"] = (
            ("y",),
            ds.coords["latitude"].isel(x=0).values,
            ds.coords["latitude"].attrs,
        )
        ds.coords["y"].attrs.update({"axis": "Y", "long_name": "latitude"})
        ds.coords["x"] = (
            ("x",),
            ds.coords["longitude"].isel(y=0).values,
            ds.coords["longitude"].attrs
        )
        ds.coords["x"].attrs.update({"axis": "X", "long_name": "longitude"})
        ds.attrs.update(
            {
                "geospatial_lat_min": ds.coords["y"].min().values,
                "geospatial_lat_max": ds.coords["y"].max().values,
                "geospatial_lon_min": ds.coords["x"].min().values,
                "geospatial_lon_max": ds.coords["x"].max().values
            }
        )
    else:
        _logger.warn("Unrecognized CRS: no x and y coordinates added")

    # Add general metadata common to all variables
    for name, var in ds.data_vars.items():
        var.attrs["coverage_content_type"] = "modelResult"
        # Add CRS metadata.  Assumes all grib variables are 2D
        if "crs_wkt" not in var.attrs or var.attrs["crs_wkt"] == ds.attrs["crs_wkt"]:
            var.attrs["grid_mapping"] = "grid_mapping"
        else:
            var_crs = pyproj.CRS.from_wkt(var.attrs["crs_wkt"])
            var_crs_name = f"{var:s}_grid_mapping"
            ds.coords[var_crs_name] = ((), -1, var_crs.to_cf())
    for name, var in ds.coords.items():
        if not name.endswith("grid_mapping"):
            var.attrs["coverage_content_type"] = "coordinate"
        else:
            var.attrs["coverage_content_type"] = "referenceInformation"

    # Get metadata from filesystem
    file_metadata = os.stat(ds.encoding)
    file_ctime = datetime.datetime.fromtimestamp(file_metadata.st_ctime)
    file_mtime = datetime.datetime.fromtimestamp(file_metadata.st_mtime)
    ds.attrs.update(
        {
            "Conventions": "CF-1.11, ACDD-1.3",
            "date_modified": file_mtime.isoformat(),
            "date_metadata_modified": _NOW.isoformat(),
            "history": f"{_NOW:%c}: Grib 2 metadata converted to CF\n{file_ctime:%c}: Grib 2 file written or downloaded",
            "standard_name_vocabulary": "CF Standard Name Table v93",
            "ncei_template_version": "NCEI_NetCDF_Grid_Template_v2.0",
            "featureType": "grid",
            "cdm_data_type": "Grid",
        }
    )

    # Add standard_names
    std_name_df = cf_standard_names.set_index("NCEP GRIB Variable")
    for name, var in ds.variables.items():
        try:
            var_metadata = std_name_df.loc[name, :]
        except KeyError:
            pass
        else:
            var.attrs.update(
                {
                    "standard_name": var_metadata["CF Standard Name"].values,
                    "long_name": var_metadata["NCEP Description"].values,
                }
            )
            cell_method = var_metadata["CF Cell Method"].values
            if cell_method is not None:
                var.attrs["cell_methods"] = cell_method
        if name in ("refDate", "validDate"):
            # Apparently deprecated in CF 1.13 in favor of implying
            # leap second handling by calendar selectoin
            var.attrs["units_metadata"] = "leap_seconds: unknown"
            if name == "validDate":
                coverage_start = var.min().values
                ds.attrs["time_coverage_start"] = str(coverage_start)
                coverage_end = var.max().values
                ds.attrs["time_coverage_end"] = str(coverage_end)
                coverage_duration = pd.to_timedelta(coverage_end - coverage_start)
                ds.attrs["time_coverage_duration"] = coverage_duration.isoformat()
        elif name == "latitude":
            if "geospatial_lat_min" not in ds.attrs:
                # Skip the calculations if already done by lat-lon
                # CRS dim coord assignments
                lat_min = var.min().values
                lat_max = var.max().values
                ds.attrs.update(
                    {"geospatial_lat_min": lat_min, "geospatial_lat_max": lat_max}
                )
        elif name == "longitude":
            if "geospatial_lon_min" not in ds.attrs:
                # Skip calculation if lat-lon CRS dim-coord
                # assignments already did it faster
                lon_min = var.min().values
                lon_max = var.max().values
                ds.attrs.update(
                    {"geospatial_lon_min": lon_min, "geospatial_lon_max": lon_max}
                )
        try:
            ds.attrs["institution"] = var.attrs["originatingCenter"]
            ds.attrs["source"] = var.attrs["originatingCenter"]
        except KeyError:
            pass
    return ds
