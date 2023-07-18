import pytest
import itertools
from pathlib import Path

from miniscope_io.io import SDCard
from miniscope_io.formats import WireFreeSDLayout

@pytest.fixture
def wirefree():
    """
    SDCard with wirefree layout pointing to the sample data file

    """
    sd_path = Path(__file__).parent.parent / 'data' / 'wirefree_example.img'
    sdcard = SDCard(drive = sd_path, layout = WireFreeSDLayout)
    return sdcard



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
            # if we just read the 0th frame, we should have 1 position
            assert len(wirefree.positions) == i + 1

    # after we exit the context manager, we should lose our current frame
    assert wirefree.frame is None
    # we should also not be able to read anymore
    with pytest.raises(RuntimeError):
        frame = wirefree.read()
    # and the file descriptor should also be gone
    assert wirefree._f is None
    # but we should keep our positions
    assert len(wirefree.positions) == 20



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