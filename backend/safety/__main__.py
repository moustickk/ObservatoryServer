from backend.safety.threads import (
    start_monitor
)


def main():

    start_monitor()

    input(
        "Safety monitor running..."
    )


if __name__ == "__main__":

    main()