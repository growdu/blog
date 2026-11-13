"""期号登记表的守卫：期号、口播稿、契约、旁白必须对得上。"""
from __future__ import annotations

from pyv import episodes as episodes_mod


def test_every_episode_has_a_script_and_a_contract():
    for ep in episodes_mod.EPISODE_ORDER:
        assert episodes_mod.script_path(ep).is_file(), ep
        assert episodes_mod.contract_path(ep).is_file(), ep


def test_order_covers_every_registered_episode():
    assert set(episodes_mod.EPISODE_ORDER) == set(episodes_mod.EPISODES)


def test_episode_numbers_are_sequential_and_unique():
    numbers = [episodes_mod.EP_NUMBERS[ep] for ep in episodes_mod.EPISODE_ORDER]
    assert numbers == [f"ep{index:02d}" for index in range(1, len(numbers) + 1)]
    assert len(set(numbers)) == len(numbers)


def test_contract_file_name_follows_the_episode_id():
    """契约文件名就是 EP 号——改了映射就一定对不上。"""
    for ep in episodes_mod.EPISODE_ORDER:
        assert episodes_mod.contract_path(ep).name == f"{ep}.json"


def test_narration_and_storyboard_follow_the_episode_id():
    for ep in episodes_mod.EPISODE_ORDER:
        assert episodes_mod.narration_path(ep).name == f"narration_{ep}.mp3"
        assert episodes_mod.storyboard_path(ep).name == f"storyboard_{ep}.json"


def test_default_episode_is_the_first_one():
    assert episodes_mod.DEFAULT_EP == episodes_mod.EPISODE_ORDER[0]
    assert episodes_mod.DEFAULT_EP in episodes_mod.EPISODES


def test_known_eps_lists_every_episode():
    assert set(episodes_mod.known_eps()) == set(episodes_mod.EPISODES)
