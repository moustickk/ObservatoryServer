from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parents[2]

LOG_DIR = (
    BASE_DIR
    / "data"
    / "logs"
)

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def write_log(
    filename,
    message
):

    log_file = LOG_DIR / filename

    now = datetime.now()

    timestamp = now.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    lines = []

    try:

        with open(
            log_file,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:

                try:

                    if line.startswith("["):

                        date_str = line[1:20]

                        log_date = datetime.strptime(
                            date_str,
                            "%Y-%m-%d %H:%M:%S"
                        )

                        age = (
                            now - log_date
                        ).total_seconds()

                        if age <= 48 * 3600:

                            lines.append(line)

                except Exception:
                    pass

    except FileNotFoundError:
        pass

    lines.insert(
        0,
        f"[{timestamp}] {message}\n"
    )

    with open(
        log_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.writelines(lines)