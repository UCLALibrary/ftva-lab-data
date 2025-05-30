import pandas as pd
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group


class Command(BaseCommand):
    help = "Create users from export of Google Sheet provided by FTVA staff"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "-f",
            "--file_name",
            type=str,
            required=True,
            help="Path to the XLSX export of Google Sheet",
        )

        parser.add_argument(
            "--email_users",
            action="store_true",
            default=False,
            help="Email users with their password reset link",
        )

    def handle(self, *args, **options) -> None:
        file_name = options["file_name"]
        # `sheet_name=None` means read all sheets into a dict of DataFrames
        sheet_dict = pd.read_excel(file_name, sheet_name=None)
        for sheet_name in sheet_dict.keys():
            editors_group, _ = Group.objects.get_or_create(name="editors")
            df = sheet_dict[sheet_name]
            for index, row in df.iterrows():
                # Avoid resetting passwords for existing users
                if not User.objects.filter(username=row["username"]).exists():
                    user = User.objects.create(
                        username=row["username"],
                        email=row["email"],
                        first_name=row["first_name"],
                        last_name=row["last_name"],
                    )
                    # Editors group is the only useful one for now
                    if sheet_name.lower() == "editors":
                        user.groups.add(editors_group)
                    user.set_unusable_password()
                    user.save()
                    print(f"Created {user.username}")

                    if options["email_users"]:
                        # TODO: email users with link to reset password
                        print(
                            f"[TODO] Sent email with link to reset password to {user.email}"
                        )
                else:
                    print(f"{row['username']} already exists")
