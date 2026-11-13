"""页面动作原语。跑在本地 Chromium 上，不联网。"""

import pytest

from browser.driver import ActionError, PageDriver


@pytest.fixture
def driver(page):
    return PageDriver(page, timeout_ms=3000)


def test_fill_writes_the_value(page, driver):
    page.set_content("<textarea id='t'></textarea>")
    driver.fill("#t", "两个事务改同一行")
    assert page.input_value("#t") == "两个事务改同一行"


def test_fill_replaces_the_previous_value(page, driver):
    page.set_content("<input id='t' value='旧的'>")
    driver.fill("#t", "新的")
    assert page.input_value("#t") == "新的"


def test_fill_on_a_missing_element_names_the_selector(page, driver):
    page.set_content("<div>nothing here</div>")
    with pytest.raises(ActionError) as error:
        driver.fill("#missing", "x")
    message = str(error.value)
    assert "#missing" in message
    assert "页面上找不到" in message


def test_fill_tries_the_candidates_in_order(page, driver):
    page.set_content("<textarea id='second'></textarea>")
    driver.fill(["#first", "#second"], "值")
    assert page.input_value("#second") == "值"


def test_upload_sets_a_real_file(page, driver, tmp_path):
    page.set_content("<input id='f' type='file'>")
    target = tmp_path / "clip.mp4"
    target.write_bytes(b"\x00" * 32)
    driver.upload("#f", target)
    name = page.eval_on_selector("#f", "el => el.files[0].name")
    size = page.eval_on_selector("#f", "el => el.files[0].size")
    assert name == "clip.mp4"
    assert size == 32


def test_upload_refuses_a_file_that_is_not_there(page, driver, tmp_path):
    page.set_content("<input id='f' type='file'>")
    with pytest.raises(ActionError) as error:
        driver.upload("#f", tmp_path / "nope.mp4")
    assert "不存在" in str(error.value)


def test_upload_without_any_input_says_so(page, driver, tmp_path):
    page.set_content("<div>no upload here</div>")
    target = tmp_path / "clip.mp4"
    target.write_bytes(b"\x00")
    with pytest.raises(ActionError) as error:
        driver.upload("#f", target)
    message = str(error.value)
    assert "找不到" in message
    assert "#f" in message


def test_wait_for_times_out_with_a_readable_message(page, driver):
    page.set_content("<div>hi</div>")
    with pytest.raises(ActionError) as error:
        driver.wait_for("#never", timeout_ms=300)
    assert "#never" in str(error.value)
    assert "300 ms" in str(error.value)


def test_wait_for_returns_when_the_element_shows_up(page, driver):
    page.set_content("<div id='later' style='display:none'>x</div>")
    page.eval_on_selector("#later", "el => el.style.display = ''")
    driver.wait_for("#later", timeout_ms=1000)


def test_exists_does_not_raise(page, driver):
    page.set_content("<div id='here'></div>")
    assert driver.exists("#here") is True
    assert driver.exists("#gone") is False


def test_screenshot_writes_a_file(page, driver, tmp_path):
    page.set_content("<h1>hello</h1>")
    target = driver.screenshot(tmp_path / "shot.png")
    assert target.is_file()
    assert target.stat().st_size > 0
