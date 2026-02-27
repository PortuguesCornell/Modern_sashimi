from multiprocessing import Queue
from sashimi.processes.logging import LoggingProcess
from sashimi.utilities import clean_json
from sashimi.events import LoggedEvent
from sashimi.config import read_config
from sashimi.hardware.external_trigger import external_comm_class_dict
from queue import Empty
from multiprocessing import Event


conf = read_config()


class ExternalComm(LoggingProcess):
    def __init__(
        self,
        stop_event: LoggedEvent,
        experiment_start_event: LoggedEvent,
        is_saving_event: LoggedEvent,
        is_waiting_event: LoggedEvent,
        duration_queue: Queue,
        address=conf["external_communication"]["address"],
        scanning_trigger=True,
    ):
        super().__init__(name="external_comm")
        self.current_settings_queue = Queue()
        self.current_settings = None
        self.start_comm = experiment_start_event.new_reference(self.logger)
        self.stop_event = stop_event.new_reference(self.logger)
        self.saving_event = is_saving_event.new_reference(self.logger)
        self.is_triggered_event = Event()
        self.duration_queue = duration_queue
        self.address = address
        if conf["scopeless"]:
            self.comm = external_comm_class_dict["mock"]()
        else:
            self.comm = external_comm_class_dict[
                conf["external_communication"]["name"]
            ](self.address)
        self.scanning_trigger = scanning_trigger
        if self.scanning_trigger:
            self.waiting_event = is_waiting_event.new_reference(self.logger)
        self._last_trigger_cond = False

    def trigger_condition(self):
        if self.scanning_trigger:
            cond = (
                self.start_comm.is_set()
                and self.saving_event.is_set()
                and self.is_triggered_event.is_set()
                and not self.waiting_event.is_set()
            )
            # Log only on change to avoid flooding every loop/frame
            if cond != self._last_trigger_cond:
                self.logger.log_message(
                    f"trigger_condition changed: start_comm={self.start_comm.is_set()}, saving={self.saving_event.is_set()}, is_triggered={self.is_triggered_event.is_set()}, waiting={self.waiting_event.is_set()} -> {cond}"
                )
                self._last_trigger_cond = cond
            return cond

    def run(self):
        self.logger.log_message("started")
        while not self.stop_event.is_set():
            while True:
                try:
                    self.current_settings = self.current_settings_queue.get(
                        timeout=0.00001
                    )
                    current_config = dict(lightsheet=clean_json(self.current_settings))
                except Empty:
                    break
            if self.trigger_condition():
                # Wait for camera start signal (experiment_start_event) to ensure
                # frames are actually being produced before sending the external
                # trigger. Use the underlying Event.wait with a short timeout.
                try:
                    started = self.start_comm.event.wait(timeout=1.0)
                except Exception:
                    # If underlying event is not available, fall back to sending
                    started = self.start_comm.is_set()

                if not started:
                    self.logger.log_message("Skipping trigger: camera start signal not received yet")
                    continue

                print(f"[ExternalComm] sending trigger with config keys: {list(current_config.keys())}")
                duration = self.comm.trigger_and_receive_duration(current_config)
                if duration is not None:
                    self.duration_queue.put(duration)
                self.logger.log_message("sent communication")
                print("[ExternalComm] clearing start_comm")
                self.start_comm.clear()
        self.close_log()
