from django.test import TestCase, Client
from ftva_lab_data.models import SheetImport
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User, Group, Permission
from django.urls import reverse
from ftva_lab_data.views_utils import get_field_value


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

    fixtures = ["sample_data.json"]

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

        # Create editors group and add permissions to add and edit SheetImport
        cls.editors_group, _ = Group.objects.get_or_create(name="editors")
        cls.edit_permissions = Permission.objects.filter(
            codename__in=["add_sheetimport", "change_sheetimport"]
        )
        cls.editors_group.permissions.add(*cls.edit_permissions)

        # Add authorized user to the editors group
        cls.authorized_user.groups.add(cls.editors_group)

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
