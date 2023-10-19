import argparse

from pathier import Pathier

root = Pathier(__file__).parent


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "name",
        type=str,
        help=""" The name to use for the created file stem and the Gruel subclass name. """,
    )
    args = parser.parse_args()

    return args


def main(args: argparse.Namespace | None = None):
    if not args:
        args = get_args()
    content = (
        (root / "template.py").read_text().replace("SubGruel", args.name.capitalize())
    )
    (Pathier.cwd() / f"{args.name.lower()}.py").write_text(content)


if __name__ == "__main__":
    main(get_args())
