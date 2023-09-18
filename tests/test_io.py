import pdb

import numpy as np
import pytest
import tempfile
from pathlib import Path
import os
import warnings

from miniscope_io.sdcard import DataHeader
from miniscope_io.formats import WireFreeSDLayout, WireFreeSDLayout_Battery
from miniscope_io.io import SDCard
from miniscope_io.exceptions import EndOfRecordingException
from miniscope_io.data import Frame
from miniscope_io.utils import hash_file

from .fixtures import wirefree, wirefree_battery


def test_read(wirefree):
    """
    Test that we can read a frame!

    For now since we're just using the example, don't try and validate the output,
    we'll do that later.
    """
    n_frames = 20

    # before we enter the context manager, we shouldn't be able to read
    with pytest.raises(RuntimeError):
        frame = wirefree.read()

    # failing to read should not increment the frame and it should still be None
    assert wirefree.frame is None

    with wirefree:
        for i in range(n_frames):
            # Frame indicates what frame we are just about to read
            assert wirefree.frame == i

            frame = wirefree.read()

            # the frame is the right shape
            assert len(frame.shape) == 2
            assert frame.shape[0] == wirefree.config.height
            assert frame.shape[1] == wirefree.config.width

            # assert they're not all zeros - ie. we read some data
            assert frame.any()

            # we should have stashed frame start positions
            # if we just read the 0th frame, we should have 2 positions
            # for the 0th and 1st frame
            assert len(wirefree.positions) == i + 2

    # after we exit the context manager, we should lose our current frame
    assert wirefree.frame is None
    # we should also not be able to read anymore
    with pytest.raises(RuntimeError):
        frame = wirefree.read()
    # and the file descriptor should also be gone
    assert wirefree._f is None
    # but we should keep our positions
    assert len(wirefree.positions) == n_frames + 1

def test_return_headers(wirefree):
    """
    We can return the headers for the individual buffers in a frame
    """
    with wirefree:
        frame_object = wirefree.read(return_header=True)
        assert isinstance(frame_object, Frame)

        assert len(frame_object.headers) == 5
        assert all([isinstance(b, DataHeader) for b in frame_object.headers])

def test_frame_count(wirefree):
    """
    We can infer the total number of frames in a recording from the data header
    """
    # known max frames given the data header in the example data
    assert wirefree.frame_count == 388

    # if we try and read past the end, we get an exception
    with wirefree:
        wirefree.frame = 389
        with pytest.raises(EndOfRecordingException):
            frame = wirefree.read()

def test_relative_path():
    """
    Test that we can use both relative and absolute paths in the SD card model
    """
    # get absolute path of working directory, then get relative path to data from there
    abs_cwd = Path(os.getcwd()).resolve()
    abs_child = Path(__file__).parent.parent / 'data' / 'wirefree_example.img'
    rel_path = abs_child.relative_to(abs_cwd)

    assert not rel_path.is_absolute()
    sdcard = SDCard(drive = rel_path, layout = WireFreeSDLayout)

    # check we can do something basic like read config
    assert sdcard.config is not None

    # check it remains relative after init
    assert not sdcard.drive.is_absolute()

    # now try with an absolute path
    abs_path = rel_path.resolve()
    assert abs_path.is_absolute()
    sdcard_abs = SDCard(drive= abs_path, layout= WireFreeSDLayout)
    assert sdcard_abs.config is not None
    assert sdcard_abs.drive.is_absolute()


@pytest.mark.parametrize(
    ['file', 'fourcc', 'hashes'],
    [
        ('video.avi', 'GREY', ('2315d20f3d0c0f3f53a9d38f3b99b322148b7855a3c5d9848a866988eb3fc97c', '70b6898113a6d9f05c02bd52131ee56dc68b1c65fed518ea2265440fab801cc6')),
        ('video.mp4', 'mp4v', ('85c98346bf50a2bccc0c9aed485a2159b52e93b05ab180db0885d903fc13b143', '9155aa6e44d8863d3defbd815ba8ac33d036dd4eb06c474ba3dd6270a28d47f6'))
    ]
)
def test_write_video(wirefree, file, fourcc, hashes):
    """
    Test that we can write videos from an SD card!!
    """
    with tempfile.TemporaryDirectory() as tempdir:
        path = Path(tempdir) / file
        wirefree.to_video(path, fourcc=fourcc, progress=False)
        file_hash = hash_file(path)
        assert file_hash in hashes

@pytest.mark.parametrize(
    ['n_frames', 'out_file', 'hash'],
    [
        (50, Path(__file__).parent / '__tmp__' / 'test_toimg.img', '9b48a4ae3458187072d73840b51c9de6f986dd2f175c566dbb1d44216c313e19')
    ]
)
def test_to_img(wirefree_battery, n_frames, out_file, hash):
    wirefree_battery.to_img(out_file, n_frames, force=True)
    out_hash = hash_file(out_file)

    assert out_hash == hash

    sd = SDCard(out_file, WireFreeSDLayout_Battery)

    # we should be able to read all the frames!
    frames = []
    with sd:
        for i in range(n_frames):
            frames.append(sd.read(return_header=True))

    assert not any([f.data is None for f in frames])
    assert all([np.nonzero(f.data) for f in frames])

    # we should not write to file if it exists and force is False
    assert out_file.exists()
    mtime = os.path.getmtime(out_file)

    with pytest.raises(FileExistsError):
        wirefree_battery.to_img(out_file, n_frames, force=False)

    assert mtime == os.path.getmtime(out_file)

    # forcing should overwrite the file
    wirefree_battery.to_img(out_file, n_frames, force=True)
    assert mtime != os.path.getmtime(out_file)

    out_file.unlink()





#
# @pytest.mark.parametrize(
#     ['data', 'header', 'sector', 'word'],
#     list(itertools.product(
#         (63964, 49844),
#         (9, 10),
#         (512,),
#         (4,)
#     ))
# )
# def test_n_blocks(data, header, sector, word):
#     """
#     Original:
#
#     numBlocks = int((dataHeader[BUFFER_HEADER_DATA_LENGTH_POS] + \
#       (dataHeader[BUFFER_HEADER_HEADER_LENGTH_POS] * 4) + (512 - 1)) / 512)
#     data = np.fromstring(
#       f.read(
#         numBlocks*512 - dataHeader[BUFFER_HEADER_HEADER_LENGTH_POS] * 4
#       ),
#       dtype=np.uint8
#     )
#
#     """
#     n_blocks = int(
#         (data + (header * word) + (sector - 1)) / sector
#     )
#     read_bytes = n_blocks * sector - header * word
#
#     assert read_bytes == data