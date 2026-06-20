"""Test Garmin Connect download decisions."""

__author__ = "Tom Goetz"
__copyright__ = "Copyright Tom Goetz"
__license__ = "GPL"


import os
import tempfile
import unittest
from unittest import mock

from garmindb.download import Download


class TestDownload(unittest.TestCase):
    def test_existing_activity_json_does_not_skip_missing_fit(self):
        calls = {"details": [], "fit": [], "summary": [], "unzip": []}
        activity = {"activityId": 123, "activityName": "Morning Run"}

        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, "activity_123.json"), "w") as file:
                file.write("{}")

            download = Download.__new__(Download)
            download._Download__get_activity_summaries = lambda start, count: [activity]
            download._Download__save_activity_details = (
                lambda directory_arg, activity_id, overwite: calls["details"].append(
                    (directory_arg, activity_id, overwite)
                )
            )
            download._Download__save_activity_file = (
                lambda activity_id: calls["fit"].append(activity_id)
            )
            download._Download__unzip_files = lambda directory_arg: calls["unzip"].append(
                directory_arg
            )
            download.save_json_to_file = (
                lambda filename, json_data, overwite=False: calls["summary"].append(
                    (filename, json_data, overwite)
                )
            )

            with mock.patch("garmindb.download.time.sleep") as sleep:
                Download.get_activities(download, directory, 1, overwite=False)

        self.assertEqual(calls["summary"], [])
        self.assertEqual(calls["details"], [(directory, "123", False)])
        self.assertEqual(calls["fit"], ["123"])
        self.assertEqual(calls["unzip"], [directory])
        sleep.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
