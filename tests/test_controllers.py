import unittest
from unittest.mock import MagicMock, patch

from src.constants import OPENAI_BILLING_OVERVIEW_URL
from src.controllers import TranscriptionController
from src.exceptions import ApiConnectionError


class ControllerErrorHandlingTests(unittest.TestCase):
    def make_controller(self):
        ui_elements = {
            'root': MagicMock(),
            'progress': MagicMock(),
            'progress_label': MagicMock(),
        }
        controller = TranscriptionController(MagicMock(), MagicMock(), MagicMock(), ui_elements)
        controller.add_log = MagicMock()
        controller.update_status = MagicMock()
        return controller

    def test_insufficient_credit_uses_billing_dialog(self):
        controller = self.make_controller()
        exception = ApiConnectionError(
            "quota exceeded",
            error_code="INSUFFICIENT_CREDIT",
            user_message="OpenAI APIの利用残高が不足している可能性があります。"
        )

        with patch.object(controller, '_show_openai_billing_dialog') as show_dialog, \
             patch('src.controllers.messagebox.showerror') as show_error:
            controller._handle_processing_error(exception, exception.user_message, exception.user_message)

        show_dialog.assert_called_once_with(exception.user_message)
        show_error.assert_not_called()

    def test_queue_processing_logs_billing_url_for_insufficient_credit(self):
        controller = self.make_controller()
        controller.queue_processing = True
        controller.current_file = 'dummy.mp3'
        exception = ApiConnectionError(
            "quota exceeded",
            error_code="INSUFFICIENT_CREDIT",
            user_message="OpenAI APIの利用残高が不足している可能性があります。"
        )

        controller._handle_processing_error(exception, exception.user_message, exception.user_message)

        self.assertTrue(any(
            OPENAI_BILLING_OVERVIEW_URL in str(call.args[0])
            for call in controller.add_log.call_args_list
        ))
        controller.ui_elements['root'].after.assert_called_once()


if __name__ == '__main__':
    unittest.main()
