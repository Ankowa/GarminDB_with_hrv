"""Test normalized activity record field capture."""

__author__ = "Tom Goetz"
__copyright__ = "Copyright Tom Goetz"
__license__ = "GPL"


import datetime
import json
import tempfile
import unittest

import fitfile
from fitfile.data_message import MessageFields
from fitfile.field_enums import UnknownEnumValue
from fitfile.field_value import FieldValue
from fitfile.fields import NamedField
from idbutils import DbParams

from garmindb import ActivityFitFileProcessor
from garmindb.garmindb import ActivitiesDb, ActivityRecordFields, ActivityRecords


class FakeFitFile:
    """Minimal FIT file object for record import tests."""

    filename = "/tmp/123456789_ACTIVITY.fit"

    def utc_datetime_to_local(self, timestamp):
        if timestamp.tzinfo:
            return timestamp.replace(tzinfo=None)
        return timestamp


class TestActivityRecordFields(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_params = DbParams(db_type="sqlite", db_path=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def field_value(name, value, raw_value=None, units=None):
        raw_value = value if raw_value is None else raw_value
        return FieldValue(NamedField(name, units=units), raw_value, None, **{name: value})

    @classmethod
    def message_fields_from_values(cls, field_values):
        fields = MessageFields()
        for field_value in field_values.values():
            fields.update(field_value)
        return fields

    def write_record(self, field_values):
        processor = ActivityFitFileProcessor(self.db_params)
        processor.activity_fit_file_plugins = []
        activity_db = ActivitiesDb(self.db_params)
        processor.garmin_act_db = activity_db
        message_fields = self.message_fields_from_values(field_values)
        with activity_db.managed_session() as session:
            processor.garmin_act_db_session = session
            processor._write_record_entry(FakeFitFile(), message_fields, 0, field_values)
        return activity_db

    def test_legacy_activity_record_is_still_written(self):
        timestamp = datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
        field_values = MessageFields()
        field_values["timestamp"] = self.field_value("timestamp", timestamp)
        field_values["position_lat"] = self.field_value("position_lat", 12.5, units="degrees")
        field_values["position_long"] = self.field_value("position_long", 45.5, units="degrees")
        field_values["heart_rate"] = self.field_value("heart_rate", 151, units="bpm")
        field_values["speed"] = self.field_value("speed", 8.25, units="mph")

        activity_db = self.write_record(field_values)

        with activity_db.managed_session() as session:
            record = session.query(ActivityRecords).one()
            self.assertEqual(record.activity_id, "123456789")
            self.assertEqual(record.record, 0)
            self.assertEqual(record.hr, 151)
            self.assertEqual(record.speed, 8.25)
            self.assertEqual(record.timestamp, timestamp.replace(tzinfo=None))

    def test_decoded_record_fields_are_written(self):
        timestamp = datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
        field_values = MessageFields()
        field_values["timestamp"] = self.field_value("timestamp", timestamp)
        field_values["heart_rate"] = self.field_value("heart_rate", 151, units="bpm")
        field_values["sport"] = self.field_value("sport", fitfile.Sport.running, raw_value=1)
        field_values["array_field"] = self.field_value(
            "array_field",
            [1, fitfile.Sport.running, UnknownEnumValue(999), None],
            raw_value=[1, 1, 999, None],
            units="custom",
        )
        field_values["nullable_field"] = self.field_value("nullable_field", None)
        field_values["unknown_250"] = self.field_value("unknown_250", UnknownEnumValue(250), raw_value=250)

        activity_db = self.write_record(field_values)

        with activity_db.managed_session() as session:
            rows = {
                row.field_name: row
                for row in session.query(ActivityRecordFields)
                .order_by(ActivityRecordFields.field_name)
                .all()
            }

        self.assertEqual(rows["heart_rate"].field_value, "151")
        self.assertEqual(rows["heart_rate"].field_units, "bpm")
        self.assertEqual(rows["heart_rate"].field_raw_value, "151")
        self.assertEqual(rows["sport"].field_value, "running")
        self.assertEqual(rows["sport"].field_raw_value, "1")
        self.assertEqual(json.loads(rows["array_field"].field_value), [1, "running", "UnknownEnumValue_999", None])
        self.assertEqual(json.loads(rows["array_field"].field_raw_value), [1, 1, 999, None])
        self.assertIsNone(rows["nullable_field"].field_value)
        self.assertIsNone(rows["nullable_field"].field_raw_value)
        self.assertEqual(rows["unknown_250"].field_value, "UnknownEnumValue_250")
        self.assertEqual(rows["unknown_250"].field_raw_value, "250")


if __name__ == "__main__":
    unittest.main(verbosity=2)
