# ftva-lab-data
This is a Django application for managing FTVA Digital Lab data, replacing the Google Sheet they previously used.

## Developer Information

### Overview of environment

The development environment requires:
* `git` (at least version 2)
* `docker`(version 25+) and `docker compose` (version 2+)

#### Dev container

This project comes with a basic dev container definition, in `.devcontainer/devcontainer.json`. It's known to work with VS Code,
and may work with other IDEs like PyCharm.  For VS Code, it also installs the Python, Black (formatter), and Flake8 (linter)
extensions.

When prompted by VS Code, click "Reopen in container".  This will (re)build the Django container, `ftva-lab-data-django`. It will also
(re)build a copy of that container, `vsc-ftva-lab-data-<long_hash>-uid`, install VS Code development tools & extensions within that container,
and start the `docker compose` system.  VS Code will be connected to the Django container, with all code available for editing in that context.

The project's directory is available within the container at `/home/django/ftva-lab-data`.

#### PostgreSQL container

The development database is a Docker container running PostgreSQL 16, which matches our deployment environment.

#### Django container

This uses Django 5.2, in a Debian 12 (Bookworm) container running Python 3.13.  All code
runs in the container, so local version of Python does not matter.

The container runs via `docker_scripts/entrypoint.sh`, which
* Updates container with any new requirements, if the image hasn't been rebuilt (DEV environment only).
* Waits for the database to be completely available.  This can take 5-10 seconds, depending on your hardware.
* Applies any pending migrations (DEV environment only).
* Creates a generic Django superuser, if one does not already exist (DEV environment only).
* Loads fixtures to populate lookup tables and to add a few sample records.
* Starts the Django application server.

## Setup
1. Clone the repository.

   ```$ git clone git@github.com:UCLALibrary/ftva-lab-data.git```

2. Change directory into the project.

   ```$ cd ftva-lab-data```

3. Build using docker compose.

   ```$ docker compose build```

4. Bring the system up, with containers running in the background.

   ```$ docker compose up -d```

5. Logs can be viewed, if needed (`-f` to tail logs).

   ```
   $ docker compose logs -f db
   $ docker compose logs -f django
   ```

6. Run commands in the containers, if needed.

   ```
   # Open psql client in the dev database container
   $ docker compose exec db psql -d ftva_lab_data -U ftva_lab_data
   # Open a shell in the django container
   $ docker compose exec django bash
   # Django-aware Python shell
   $ docker compose exec django python manage.py shell
   # Apply new migrations without a restart
   $ docker compose exec django python manage.py migrate
   # Populate database with sample data (once it exists...)
   $ docker compose exec django python manage.py loaddata --app ftva_lab_data sample_data
   ```

   7. Connect to the running application via browser

   [Application](http://127.0.0.1:8000) and [Admin](http://127.0.0.1:8000/admin)

8. Edit code locally.  All changes are immediately available in the running container, but if a restart is needed:

   ```$ docker compose restart django```

9. Shut down the system when done.

   ```$ docker compose down```

### Loading data

#### Converting data for import

1. Get a copy of the [Digital Lab Hard Drives Google sheet](https://docs.google.com/spreadsheets/d/1UcytVzczTxxFHhfxQzhr7pUKjL9bcIzoqIhLC0vRc6g/edit?gid=1871334680#gid=1871334680) (access required) as an Excel file, called `ftva_dl_sheet.xlsx` for this example.

2. Convert it to a JSON fixture suitable for loading into Django. This will create `sheet_data.json` in the current directory,
with data from all relevant sheets in the Excel file:

   ```python manage.py convert_dl_sheet_data -f ftva_dl_sheet.xlsx```

3. Load into Django:

   ```python manage.py loaddata sheet_data.json```

4. Output should look like this (count will vary):

   ```Installed 26760 object(s) from 1 fixture(s)```

#### Cleaning up loaded data

Some large-scale data cleanup is best done after loading the raw data, as in the previous step.  Once loaded, to run the cleanup:

```python manage.py clean_imported_data```

This will:
* Delete empty records
* Set hard drive names (where available / relevant)
* Set file folder names, by filling in blanks wherever possible
* Delete header rows, which were imported to help figure out how to do some of the other cleanup
* Delete rows which have only hard drive names in them

#### Cleaning up tape / carrier information

Two columns in the original data often combined tape "carrier" information (the ids of the tapes) with the locations of those tapes.
To split these into the appropriate separate fields where possible, run:

```python manage.py clean_tape_info [--update_records | --report_problems]```

These are mutually exclusive, and one or the other must be provided.
Use `--update_records` to update the database; use `--report_problems` to print information about records which have invalid data, needing
manual review.

#### Importing status info

FTVA staff created a spreadsheet that includes status information related to the records loaded from the Digital Lab's Google Sheet. Ask a teammember for a copy of this spreadsheet, if need be. The status data can then be loaded using the `import_status_info` management command:

```python manage.py import_status_info --file_name {PATH_TO_SPREADSHEET}```

#### Loading group and permission definitions

Certain views within the application are restricted to users with appropriate permissions. Corresponding group and permission definitions are included in the `groups_and_permissions.json` fixture.  This is loaded automatically in the development environment, but also can be loaded manually:

```python manage.py loaddata groups_and_permissions.json```

#### Loading users

FTVA staff provided a list of users in a Google Sheet. Ask a teammate for the sheet, if need be. Users can be loaded from the sheet using the following management command:

```python manage.py create_users_from_sheet -f {SPREADSHEET_PATH}.xlsx```

The script accepts two command line arguments:

- `-f` (or `--file_name`) _required_: path to an Excel (XLSX) export of the FTVA Google Sheet containing user data
- `--email_users`: whether to email users with a link to set their passwords
  - NOTE: the emailing logic is not currently implemented. This feature will be added later.

#### Convenience script

In the **development environment only**, much of the above can be done by running `./process_data.sh`.

### Logging

Basic logging is available, with logs captured in `logs/application.log`.  At present, logs from both the custom application code and Django itself are captured.

Logging level is set to `INFO` via `.docker-compose_django.env`.  If there's a regular need/desire for DEBUG level, we can discuss that.

#### How to log

Logging can be used in any Python file in the project.  For example, in `views.py`:
```
# Include the module with other imports
import logging
# Instantiate a logger, generally before any functions in the file
logger = logging.getLogger(__name__)

def my_view():
    logger.info('This is a log message from my_view')

    query_results = SomeModel.objects.all()
    for r in query_results:
        logger.info(f'{r.some_field=}')

    try:
        1/0
    except Exception as e:
        logger.exception('Example exception')

    logger.debug('This DEBUG message only appears if DJANGO_LOG_LEVEL=DEBUG')
```
#### Log format
The current log format includes:
* Level: DEBUG, INFO, WARNING, ERROR, or CRITICAL
* Timestamp via `asctime`
* Logger name: to distinguish between sources of messages (`django` vs the specific application)
* Module: somewhat redundant with logger name
* Message: The main thing being logged


#### Viewing the log
Local development environment: `view logs/application.log`.

In deployed container:
* `/logs/`: see latest 200 lines of the log
* `/logs/nnn`: see latest `nnn` lines of the log

### Testing

Tests focus on code which has significant side effects or implements custom logic.
Run tests in the container:

```$ docker compose exec django python manage.py test```

#### Preparing a release

Our deployment system is triggered by changes to the Helm chart.  Typically, this is done by incrementing `image:tag` (on or near line 9) in `charts/prod-<appname></appname>-values.yaml`.  We use a simple [semantic versioning](https://semver.org/) system:
* Bug fixes: update patch level (e.g., `v1.0.1` to `v1.0.2`)
* Backward compatible functionality changes: update minor level (e.g., `v1.0.1` to `v1.1.0`)
* Breaking changes: update major level (e.g., `v1.0.1` to `v2.0.0`)

In addition to updating version in the Helm chart, update the Release Notes in `release_notes.html`.  Put the latest changes first, following the established format.
