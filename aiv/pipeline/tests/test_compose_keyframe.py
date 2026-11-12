"""成片的编码参数：关键帧间隔必须 ≤ 10 秒。

B站《文件上传预处理》写死了「视频关键帧至少 10 秒一个」。
我们的成片由分段渲染再拼成，每段独立编码，段边界会拉长关键帧间隔——
EP02 实测最大 10.417s，超标。

根治办法不是在发布前重编码，而是在源头把 GOP 定死。
"""
from pyv import compose


def test_encode_args_pin_the_keyframe_interval():
    args = compose.encode_args(24)
    assert "-g" in args
    assert args[args.index("-g") + 1] == "240"


def test_the_interval_is_ten_seconds_at_24fps():
    """240 帧 @24fps = 10 秒。改了 fps 或改了间隔，这条测试会红。"""
    assert compose.KEYFRAME_INTERVAL == compose.FPS_BASE * 10


def test_both_encode_paths_use_the_same_args():
    """成片的两条编码路径（拼接与混音）必须用同一套参数，
    否则「有旁白的成片」和「无声成片」的关键帧间隔会不一样。"""
    args = compose.encode_args(24)
    assert "-g" in compose.concat_encode_args()
    assert compose.concat_encode_args() == args
