from datetime import datetime
from os.path import dirname, join

import pytest  # noqa
from city_scrapers_core.constants import BOARD, PASSED
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.cuya_library import CuyaLibrarySpider

test_response = file_response(
    join(dirname(__file__), "files", "cuya_library.html"),
    url=(
        "https://cuyahogalibrary.org/About-Us/Our-Organization/Board-Meetings/Board-Reports/2018.aspx"  # noqa
    ),
)
spider = CuyaLibrarySpider()

freezer = freeze_time("2019-09-25")
freezer.start()

parsed_items = [item for item in spider.parse(test_response)]

freezer.stop()


def test_count():
    assert len(parsed_items) == 23


def test_title():
    assert parsed_items[0]["title"] == "Board of Trustees"


def test_description():
    assert parsed_items[0]["description"] == ""


def test_start():
    assert parsed_items[0]["start"] == datetime(2019, 1, 22, 18, 0)


def test_end():
    assert parsed_items[0]["end"] is None


def test_time_notes():
    assert parsed_items[0]["time_notes"
                           ] == "Details may change, confirm with staff before attending"


def test_id():
    assert parsed_items[0]["id"] == "cuya_library/201901221800/x/board_of_trustees"


def test_status():
    assert parsed_items[0]["status"] == PASSED


def test_location():
    assert parsed_items[0]["location"] == spider.location


def test_source():
    assert parsed_items[0]["source"] == test_response.url


def test_links():
    assert parsed_items[0]["links"] == [{
        "href":
            "https://cuyahogalibrary.org/About-Us/Our-Organization/Board-Meetings/Board-Reports/2018-1/Board-of-Trustees/01-2019-January-Board-Book",  # noqa
        "title": "Board Book"
    }]


def test_classification():
    assert parsed_items[0]["classification"] == BOARD


def test_all_day():
    assert parsed_items[0]["all_day"] is False
