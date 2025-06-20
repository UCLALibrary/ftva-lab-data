from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User, Group
from django.urls import reverse
from ftva_lab_data.management.commands.clean_tape_info import (
    get_tape_info_parts,
    process_carrier_fields,
)
from ftva_lab_data.management.commands.clean_imported_data import (
    delete_empty_records,
    delete_header_records,
    set_file_folder_names,
    set_hard_drive_names,
)
from ftva_lab_data.models import ItemStatus, SheetImport
from ftva_lab_data.management.commands.import_status_info import (
    parse_status_info,
)
from ftva_lab_data.views_utils import (
    get_field_value,
    get_item_display_dicts,
    get_search_result_items,
)
from ftva_lab_data.table_config import COLUMNS


class GetFieldValueTestCase(TestCase):
    def setUp(self):
        # Create a test SheetImport object with foreign key relations
        self.user = get_user_model().objects.create_user(username="testuser")
        self.item_with_user = SheetImport.objects.create(
            file_name="test_file", assigned_user=self.user
        )
        self.item_without_user = SheetImport.objects.create(
            file_name="test_file_no_user"
        )

    def test_get_field_value_direct_field(self):
        value = get_field_value(self.item_with_user, "file_name")
        self.assertEqual(value, "test_file")

    def test_get_field_value_foreign_key_field(self):
        # Test foreign key field access
        value = get_field_value(self.item_with_user, "assigned_user__username")
        self.assertEqual(value, "testuser")

    def test_get_field_value_non_existent_field(self):
        # Test non-existent field access
        value = get_field_value(self.item_with_user, "non_existent_field")
        self.assertEqual(value, "")

    def test_get_field_value_empty_string(self):
        # Test empty string field access
        value = get_field_value(self.item_without_user, "assigned_user__username")
        self.assertEqual(value, "")


class UserAccessTestCase(TestCase):
    """Tests expected behavior for different users requesting various views."""

    fixtures = ["sample_data.json", "groups_and_permissions.json"]

    @classmethod
    def setUpTestData(cls) -> None:
        # Create client and SheetImport object for tests
        cls.client = Client()
        cls.test_object = SheetImport.objects.get(pk=2)
        cls.test_form_data = {"file_name": "test_file_name.txt"}

        # Create two users, one to add to editors group and one with no group
        cls.unauthorized_user = User.objects.create_user(
            username="unauthorized", password="testpassword"
        )
        cls.authorized_user = User.objects.create_user(
            username="authorized", password="testpassword"
        )

        # Add authorized user to the editors group created in fixture
        # which has necessary permissions for `add_item` and `edit_item` views
        editors_group = Group.objects.get(name="editors")
        cls.authorized_user.groups.add(editors_group)
        # Add authorized user to super-editors group to add permissions for `assign_to_user` view
        super_editors_group = Group.objects.get(name="super-editors")
        cls.authorized_user.groups.add(super_editors_group)

    def test_authorized_user_can_add(self):
        """Asserts that user added to `editors` group in setup
        can GET and POST to the `add_item` view.
        """
        self.client.login(username="authorized", password="testpassword")
        url = reverse("add_item")

        # GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # POST request
        response = self.client.post(url, data=self.test_form_data)
        self.assertEqual(response.status_code, 302)  # POST should redirect
        # Confirm item successfully added to database
        new_item = SheetImport.objects.get(file_name=self.test_form_data["file_name"])
        self.assertEqual(new_item.file_name, self.test_form_data["file_name"])

    def test_authorized_user_can_edit(self):
        """Asserts that user added to `editors` group in setup
        can GET and POST to the `edit_item` view.
        """
        self.client.login(username="authorized", password="testpassword")
        url = reverse("edit_item", args=[self.test_object.id])

        # GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # POST request
        response = self.client.post(url, self.test_form_data)
        # Should redirect after successful POST
        self.assertEqual(response.status_code, 302)
        # Confirm item successfully updated in database
        self.test_object.refresh_from_db()
        self.assertEqual(self.test_object.file_name, self.test_form_data["file_name"])

    def test_unauthorized_user_cannot_add(self):
        """Asserts that unauthorized user with no group receives 403
        when trying to GET and POST to the `add_item` view.
        """
        self.client.login(username="unauthorized", password="testpassword")
        url = reverse("add_item")

        # GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        # POST request
        response = self.client.post(url, self.test_form_data)
        self.assertEqual(response.status_code, 403)

    def test_unauthorized_user_cannot_edit(self):
        """Asserts that unauthorized user with no group receives 403
        when trying to GET and POST to the `edit_item` view.
        """
        self.client.login(username="unauthorized", password="testpassword")
        url = reverse("edit_item", args=[self.test_object.id])

        # GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        # POST request
        response = self.client.post(url, self.test_form_data)
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_redirected_to_login_page(self):
        """Asserts that an anonymous user (i.e. not logged in)
        is redirected to login page when trying to GET the base path.
        """
        url = "/"

        # GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_unauthorized_user_cannot_assign_user(self):
        """Asserts that unauthorized user with no group receives 403
        when trying to POST to the `assign_user` view.
        """
        self.client.login(username="unauthorized", password="testpassword")
        url = reverse("assign_to_user")
        # POST request
        response = self.client.post(
            url, {"ids": [self.test_object.id], "user_id": self.authorized_user.id}
        )
        self.assertEqual(response.status_code, 403)

    def authorized_user_can_assign_user(self):
        """Asserts that authorized user can POST to the `assign_user` view."""
        self.client.login(username="authorized", password="testpassword")
        url = reverse("assign_to_user")
        # POST request
        response = self.client.post(
            url, {"ids": [self.test_object.id], "user_id": self.authorized_user.id}
        )
        self.assertEqual(response.status_code, 200)
        # Confirm item successfully assigned to user
        self.test_object.refresh_from_db()
        self.assertEqual(self.test_object.assigned_user, self.authorized_user)


class TablePaginationTestCase(TestCase):
    """Tests pagination functionality in the search results table."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="authorized", password="testpassword"
        )
        self.client.login(username="authorized", password="testpassword")

        # Clear any existing SheetImport objects to avoid id conflicts
        SheetImport.objects.all().delete()

        # Create enough SheetImport objects to require pagination
        # (i.e. more than the default page size of 10)
        for i in range(15):
            SheetImport.objects.create(file_name=f"test_file_{i}", id=i)
        # Create SheetImport objects with different filenames
        SheetImport.objects.create(
            file_name="unique_file_1", hard_drive_name="test_drive_1", id=100
        )

    def test_search_results_with_pagination(self):
        # This search should match the 15 "test_file_" objects created in setUp,
        # but not the "unique_file_1" object.
        search_term = "test"
        search_column = "file_name"

        # Get page 1 of filtered results
        response_page_1 = self.client.get(
            reverse("render_table"),
            {"search": search_term, "search_column": search_column, "page": 1},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response_page_1.status_code, 200)
        # Check that only results matching the search_column are present
        page_1_content = response_page_1.content.decode()
        # Results are ordered by id, so we expect the first 10 results we created
        self.assertIn("test_file_0", page_1_content)
        self.assertNotIn("unique_file_1", page_1_content)

        # Get page 2 of filtered results
        response_page_2 = self.client.get(
            reverse("render_table"),
            {"search": search_term, "search_column": search_column, "page": 2},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response_page_2.status_code, 200)
        page_2_content = response_page_2.content.decode()
        self.assertIn("test_file_10", page_2_content)
        self.assertNotIn("unique_file_1", page_2_content)


class HistoryModelTestCase(TestCase):
    """Tests usage of Django simple history."""

    fixtures = ["sample_data.json"]

    def test_field_changes_are_captured(self):
        obj = SheetImport.objects.get(pk=2)
        # Re-save it to create first history reference, which does not exist
        # automatically in the transient test database.
        obj.save()
        self.assertEqual(obj.history.count(), 1)
        # Grab a copy of the title, change it and save the object.
        old_value = obj.title
        new_value = "MY NEW TITLE"
        obj.title = new_value
        obj.save()
        self.assertEqual(obj.title, new_value)
        # Get the earliest version and confirm its title is the original value.
        previous_obj = obj.history.earliest()
        self.assertEqual(previous_obj.title, old_value)


class ItemDisplayTestCase(TestCase):
    """Tests the get_item_display_dicts function."""

    fixtures = ["item_statuses.json"]

    def setUp(self):
        # Create a test SheetImport object
        self.item = SheetImport.objects.create(
            file_name="test_file",
            hard_drive_name="test_drive",
            file_folder_name="test_folder",
            inventory_number="INV001",
            resolution="1920x1080",
        )
        # Use status value from item_statuses.json fixture
        self.item.status.add(1)

    def test_get_item_display_dicts(self):
        display_dicts = get_item_display_dicts(self.item)
        # Check that the returned dictionary has the expected structure
        self.assertIn("header_info", display_dicts)
        self.assertIn("storage_info", display_dicts)
        self.assertIn("file_info", display_dicts)
        self.assertIn("inventory_info", display_dicts)
        self.assertIn("advanced_info", display_dicts)
        # Check that the values in the dictionaries match the item attributes
        self.assertEqual(display_dicts["header_info"]["file_name"], "test_file")
        self.assertEqual(
            display_dicts["header_info"]["status"],
            ["Incorrect inv no in filename"],
        )
        self.assertEqual(display_dicts["storage_info"]["Hard Drive Name"], "test_drive")
        self.assertEqual(display_dicts["file_info"]["File/Folder Name"], "test_folder")
        self.assertEqual(display_dicts["inventory_info"]["Inventory Number"], "INV001")
        self.assertEqual(display_dicts["advanced_info"]["Resolution"], "1920x1080")
        # Check that empty fields are handled correctly (i.e. are in the dict as empty strings)
        self.assertEqual(display_dicts["storage_info"].get("Carrier A"), "")


class CleanImportedDataTestCase(TestCase):
    """Tests methods from the clean_imported_data management command."""

    # Contains 10 rows total:
    # 2 header rows, 2 hard-drive-only rows, 1 empty row, and 5 real data rows.
    # All data is available during each test.
    fixtures = ["test_clean_imported_data.json"]

    def test_delete_empty_records(self):
        before_deletion = SheetImport.objects.count()
        records_deleted = delete_empty_records()
        self.assertEqual(records_deleted, 1)
        after_deletion = SheetImport.objects.count()
        self.assertEqual((before_deletion - after_deletion), 1)

    def test_set_hard_drive_names(self):
        records_updated = set_hard_drive_names()
        # Only the 5 real data rows should be updated, not the empty row
        # or the 2 hard-drive-only rows or the 2 header rows.
        self.assertEqual(records_updated, 5)

    def test_set_file_folder_names(self):
        records_updated = set_file_folder_names()
        # Only 3 real data rows should be updated; 2 of the 5 already have folder names.
        # The empty row, the 2 hard-drive-only rows and the 2 header rows should not be updated.
        self.assertEqual(records_updated, 3)

    def test_delete_header_records(self):
        records_deleted = delete_header_records()
        self.assertEqual(records_deleted, 2)


class CleanTapeInfoTestCase(TestCase):
    """Tests methods from the clean_tape_info management command."""

    # Contains 5 rows total: 3 with valid tape info, 2 with invalid.
    fixtures = ["test_clean_tape_info.json"]

    def test_get_tape_info_parts_are_valid(self):
        valid_values = [
            "820001",
            "AAB963",
            "000027 (in vault) S217-01A 11C",
            "CLNU00 (in vault) S217-01A 11A",
            "M265154 (to vault) S217-01A-13D",
        ]
        for value in valid_values:
            with self.subTest(value=value):
                tape_info_parts = get_tape_info_parts(value)
                self.assertIsNotNone(tape_info_parts)

    def test_get_tape_info_parts_are_invalid(self):
        invalid_values = [
            "000028 & AAB967",
            "AAC018- LTO Corrupted- Will not mount (4/25/2018)",
            "CLNU02/AAC062 (in vault) S217-01A 11A",
            "Not on LTO AAB969",
            "M258145 Part 01 of 03 (to vault) S217-01A-13C",
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                tape_info_parts = get_tape_info_parts(value)
                self.assertEqual(tape_info_parts, (None, None))

    def test_get_tape_info_parts_single(self):
        tape_info = "AAB963"
        tape_info_parts = get_tape_info_parts(tape_info)
        self.assertEqual(tape_info_parts, (tape_info, None))

    def test_get_tape_info_parts_combined(self):
        tape_info = "CLNU00 (in vault) S217-01A 11A"
        tape_id = "CLNU00"
        vault_location = "S217-01A 11A"
        tape_info_parts = get_tape_info_parts(tape_info)
        self.assertEqual(tape_info_parts, (tape_id, vault_location))

    def test_process_carrier_fields_update_records(self):
        records_updated = process_carrier_fields(
            "carrier_a", update_records=True, report_problems=False
        )
        # Test fixture has 5 rows total: 3 with valid tape info which should be updated,
        # 2 with invalid which should not.
        self.assertEqual(records_updated, 3)


class SearchTestCase(TestCase):
    """Tests the get_search_items search function."""

    @classmethod
    def setUpTestData(cls) -> None:
        # Supporting objects
        user = get_user_model().objects.create_user(username="testuser")
        status = ItemStatus.objects.create(status="Test status")

        # Basic item with fields for searching
        cls.item_basic = SheetImport.objects.create(
            hard_drive_name="HD1",
            file_folder_name="FF1",
            sub_folder_name="SF1",
            file_name="F1",
            inventory_number="Inv_No",
            carrier_a="ABC123",
            carrier_a_location="VAULT-01",
        )

        # Basic item with a user assigned
        cls.item_with_user = SheetImport.objects.create(
            hard_drive_name="HD_shared",
            file_folder_name="FF2",
            sub_folder_name="SF2",
            file_name="F2_Inv_No_embedded",
            inventory_number="I2",
            assigned_user=user,
        )

        # Basic item with a status assigned
        cls.item_with_status = SheetImport.objects.create(
            hard_drive_name="HD_shared",
            file_folder_name="FF3",
            sub_folder_name="SF3",
            file_name="F3",
            inventory_number="I3",
        )
        cls.item_with_status.status.add(status)

        # List of all fields used for searching
        cls.search_fields = [field for field, _ in COLUMNS]

    def test_search_is_case_insensitive(self):
        items = get_search_result_items(
            # Data is uppercase, search term is lowercase
            search="ff1",
            search_fields=["file_folder_name"],
        )
        self.assertEqual(items.all()[0], self.item_basic)

    def test_search_finds_unique_record(self):
        items = get_search_result_items(
            search="FF1",
            search_fields=["file_folder_name"],
        )
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.all()[0], self.item_basic)

    def test_search_finds_substring(self):
        items = get_search_result_items(
            # One record has file_name with 'embed' in the middle
            search="embed",
            search_fields=["file_name"],
        )
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.all()[0], self.item_with_user)

    def test_search_finds_term_in_different_fields(self):
        items = get_search_result_items(
            # Two records have 'Inv_No', each in a different field
            search="Inv_No",
            # No search column defined, so search all fields
            search_fields=self.search_fields,
        )
        self.assertEqual(items.count(), 2)

    def test_search_finds_status_in_all_fields(self):
        items = get_search_result_items(
            # One record has a status assigned
            search="Test status",
            # No search column defined, so search all fields
            search_fields=self.search_fields,
        )
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.all()[0], self.item_with_status)

    def test_search_finds_status_in_status_field(self):
        items = get_search_result_items(
            # One record has a status assigned
            search="Test status",
            search_fields=["status"],
        )
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.all()[0], self.item_with_status)

    def test_search_finds_user_in_all_fields(self):
        items = get_search_result_items(
            # One record has a user assigned
            search="testuser",
            # No search column defined, so search all fields
            search_fields=self.search_fields,
        )
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.all()[0], self.item_with_user)

    def test_search_finds_user_in_user_field(self):
        items = get_search_result_items(
            # One record has a user assigned
            search="testuser",
            search_fields=["assigned_user_full_name"],
        )
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.all()[0], self.item_with_user)

    def test_search_finds_carrier_in_property_field(self):
        items = get_search_result_items(
            search="ABC123",
            search_fields=["carrier_a_with_location"],
        )
        self.assertEqual(items.all()[0], self.item_basic)

    def test_search_finds_carrier_location_in_property_field(self):
        items = get_search_result_items(
            search="VAULT-01",
            search_fields=["carrier_a_with_location"],
        )
        self.assertEqual(items.all()[0], self.item_basic)


class ItemStatusTestCase(TestCase):
    fixtures = ["item_statuses.json"]

    @classmethod
    def setUpTestData(cls):

        # This maps all the unique values
        # in Column A of the `Copy of DL Sheet_10_18_2024` Google Sheet
        # to a tuple of corresponding `ItemStatus` IDs,
        # as defined in `fixtures/item_statuses.json`
        cls.status_info_test_map = [
            ("YES: invalid vault Presence of multiple Inventory_nos", (3, 5)),
            ("YES: invalid vault", (3,)),
            ("YES: Duplicated in Source Data (invalid vault)", (2, 3)),
            (
                "YES: invalid vault Presence of multiple Inventory_nos; Duplicated in Source Data",
                (3, 5, 2),
            ),
            ("YES: invalid vault (Multiple corresponding Inventory_no in PD)", (3, 6)),
            ("YES: invalid vault (invalid inventory_no)", (3, 4)),
            (
                "YES: invalid vault (invalid inventory_no); Duplicated in Source Data",
                (3, 4, 2),
            ),
            ("Presence of multiple Inventory_nos", (5,)),
            (
                "YES: Duplicated in Source Data Presence of multiple Inventory_nos",
                (2, 5),
            ),
            ("YES: Multiple corresponding Inventory_no in PD", (6,)),
            ("YES:invalid inventory_no", (4,)),
            ("Duplicated in Source Data", (2,)),
            (
                "YES: Duplicated in Source Data (Multiple corresponding Inventory_no in PD)",
                (2, 6),
            ),
            ("YES: Duplicated in Source Data (invalid inventory_no)", (2, 4)),
            ("YES:invalid Inventory_no", (4,)),
            ("Inventory number in filename is incorrect", (1,)),
            ("", ()),
        ]

    def test_parse_status_info(self):
        for status_info, expected_status_ids in self.status_info_test_map:
            with self.subTest(
                status_info=status_info, expected_status_ids=expected_status_ids
            ):
                parsed_status = parse_status_info(status_info)
                # Using sets to check equivalence
                # because order shouldn't matter here.
                self.assertSetEqual(set(parsed_status), set(expected_status_ids))
