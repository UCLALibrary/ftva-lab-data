from django.test import TestCase, Client
from ftva_lab_data.models import SheetImport
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User, Group
from django.urls import reverse
from ftva_lab_data.views_utils import get_field_value, get_item_display_dicts


class GetFieldValueTests(TestCase):
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
        self.assertEqual(response.status_code, 200)
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
        self.assertEqual(display_dicts["storage_info"].get("DML LTO Tape ID"), "")
        #
