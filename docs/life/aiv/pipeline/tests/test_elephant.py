from pyv import character, elephant

# 旧 2D 形象已移到仓库根，路径统一由 character 模块给出
IMAGE = character.LEGACY_IMAGE


def test_load_parts_finds_expected_regions():
    parts = elephant.load_parts(IMAGE)
    assert parts.head.size[0] > 600
    assert parts.arm_left.size[1] > 150
    assert parts.arm_right.size[1] > 150
    assert parts.body.size[1] > 200


def test_pivots_lie_inside_their_part():
    parts = elephant.load_parts(IMAGE)
    for name, pivot in parts.pivots.items():
        part = getattr(parts, name)
        x0, y0, x1, y1 = part.crop_box
        assert x0 <= pivot[0] <= x1, name
        assert y0 <= pivot[1] <= y1, name


def test_parts_cover_the_whole_mascot():
    """三个部件的实心像素加起来应等于原图的不透明像素（不能有遗漏）。"""
    import numpy as np
    from PIL import Image
    parts = elephant.load_parts(IMAGE)
    source = np.array(Image.open(IMAGE).convert("RGBA"))[..., 3] > 128
    total = np.zeros_like(source)
    for name in ("head", "arm_left", "arm_right", "body"):
        part = getattr(parts, name)
        arr = np.array(part.image)[..., 3] > 128
        x0, y0, x1, y1 = part.crop_box
        total[y0:y1, x0:x1] |= arr
    assert (total & source).sum() == source.sum()


def test_parts_do_not_share_pixels():
    """各部件的实心像素不能重叠（在原图坐标系里比较）。"""
    import numpy as np
    parts = elephant.load_parts(IMAGE)
    names = ["head", "arm_left", "arm_right", "body"]
    for i, a in enumerate(names):
        part_a = getattr(parts, a)
        arr_a = np.array(part_a.image)[..., 3] > 128
        for b in names[i + 1:]:
            part_b = getattr(parts, b)
            arr_b = np.array(part_b.image)[..., 3] > 128
            x0 = max(part_a.crop_box[0], part_b.crop_box[0])
            y0 = max(part_a.crop_box[1], part_b.crop_box[1])
            x1 = min(part_a.crop_box[2], part_b.crop_box[2])
            y1 = min(part_a.crop_box[3], part_b.crop_box[3])
            if x1 <= x0 or y1 <= y0:
                continue
            sub_a = arr_a[y0 - part_a.crop_box[1]:y1 - part_a.crop_box[1],
                          x0 - part_a.crop_box[0]:x1 - part_a.crop_box[0]]
            sub_b = arr_b[y0 - part_b.crop_box[1]:y1 - part_b.crop_box[1],
                          x0 - part_b.crop_box[0]:x1 - part_b.crop_box[0]]
            assert not (sub_a & sub_b).any(), (a, b)


def test_head_part_keeps_dark_outline():
    """头部部件必须包含深色描边与眼睛，不能只剩浅蓝填充。"""
    import numpy as np
    parts = elephant.load_parts(IMAGE)
    arr = np.array(parts.head.image.convert("RGBA"))
    r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
    dark = (arr[..., 3] > 128) & (b > r + 25) & (r < 110)
    assert dark.sum() > 500


def test_body_part_keeps_badge_and_icon():
    """躯干部件必须保留橙黄图标与徽章。"""
    import numpy as np
    parts = elephant.load_parts(IMAGE)
    arr = np.array(parts.body.image.convert("RGBA"))
    r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
    orange = (arr[..., 3] > 128) & (r > 200) & (g > 140) & (g < 205) & (b < 110)
    assert orange.sum() > 2000


def test_anchor_is_at_the_bottom_of_the_body():
    parts = elephant.load_parts(IMAGE)
    x0, y0, x1, y1 = parts.body.crop_box
    assert parts.anchor[1] == y1


def test_pose_defaults_are_neutral():
    pose = elephant.Pose()
    assert pose.nod == 0.0 and pose.wave == 0.0
    assert pose.turn == 0.0 and pose.point == 0.0


def test_parts_convert_to_cairo_surface():
    import cairo
    parts = elephant.load_parts(IMAGE)
    surface = parts.surface("head")
    assert isinstance(surface, cairo.ImageSurface)
    assert surface.get_width() == parts.head.size[0]
