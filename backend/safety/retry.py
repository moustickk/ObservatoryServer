import time


def execute_with_retry(
    callback,
    retries=3,
    delay=5
):

    last_exception = None

    for _ in range(retries):

        try:

            return callback()

        except Exception as ex:

            last_exception = ex

            time.sleep(delay)

    raise last_exception