from xarray.backends.plugins import detect_parameters
import typing
import xarray as xr

class TestBackend:
    def open_dataset(
        self,
        filename: str,
        *,
        drop_variables: typing.Optional[typing.List[str]] = None,
        save_index: bool = True,
        filters: typing.Mapping[str, typing.Any] = dict(),
        data_model: typing.Optional[str] = None,
        chunks: typing.Optional[
            typing.Union[int, typing.Dict[typing.Any, typing.Any], typing.Literal["auto"]]
        ] = None,
    ) -> xr.Dataset:
        pass

try:
    print("Testing complex signature...")
    params = detect_parameters(TestBackend.open_dataset)
    print(f"Params: {params}")
except TypeError as e:
    print(f"Caught TypeError: {e}")

class TestBackendSimple:
    def open_dataset(
        self,
        filename,
        drop_variables=None,
        save_index=True,
        filters=None,
        data_model=None,
        chunks=None,
    ) -> xr.Dataset:
        pass

try:
    print("\nTesting simple signature...")
    params = detect_parameters(TestBackendSimple.open_dataset)
    print(f"Params: {params}")
except TypeError as e:
    print(f"Caught TypeError: {e}")

class TestBackendStar:
    def open_dataset(
        self,
        filename,
        *,
        chunks=None,
    ) -> xr.Dataset:
        pass

try:
    print("\nTesting signature with star...")
    params = detect_parameters(TestBackendStar.open_dataset)
    print(f"Params: {params}")
except TypeError as e:
    print(f"Caught TypeError: {e}")
