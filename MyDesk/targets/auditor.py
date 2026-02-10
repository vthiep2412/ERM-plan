from .input_blocker import set_key_logger


class KeyAuditor:
    def __init__(self, callback_func):
        """
        callback_func: Function to call when a key is pressed.
        Signature: callback(keystring)
        """
        self.callback = callback_func

    def start(self):
        print("[+] Key Auditor registering with InputBlocker")
        # Register our callback with the central hook
        set_key_logger(self.callback)

    def stop(self):
        print("[-] Key Auditor deregistering")
        set_key_logger(None)
