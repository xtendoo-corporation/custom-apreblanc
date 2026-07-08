from odoo import fields
from odoo.tests import tagged

from odoo.addons.hr_holidays.tests.common import TestHrHolidaysCommon


@tagged("post_install", "-at_install")
class TestHrLeaveCalendarRecompute(TestHrHolidaysCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar_a = cls._create_calendar("Calendar A", [0, 1, 2, 3, 4])
        cls.calendar_b = cls._create_calendar("Calendar B", [0, 1, 2, 3])
        cls.employee_emp.resource_calendar_id = cls.calendar_a
        cls.leave_type = cls.env["hr.leave.type"].with_user(cls.user_hrmanager_id).create(
            {
                "name": "Calendar Recompute Leave",
                "requires_allocation": "no",
                "leave_validation_type": "hr",
                "request_unit": "day",
            }
        )

    @classmethod
    def _create_calendar(cls, name, day_indexes):
        return cls.env["resource.calendar"].create(
            {
                "name": name,
                "tz": "Europe/Brussels",
                "attendance_ids": [
                    (
                        0,
                        0,
                        {
                            "name": f"{name} {day_index}",
                            "dayofweek": str(day_index),
                            "hour_from": 8.0,
                            "hour_to": 16.0,
                        },
                    )
                    for day_index in day_indexes
                ],
            }
        )

    def _create_leave(self):
        return self.env["hr.leave"].with_user(self.user_hrmanager_id).create(
            {
                "name": "Calendar recompute test leave",
                "employee_id": self.employee_emp.id,
                "holiday_status_id": self.leave_type.id,
                "request_date_from": fields.Date.from_string("2026-07-06"),
                "request_date_to": fields.Date.from_string("2026-07-10"),
            }
        )

    def test_recompute_with_manual_calendar(self):
        leave = self._create_leave()
        self.assertEqual(leave.number_of_days, 5)
        self.assertEqual(leave.xtd_calculation_calendar_id, self.calendar_a)

        leave.write({"xtd_calculation_calendar_id": self.calendar_b.id})
        self.assertEqual(leave.number_of_days, 5)

        leave.xtd_action_recompute_duration_with_calendar()
        self.assertEqual(leave.number_of_days, 4)

    def test_employee_calendar_change_does_not_recompute_automatically(self):
        leave = self._create_leave()
        self.assertEqual(leave.number_of_days, 5)

        self.employee_emp.resource_calendar_id = self.calendar_b
        self.assertEqual(leave.number_of_days, 5)

        leave.xtd_action_recompute_duration_with_calendar_mass(
            xtd_calendar_mode="employee"
        )
        self.assertEqual(leave.xtd_calculation_calendar_id, self.calendar_b)
        self.assertEqual(leave.number_of_days, 4)

    def test_recompute_fills_missing_calendar(self):
        leave = self._create_leave()
        self.employee_emp.resource_calendar_id = self.calendar_b
        leave.write({"xtd_calculation_calendar_id": False})
        self.assertFalse(leave.xtd_calculation_calendar_id)

        leave.xtd_action_recompute_duration_with_calendar_mass(
            xtd_calendar_mode="keep"
        )
        self.assertEqual(leave.xtd_calculation_calendar_id, self.calendar_b)
        self.assertEqual(leave.number_of_days, 4)
