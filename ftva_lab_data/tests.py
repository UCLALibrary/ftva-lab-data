from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User, Group
from django.urls import reverse
from ftva_lab_data.forms import ItemForm
from ftva_lab_data.management.commands.set_empty_inv_no_status import (
    set_empty_inv_no_status,
)
from ftva_lab_data.management.commands.clean_tape_info import (
    get_tape_info_parts,
    process_carrier_fields,
)
from ftva_lab_data.management.commands.clean_imported_data import (
    delete_empty_records,
    delete_header_records,
    set_carrier_info,
    set_file_folder_names,
    set_hard_drive_names,
)
from ftva_lab_data.models import ItemStatus, SheetImport
from ftva_lab_data.management.commands.import_status_and_inventory_numbers import (
    parse_status_info,
)
from ftva_lab_data.views_utils import (
    get_field_value,
    get_item_display_dicts,
    get_search_result_items,
    get_items_per_page_options,
    format_data_for_export,
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
        # (i.e. more than the maximum page size allowed by `items_per_page`)
        for i in range(150):
            SheetImport.objects.create(file_name=f"test_file_{i}", id=i)
        # Create SheetImport objects with different filenames
        SheetImport.objects.create(
            file_name="unique_file_1", hard_drive_name="test_drive_1", id=1000
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

    def test_valid_items_per_page_options(self):
        url = reverse("render_table")
        items_per_page_options = get_items_per_page_options()

        # Test that for each option from `get_items_per_page_options()`,
        # the per page value in the paginator object
        # and in the session store stay in sync.
        # So long as they are in sync, the table should render correctly
        # and the per page setting should persist within the session.
        for option in items_per_page_options:
            with self.subTest(option=option):
                response = self.client.get(url, {"items_per_page": option})

                paginator_per_page = response.context.get("page_obj").paginator.per_page
                session_per_page = response.context.get("request").session[
                    "items_per_page"
                ]

                self.assertEqual(paginator_per_page, session_per_page)

    def test_invalid_items_per_page_options(self):
        url = reverse("render_table")

        # The view expects `items_per_page` to be an integer,
        # so this tests an empty string and a boolean
        # to make sure they are handled correctly by the view
        # and fall back to the default per-page option.
        invalid_options = ["", True]

        for option in invalid_options:
            with self.subTest(option=option):
                response = self.client.get(url, {"items_per_page": option})

                paginator_per_page = response.context.get("page_obj").paginator.per_page
                session_per_page = response.context.get("request").session[
                    "items_per_page"
                ]
                # The default per-page option is the first item
                # in the list returned by `items_per_page_options`.
                default_per_page = get_items_per_page_options()[0]
                # The per-page values in both the paginator and session objects
                # should fall back to the default when give non-int values.
                self.assertEqual(paginator_per_page, default_per_page)
                self.assertEqual(session_per_page, default_per_page)


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

    def test_set_carrier_info(self):
        carrier_a_count_before = SheetImport.objects.filter(carrier_a="MMM555").count()
        self.assertEqual(carrier_a_count_before, 2)
        records_updated = set_carrier_info()
        carrier_a_count_after = SheetImport.objects.filter(carrier_a="MMM555").count()
        self.assertEqual(carrier_a_count_after, 3)
        # Only 2 of the 4 test carrier rows should be updated: one missing carrier_a
        # and 1 missing carrier_b.
        self.assertEqual(records_updated, 2)

    def test_set_file_folder_names(self):
        records_updated = set_file_folder_names()
        # Only 3 real data rows should be updated; 2 of the 5 already have folder names.
        # The empty row, the 2 hard-drive-only rows and the 2 header rows should not be updated.
        # Nor should the row with no file info, but with other data (carrier a, inventory numbner).
        self.assertEqual(records_updated, 3)

    def test_delete_header_records(self):
        records_deleted = delete_header_records()
        # 3 total: 2 full header records, and 1 brief one (minimal fields) for carrier testing.
        self.assertEqual(records_deleted, 3)


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

    def test_search_finds_numeric_ids(self):
        # Confirm string id is converted to int and the appropriate record found.
        # ids created during tests are not guaranteed, so find out what it is now
        # and use that.
        search = str(self.item_basic.id)
        items = get_search_result_items(
            search=search,
            search_fields=["id"],
        )
        self.assertEqual(items.all()[0], self.item_basic)

    def test_search_ignores_nonnumeric_ids(self):
        # Confirm searching for non-numeric ids (like "abc") find nothing, with no error.
        items = get_search_result_items(
            search="abc",
            search_fields=["id"],
        )
        self.assertEqual(items.count(), 0)


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


class AddEditItemTestCase(TestCase):
    """Tests for the `add_item` and `edit_item` views."""

    fixtures = ["sample_data.json", "groups_and_permissions.json"]

    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        cls.authorized_user = User.objects.create_user(
            username="authorized", password="testpassword"
        )
        editors_group = Group.objects.get(name="editors")
        cls.authorized_user.groups.add(editors_group)

        cls.test_object = SheetImport.objects.get(pk=2)

    def test_required_fields_display_with_indicator(self):
        self.client.login(username="authorized", password="testpassword")
        url = reverse("add_item")

        response = self.client.get(url)

        # At minimum, the label for the `file_name` field should have `required-field-label`
        # in its CSS class list, which appends an asterisk using the CSS `::after` pseudo-element.
        # The presence of this class should be enough to prove that
        # the conditional block in `add_edit_item.html` is working.
        expected_markup = (
            '<label class="form-label required-field-label" '
            'for="id_file_name">File name</label>'
        )
        self.assertContains(
            response=response,
            text=expected_markup,
            count=1,
            html=True,
        )


class RequiredFormFieldTestCase(TestCase):
    def test_missing_required_field_prevents_validation(self):
        # file_name is currently the only required field.
        form_data = {"file_name": ""}
        form = ItemForm(data=form_data)
        # Missing data means form is not valid.
        self.assertFalse(form.is_valid())

    def test_missing_required_field_prevents_save(self):
        # file_name is currently the only required field.
        form_data = {"file_name": ""}
        form = ItemForm(data=form_data)
        # Trying to save invalid form data should raise a ValueError.
        with self.assertRaises(ValueError):
            form.save()

    def test_having_required_field_allows_validation(self):
        # file_name is currently the only required field.
        form_data = {"file_name": "My new file"}
        form = ItemForm(data=form_data)
        # Form should be valid when file_name has a value.
        self.assertTrue(form.is_valid())

    def test_having_required_field_allows_save(self):
        # file_name is currently the only required field.
        form_data = {"file_name": "My new file"}
        form = ItemForm(data=form_data)
        new_item = form.save()
        self.assertIsNotNone(new_item)
        self.assertIsInstance(new_item, SheetImport)


class DataExportTestCase(TestCase):
    """Tests the format_data_for_export function."""

    fixtures = ["sample_data.json", "item_statuses.json"]

    def setUp(self):
        # Create a test user to assign to a SheetImport object
        self.user = get_user_model().objects.create_user(
            username="testuser", first_name="Example", last_name="User"
        )
        SheetImport.objects.filter(pk=2).update(assigned_user=self.user)

        # Give the other SheetImport object two statuses
        SheetImport.objects.get(pk=3).status.add(1, 2)

        # Create a list of SheetImport objects to test with
        self.rows = [SheetImport.objects.get(pk=2), SheetImport.objects.get(pk=3)]

    def test_format_data_for_export(self):
        data_dicts = [row.__dict__ for row in self.rows]
        export_data = format_data_for_export(data_dicts)

        # Test that the assigned user's full name is formatted correctly
        # export_data is now a list of dicts, not a df
        self.assertIn("Example User", export_data[0]["assigned_user"])
        # Check that the Statuses are concatenated correctly
        self.assertIn(
            "Duplicated in source data, Incorrect inv no in filename",
            export_data[1]["status"],
        )


class SetEmptyInvNoStatusTestCase(TestCase):
    """Tests the set_empty_inv_no_status management command."""

    fixtures = ["item_statuses.json"]

    def test_set_empty_inv_no_status(self):
        # Create a SheetImport object with an empty inventory number
        item = SheetImport.objects.create(file_name="test_file", inventory_number="")

        # Call the management command function directly
        set_empty_inv_no_status()

        # Check that the status was set correctly
        self.assertTrue(item.status.filter(status="Invalid inv no").exists())

    def test_set_empty_inv_no_status_existing_status(self):
        # Create a SheetImport object with an empty inventory number
        # and an existing 'Needs review' status
        item = SheetImport.objects.create(file_name="test_file_2", inventory_number="")
        item.status.add(ItemStatus.objects.get(status="Needs review"))

        # Call the management command function directly
        set_empty_inv_no_status()

        # Check that both statuses are present, and exactly two statuses exist
        self.assertTrue(item.status.filter(status="Invalid inv no").exists())
        self.assertTrue(item.status.filter(status="Needs review").exists())
        self.assertEqual(item.status.count(), 2)

    def test_set_empty_inv_no_status_existing_inv_no(self):
        # Create a SheetImport object with a non-empty inventory number
        item = SheetImport.objects.create(
            file_name="test_file_3", inventory_number="INV123"
        )

        # Call the management command function directly
        set_empty_inv_no_status()

        # Check that no status was added
        self.assertFalse(item.status.filter(status="Invalid inv no").exists())
