from sashimi.hardware.external_trigger.interface import AbstractComm
import zmq
from typing import Optional
import math


class StytraComm(AbstractComm):
    def __init__(self, address):
        super().__init__(address)
        self.address = address

    def trigger_and_receive_duration(self, config) -> Optional[float]:
        zmq_context = zmq.Context()
        with zmq_context.socket(zmq.REQ) as zmq_socket:
            print(f"[StytraComm] connecting to {self.address}")
            zmq_socket.connect(self.address)
            print(f"[StytraComm] sending config: {config}")
            zmq_socket.send_json(config)
            poller = zmq.Poller()
            poller.register(zmq_socket, zmq.POLLIN)
            duration = None
            print("[StytraComm] waiting for reply (1000 ms)")
            if poller.poll(1000):
                reply = zmq_socket.recv_json()
                print(f"[StytraComm] received reply: {reply}")
                # Accept either a naked number or a dict with a 'duration' key

                if isinstance(reply, dict) and "duration" in reply:
                    duration = reply["duration"]
                else:
                    duration = reply

                # normalize and validate duration as a finite float
                try:
                    duration_val = float(duration)
                except Exception:
                    duration_val = None

                if duration_val is None or not math.isfinite(duration_val):
                    print("[StytraComm] received non-finite duration; ignoring and returning None")
                    duration = None
                else:
                    duration = duration_val

        zmq_context.destroy()
        print(f"[StytraComm] returning duration: {duration}")
        return duration
