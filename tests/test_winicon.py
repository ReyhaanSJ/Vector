import struct

from vector.winicon import ICON, group_icon, parse_ico


def test_vector_icon_splits_into_sizes():
    images = parse_ico(ICON.read_bytes())
    assert len(images) >= 8                               # 16 px up to 256 px
    sizes = {entry[0] or 256 for entry, _ in images}      # 0 means 256 in .ico files
    assert {16, 32, 48, 256} <= sizes
    assert all(img for _, img in images)


def test_group_icon_lists_every_image_with_ids():
    images = parse_ico(ICON.read_bytes())
    group = group_icon(images)
    reserved, kind, count = struct.unpack_from("<HHH", group, 0)
    assert (reserved, kind, count) == (0, 1, len(images))
    assert len(group) == 6 + 14 * len(images)
    ids = [struct.unpack_from("<H", group, 6 + 14 * i + 12)[0] for i in range(count)]
    assert ids == list(range(1, count + 1))
