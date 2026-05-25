import time
import warnings
import pandas as pd
import xarray as xr
import grib2io
# Note: In a real environment where grib2io is installed, we would use:
# from grib2io.icechunk import open_grib2
# For this script to be valid for the PR, it should assume grib2io is available.


def run_stress_test(years=["2023", "2024"]):
    """
    Stress test for robust GRIB2 data retrieval using 2 years of GFS data from S3.
    Demonstrates the use of built-in retry logic and the robust .grib2io.compute() method.
    """
    BUCKET = "noaa-gfs-bdp-pds"
    GRID = "0p25"
    CYCLE = "00"
    FORECAST = "f000"

    # More tolerant network settings for remote NOAA S3 reads via s3fs/botocore.
    storage_options = {
        "anon": True,
        "config_kwargs": {
            "connect_timeout": 30,
            "read_timeout": 120,
            "retries": {"max_attempts": 10, "mode": "adaptive"},
        },
    }

    # Filter to 2-metre temperature only
    T2M_FILTERS = {"shortName": "TMP", "typeOfFirstFixedSurface": 103}

    # Build URLs for the selected years.
    all_urls = []
    for year in years:
        year_start = pd.to_datetime(f"{year}-01-01")
        year_end = pd.to_datetime(f"{year}-12-31")
        dates = pd.date_range(year_start, year_end, freq="D")
        urls = [f"s3://{BUCKET}/gfs.{d.strftime('%Y%m%d')}/{CYCLE}/atmos/gfs.t{CYCLE}z.pgrb2.{GRID}.{FORECAST}" for d in dates]
        all_urls.extend(urls)

    print(f"Total files to scan: {len(all_urls)}")

    t0 = time.perf_counter()
    try:
        # 1. Use the standard Xarray interface with the grib2io engine.
        # Setting use_icechunk=True enables the robust virtual store logic.
        ds = xr.open_dataset(
            all_urls,
            engine="grib2io",
            use_icechunk=True,
            storage_options=storage_options,
            filters=T2M_FILTERS,
            max_workers=8,
            network_timeout=300,
            max_concurrent_requests=4,
            max_scan_attempts=5,  # Parameter for robust scanning
            chunks={"valid_time": 30},  # Enable Dask
        )

        elapsed = time.perf_counter() - t0
        print(f"Scanned {len(all_urls)} files in {elapsed:.1f}s ({elapsed / len(all_urls):.3f}s/file)")
        print(ds)

        t2m = ds["TMP"]
        if "height_above_ground" in t2m.dims:
            t2m = t2m.isel(height_above_ground=0)

        # 2. Use the new .grib2io.compute() method for robust data retrieval with retries.
        print("Computing mean T2M for the 2-year period using robust compute...")
        t1 = time.perf_counter()

        # This replaces the need for user-defined retry loops.
        mean_t2m = t2m.mean("valid_time").grib2io.compute(max_attempts=10)

        elapsed_compute = time.perf_counter() - t1
        print(f"Computed mean in {elapsed_compute:.1f}s")
        print(f"Mean T2M: {mean_t2m.mean().values} K")

    except ImportError:
        print("grib2io[icechunk] dependencies not fully installed. Skipping execution.")
    except Exception as e:
        print(f"Stress test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    run_stress_test(["2023", "2024"])
