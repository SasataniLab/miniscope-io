import pdb

import pytest
import pandas as pd

from miniscope_io.stream_daq import StreamDevConfig, StreamDaq
from miniscope_io.utils import hash_video, hash_file
from .conftest import DATA_DIR, CONFIG_DIR


@pytest.fixture()
def default_streamdaq(set_okdev_input) -> StreamDaq:

    test_config_path = CONFIG_DIR / "stream_daq_test_200px.yml"
    daqConfig = StreamDevConfig.from_yaml(test_config_path)

    data_file = DATA_DIR / "stream_daq_test_fpga_raw_input_200px.bin"
    set_okdev_input(data_file)

    daq_inst = StreamDaq(device_config=daqConfig)
    return daq_inst


@pytest.mark.parametrize(
    "config,data,video_hash_list,show_video",
    [
        (
            "stream_daq_test_200px.yml",
            "stream_daq_test_fpga_raw_input_200px.bin",
            '["f878f9c55de28a9ae6128631c09953214044f5b86504d6e5b0906084c64c644c","8a6f6dc69275ec3fbcd69d1e1f467df8503306fa0778e4b9c1d41668a7af4856","3676bc4c6900bc9ec18b8387abdbed35978ebc48408de7b1692959037bc6274d"] ',
            False,
        )
    ],
)
def test_video_output(config, data, video_hash_list, tmp_path, show_video, set_okdev_input):
    output_video = tmp_path / "output.avi"

    test_config_path = CONFIG_DIR / config
    daqConfig = StreamDevConfig.from_yaml(test_config_path)

    data_file = DATA_DIR / data
    set_okdev_input(data_file)

    daq_inst = StreamDaq(device_config=daqConfig)
    daq_inst.capture(source="fpga", video=output_video, show_video=show_video)

    assert output_video.exists()

    output_video_hash = hash_video(output_video)

    assert output_video_hash in video_hash_list


@pytest.mark.parametrize(
    "config,data",
    [
        (
            "stream_daq_test_200px.yml",
            "stream_daq_test_fpga_raw_input_200px.bin",
        )
    ],
)
def test_binary_output(config, data, set_okdev_input, tmp_path):
    test_config_path = CONFIG_DIR / config
    daqConfig = StreamDevConfig.from_yaml(test_config_path)

    data_file = DATA_DIR / data
    set_okdev_input(data_file)

    output_file = tmp_path / "output.bin"

    daq_inst = StreamDaq(device_config=daqConfig)
    daq_inst.capture(source="fpga", binary=output_file, show_video=False)

    assert output_file.exists()

    assert hash_file(data_file) == hash_file(output_file)


@pytest.mark.parametrize("write_metadata", [True, False])
def test_csv_output(tmp_path, default_streamdaq, write_metadata, caplog):
    """
    Giving a path to the ``metadata`` capture kwarg should save header metadata to a csv
    """
    output_csv = tmp_path / "output.csv"

    if write_metadata:
        default_streamdaq.capture(source="fpga", metadata=output_csv, show_video=False)

        df = pd.read_csv(output_csv)
        # actually not sure what we should be looking for here, for now we just check for shape
        # this should be the same as long as the test data stays the same,
        # but it's a pretty weak test.
        assert df.shape == (855, 11)

        # ensure there were no errors during capture
        for record in caplog.records:
            assert "Exception saving headers" not in record.msg
    else:
        default_streamdaq.capture(source="fpga", metadata=None)
        assert not output_csv.exists()


def test_metadata_plotting(tmp_path, default_streamdaq):
    """
    Setting the capture kwarg ``show_metadata == True`` should plot the frame metadata
    during capture.
    """
    default_streamdaq.capture(source="fpga", show_metadata=True)

    # unit tests for the stream plotter should go elsewhere, here we just
    # test that the object was instantiated and that it got the data it should have
    assert default_streamdaq._header_plotter is not None
    assert [
        k for k in default_streamdaq._header_plotter.data.keys()
    ] == default_streamdaq.config.runtime.plot.keys
    assert all(
        [
            len(v) == default_streamdaq.config.runtime.plot.history
            for v in default_streamdaq._header_plotter.data.values()
        ]
    )
    assert (
        len(default_streamdaq._header_plotter.index)
        == default_streamdaq.config.runtime.plot.history
    )
