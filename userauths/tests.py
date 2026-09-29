from unittest.mock import patch

from django.test import SimpleTestCase

from userauths.views import _admin_invite_matches


class AdminInviteTests(SimpleTestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_invite_is_rejected_when_no_code_is_configured(self):
        self.assertFalse(_admin_invite_matches(""))

    @patch.dict("os.environ", {"PAYLIO_ADMIN_INVITE_CODE": "private-code"})
    def test_configured_invite_is_required_and_compared(self):
        self.assertFalse(_admin_invite_matches(""))
        self.assertFalse(_admin_invite_matches("incorrect"))
        self.assertTrue(_admin_invite_matches("private-code"))
