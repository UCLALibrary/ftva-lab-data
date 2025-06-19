#!/bin/sh

##### QAD script for data import and cleanup #####

# Stop system, if running
docker compose down
sleep 15

# Drop old database, for a clean start
echo "Dropping old database..."
docker volume rm ftva-lab-data_pg_data

# Start system
docker compose up -d
sleep 15

# Load users
echo ""
echo "Loading users..."
docker compose exec django python manage.py create_users_from_sheet -f list_of_django_users.xlsx

# Convert DL sheet to JSON
echo ""
echo "Converting DL sheet data..."
docker compose exec django python manage.py convert_dl_sheet_data -f ftva_dl_sheet.xlsx -s LTO-Backup

# Load the full set of converted data
echo ""
echo "Loading converted data..."
docker compose exec django python manage.py loaddata sheet_data.json

# Create initial history records for full set of converted data, which apparently does
# not happen automatically?
echo ""
echo "Generating initial history records..."
docker compose exec django python manage.py populate_history --auto --batchsize 2500

# Clean the data
echo ""
echo "Cleaning the data (hard drives, folders, and unwanted rows)..."
docker compose exec django python manage.py clean_imported_data

# Update the tape info
echo ""
echo "Updating the tape carrier / location info..."
docker compose exec django python manage.py clean_tape_info --update_records

# Import status info
echo ""
echo "Importing status info..."
docker compose exec django python manage.py import_status_info --file_name copy_dl_sheet_2024-10-18.xlsx
