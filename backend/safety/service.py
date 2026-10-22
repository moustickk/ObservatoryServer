class SafetyService:

    def __init__(self):

        self.safe = False

    def set_safe(
        self,
        value
    ):

        self.safe = value

    def status(self):

        return {
            "safe": self.safe
        }