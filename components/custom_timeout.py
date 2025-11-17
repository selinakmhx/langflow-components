from time import sleep
from typing import Any, Dict

from langflow.custom import Component
from langflow.io import BoolInput, IntInput, Output
from langflow.schema import Data


class CustomTimeoutComponent(Component):
    display_name = "Custom Timeout"
    description = "A component that demonstrates custom timeout configuration."
    icon = "timer"
    name = "CustomTimeout"

    inputs = [
        IntInput(
            name="timeout_seconds",
            display_name="Timeout (seconds)",
            info="Set the timeout duration in seconds. Set to 0 for no timeout.",
            value=30,
            advanced=True,
        ),
        BoolInput(
            name="disable_timeout",
            display_name="Disable Timeout",
            info="When enabled, the operation will have no timeout limit.",
            value=False,
            advanced=True,
        ),
        IntInput(
            name="task_duration",
            display_name="Task Duration (seconds)",
            info="Simulate a task that takes this many seconds to complete.",
            value=5,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run_task"),
    ]

    def run_task(self) -> Data:
        # Determine the actual timeout value
        if self.disable_timeout:
            actual_timeout = None
            timeout_message = "disabled (no timeout)"
        elif self.timeout_seconds <= 0:
            actual_timeout = None
            timeout_message = "disabled (0 or negative value)"
        else:
            actual_timeout = self.timeout_seconds
            timeout_message = f"{actual_timeout} seconds"

        # Prepare the result data
        result_data = {
            "task_duration": self.task_duration,
            "timeout_setting": timeout_message,
            "status": "started",
        }

        try:
            # Actually wait for the specified duration
            # In a real implementation, this would be your actual task
            import time
            start_time = time.time()
            
            # Wait for the specified duration
            time.sleep(self.task_duration)
            
            elapsed_time = time.time() - start_time
            result_data["elapsed_time"] = round(elapsed_time, 2)
            result_data["status"] = "completed"
            result_data["message"] = f"Task completed in {round(elapsed_time, 2)} seconds"
            
            return Data(data=result_data)
            
        except Exception as e:
            # Handle timeout exceptions
            result_data["status"] = "error"
            result_data["error"] = str(e)
            return Data(data=result_data)