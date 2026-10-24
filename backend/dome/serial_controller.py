import serial
import threading
import time


class RoofController:

    def __init__(
        self,
        port,
        baudrate
    ):

        self.lock = threading.Lock()

        self.ser = serial.Serial(
            port,
            baudrate,
            timeout=2
        )
        
        time.sleep(2)
        self.ser.reset_input_buffer()

    def send(
        self,
        cmd
    ):

        with self.lock:

            self.ser.reset_input_buffer()

            self.ser.write(
                f"{cmd}\n".encode()
            )

            response = (
                self.ser.readline()
                .decode(errors="ignore")
                .strip()
            )

            if response.startswith(
                "Etat initial :"
            ):

                response = (
                    self.ser.readline()
                    .decode(errors="ignore")
                    .strip()
                )

            print(
                f"Arduino response: [{response}]"
            )

            return response

    def open(self):

        return self.send(
            "OPEN"
        )

    def close(self):

        return self.send(
            "CLOSE"
        )

    def stop(self):

        return self.send(
            "STOP"
        )

    def status(self):

        return self.send(
            "STATUS"
        )