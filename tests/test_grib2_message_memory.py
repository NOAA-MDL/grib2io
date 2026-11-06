import gc
import weakref

import grib2io


def _nbm_file(request):
    return request.config.rootdir / "tests" / "input_data" / "blend.t00z.core.f001.tmp.co.grib2"


def test_flush_data_removes_unpacked_arrays(request):
    with grib2io.open(_nbm_file(request)) as g:
        msg = g[0]
        msg.data
        assert hasattr(msg, "_missvalmap")
        msg.flush_data()
        assert msg._data is None
        assert msg.bitmap is None
        assert not hasattr(msg, "_missvalmap")
        assert msg.data.shape == (msg.ny, msg.nx)


def test_message_freed_without_garbage_collection(request):
    gc.disable()
    try:
        with grib2io.open(_nbm_file(request)) as g:
            msg = g[0]
            msg.data
        ref = weakref.ref(msg)
        del g, msg
        assert ref() is None
    finally:
        gc.enable()
